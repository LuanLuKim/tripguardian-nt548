"""Fetch each brand's tariff page, read it, check it, merge it into config/rides_tariffs.json (docs/BOOKING.md §Gọi xe).

The table is the only thing journey.rides prices from, and it changes only by this build: every page is fetched twice
(a CDN edge has served a stale page), read by its own parser, and compared with the table in git. The report
(data/rides/report.json, printed too) lists every row left out, every row read other than its label says, every
conflict, and every fare that moved more than CHANGE_PCT. The table is not written when a page cannot be read, two
fetches disagree, a brand loses areas, or a fare moved more than CHANGE_PCT without `accept` (a price war or a
misread: a person decides which)."""

import json
import time
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

from . import be, grab, lado, xanhsm
from .common import ROOT, Parsed, provinces

TABLE = ROOT / "config" / "rides_tariffs.json"
DATA = ROOT / "data" / "rides"
CHANGE_PCT = 30
PROBE_KM = (3, 10, 30)  # distances a fare is compared at, old table vs new
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"
VN = timezone(timedelta(hours=7))

# brand -> {page name: url}; the page is kept at data/rides/<brand>/<page name>.html
PAGES = {
    "grab": {"page": grab.URL},
    "be": {"page": be.URL},
    "xanhsm": dict(xanhsm.URLS),
    "lado": {"page": lado.URL},
}


class BuildError(RuntimeError):
    pass


def fetch(url: str, timeout: int = 60) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "vi-VN,vi;q=0.9"})
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 (fixed https URLs above)
        return r.read().decode("utf-8", errors="replace")


def _parse(brand: str, pages: dict) -> tuple[Parsed, dict]:
    if brand == "grab":
        return grab.parse(pages["page"])
    if brand == "be":
        return be.parse(pages["page"])
    if brand == "xanhsm":
        return xanhsm.parse(pages)
    return lado.parse(pages["page"])


def _snapshot(p: Parsed) -> str:
    return json.dumps({"fares": {a: {s: f.as_dict() for s, f in v.items()} for a, v in p.fares.items()},
                       "routes": p.routes, "airport": p.airport_pickup}, sort_keys=True, ensure_ascii=False)


def refresh(out: Path = DATA) -> list[str]:
    """Fetch every page twice; keep the second copy when both read the same, else stop. Returns what was saved."""
    saved = []
    for brand, pages in PAGES.items():
        first = {name: fetch(url) for name, url in pages.items()}
        time.sleep(2)
        second = {name: fetch(url) for name, url in pages.items()}
        if _snapshot(_parse(brand, first)[0]) != _snapshot(_parse(brand, second)[0]):
            raise BuildError(f"{brand}: two fetches of {list(pages.values())} read differently (a stale cache): rerun")
        (out / brand).mkdir(parents=True, exist_ok=True)
        for name, html in second.items():
            path = out / brand / f"{name}.html"
            path.write_text(html, encoding="utf-8")
            saved.append(str(path.relative_to(ROOT)))
    return saved


def _pages(brand: str, src: Path) -> dict:
    pages = {}
    for name in PAGES[brand]:
        path = src / brand / f"{name}.html"
        if not path.exists():
            raise BuildError(f"{path.relative_to(ROOT)} missing: run `python -m journey.tariffs refresh`")
        pages[name] = path.read_text(encoding="utf-8")
    return pages


def _fee_note(fee: dict | None) -> str | None:
    if not fee:
        return None
    d = datetime.fromisoformat(fee["until"]).strftime("%d/%m/%Y")
    k = lambda v: f"{v:,}".replace(",", ".") + "đ"  # noqa: E731
    after = f", sau đó {fee['after_pct']}% giá cước" if fee.get("after_pct") else ""
    return (f"Đã cộng phí nền tảng {k(fee['motorbike'][0])}–{k(fee['motorbike'][1])} (xe máy), "
            f"{k(fee['car'][0])}–{k(fee['car'][1])} (ô tô) tới {d}{after}")


def _route_label(r: dict, services: dict) -> str:
    """"GrabCar 4 chỗ · giá tuyến Hà Nội ⇄ sân bay Nội Bài": the page's own wording stays in `source_label`."""
    prov = provinces()
    name = lambda k: (prov.subareas.get(k) or prov.areas[k])["name"]  # noqa: E731
    to = r["to"]
    end = f"sân bay {prov.airports[to['airport']]['name']}" if "airport" in to else name(to["area"])
    start = ", ".join(name(k) for k in r["from"])
    return f"{r.get('name') or services[r['service']]['label']} · giá tuyến {start} {'⇄' if r['both_ways'] else '→'} {end}"


def _brand(key: str, name: str, mod, sources: list, parsed: Parsed, as_of: str, note: str | None, services=None,
           **extra) -> dict:
    services = services or mod.SERVICES
    routes = [{**{k: v for k, v in r.items() if k not in ("label", "name")}, "label": _route_label(r, services),
               "source_label": r["label"]} for r in parsed.routes]
    return {"name": name, "sources": sources, "as_of": as_of, "note": note, "services": services,
            "fares": {a: {s: f.as_dict() for s, f in sorted(v.items())} for a, v in sorted(parsed.fares.items())},
            "routes": routes, "airport_pickup": parsed.airport_pickup, **extra}


def _report_rows(brand: str, p: Parsed) -> dict:
    return {"areas": len(p.fares), "fares": sum(len(v) for v in p.fares.values()), "routes": len(p.routes),
            "skipped": [{"where": w, "why": y} for w, y in p.skipped],
            "reread": [{"where": w, "what": y} for w, y in p.reread],
            "conflicts": [{"area": a, "service": s, "kept": k, "dropped": d, "where": w} for a, s, k, d, w in p.conflicts]}


