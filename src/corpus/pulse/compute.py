"""Signals -> pulse items (docs/CORPUS.md §Nhịp). Pure: no file, no model, no clock (`now` is passed in).

`sig` is what signals.load returns:
    places        {fid: {name, category, area, rating_direction}}   the served corpus; only these can be hot / top / new
    videos        {fid: [{id, url, author, date, text}]}            TikTok videos listed at the place's POI page
    reviews       {fid: [{date, author, stars}]}                    dated Maps reviews
    review_totals {fid: int}                                        reviews Maps states for the place
    web           {fid: [domain]}                                   sites whose Documents name the place (undated)
    status        {fid: {name, status, as_of, reviews}}             Maps status of every crawled place
    claims        [LocalClaim dict]                                 data/<city>/local/local_claims.json
Every item: {id, kind, subject: {type, id, name}, signals, dates, evidence[]}; an item without evidence is never made.
"""

import re
import unicodedata
from datetime import date, timedelta

from .render import plain_quote

KINDS = ("trend", "hot", "top", "event", "season", "new")
EVIDENCE_MAX = 5
MIN_SUBJECT = 5  # characters of an accent-folded season subject before a video text may be searched for it
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
                                # "đang hot" is one bar everywhere: clips by different authors in the window (config `hot`)
                                **({"hot": True} if len(v_authors) >= cfg["hot"]["min_authors"] and len(vids) >= cfg["hot"]["min_videos"] else {}),
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


def _claim_evidence(c: dict) -> list[dict]:
    return [{"type": "web_document", "id": e["doc_id"], "url": e["source_url"], "domain": e["domain"],
             "date": (e.get("retrieved_at") or "")[:10] or None, "quote": e["quote"]} for e in (c.get("evidence") or [])[:2]]


def events(sig: dict, cfg: dict, now: date, city_name: str = "") -> list[dict]:
    c = cfg["event"]
    end = now + timedelta(days=c["horizon_days"])
    out = []
    web = sig.get("events")
    fresh = bool(web and (now - _day(web["day"])).days <= c.get("web_fresh_days", 3))
    if fresh:
        # dated events read from this month's pages: they replace the claims, which know only a month
        out += web_events(web["events"], now, end, c["max_items"] - len(out), c["hot_sources"])
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
                                "text": cl["text"], **({"hot": {"sources": cl["sources"]}} if cl["sources"] >= c["hot_sources"] else {})},
                    "dates": {"from": start.isoformat()}, "evidence": _claim_evidence(cl)})
    out.sort(key=lambda i: (i["dates"].get("on") or i["dates"]["from"], i["id"]))
    return out[:c["max_items"]]


FESTIVE = ("festival", "le hoi", "hoi ", "trien lam", "expo", "giai chay", "marathon", "dem nhac", "hoa nhac", "chao nam moi")


