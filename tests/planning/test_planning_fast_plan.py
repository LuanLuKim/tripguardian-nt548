"""The plan shows at once (docs/PLANNING.md §Thuật toán ⓑ, §Quá tải): Lựa chọn's preview never searches the overload
directions; the plan made after it opens with them. A visit shrinks to fit a day, never below its own shortest length,
never one the user set, and the plan says which visits it shortened."""

from plan_fixtures import CENTRE, CFG, LODGING, FakeLive, decision, fake_matrix, no_geocode, spot
from planning.engine import Engine


def engine(records, background=False):
    return Engine(records + LODGING, cfg=CFG, live_cfg=FakeLive(), geocode_fn=no_geocode, matrix_fn=fake_matrix,
                  sun_fn=lambda *a: (360, 1050), route_fn=lambda *a: {"points": []}, background=background)


def heavy(n):
    return [spot(f"c{i}", CENTRE, i, visit=(120, 150, 180), price={"typical_vnd": 10_000 * (i + 1)}) for i in range(n)]


def test_an_overloaded_preview_shows_what_fits_and_the_plan_opens_with_the_directions():
    recs = heavy(10)
    e = engine(recs)
    d = decision([r["id"] for r in recs], days=2)
    preview = e.preview(d)
    assert [v["id"] for v in preview["variants"]] == ["main"]
    assert sum(len(day) for day in preview["variants"][0]["places"]) < len(recs)     # the rest is left over
    view = e.create(d)["view"]
    assert view["overload"] and {v["id"] for v in view["variants"]} <= {"fit", "cost", "most", "main", "kept"}
    assert not view["overload"].get("pending")


def test_a_background_search_is_waited_for_by_the_plan():
    recs = heavy(10)
    e = engine(recs, background=True)
    d = decision([r["id"] for r in recs], days=2)
    e.preview(d)
    view = e.create(d)["view"]
    assert view["overload"] and view["overload"]["directions"]


def tight_day():
    """One day 08:00-12:00 and three places of 30-90-120 minutes: 3 x 90 at the normal pace cannot fit with the road."""
    recs = [spot(f"p{i}", CENTRE, i, visit=(30, 90, 120)) for i in range(3)]
    d = decision([r["id"] for r in recs], days=1)
    d["trip_context"]["context"]["frame"] = {
        "days": [{"date": "2026-12-12", "start": "08:00", "end": "12:00", "busy": [], "intensity": "normal"}],
        "arrive": None, "leave": None, "drive_day_min": None,
        "meals": {"skip": ["breakfast", "lunch", "dinner"], "breakfast_at_lodging": False, "snacks": False,
                  "shift_min": 0},
        "rest": None, "visit": {}}
    return recs, d


def visits(view) -> dict:
    out = {}
    for day in view["itinerary"]:
        for i in day["items"]:
            if i["kind"] == "visit":
                a, b = (int(x[:2]) * 60 + int(x[3:]) for x in (i["start"], i["end"]))
                out[i["place_id"]] = b - a
    return out


def test_a_tight_day_shortens_visits_to_their_floor_and_says_so():
    recs, d = tight_day()
    e = engine(recs)
    view = e.create(d)["view"]
    got = visits(view)
    assert got and all(minutes >= 30 for minutes in got.values())        # never below `short`
    assert any(minutes < 90 for minutes in got.values())
    card = next(v for v in view["variants"] if v["id"] == view["state"]["chosen_variant"])
    note = next(w for w in card["warnings"] if w["code"] == "visit_shortened")
    assert "bớt" in note["text"] and "tối thiểu" in note["text"]


def test_a_length_the_user_set_is_never_shortened():
    recs, d = tight_day()
    e = engine(recs)
    sid = e.create(d)["id"]
    shown = visits(e.load(sid)["view"])
    pid = next(iter(shown))
    action = {"type": "set_visit_duration", "place": pid, "minutes": 100}
    token = e.preview_act(sid, action)["token"]
    view = e.act(sid, {**action, "_preview_token": token})["view"]
    got = visits(view)
    assert got.get(pid) == 100 or pid not in got           # kept whole, or not placed at all: never cut