def _cost(t: dict, km: float) -> float:
    total, done = float(t["open"]), float(t["open_km"])
    for upto, rate in t["per_km"]:
        end = km if upto is None else min(km, float(upto))
        if end > done:
            total += (end - done) * rate
            done = end
    return total


def compare(old: dict, new: dict) -> dict:
    """Fares that moved more than CHANGE_PCT at any PROBE_KM, and areas / services one table has and the other not."""
    moved, lost, added = [], [], []
    for b, nb in new["brands"].items():
        ob = (old.get("brands") or {}).get(b) or {}
        of, nf = ob.get("fares") or {}, nb["fares"]
        for area in sorted(set(of) | set(nf)):
            for sid in sorted(set(of.get(area, {})) | set(nf.get(area, {}))):
                o, n = of.get(area, {}).get(sid), nf.get(area, {}).get(sid)
                if o is None:
                    added.append(f"{b}/{area}/{sid}")
                elif n is None:
                    lost.append(f"{b}/{area}/{sid}")
                else:
                    for km in PROBE_KM:
                        a, c = _cost(o, km), _cost(n, km)
                        if a and abs(c - a) / a * 100 > CHANGE_PCT:
                            moved.append({"fare": f"{b}/{area}/{sid}", "km": km, "old": round(a), "new": round(c)})
                            break
    return {"moved": moved, "lost": lost, "added": added}


def build(src: Path = DATA, table: Path = TABLE, report: Path | None = None, accept: bool = False,
          today: str | None = None) -> dict:
    """Read the saved pages into a new table; write it (and the report) unless a check fails. Returns the report."""
    today = today or datetime.now(VN).date().isoformat()
    report = report or (src / "report.json")
    parsed, meta = {}, {}
    for brand in PAGES:
        parsed[brand], meta[brand] = _parse(brand, _pages(brand, src))
    g, b, x, lo = parsed["grab"], parsed["be"], parsed["xanhsm"], parsed["lado"]
    gmeta = meta["grab"]
    # Lado's taxis are Xanh SM's cars in Lâm Đồng: one brand, Lado's board for that area only
    for area, svc in lo.fares.items():
        if area in x.fares:
            raise BuildError(f"Xanh SM publishes {area} itself now: drop the Lado board for it (journey/tariffs/lado.py)")
        x.fares[area] = svc
    x.routes += lo.routes
    services = {**xanhsm.SERVICES, **lado.SERVICES}
    new = {
        "version": 1,
        "built_at": datetime.now(VN).isoformat(timespec="seconds"),
        "brands": {
            "grab": _brand("grab", grab.NAME, grab, [grab.URL], g, gmeta.get("page_updated") or today,
                           _fee_note(gmeta.get("fee")), platform_fee=gmeta.get("fee")),
            "be": _brand("be", be.NAME, be, [be.URL], b, today, "Giá niêm yết trên be.com.vn, chưa có phụ phí đêm"),
            "xanhsm": _brand("xanhsm", xanhsm.NAME, xanhsm, [*xanhsm.URLS.values(), lado.URL], x, today,
                             "Giá niêm yết, có thể giảm hoặc tăng theo giờ. Ở Lâm Đồng xe là taxi điện của đối tác Lado "
                             "trên nền tảng Xanh SM (Green SM), tính theo bảng giá Lado", services=services),
        },
    }
    old = json.loads(table.read_text(encoding="utf-8")) if table.exists() else {}
    diff = compare(old, new) if old else {"moved": [], "lost": [], "added": [], "first_build": True}
    rep = {"built_at": new["built_at"], "table": str(table.relative_to(ROOT)) if table.is_relative_to(ROOT) else str(table),
           "brands": {k: _report_rows(k, v) for k, v in parsed.items()}, "changes": diff, "written": False, "errors": []}
    errors = rep["errors"]
    for k, v in parsed.items():
        if not v.fares:
            errors.append(f"{k}: no fare read: the page layout changed")
    for k in ("grab", "be", "xanhsm"):
        n_old = len(((old.get("brands") or {}).get(k) or {}).get("fares") or {})
        n_new = len(new["brands"][k]["fares"])
        if n_old and n_new < n_old * 0.8:
            errors.append(f"{k}: {n_new} areas, {n_old} before: a page lost most of its table")
    if diff["moved"] and not accept:
        errors.append(f"{len(diff['moved'])} fares moved more than {CHANGE_PCT}%: check them on the page, then build "
                      f"with --accept")
    if not errors:
        table.write_text(json.dumps(new, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        rep["written"] = True
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(rep, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return rep


def summary(rep: dict) -> str:
    """The report as lines a person reads after a build."""
    out = []
    for k, r in rep["brands"].items():
        out.append(f"{k}: {r['areas']} areas, {r['fares']} fares, {r['routes']} routes")
        out += [f"  skipped  {s['where']}: {s['why']}" for s in r["skipped"]]
        out += [f"  reread   {s['where']}: {s['what']}" for s in r["reread"]]
        out += [f"  conflict {c['area']}/{c['service']} at {c['where']}: kept {c['kept']}, dropped {c['dropped']}"
                for c in r["conflicts"]]
    ch = rep["changes"]
    out += [f"moved {m['fare']} at {m['km']} km: {m['old']} -> {m['new']}" for m in ch["moved"]]
    out += [f"lost  {x}" for x in ch["lost"]] + [f"added {x}" for x in ch["added"]]
    out += [f"ERROR {e}" for e in rep["errors"]]
    out.append(f"{'written' if rep['written'] else 'NOT written'}: {rep['table']}")
    return "\n".join(out)
