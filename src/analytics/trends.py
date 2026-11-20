"""Admin "Xu hướng" screen (docs/ANALYTICS.md §6): what people look at, pick, like and put in their plans, what they
ask Trip for and how they plan their trips. Read-only; every number is a count of journeys (or people when there is no
journey) over the range, never a weighted score. Test accounts are left out unless test=1 (users.TEST_DOMAINS)."""

import statistics
from collections import Counter
from datetime import date, timedelta

from .queries import _range
from .users import OWNED, TEST_DOMAINS

RECENT = timedelta(days=7)  # "đang lên": interest in the last 7 days of the range against the 7 days before
# Place events, by column of the table: (column, event name, extra condition).
PLACE_EVENTS = (
    ("shown", "card_impression", ""),
    ("viewed", "detail_open", ""),
    ("chosen", "decision.act.select", ""),
    ("liked", "place_like", "AND props->>'value' = 'on'"),
    ("dropped", "decision.act.drop", ""),
    ("outbound", "outbound_click", ""),
    ("checked_in", "companion.checkin", ""),
)
INTEREST = ("viewed", "chosen", "liked", "outbound")
TOP = 300


def _count(values) -> list[dict]:
    """Most common first; ties by key so the order never depends on row order."""
    c = Counter(v for v in values if v not in (None, ""))
    return [{"key": k, "n": n} for k, n in sorted(c.items(), key=lambda kv: (-kv[1], str(kv[0])))]


def _given(trip: dict, key: str):
    """A context value the person said (or their profile gave), never a default."""
    if (trip.get("sources") or {}).get(key) in (None, "default"):
        return None
    return (trip.get("context") or {}).get(key)


