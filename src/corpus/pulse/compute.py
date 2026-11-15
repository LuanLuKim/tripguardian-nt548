"""Signals -> pulse items (docs/CORPUS.md §Nhịp). Pure: no file, no model, no clock (`now` is passed in).

`sig` is what signals.load returns:
    places        {fid: {name, category, area, rating_direction}}   the served corpus; only these can be hot / top / new
    videos        {fid: [{id, url, author, date, text}]}            TikTok videos listed at the place's POI page
    reviews       {fid: [{date, author, stars}]}                    dated Maps reviews
    review_totals {fid: int}                                        reviews Maps states for the place
    web           {fid: [domain]}                                   sites whose Documents name the place (undated)
    status        {fid: {name, status, as_of, reviews}}             Maps status of every crawled place
    claims        [LocalClaim dict]                                 data/<city>/local/local_claims.json
    holidays      [{date, name}]                                    corpus.views calendar
Every item: {id, kind, subject: {type, id, name}, signals, dates, evidence[]}; an item without evidence is never made.
"""

import re
import unicodedata
from datetime import date, timedelta

KINDS = ("trend", "hot", "top", "event", "season", "new", "closed")
EVIDENCE_MAX = 5
MIN_SUBJECT = 5  # characters of an accent-folded season subject before a video text may be searched for it
CLOSED = "Bị đóng vĩnh viễn"
STATUS_RANK = {"confirmed": 0, "kept": 1, "unverified": 2}  # conflict / contradicted claims are not evidence for a bulletin


def fold(text: str) -> str:
    s = unicodedata.normalize("NFD", (text or "").replace("đ", "d").replace("Đ", "D"))
    return " ".join("".join(c for c in s if not unicodedata.combining(c)).lower().split())


def _day(iso: str) -> date:
    return date.fromisoformat(iso[:10])


def _place(fid: str, info: dict) -> dict:
    return {"type": "place", "id": fid, "name": info["name"]}


def _within(rows: list[dict], now: date, window: int) -> list[dict]:
    lo = now - timedelta(days=window)
    return [r for r in rows if lo <= _day(r["date"]) <= now]


def _videos_in(sig: dict, fid: str, now: date, window: int) -> list[dict]:
    return _within(sig["videos"].get(fid) or [], now, window)


def _video_evidence(rows: list[dict]) -> list[dict]:
    newest = sorted(rows, key=lambda v: (v["date"], v["id"]), reverse=True)[:EVIDENCE_MAX]
    return [{"type": "tiktok_video", "id": v["id"], "url": v["url"], "date": v["date"]} for v in newest]


def hot(sig: dict, cfg: dict, now: date) -> list[dict]:
    c = cfg["hot"]
    out = []
    for fid, info in sig["places"].items():
        rows = _videos_in(sig, fid, now, c["window_days"])
        authors = {r["author"] for r in rows}
        if len(authors) < c["min_authors"] or len(rows) < c["min_videos"]:
            continue
        out.append({"id": f"hot:{fid}", "kind": "hot", "subject": _place(fid, info),
                    "signals": {"videos": len(rows), "authors": len(authors), "newest": max(r["date"] for r in rows),
                                "window_days": c["window_days"]},
                    "dates": {"from": (now - timedelta(days=c["window_days"])).isoformat(), "to": now.isoformat()},
                    "evidence": _video_evidence(rows)})
    out.sort(key=lambda i: (-i["signals"]["authors"], -i["signals"]["videos"], i["signals"]["newest"], i["id"]))
    return out[:c["max_items"]]


