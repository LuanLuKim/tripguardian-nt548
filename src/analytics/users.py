"""Admin "Người dùng" screen (docs/ANALYTICS.md §5): who uses the product, how far each person gets, which features
nobody touches. Read-only. An event belongs to the owner of its journey when it has one (a guest's journeys move to
the account on sign-in; purged guests leave events with user_id NULL), else to events.user_id."""

import statistics
from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from .queries import _range

VN = timezone(timedelta(hours=7))
# Reserved domains: the test sign-in (src/harness/server.py, walker@test.local) and walk-through scripts use them.
TEST_DOMAINS = ("test.local", "example.com")
BAD = "(props ? 'error' OR props->>'path' = 'fallback')"
OWNED = ("WITH ev AS (SELECT coalesce(j.user_id, e.user_id) AS uid, e.at, e.name, e.props, e.journey_id "
         "FROM events e LEFT JOIN journeys j ON j.id = e.journey_id) ")
DAY = "(at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date"

# One person's way through the product; each step is reached once, at any time (key, label, event name).
LADDER = (
    ("signup", "Có tài khoản", None),
    ("journey", "Tạo hành trình", "journey.create"),
    ("compiled", "Trip hiểu xong", "trip.turn"),
    ("chose", "Chọn ≥ 1 nơi", "decision.act.select"),
    ("confirm", "Chốt lịch", "planning.confirm"),
    ("feedback", "Gửi phản hồi", "feedback.submit"),
    ("again", "Lập chuyến ở ngày khác", None),
)

# Features an operator asks "is anyone using this?" about: (key, label, group, event names; "x.*" is a prefix).
FEATURES = (
    ("chat", "Trò chuyện Hiểu chuyến", "Hiểu chuyến", ("trip.turn",)),
    ("theme", "Chủ đề ở trang chủ", "Hiểu chuyến", ("theme_open",)),
    ("search", "Tìm nơi theo tên", "Chọn nơi", ("places.search",)),
    ("detail", "Xem chi tiết nơi", "Chọn nơi", ("detail_open",)),
    ("like", "Thích một nơi", "Chọn nơi", ("place_like",)),
    ("more", "Xem thêm trang", "Chọn nơi", ("page_more",)),
    ("compare", "So sánh hai nơi", "Chọn nơi", ("compare_open",)),
    ("why_not", "Vì sao không gợi ý", "Chọn nơi", ("why_not",)),
    ("assist_decision", "Trợ lý Lựa chọn", "Chọn nơi", ("decision.turn",)),
    ("edit_plan", "Sửa lịch (đổi, bỏ, kéo)", "Lịch trình", ("planning.act.*",)),
    ("assist_plan", "Trợ lý Lịch trình", "Lịch trình", ("planning.turn",)),
    ("confirm", "Chốt lịch", "Lịch trình", ("planning.confirm",)),
    ("booking", "Mở trang đặt vé / phòng", "Lịch trình", ("booking_click",)),
    ("today", "Màn Hôm nay", "Trong chuyến", ("today_open",)),
    ("checkin", "Check-in tại điểm", "Trong chuyến", ("companion.checkin",)),
    ("calendar", "Google Calendar", "Trong chuyến", ("calendar.connect",)),
    ("push", "Hỏi quyền thông báo", "Trong chuyến", ("push_permission",)),
    ("feedback", "Phản hồi sau chuyến", "Sau chuyến", ("feedback.submit",)),
    ("remember", "Nhớ hồ sơ cho lần sau", "Cá nhân", ("profile.remember",)),
    ("copy", "Lấy chuyến bạn gửi", "Cá nhân", ("journey.copy",)),
)


def _uses(name: str, names: tuple) -> bool:
    return any(name == n or (n.endswith(".*") and name.startswith(n[:-1])) for n in names)


def _users(conn, test: bool) -> dict:
    """Every users row as {uid: person}; test accounts only when asked."""
    rows = conn.execute(
        "SELECT id, kind, status, email::text AS email, display_name, nickname::text AS nickname, "
        "google_sub IS NOT NULL AS google, password_hash IS NOT NULL AS password, "
        "(avatar_key IS NOT NULL OR picture_url IS NOT NULL) AS avatar, u.created_at, last_login_at, deleted_at, "
        "p.home_city, p.usual_mobility, p.usual_companions, coalesce(p.consents, '{}') AS consents "
        "FROM users u LEFT JOIN profiles p ON p.user_id = u.id").fetchall()
    out = {}
    for r in rows:
        r = dict(r)
        r["test"] = bool(r["email"]) and r["email"].rsplit("@", 1)[-1].lower() in TEST_DOMAINS
        if r["test"] and not test:
            continue
        r["type"] = "guest" if r["kind"] == "guest" else "account"
        r["login"] = ("both" if r["google"] and r["password"] else "google" if r["google"]
                      else "password" if r["password"] else "none")
        out[r["id"]] = r
    return out