def trends(pool, params: dict) -> dict:
    start, end = _range(params)
    recent = end - RECENT
    test = params.get("test") == "1"
    with pool.connection() as conn:
        test_ids = [] if test else [r["id"] for r in conn.execute(
            "SELECT id FROM users WHERE split_part(email::text, '@', 2) = ANY(%s)", (list(TEST_DOMAINS),))]
        synthetic = [r["journey_id"] for r in conn.execute(
            "SELECT DISTINCT journey_id FROM events WHERE name = 'journey.create' AND props ? 'synthetic'")]
        keep = "AND (uid IS NULL OR NOT uid = ANY(%s)) AND (journey_id IS NULL OR NOT journey_id = ANY(%s))"
        unit = "coalesce(journey_id, uid::text, at::text)"
        places: dict[str, dict] = {}
        for col, name, extra in PLACE_EVENTS:
            for r in conn.execute(
                    OWNED + f"SELECT props->>'place_id' AS pid, count(DISTINCT {unit}) AS n, "
                    f"count(DISTINCT {unit}) FILTER (WHERE at >= %s) AS recent, "
                    f"count(DISTINCT {unit}) FILTER (WHERE at >= %s AND at < %s) AS before "
                    f"FROM ev WHERE name = %s AND at >= %s AND at < %s AND props->>'error' IS NULL "
                    f"AND props ? 'place_id' {extra} {keep} GROUP BY 1",
                    (recent, recent - RECENT, recent, name, start, end, test_ids, synthetic)):
                p = places.setdefault(r["pid"], {"place_id": r["pid"], "recent": 0, "before": 0})
                p[col] = r["n"]
                if col in INTEREST:
                    p["recent"] += r["recent"]
                    p["before"] += r["before"]
        # Chosen in a journey that had been shown the card: the honest numerator of "tỉ lệ chọn" (people also pick
        # places by name in chat, without ever seeing a card).
        for r in conn.execute(
                OWNED + "SELECT props->>'place_id' AS pid, count(DISTINCT journey_id) AS n FROM ev s "
                "WHERE name = 'decision.act.select' AND at >= %s AND at < %s AND props->>'error' IS NULL "
                f"{keep} AND EXISTS (SELECT 1 FROM events i WHERE i.journey_id = s.journey_id "
                "AND i.name = 'card_impression' AND i.props->>'place_id' = s.props->>'place_id') GROUP BY 1",
                (start, end, test_ids, synthetic)):
            places.setdefault(r["pid"], {"place_id": r["pid"], "recent": 0, "before": 0})["chosen_seen"] = r["n"]
        for r in conn.execute(
                "SELECT item_id AS pid, count(DISTINCT user_id) AS n FROM saved_items WHERE kind = 'place' "
                "AND saved_at >= %s AND saved_at < %s AND NOT user_id = ANY(%s) GROUP BY 1", (start, end, test_ids)):
            places.setdefault(r["pid"], {"place_id": r["pid"], "recent": 0, "before": 0})["saved"] = r["n"]
        stops = [dict(r) for r in conn.execute(
            "SELECT t.id AS trip, t.start_date, t.created_at, s.day, s.seq, s.place_id, s.name, "
            "(s.planned_arrive AT TIME ZONE 'Asia/Ho_Chi_Minh') AS arrive FROM trips t JOIN trip_stops s ON s.trip_id = t.id "
            "WHERE t.created_at >= %s AND t.created_at < %s AND (t.user_id IS NULL OR NOT t.user_id = ANY(%s)) "
            "AND NOT EXISTS (SELECT 1 FROM events e WHERE e.journey_id = t.journey_id AND e.name = 'journey.create' "
            "AND e.props ? 'synthetic') ORDER BY t.id, s.day, s.seq", (start, end, test_ids))]
        asks = _asks(conn, start, end, test_ids)
        themes = [dict(r) for r in conn.execute(
            OWNED + f"SELECT props->>'theme' AS key, count(DISTINCT coalesce(uid::text, at::text)) AS n FROM ev "
            f"WHERE name = 'theme_open' AND at >= %s AND at < %s {keep} GROUP BY 1 ORDER BY 2 DESC",
            (start, end, test_ids, synthetic))]
        searches = [dict(r) for r in conn.execute(
            OWNED + "SELECT lower(trim(props->>'q')) AS q, count(*) AS n, "
            "count(*) FILTER (WHERE (props->>'hits')::int = 0) AS misses FROM ev WHERE name = 'places.search' "
            f"AND at >= %s AND at < %s AND coalesce(props->>'q', '') <> '' {keep} GROUP BY 1 ORDER BY 2 DESC LIMIT 25",
            (start, end, test_ids, synthetic))]
        reasons = [dict(r) for r in conn.execute(
            OWNED + "SELECT coalesce(props->>'reason', 'none') AS key, count(*) AS n FROM ev "
            f"WHERE name = 'decision.act.drop' AND at >= %s AND at < %s {keep} GROUP BY 1 ORDER BY 2 DESC",
            (start, end, test_ids, synthetic))]

    # Places in confirmed plans (trips are written when a plan is confirmed), names as the plan saved them.
    names: dict[str, str] = {}
    by_trip: dict = {}
    for s in stops:
        names.setdefault(s["place_id"], s["name"])
        by_trip.setdefault(s["trip"], []).append(s)
    for trip, rows in by_trip.items():
        for pid in {s["place_id"] for s in rows}:
            places.setdefault(pid, {"place_id": pid, "recent": 0, "before": 0})
            places[pid]["planned"] = places[pid].get("planned", 0) + 1
    cols = [c for c, *_ in PLACE_EVENTS] + ["saved", "planned", "chosen_seen"]
    for p in places.values():
        for c in cols:
            p.setdefault(c, 0)
        p["name"] = names.get(p["place_id"])
    ranked = sorted(places.values(), key=lambda p: (-(p["chosen"] + p["planned"] + p["viewed"] + p["liked"]), p["place_id"]))

    pairs: Counter = Counter()
    chains: Counter = Counter()
    lengths, per_day, lead = [], [], []
    hours: Counter = Counter()
    weekdays: Counter = Counter()
    for rows in by_trip.values():
        ids = sorted({s["place_id"] for s in rows})
        pairs.update((a, b) for i, a in enumerate(ids) for b in ids[i + 1:])
        days: dict[int, list] = {}
        for s in rows:
            days.setdefault(s["day"], []).append(s)
            if s["arrive"]:
                hours[s["arrive"].hour] += 1
                weekdays[s["arrive"].weekday()] += 1
        for d in days.values():
            chains.update((a["place_id"], b["place_id"]) for a, b in zip(d, d[1:]))
            per_day.append(len(d))
        lengths.append(len(days))
        if rows[0]["start_date"]:
            lead.append((rows[0]["start_date"] - rows[0]["created_at"].date()).days)

    def pairs_out(c: Counter):
        return [{"a": a, "b": b, "n": n, "a_name": names.get(a), "b_name": names.get(b)}
                for (a, b), n in sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))[:12] if n >= 2]

    plans = {
        "trips": len(by_trip), "stops": len(stops),
        "days": _count(lengths), "per_day_median": statistics.median(per_day) if per_day else None,
        "hours": [{"key": h, "n": hours.get(h, 0)} for h in range(5, 24)],
        "weekdays": [weekdays.get(d, 0) for d in range(7)],
        "lead_median": statistics.median(lead) if lead else None,
        "pairs": pairs_out(pairs), "chains": pairs_out(chains),
    }

    starts = [_given(t, "start_date") for t in asks]
    intent = {
        "journeys": len(asks),
        "companions": _count(c for t in asks for c in (_given(t, "companions") or [])),
        "people": _count(_given(t, "people") for t in asks),
        "days": _count(_given(t, "days") for t in asks),
        "mobility": _count(_given(t, "mobility") for t in asks),
        "purpose": _count(_given(t, "purpose") for t in asks),
        "budget": _count(_budget(_given(t, "budget_vnd"), _given(t, "people")) for t in asks),
        "months": _count(s[:7] for s in starts if s),
        "start_weekday": _count(date.fromisoformat(s).weekday() for s in starts if s),
        "interests": _count(w.get("feature") for t in asks for w in (t.get("soft_weights") or [])
                            if w.get("source") == "user" and w.get("strength") != "avoid"),
        "groups": _count(g for t in asks for g in (t.get("liked_groups") or [])),
        "kinds": _count((k.get("kind") or "").strip().lower() for t in asks
                        for k in ((t.get("wishes") or {}).get("kinds") or []))[:20],
        "dishes": _count((k.get("dish") or "").strip().lower() for t in asks
                         for k in ((t.get("wishes") or {}).get("dishes") or []))[:20],
        "vibes": _count((v.get("phrase") or "").strip().lower() for t in asks for v in (t.get("vibes") or [])
                        if v.get("phrase") != "ảnh bạn gửi")[:20],
    }
    return {"range": [start.date().isoformat(), (end - timedelta(days=1)).date().isoformat()], "test": test,
            "recent_from": recent.date().isoformat(), "places": ranked[:TOP], "plans": plans, "intent": intent,
            "themes": themes, "searches": searches, "drop_reasons": reasons}