def web_events(events: list[dict], now: date, end: date, room: int, hot_sources: int = 2) -> list[dict]:
    """The `room` events most worth a visitor's while, among those not over and starting before `end`: more sites that
    name it first, then a festival, fair, race or concert night, then the sooner one; shown in date order. An event
    that `hot_sources` independent sites report is "đang hot" (no clip of the POI crawl names an event, so clips cannot say)."""
    def domains(e):
        return len({s["domain"] for s in e["sources"]})
    live = [e for e in events if _day(e["end"]) >= now and _day(e["start"]) <= end]
    best = sorted(live, key=lambda e: (-domains(e), not any(w in f" {fold(e['name'])} " for w in FESTIVE), e["start"]))[:max(0, room)]
    return [{"id": f"event:web:{e['start']}:{fold(e['name'])[:40].replace(' ', '-')}", "kind": "event",
             "subject": {"type": "event", "id": None, "name": e["name"]},
             # status / months: the fields a claim event carries, so a reader built before dated events (prod's frozen
             # corpus.pulse.render) still shows it, as "Diễn ra tháng 11 · 3 nguồn"
             "signals": {"source": "web", "time": e["time"], "venue": e["venue"], "summary": e["summary"],
                         "image": e["image"], **({"image_from": e["image_from"]} if e.get("image_from") else {}),
                         **({"parts": e["parts"]} if e.get("parts") else {}),  # its programmes (corpus.events.gate.fold_parts)
                         "sources": domains(e), "status": "confirmed", **({"hot": {"sources": domains(e)}} if domains(e) >= hot_sources else {}),
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


# words two pages put around the same season's name ("mùa hoa dã quỳ ở Đà Lạt" = "hoa dã quỳ" = "dã quỳ")
SEASON_LOOSE = {"mua", "hoa", "o", "tai", "doi", "dalat", "nam", "nay", "va"}
# what is left of a name that is only weather or a word ("Mùa khô", "Mùa thu", "hồng"): not a season to go and see
SEASON_VAGUE = {"", "kho", "mua", "thu", "dong", "xuan", "he", "may", "hong", "thang", "lanh", "nang", "suong", "suong mu", "langbiang"}


def season_key(subject: str) -> str:
    words = f" {fold(subject)} ".replace(" da lat ", " ").split()    # the city as a phrase: "dã quỳ" keeps its "da"
    return " ".join(w for w in words if w not in SEASON_LOOSE and not w.isdigit())


def season_same(cfg: dict, sig: dict | None = None, now: date | None = None) -> tuple[dict[str, str], dict[str, set[str]], set[str]]:
    """({key: leading key}, {leading key: every name of the season, accent-folded}, {keys that are no season}).

    Names the pages give ONE season that no word rule can tell apart ("vườn hồng" and "mùa hồng chín" are the persimmon
    season; "mùa dâu" and "dâu tây" the strawberry one) come from two places: the groups the night's model call made
    (`sig["events"]["season_groups"]`, corpus.events.seasons; ignored when older than `season.groups_fresh_days`) and
    config `season.same`, which is hand-entered, wins on a name both group, and works without any model."""
    same, names, drop = {}, {}, set()

    def put(group: list[str]) -> None:
        lead = same.get(season_key(group[0]), season_key(group[0]))
        for n in group:
            if (k := season_key(n)) not in same:
                same[k] = lead
                names.setdefault(lead, set()).update({_plain(n), k})
    for g in cfg["season"].get("same", ()):
        put(g)
    made = (sig or {}).get("events") or {}
    made = made.get("season_groups") if made and now and (now - _day(made["day"])).days <= cfg["season"].get("groups_fresh_days", 3) else None
    if made:
        for g in made["groups"]:
            if g:
                put(g)
        drop = {season_key(n) for n in made["not_seasons"]} - set(same)
    return same, names, drop


def season_claims(sig: dict, now: date, city_name: str = "") -> list[dict]:
    """The claims that may name a season this month (before they are grouped): a season / best-time claim with a page
    behind it, about a thing to see, not the city; a place's claim only when it is a `season` claim."""
    out = []
    for cl in sig["claims"]:
        if (cl["kind"] not in ("season", "best_time") or cl["status"] not in STATUS_RANK or now.month not in cl["when"]["months"]
                or not cl.get("evidence") or fold(cl["subject"]) == fold(city_name)):
            continue
        if cl["subject_kind"] != "phenomenon" and not (cl["kind"] == "season" and cl["subject_kind"] in ("poi", "poi_unresolved")):
            continue    # a city's or a dish's season, or a place's best time to visit (the dry months): not a season to see
        out.append(cl)
    return out


def _plain(subject: str) -> str:
    """The subject as a video's text would say it: accent-folded, the city dropped ("hồng treo gió Đà Lạt")."""
    return " ".join(f" {fold(subject)} ".replace(" da lat ", " ").split())


# Where a season is seen (owner 2026-11-15: "mùa hoa gì" asks where to go and see it): places to visit, never a stay,
# a meal or a shop
SEE_GROUPS = {"attraction", "garden_farm", "nature", "camping", "other", "religious", "amusement"}
SEE_WINDOW = 350        # characters on each side of the season's name in a page
SEE_PAGES = 2           # pages that name the place near the season, at least
SEE_LIFT = 1.2          # how much likelier a season page names it than any page of the corpus, at least
SEE_COMMON = 0.15       # a name in more than this share of all pages is a common phrase ("Rừng thông"), not a place
SEE_MAX = 3
SEE_OWN = 2             # places named after the season ("Vườn dâu tây …") at most, so the pages' own picks still show


def _words(text: str) -> str:
    """Accent-folded words only: a name before a comma or a full stop is still a name."""
    return " ".join(re.sub(r"[^0-9a-z]+", " ", fold(text)).split())


def _see_names(sig: dict) -> tuple[dict, dict, int]:
    """({folded name: place id} of the places a season may be seen at, {folded name: pages naming it}, pages);
    worked out once per build."""
    if "_see" not in sig:
        names = {}
        for fid, p in sig["places"].items():
            k = _words(p["name"])
            if p.get("group") in SEE_GROUPS and len(k.split()) >= 2 and len(k) >= 7:
                names.setdefault(k, fid)
        pages = {did: f" {_words(t)} " for did, t in (sig.get("documents") or {}).items()}
        df = {k: sum(f" {k} " in t for t in pages.values()) for k in names}
        sig["_see"] = (names, df, pages)
    return sig["_see"]


def see_places(sig: dict, key: str, doc_ids: set[str]) -> list[str]:
    """Up to SEE_MAX place ids to see the season `key` at: up to SEE_OWN places named after it ("Đồi Cỏ Hồng"), then the
    places its own pages name within SEE_WINDOW of its name, in SEE_PAGES pages at least and SEE_LIFT times likelier
    than in any page; a name in SEE_COMMON of all pages is left out. The most pages first. No model here."""
    names, df, pages = _see_names(sig)
    if not pages:
        return []
    own = [fid for k, fid in names.items() if len(key.split()) >= 2 and f" {key} " in f" {k} "]
    word = re.compile(r"(?<= )" + re.escape(key) + r"(?= )")
    near: dict[str, int] = {}
    docs = [pages[d] for d in doc_ids if d in pages]
    for t in docs:
        spans = [(m.start() - SEE_WINDOW, m.end() + SEE_WINDOW) for m in word.finditer(t)]
        if not spans:
            continue
        for k in names:
            at = t.find(f" {k} ")
            while at >= 0:
                if any(a <= at <= b for a, b in spans):
                    near[k] = near.get(k, 0) + 1
                    break
                at = t.find(f" {k} ", at + 1)
    n = len(pages)
    ranked = [names[k] for k, c in sorted(near.items(), key=lambda x: (-x[1], x[0]))
              if c >= SEE_PAGES and df[k] <= SEE_COMMON * n and (c / len(docs)) / max(df[k] / n, 1e-9) >= SEE_LIFT]
    own = sorted(own, key=lambda fid: (-near.get(_words(sig["places"][fid]["name"]), 0), sig["places"][fid]["name"]))
    return list(dict.fromkeys(own[:SEE_OWN] + ranked))[:SEE_MAX]


def seasons(sig: dict, cfg: dict, now: date, city_name: str = "") -> list[dict]:
    """What is in season this month: the season and best-time claims about a thing to see (a flower, the clouds, the
    persimmons), one item per season however the pages name it. A season is a thing, not a place: a place's claim joins
    the group of the thing it is named after ("đồi Cỏ Hồng" with "cỏ hồng") but a group of places alone is the weather
    of those places ("Nên đi vào mùa khô") and is dropped, as is a name only one page speaks of. All the seasons stay;
    one that people posted about a lot lately carries `hot` and comes first, then the most sources. A claim nobody
    checked yet still counts (marked "tham khảo"): "hoa dã quỳ" in 47 pages is the season of November even before a check."""
    c = cfg["season"]
    same, aliases, not_seasons = season_same(cfg, sig, now)
    groups: dict[str, list[dict]] = {}
    for cl in season_claims(sig, now, city_name):
        key = season_key(cl["subject"])
        key = same.get(key, key)
        if key in SEASON_VAGUE or key in not_seasons or key.startswith("thang "):
            continue
        groups.setdefault(key, []).append(cl)
    out = []
    shots = (sig.get("events") or {}).get("seasons") or {}   # corpus.events: a picture per season name, found the night before
    clips = _season_clips(sig, now, max(c["video_window_days"], c["hot_window_days"]))
    for key, cls in groups.items():
        if not any(x["subject_kind"] == "phenomenon" for x in cls):
            continue
        lead = min(cls, key=lambda x: (-x["sources"], STATUS_RANK[x["status"]], -x["confidence"], x["subject"]))
        status = min((x["status"] for x in cls), key=STATUS_RANK.get)
        domains = {e["domain"] for x in cls for e in x["evidence"] if e.get("domain")}
        sources = max(max(x["sources"] for x in cls), len(domains))
        if sources < c["min_sources"]:
            continue
        # every name the group is called, the pages' and the config's: a video says "vườn hồng", not "hồng chín"
        names = {key, *(_plain(x["subject"]) for x in cls), *aliases.get(key, ())}
        talk = _talk(clips, names, now, c)
        video = max(talk["rows"], key=lambda v: (v["date"], v["id"])) if talk["rows"] else None
        hot = talk["hot"]
        # the group's quotes, those that name this month first: the row's sentence and the two pages shown under it
        merged = {**lead, "evidence": sorted((e for x in cls for e in x["evidence"]),
                                             key=lambda e: not _names_month(e.get("quote") or "", now.month))}
        evidence = _claim_evidence(merged) + ([{"type": "tiktok_video", **{k: video[k] for k in ("id", "url", "date")}}] if video else [])
        shot = shots.get(fold(lead["subject"])) or {}
        see = see_places(sig, key, {e["doc_id"] for x in cls for e in x["evidence"] if e.get("doc_id")})
        out.append({"id": f"season:{key.replace(' ', '-')}", "kind": "season",
                    "subject": {"type": "season", "id": None, "name": lead["subject"]},
                    "signals": {"months": _months_of(cls, lead, now), "sources": sources, "status": status,
                                "latest_video": {k: video[k] for k in ("id", "date", "url")} if video else None,
                                **({"hot": hot} if hot else {}),
                                **({"summary": s} if (s := season_summary([{"type": "web_document", "quote": e.get("quote")}
                                                                           for e in merged["evidence"][:20]], now.month)) else {}),
                                **({"image": shot["image"], "image_from": shot["image_from"]} if shot.get("image") else {}),
                                **({"see": see} if see else {})},
                    "dates": {"month": now.month}, "evidence": evidence})
    out.sort(key=lambda i: (not i["signals"].get("hot"), -(i["signals"].get("hot") or {}).get("authors", 0), -i["signals"]["sources"],
                            STATUS_RANK[i["signals"]["status"]], i["id"]))
    return out[:c.get("limit", c["max_items"])]


SPAN_MAX = 6    # a claim that runs longer than this months is "most of the year", not the season's own span


def _months_of(cls: list[dict], lead: dict, now: date) -> list[int]:
    """The months this season is on, around today: the months its names say, so "vườn hồng" 9–11 completes "mùa hồng chín" 8, 9, 11, 12.
    A claim longer than SPAN_MAX months is left out ("cả năm" would make every season January to December). A month that
    only a minority of the names that give today's month also give is one page's stray (24 pages on clouds, two of them
    saying May), and the months kept are the run through today: what is not connected to this month is not "now"."""
    own = [x["when"]["months"] for x in cls if len(x["when"]["months"]) <= SPAN_MAX and now.month in x["when"]["months"]]
    if not own:
        return sorted(lead["when"]["months"])
    votes = {m: sum(m in ms for ms in own) for m in range(1, 13)}
    keep = {m for m, v in votes.items() if v and 2 * v >= votes[now.month]}
    run, m = {now.month}, now.month
    while (m := m % 12 + 1) in keep and m not in run:
        run.add(m)
    m = now.month
    while (m := (m - 2) % 12 + 1) in keep and m not in run:
        run.add(m)
    return sorted(run)


def _season_clips(sig: dict, now: date, window: int) -> list[tuple[dict, str]]:
    """[(video, its accent-folded text)] of the last `window` days, each video once (one lists under several places)."""
    seen: dict[str, tuple[dict, str]] = {}
    for vs in sig["videos"].values():
        for v in _within(vs, now, window):
            if v["id"] not in seen:
                seen[v["id"]] = (v, fold(v.get("text") or ""))
    return list(seen.values())


def _talk(clips: list[tuple[dict, str]], names: set[str], now: date, c: dict) -> dict:
    """The clips whose own text names the season (any of its names, whole words, in order) and whether that is a lot:
    the same bar as a place that is "đang hot" (config `hot`): clips by different authors in the last `hot_window_days`."""
    names = {n for n in names if len(n) >= MIN_SUBJECT}   # "hồng" would match every pink and every rose; "dau" is also "đâu"
    if not names:
        return {"rows": [], "hot": None}
    word = re.compile(r"(?<!\w)(?:" + "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True)) + r")(?!\w)")
    rows = [v for v, text in clips if word.search(text)]
    recent = [v for v in rows if v["date"] >= (now - timedelta(days=c["hot_window_days"])).isoformat()]
    authors = {v["author"] for v in recent}
    hot = ({"videos": len(recent), "authors": len(authors), "newest": max(v["date"] for v in recent), "window_days": c["hot_window_days"]}
           if len(recent) >= c["hot_min_videos"] and len(authors) >= c["hot_min_authors"] else None)
    return {"rows": [v for v in rows if v["date"] >= (now - timedelta(days=c["video_window_days"])).isoformat()], "hot": hot}


def _names_month(quote: str, month: int) -> bool:
    return bool(re.search(rf"(?<!\d)th[aá]ng\s*{month}(?!\d)", quote, re.I))


SUMMARY_CHARS = (40, 240)   # a season's sentence: a page's own words, long enough to say something, short enough for a row


def season_summary(evidence: list[dict], month: int) -> str | None:
    """The season's sentence in the chat's trends block: one page's own quote, the one that names this month first
    ("tháng 11"), else the first that fits; None when no quote is the right length. No model writes it."""
    quotes = [q for e in evidence if e["type"] == "web_document"
              and SUMMARY_CHARS[0] <= len(q := plain_quote(e.get("quote") or "")) <= SUMMARY_CHARS[1]]
    return next((q for q in quotes if _names_month(q, month)), quotes[0] if quotes else None)


def build(sig: dict, cfg: dict, now: date, city_name: str = "") -> list[dict]:
    """All items, in the bulletin's section order."""
    return (trending(sig, cfg, now) + hot(sig, cfg, now) + top(sig, cfg, now) + events(sig, cfg, now, city_name) + seasons(sig, cfg, now, city_name)
            + new(sig, cfg, now))