def _activity(conn, people: dict, start: datetime, end: datetime) -> None:
    """Adds per-person milestones, day counts, errors and feedback to `people` (all time, plus counts in range)."""
    for p in people.values():
        p.update(names={}, names_range={}, compiled=False, bad=0, bad_range=0, last_seen=None, days=set(),
                 trip_days=0, min_score=None, feedback=0, journeys=0, confirmed=0)
    ids = list(people)
    for r in conn.execute(
            OWNED + "SELECT uid, name, count(*) FILTER (WHERE props->>'error' IS NULL) AS ok, "
            "count(*) FILTER (WHERE props->>'error' IS NULL AND at >= %s AND at < %s) AS ok_range, "
            "bool_or((props->>'compiled') = 'true') AS compiled, "
            f"count(*) FILTER (WHERE {BAD}) AS bad, count(*) FILTER (WHERE {BAD} AND at >= %s AND at < %s) AS bad_range, "
            "max(at) AS last FROM ev WHERE uid = ANY(%s) GROUP BY 1, 2", (start, end, start, end, ids)):
        p = people.get(r["uid"])
        if p is None:
            continue
        p["names"][r["name"]] = r["ok"]
        if r["ok_range"]:
            p["names_range"][r["name"]] = r["ok_range"]
        p["compiled"] |= bool(r["compiled"])
        p["bad"] += r["bad"]
        p["bad_range"] += r["bad_range"]
        p["last_seen"] = max(filter(None, (p["last_seen"], r["last"])))
    for r in conn.execute(OWNED + f"SELECT uid, {DAY} AS d, (name = 'journey.create') AS trip FROM ev "
                          "WHERE uid = ANY(%s) GROUP BY 1, 2, 3", (ids,)):
        if p := people.get(r["uid"]):
            p["days"].add(r["d"])
            p["trip_days"] += r["trip"]
    for r in conn.execute(
            "SELECT j.user_id AS uid, count(*) AS n, count(*) FILTER (WHERE EXISTS (SELECT 1 FROM events e WHERE "
            "e.journey_id = j.id AND e.name = 'planning.confirm' AND e.props->>'error' IS NULL)) AS confirmed "
            "FROM journeys j WHERE j.user_id = ANY(%s) GROUP BY 1", (ids,)):
        if p := people.get(r["uid"]):
            p["journeys"], p["confirmed"] = r["n"], r["confirmed"]
    for r in conn.execute(
            "SELECT coalesce(j.user_id, f.user_id) AS uid, count(DISTINCT f.id) AS n, min((v.value)::int) AS low "
            "FROM feedback f LEFT JOIN journeys j ON j.id = f.journey_id "
            "LEFT JOIN LATERAL jsonb_each_text(f.scores) v ON true WHERE coalesce(j.user_id, f.user_id) = ANY(%s) "
            "GROUP BY 1", (ids,)):
        if p := people.get(r["uid"]):
            p["feedback"], p["min_score"] = r["n"], r["low"]


def _reached(p: dict) -> list[str]:
    names = p["names"]
    got = {"signup"}
    for key, _, name in LADDER:
        if name and names.get(name) and (key != "compiled" or p["compiled"]):
            got.add(key)
    if p["trip_days"] >= 2:
        got.add("again")
    return [k for k, *_ in LADDER if k in got]


def _furthest(p: dict) -> int:
    """Index in LADDER of the last step reached in order (a later step without the ones before still counts)."""
    reached = set(_reached(p))
    return max(i for i, (k, *_) in enumerate(LADDER) if k in reached)


def _ranges(params: dict) -> tuple[datetime, datetime, datetime]:
    start, end = _range(params)
    return start, end, start - (end - start)