def top(sig: dict, cfg: dict, now: date) -> list[dict]:
    c = cfg["top"]
    out = []
    for fid, info in sig["places"].items():
        sources, signals, evidence = [], {}, []
        vids = _videos_in(sig, fid, now, c["window_days"])
        if len({v["author"] for v in vids}) >= c["tiktok_authors"]:
            sources.append("tiktok")
            signals["tiktok"] = {"videos": len(vids), "authors": len({v["author"] for v in vids}),
                                 "newest": max(v["date"] for v in vids)}
            evidence += _video_evidence(vids)
        revs = _within(sig["reviews"].get(fid) or [], now, c["window_days"])
        if len({r["author"] for r in revs}) >= c["reviews_authors"]:
            sources.append("reviews")
            signals["reviews"] = {"n": len(revs), "authors": len({r["author"] for r in revs}),
                                  "mean_stars": round(sum(r["stars"] for r in revs) / len(revs), 2),
                                  "newest": max(r["date"] for r in revs)}
            evidence.append({"type": "maps_reviews", "count": len(revs), "from": min(r["date"] for r in revs),
                             "to": max(r["date"] for r in revs)})
        if c["rising"] and info.get("rating_direction") == "rising":
            sources.append("rating_up")
            signals["rating_trend"] = "rising"
            evidence.append({"type": "maps_rating_trend", "direction": "rising"})
        domains = sorted(set(sig["web"].get(fid) or ()))
        if len(domains) >= c["web_domains"]:
            sources.append("web")
            signals["web_domains"] = domains
            evidence.append({"type": "web_documents", "domains": domains})
        if len(sources) < c["min_sources"]:
            continue
        signals["sources"] = sources
        newest = max([v for v in (signals.get("tiktok", {}).get("newest"), signals.get("reviews", {}).get("newest")) if v] or [now.isoformat()])
        out.append({"id": f"top:{fid}", "kind": "top", "subject": _place(fid, info), "signals": signals,
                    "dates": {"from": (now - timedelta(days=c["window_days"])).isoformat(), "to": now.isoformat(), "newest": newest},
                    "evidence": evidence})
    out.sort(key=lambda i: (-len(i["signals"]["sources"]), -i["signals"].get("reviews", {}).get("authors", 0),
                            -i["signals"].get("tiktok", {}).get("authors", 0), i["id"]))
    return out[:c["max_items"]]


def _sat(n: int, cap: int) -> float:
    """0..1: `n` of `cap`, no more than 1 (a place with 3x the cap is not 3x as hot)."""
    return min(1.0, n / cap) if cap else 0.0