# Trip's compiled request per journey, cut down to what the intent block reads. Envelopes average ~0.6 MB and Postgres
# must decompress a whole one to read any field, so each journey is read once per updated_at and kept in this process.
_ASKS: dict[str, tuple] = {}


def _small(trip: dict) -> dict:
    wishes = trip.get("wishes") or {}
    return {"sources": trip.get("sources") or {}, "context": trip.get("context") or {},
            "soft_weights": [{k: w.get(k) for k in ("feature", "source", "strength")} for w in trip.get("soft_weights") or []],
            "liked_groups": trip.get("liked_groups") or [],
            "wishes": {"kinds": [{"kind": k.get("kind")} for k in wishes.get("kinds") or []],
                       "dishes": [{"dish": k.get("dish")} for k in wishes.get("dishes") or []]},
            "vibes": [{"phrase": v.get("phrase")} for v in trip.get("vibes") or [] if isinstance(v, dict)]}


def _asks(conn, start, end, test_ids) -> list[dict]:
    rows = conn.execute(
        "SELECT j.id, j.updated_at FROM journeys j WHERE j.created_at >= %s AND j.created_at < %s "
        "AND (j.user_id IS NULL OR NOT j.user_id = ANY(%s)) AND NOT EXISTS (SELECT 1 FROM events e "
        "WHERE e.journey_id = j.id AND e.name = 'journey.create' AND e.props ? 'synthetic')",
        (start, end, test_ids)).fetchall()
    stale = [r["id"] for r in rows if _ASKS.get(r["id"], (None,))[0] != r["updated_at"]]
    for i in range(0, len(stale), 50):
        for r in conn.execute("SELECT id, updated_at, envelope->'outputs'->'trip' AS trip FROM journeys WHERE id = ANY(%s)",
                              (stale[i:i + 50],)):
            _ASKS[r["id"]] = (r["updated_at"], _small(r["trip"]) if r["trip"] else None)
    return [_ASKS[r["id"]][1] for r in rows if r["id"] in _ASKS and _ASKS[r["id"]][1]]


def _budget(vnd, people) -> str | None:
    """Budget per person for the whole trip, in bands (VND)."""
    if not vnd:
        return None
    per = vnd / max(1, people or 1)
    for top, label in ((1_000_000, "< 1 triệu"), (2_000_000, "1–2 triệu"), (3_000_000, "2–3 triệu"),
                       (5_000_000, "3–5 triệu")):
        if per < top:
            return label
    return "≥ 5 triệu"