def overview(pool, params: dict) -> dict:
    """KPIs against the previous period of the same length, daily activity, the person-level ladder, weekly
    retention cohorts, feature adoption, profile mix and the factual gap list. test=1 keeps test accounts."""
    start, end, prev = _ranges(params)
    test = params.get("test") == "1"
    with pool.connection() as conn:
        people = _users(conn, test)
        _activity(conn, people, start, end)
        test_ids = [] if test else [r["id"] for r in conn.execute(
            "SELECT id FROM users WHERE split_part(email::text, '@', 2) = ANY(%s)", (list(TEST_DOMAINS),))]
        daily_rows = conn.execute(
            OWNED + f"SELECT {DAY} AS d, name, count(*) AS n FROM ev WHERE at >= %s AND at < %s "
            "AND name IN ('auth.guest', 'auth.guest_adopted', 'journey.create', 'planning.confirm') "
            "AND props->>'error' IS NULL AND NOT props ? 'synthetic' AND (uid IS NULL OR NOT uid = ANY(%s)) "
            "GROUP BY 1, 2", (prev, end, test_ids)).fetchall()
        uses = conn.execute(
            OWNED + "SELECT name, uid, count(*) AS n FROM ev WHERE at >= %s AND at < %s AND props->>'error' IS NULL "
            "AND (uid IS NULL OR NOT uid = ANY(%s)) GROUP BY 1, 2", (start, end, test_ids)).fetchall()
        bad_names = [dict(r) for r in conn.execute(
            OWNED + f"SELECT name, count(*) AS n, count(DISTINCT uid) AS people FROM ev WHERE at >= %s AND at < %s "
            f"AND {BAD} AND (uid IS NULL OR NOT uid = ANY(%s)) GROUP BY 1 ORDER BY 2 DESC LIMIT 5",
            (start, end, test_ids))]
        social = {r["k"]: r["n"] for r in conn.execute(
            "SELECT k, count(DISTINCT uid) AS n FROM ("
            "SELECT 'saved' AS k, user_id AS uid FROM saved_items WHERE saved_at >= %s AND saved_at < %s "
            "UNION ALL SELECT 'friends', requester FROM friendships WHERE created_at >= %s AND created_at < %s "
            "UNION ALL SELECT 'messages', sender FROM messages WHERE sent_at >= %s AND sent_at < %s) x "
            "WHERE NOT uid = ANY(%s) GROUP BY 1", (*(start, end) * 3, test_ids))}
        misses = conn.execute("SELECT count(*) AS n FROM events WHERE name = 'places.search' AND at >= %s AND at < %s "
                              "AND (props->>'hits')::int = 0", (start, end)).fetchone()["n"]
    first, last = start.date(), (end - timedelta(days=1)).date()
    accounts = [p for p in people.values() if p["type"] == "account" and not p["deleted_at"]]
    in_range = lambda d: first <= d <= last  # noqa: E731
    in_prev = lambda d: prev.date() <= d < first  # noqa: E731
    active = [p for p in accounts if any(map(in_range, p["days"]))]
    guests_alive = [p for p in people.values() if p["type"] == "guest"]

    by_day: dict[date, dict[str, int]] = {}
    for r in daily_rows:
        by_day.setdefault(r["d"], {})[r["name"]] = r["n"]
    act_day: dict[date, int] = {}
    for p in accounts:
        for d in p["days"]:
            act_day[d] = act_day.get(d, 0) + 1

    def total(name, inside):
        return sum(v.get(name, 0) for d, v in by_day.items() if inside(d))

    seen = [d for d in by_day if in_range(d)] + [d for d in act_day if in_range(d)]
    day0 = max(first, min(seen)) if seen else first
    daily = []
    d = day0
    while d <= last:
        v = by_day.get(d, {})
        daily.append({"day": d.isoformat(), "accounts": act_day.get(d, 0), "guests": v.get("auth.guest", 0),
                      "journeys": v.get("journey.create", 0), "confirmed": v.get("planning.confirm", 0)})
        d += timedelta(days=1)

    def kpi(now, before):
        return {"n": now, "prev": before}
    new = [p for p in accounts if in_range(p["created_at"].astimezone(VN).date())]
    kpis = {
        "accounts": kpi(len(accounts), len([p for p in accounts if p["created_at"] < start])),
        "new_accounts": kpi(len(new), len([p for p in accounts if in_prev(p["created_at"].astimezone(VN).date())])),
        "active_accounts": kpi(len(active), len([p for p in accounts if any(map(in_prev, p["days"]))])),
        "returning": kpi(len([p for p in active if len([d for d in p["days"] if in_range(d)]) >= 2]), None),
        "guest_sessions": kpi(total("auth.guest", in_range), total("auth.guest", in_prev)),
        "guest_adopted": kpi(total("auth.guest_adopted", in_range), total("auth.guest_adopted", in_prev)),
        "journeys": kpi(total("journey.create", in_range), total("journey.create", in_prev)),
        "confirmed": kpi(total("planning.confirm", in_range), total("planning.confirm", in_prev)),
        "with_errors": kpi(len([p for p in accounts if p["bad_range"]]), None),
        "guests_alive": len(guests_alive),
    }

    # Ladder: accounts that signed up in the range, steps reached at any time since. "again" is not after feedback:
    # it is kept against the people who made a journey at all.
    cohort = new
    ladder, before, made = [], None, None
    for key, label, _ in LADDER:
        n = len([p for p in cohort if key in _reached(p)])
        base = made if key == "again" else before
        ladder.append({"key": key, "label": label, "n": n, "kept": round(n / base, 3) if base else None})
        before = n or before
        made = n if key == "journey" else made

    # Weekly retention: accounts by signup week (Monday, VN), share active in week k after; the last 8 cohorts.
    today = datetime.now(VN).date()
    monday = lambda x: x - timedelta(days=x.weekday())  # noqa: E731
    weeks: dict[date, list] = {}
    for p in accounts:
        weeks.setdefault(monday(p["created_at"].astimezone(VN).date()), []).append(p)
    cohorts = []
    for w in sorted(weeks)[-8:]:
        group = weeks[w]
        cells = []
        for k in range(8):
            ws = w + timedelta(weeks=k)
            if ws > today:
                cells.append(None)
                continue
            n = len([p for p in group if any(ws <= x < ws + timedelta(days=7) for x in p["days"])])
            cells.append(round(n / len(group), 3))
        cohorts.append({"week": w.isoformat(), "size": len(group), "cells": cells})

    acc_ids = {p["id"] for p in accounts}
    features = []
    for key, label, group, names in FEATURES:
        rows = [r for r in uses if _uses(r["name"], names)]
        features.append({"key": key, "label": label, "group": group, "uses": sum(r["n"] for r in rows),
                         "people": len({r["uid"] for r in rows if r["uid"] in acc_ids})})
    for key, label in (("saved", "Lưu nơi / chủ đề"), ("friends", "Kết bạn"), ("messages", "Nhắn tin cho bạn")):
        features.append({"key": key, "label": label, "group": "Cá nhân", "uses": None, "people": social.get(key, 0)})

    def has(p, f):
        return bool(p[f])
    profile = {
        "of": len(accounts),
        "login": {k: len([p for p in accounts if p["login"] == k]) for k in ("google", "password", "both", "none")},
        "fields": {f: len([p for p in accounts if has(p, f)]) for f in
                   ("nickname", "avatar", "home_city", "usual_mobility", "usual_companions")},
        "remember": len([p for p in accounts if (p["consents"] or {}).get("patterns")]),
        "terms": len([p for p in accounts if (p["consents"] or {}).get("terms")]),
    }

    with_trip = [p for p in accounts if p["names"].get("journey.create") or p["journeys"]]
    gaps = {
        "never_journey": {"n": len(accounts) - len(with_trip), "of": len(accounts)},
        "never_confirm": {"n": len([p for p in with_trip if not p["confirmed"] and not p["names"].get("planning.confirm")]),
                          "of": len(with_trip)},
        "one_day": {"n": len([p for p in accounts if len(p["days"]) == 1]), "of": len([p for p in accounts if p["days"]])},
        "errors": {"n": kpis["with_errors"]["n"], "of": len(active), "top": bad_names},
        "guests": {"n": kpis["guest_adopted"]["n"], "of": kpis["guest_sessions"]["n"]},
        "low_feedback": {"n": len([p for p in accounts if p["min_score"] is not None and p["min_score"] <= 2]),
                         "of": len([p for p in accounts if p["feedback"]])},
        "no_prior": {"n": len([p for p in accounts if not (p["usual_mobility"] or p["usual_companions"]
                                                           or (p["consents"] or {}).get("patterns"))]),
                     "of": len(accounts)},
        "unused": [f["label"] for f in features if not f["people"] and not f["uses"]],
        "search_misses": {"n": misses},
    }
    return {"range": [first.isoformat(), last.isoformat()], "test": test, "kpis": kpis, "daily": daily,
            "ladder": ladder, "cohorts": cohorts, "features": features, "profile": profile, "gaps": gaps}