def trending(sig: dict, cfg: dict, now: date) -> list[dict]:
    """The one ranking the home rail shows (docs/CORPUS.md §Nhịp, "Hạng xu hướng"): every place gets a 0-100 score from
    the same five signals, so a place talked about on one source is no longer ranked by luck of the interleave.

        score = 100 * sum(weight[k] * part[k]) / sum(weight)       part[k] in 0..1, each saturating at its own cap
        tiktok         distinct authors of clips in `window_days`           / cap.tiktok
        tiktok_recent  distinct authors of clips in the last `recent_days`  / cap.tiktok_recent   (momentum: a clip from yesterday says more)
        reviews        authors of Maps reviews in `window_days` as a share of ALL the place's reviews / cap.reviews
                       (a big place always has many reviews; only a jump above its own history is a trend)
        rising         Maps rating_trend == "rising"                        1 or 0
        web            distinct sites that name the place                   / cap.web

    A place is a candidate only with a real crowd behind it (`min_authors` clip authors or `min_review_authors` review
    authors); rising and web only add to a score, they never make a place trend alone. Places to stay and vehicle
    rentals (`exclude_groups`) are not something to visit, so they are not ranked here. `label` names the signal that
    contributed most, in one short phrase; the numbers stay in `signals`."""
    c = cfg["trending"]
    w, cap = c["weights"], c["cap"]
    out = []
    for fid, info in sig["places"].items():
        if info.get("group") in c["exclude_groups"]:
            continue
        vids = _videos_in(sig, fid, now, c["window_days"])
        v_authors = {v["author"] for v in vids}
        recent = {v["author"] for v in _videos_in(sig, fid, now, c["recent_days"])}
        revs = _within(sig["reviews"].get(fid) or [], now, c["window_days"])
        r_authors = {r["author"] for r in revs}
        if len(v_authors) < c["min_authors"] and len(r_authors) < c["min_review_authors"]:
            continue
        rising = info.get("rating_direction") == "rising"
        domains = sorted(set(sig["web"].get(fid) or ()))
        parts = {"tiktok": _sat(len(v_authors), cap["tiktok"]), "tiktok_recent": _sat(len(recent), cap["tiktok_recent"]),
                 "reviews": min(1.0, len(r_authors) / (sig["review_totals"].get(fid) or len(r_authors) or 1) / cap["reviews"]) if r_authors else 0.0, "rising": 1.0 if rising else 0.0,
                 "web": _sat(len(domains), cap["web"])}
        score = round(100 * sum(w[k] * parts[k] for k in w) / sum(w.values()))
        if score < c["min_score"]:
            continue
        lead = max(w, key=lambda k: (w[k] * parts[k], -list(w).index(k)))
        evidence = _video_evidence(vids)
        if revs:
            evidence.append({"type": "maps_reviews", "count": len(revs), "from": min(r["date"] for r in revs), "to": max(r["date"] for r in revs)})
        if rising:
            evidence.append({"type": "maps_rating_trend", "direction": "rising"})
        if domains:
            evidence.append({"type": "web_documents", "domains": domains})
        out.append({"id": f"trend:{fid}", "kind": "trend", "subject": _place(fid, info),
                    "signals": {"score": score, "lead": lead, "parts": {k: round(v, 2) for k, v in parts.items()},
                                "tiktok_authors": len(v_authors), "tiktok_recent_authors": len(recent), "review_authors": len(r_authors),
                                "rising": rising, "web_domains": len(domains),
                                "newest": max([v["date"] for v in vids] or [now.isoformat()]), "window_days": c["window_days"]},
                    "dates": {"from": (now - timedelta(days=c["window_days"])).isoformat(), "to": now.isoformat()},
                    "evidence": evidence})
    out.sort(key=lambda i: (-i["signals"]["score"], -i["signals"]["tiktok_authors"], -i["signals"]["review_authors"], i["id"]))
    return out[:c["max_items"]]


def new(sig: dict, cfg: dict, now: date) -> list[dict]:
    c = cfg["new"]
    out = []
    for fid, info in sig["places"].items():
        revs = sig["reviews"].get(fid) or []
        total = sig["review_totals"].get(fid) or 0
        if not revs or total < c["min_reviews"] or len(revs) < c["coverage"] * total:
            continue  # the crawl does not hold the place's whole history: its first review is unknown
        first = min(r["date"] for r in revs)
        age = (now - _day(first)).days
        if not 0 <= age <= c["max_age_days"]:
            continue
        out.append({"id": f"new:{fid}", "kind": "new", "subject": _place(fid, info),
                    "signals": {"first_review": first, "reviews": len(revs), "total": total, "exact": age <= c["exact_days"]},
                    "dates": {"first_review": first},
                    "evidence": [{"type": "maps_reviews", "count": len(revs), "from": first, "to": max(r["date"] for r in revs)}]})
    out.sort(key=lambda i: (i["signals"]["first_review"], i["id"]), reverse=True)
    return out[:c["max_items"]]


def closed(sig: dict, cfg: dict, now: date, previous: dict | None = None) -> list[dict]:
    c = cfg["closed"]
    seen = {i["id"] for i in (previous or {}).get("items", [])}
    out = []
    for fid, st in sig["status"].items():
        if st.get("status") != CLOSED or (st.get("reviews") or 0) < c["min_reviews"]:
            continue
        iid = f"closed:{fid}"
        out.append({"id": iid, "kind": "closed", "subject": {"type": "place", "id": fid, "name": st["name"]},
                    "signals": {"reviews": st["reviews"], "new_since_last": None if previous is None else iid not in seen},
                    "dates": {"checked": st["as_of"]},
                    "evidence": [{"type": "maps_status", "status": CLOSED, "date": st["as_of"]}]})
    out.sort(key=lambda i: (-i["signals"]["reviews"], i["id"]))
    return out[:c["max_items"]]


def _claim_evidence(c: dict) -> list[dict]:
    return [{"type": "web_document", "id": e["doc_id"], "url": e["source_url"], "domain": e["domain"],
             "date": (e.get("retrieved_at") or "")[:10] or None, "quote": e["quote"]} for e in (c.get("evidence") or [])[:2]]


def events(sig: dict, cfg: dict, now: date, city_name: str = "") -> list[dict]:
    c = cfg["event"]
    end = now + timedelta(days=c["horizon_days"])
    out = []
    for h in sig["holidays"]:
        d = _day(h["date"])
        if now <= d <= end and h.get("name"):
            out.append({"id": f"event:holiday:{h['date']}", "kind": "event", "subject": {"type": "event", "id": None, "name": h["name"]},
                        "signals": {"source": "calendar"}, "dates": {"on": h["date"]},
                        "evidence": [{"type": "calendar", "date": h["date"], "name": h["name"]}]})
    web = sig.get("events")
    if web and (now - _day(web["day"])).days <= c.get("web_fresh_days", 3):
        # dated events read from this month's pages: they replace the claims, which know only a month
        out += web_events(web["events"], now, end, c["max_items"] - len(out))
        return sorted(out, key=lambda i: (i["dates"].get("on") or i["dates"]["from"], i["id"]))
    claims = {}
    for cl in sig["claims"]:
        if (cl["kind"] != "event" or cl["status"] not in STATUS_RANK or not cl["when"]["months"] or not cl.get("evidence")
                or fold(cl["subject"]) == fold(city_name)):  # an event named only by the city has no name to show
            continue
        starts = [m_start for m in cl["when"]["months"] if (m_start := _next_month_start(now, m)) <= end]
        if not starts:
            continue
        key = fold(cl["subject"])
        best = claims.get(key)
        if best is None or (STATUS_RANK[cl["status"]], -cl["sources"]) < (STATUS_RANK[best[0]["status"]], -best[0]["sources"]):
            claims[key] = (cl, min(starts))
    for cl, start in claims.values():
        out.append({"id": f"event:{cl['claim_id']}", "kind": "event", "subject": {"type": "event", "id": None, "name": cl["subject"]},
                    "signals": {"source": "claim", "months": cl["when"]["months"], "status": cl["status"], "sources": cl["sources"],
                                "text": cl["text"]},
                    "dates": {"from": start.isoformat()}, "evidence": _claim_evidence(cl)})
    out.sort(key=lambda i: (i["dates"].get("on") or i["dates"]["from"], i["id"]))
    return out[:c["max_items"]]


FESTIVE = ("festival", "le hoi", "hoi ", "trien lam", "expo", "giai chay", "marathon", "dem nhac", "hoa nhac", "chao nam moi")


def web_events(events: list[dict], now: date, end: date, room: int) -> list[dict]:
    """The `room` events most worth a visitor's while, among those not over and starting before `end`: more sites that
    name it first, then a festival, fair, race or concert night, then the sooner one; shown in date order."""
    def domains(e):
        return len({s["domain"] for s in e["sources"]})
    live = [e for e in events if _day(e["end"]) >= now and _day(e["start"]) <= end]
    best = sorted(live, key=lambda e: (-domains(e), not any(w in f" {fold(e['name'])} " for w in FESTIVE), e["start"]))[:max(0, room)]
    return [{"id": f"event:web:{e['start']}:{fold(e['name'])[:40].replace(' ', '-')}", "kind": "event",
             "subject": {"type": "event", "id": None, "name": e["name"]},
             # status / months: the fields a claim event carries, so a reader built before dated events (prod's frozen
             # corpus.pulse.render) still shows it, as "Diễn ra tháng 11 · 3 nguồn"
             "signals": {"source": "web", "time": e["time"], "venue": e["venue"], "summary": e["summary"],
                         "image": e["image"], "sources": domains(e), "status": "confirmed",
                         "months": _months(_day(e["start"]), _day(e["end"]))},
             "dates": {"from": e["start"], "to": e["end"]},
             "evidence": [{"type": "web_document", "url": s["url"], "domain": s["domain"], "date": s["read"],
                           "quote": s["quote"]} for s in e["sources"]]}
            for e in sorted(best, key=lambda e: (e["start"], e["name"]))]