def _row(p: dict, start: datetime, end: datetime) -> dict:
    first, last = start.date(), (end - timedelta(days=1)).date()
    return {"id": p["id"], "type": p["type"], "status": p["status"], "test": p["test"], "email": p["email"],
            "name": p["display_name"], "nickname": p["nickname"], "login": p["login"], "created_at": p["created_at"],
            "last_seen": p["last_seen"] or p["last_login_at"], "active_days": len(p["days"]),
            "active_in_range": any(first <= d <= last for d in p["days"]),
            "new_in_range": start <= p["created_at"] < end, "journeys": p["journeys"], "confirmed": p["confirmed"],
            "furthest": _furthest(p), "errors": p["bad"], "errors_in_range": p["bad_range"], "feedback": p["feedback"],
            "min_score": p["min_score"]}


def people(pool, params: dict) -> list[dict]:
    """Every users row (accounts, live guests, deleted accounts), most recently seen first."""
    start, end, _ = _ranges(params)
    with pool.connection() as conn:
        found = _users(conn, params.get("test") == "1")
        _activity(conn, found, start, end)
    rows = [_row(p, start, end) for p in found.values()]
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    return sorted(rows, key=lambda r: r["last_seen"] or epoch, reverse=True)


def person(pool, uid_hex: str) -> dict:
    """One person: account, profile and consents, ladder, feature use, 26 weeks of daily activity, journeys,
    feedback and the latest events."""
    uid = UUID(uid_hex)
    start, end, _ = _ranges({})
    with pool.connection() as conn:
        found = _users(conn, True)
        if uid not in found:
            raise KeyError(uid_hex)
        one = {uid: found[uid]}
        _activity(conn, one, start, end)
        p = one[uid]
        journeys = [dict(r) for r in conn.execute(
            "SELECT j.id, j.stage, j.revision, j.created_at, j.updated_at, "
            "EXISTS (SELECT 1 FROM events e WHERE e.journey_id = j.id AND e.name = 'planning.confirm' "
            "AND e.props->>'error' IS NULL) AS confirmed, "
            f"(SELECT count(*) FROM events e WHERE e.journey_id = j.id AND {BAD.replace('props', 'e.props')}) AS errors, "
            "(SELECT min((v.value)::int) FROM feedback f, jsonb_each_text(f.scores) v WHERE f.journey_id = j.id) AS min_score "
            "FROM journeys j WHERE j.user_id = %s ORDER BY j.updated_at DESC LIMIT 200", (uid,))]
        daily = {r["d"]: r["n"] for r in conn.execute(
            OWNED + f"SELECT {DAY} AS d, count(*) AS n FROM ev WHERE uid = %s AND at >= %s GROUP BY 1",
            (uid, datetime.now(VN) - timedelta(weeks=27)))}
        events = [dict(r) for r in conn.execute(
            OWNED + "SELECT at, name, journey_id, props FROM ev WHERE uid = %s ORDER BY at DESC LIMIT 60", (uid,))]
        feedback = [dict(r) for r in conn.execute(
            "SELECT f.at, f.journey_id, f.scores, f.more_search_for, f.note FROM feedback f "
            "LEFT JOIN journeys j ON j.id = f.journey_id WHERE coalesce(j.user_id, f.user_id) = %s ORDER BY f.at DESC",
            (uid,))]
        counts = dict(conn.execute(
            "SELECT (SELECT count(*) FROM saved_items WHERE user_id = %(u)s) AS saved, "
            "(SELECT count(*) FROM friendships WHERE status = 'accepted' AND %(u)s IN (requester, addressee)) AS friends, "
            "(SELECT count(*) FROM messages WHERE sender = %(u)s) AS messages, "
            "(SELECT count(*) FROM messages WHERE sender = %(u)s AND journey_id IS NOT NULL) AS shared, "
            "(SELECT count(*) FROM trips WHERE user_id = %(u)s) AS trips, "
            "(SELECT count(*) FROM checkins c JOIN trips t ON t.id = c.trip_id WHERE t.user_id = %(u)s) AS checkins, "
            "(SELECT count(*) FROM notifications WHERE user_id = %(u)s AND status = 'sent') AS notified, "
            "(SELECT count(*) FROM notifications WHERE user_id = %(u)s AND opened_at IS NOT NULL) AS opened",
            {"u": uid}).fetchone())
    features = [{"key": key, "label": label, "group": group,
                 "uses": sum(n for name, n in p["names"].items() if _uses(name, names))}
                for key, label, group, names in FEATURES]
    consents = p["consents"] or {}
    return {**_row(p, start, end), "last_login_at": p["last_login_at"], "deleted_at": p["deleted_at"],
            "profile": {"home_city": p["home_city"], "usual_mobility": p["usual_mobility"],
                        "usual_companions": p["usual_companions"], "avatar": p["avatar"],
                        "remember": bool(consents.get("patterns")),
                        "terms": (consents.get("terms") or {}).get("version")},
            "reached": _reached(p), "features": features, "counts": counts,
            "daily": [{"day": d.isoformat(), "n": n} for d, n in sorted(daily.items())],
            "journey_list": journeys, "feedback_list": feedback, "events": events,
            "median_events_per_day": statistics.median(daily.values()) if daily else None}