def _months(start: date, end: date) -> list[int]:
    """The months an event runs through, in order (30/11–02/12 -> [11, 12])."""
    out, d = [], date(start.year, start.month, 1)
    while d <= end:
        out.append(d.month)
        d = date(d.year + (d.month == 12), d.month % 12 + 1, 1)
    return out


def _next_month_start(now: date, month: int) -> date:
    """First day of `month` that is not over yet: this month counts from today, a month already past is next year's."""
    year = now.year if month >= now.month else now.year + 1
    return now if month == now.month else date(year, month, 1)


def seasons(sig: dict, cfg: dict, now: date, city_name: str = "") -> list[dict]:
    c = cfg["season"]
    best = {}
    for cl in sig["claims"]:
        if (cl["kind"] not in ("season", "best_time") or cl["status"] not in STATUS_RANK or now.month not in cl["when"]["months"]
                or cl["subject_kind"] in ("city", "area") or fold(cl["subject"]) == fold(city_name) or not cl.get("evidence")):
            continue
        key = fold(cl["subject"])
        cur = best.get(key)
        if cur is None or (STATUS_RANK[cl["status"]], -cl["sources"], -cl["confidence"]) < (STATUS_RANK[cur["status"]], -cur["sources"], -cur["confidence"]):
            best[key] = cl
    out = []
    for key, cl in best.items():
        video = _latest_video(sig, key, now, c["video_window_days"])
        evidence = _claim_evidence(cl) + ([{"type": "tiktok_video", **{k: video[k] for k in ("id", "url", "date")}}] if video else [])
        out.append({"id": f"season:{key.replace(' ', '-')}", "kind": "season",
                    "subject": {"type": "season", "id": None, "name": cl["subject"]},
                    "signals": {"months": sorted(cl["when"]["months"]), "sources": cl["sources"], "status": cl["status"],
                                "latest_video": {k: video[k] for k in ("id", "date", "url")} if video else None},
                    "dates": {"month": now.month}, "evidence": evidence})
    out.sort(key=lambda i: (STATUS_RANK[i["signals"]["status"]], -i["signals"]["sources"], i["id"]))
    return out[:c["max_items"]]


def _latest_video(sig: dict, key: str, now: date, window: int) -> dict | None:
    """Newest video of the window whose own text names the season's subject (accent-folded words, in order)."""
    if len(key) < MIN_SUBJECT:
        return None  # "hồng" would match every pink and every rose: too short to tell the season from the word
    word = re.compile(r"(?<!\w)" + re.escape(key) + r"(?!\w)")
    rows = [v for vs in sig["videos"].values() for v in _within(vs, now, window) if word.search(fold(v.get("text") or ""))]
    return max(rows, key=lambda v: (v["date"], v["id"])) if rows else None


def build(sig: dict, cfg: dict, now: date, previous: dict | None = None, city_name: str = "") -> list[dict]:
    """All items, in the bulletin's section order."""
    return (trending(sig, cfg, now) + hot(sig, cfg, now) + top(sig, cfg, now) + events(sig, cfg, now, city_name) + seasons(sig, cfg, now, city_name)
            + new(sig, cfg, now) + closed(sig, cfg, now, previous))
