"""D.3: the evening check before each trip day (docs/PLANNING.md §Đổi lịch tối trước ngày đi)."""

from planning import eve
from plan_fixtures import CFG, rec

DATE = "2026-12-12"
FETCHED = "2026-12-11T20:00:00+07:00"


def hours(**at):
    """Hourly forecast: every hour dry unless given, e.g. h14=(0.85, 3.0) or h6={"fog": True}."""
    out = {}
    for h in range(24):
        v = at.get(f"h{h}")
        base = {"rain_prob": 0.0, "rain_mm": 0.0, "gust_kmh": 10.0, "storm": False, "fog": False, "disagree": False}
        if isinstance(v, tuple):
            base.update(rain_prob=v[0], rain_mm=v[1])
        elif isinstance(v, dict):
            base.update(v)
        out[h] = base
    return {"hours": out, "source": "open-meteo", "fetched_at": FETCHED}


def day(*stops, d=1, date=DATE):
    return {"day": d, "date": date, "items": [{"kind": "visit", "place_id": p, "name": p, "start": a, "end": b}
                                             for p, a, b in stops]}


RECS = {r["id"]: r for r in [
    rec("garden", 11.90, 108.40, features={"weather_exposed": "present"}),
    rec("cafe", 11.91, 108.41, features={"setting": "indoor"}),
    rec("roof", 11.92, 108.42, features={"weather_exposed": "sheltered"}),
    rec("cloud", 11.93, 108.43, features={"cloud_hunting": "present"}),
    rec("stairs", 11.94, 108.44, features={"steep_or_stairs": "present", "setting": "indoor"}),
    rec("busy", 11.95, 108.45, features={"crowd": "high", "setting": "indoor"}),
    rec("plain", 11.96, 108.46),
]}


def check(itinerary_day, weather=None, **kw):
    f = eve.Factors(date=DATE, weather=weather or {}, **kw)
    return {i["place_id"]: i for i in eve.assess(itinerary_day, RECS, f, CFG)}


def test_afternoon_rain_on_an_outdoor_stop_is_level_2_with_its_source():
    out = check(day(("garden", "14:00", "17:00"), ("cafe", "09:00", "10:00")),
                {"garden": hours(h14=(0.8, 3.0), h15=(0.85, 2.0)), "cafe": hours(h14=(0.8, 3.0))})
    assert out["garden"]["level"] == 2
    cause = out["garden"]["causes"][0]
    assert cause["factor"] == "rain" and cause["source"] == "open-meteo" and cause["retrieved_at"] == FETCHED
    assert "80" in cause["text"] or "85" in cause["text"]
    assert out["cafe"]["level"] == 0                       # indoor at 9h, rain at 14h: nothing


def test_evening_rain_does_not_touch_a_morning_stop_and_drizzle_is_not_rain():
    out = check(day(("garden", "09:00", "11:00")), {"garden": hours(h20=(0.9, 8.0), h10=(0.98, 0.3))})
    assert out["garden"]["level"] <= 1                    # 98% but 0.3 mm in the window: a note at most


def test_rain_on_a_sheltered_place_is_only_a_note():
    out = check(day(("roof", "14:00", "16:00")), {"roof": hours(h14=(0.9, 6.0))})
    assert out["roof"]["level"] == 1


def test_a_thunderstorm_in_the_window_on_an_outdoor_place_cannot_go():
    out = check(day(("garden", "14:00", "16:00")), {"garden": hours(h15={"storm": True, "rain_prob": 0.9, "rain_mm": 9.0})})
    assert out["garden"]["level"] == 3


def test_morning_fog_at_a_cloud_hunting_stop_is_level_2():
    out = check(day(("cloud", "05:30", "07:00")), {"cloud": hours(h5={"fog": True}, h6={"fog": True})})
    assert out["cloud"]["level"] == 2 and out["cloud"]["causes"][0]["factor"] == "fog"


def test_rain_on_steps_is_level_2_even_indoors():
    out = check(day(("stairs", "14:00", "15:00")), {"stairs": hours(h14=(0.8, 4.0))})
    assert out["stairs"]["level"] == 2 and out["stairs"]["causes"][0]["factor"] == "slippery"


def test_unknown_weather_is_never_an_alarm():
    out = check(day(("garden", "14:00", "17:00")), {"garden": None})
    assert out["garden"]["level"] == 0
    silent = hours()
    for h in silent["hours"].values():
        h.update(rain_prob=None, rain_mm=None, storm=None, fog=None, gust_kmh=None)
    assert check(day(("garden", "14:00", "17:00")), {"garden": silent})["garden"]["level"] == 0


def test_models_that_disagree_cap_a_weather_cause_at_a_note():
    w = hours(h14={"rain_prob": 0.9, "rain_mm": 6.0, "disagree": True})
    assert check(day(("garden", "14:00", "16:00")), {"garden": w})["garden"]["level"] == 1


def test_a_peak_event_matters_only_to_a_crowd_averse_traveller_at_a_busy_place():
    ev = [{"name": "Festival Hoa", "crowd": "peak", "source": "config/events.yaml"}]
    it = day(("busy", "10:00", "11:00"), ("plain", "12:00", "13:00"))
    averse = check(it, events=ev, crowd_averse=True)
    assert averse["busy"]["level"] == 2 and averse["plain"]["level"] == 0
    assert check(it, events=ev, crowd_averse=False)["busy"]["level"] == 1


def test_a_closure_or_a_new_day_window_means_the_stop_cannot_go():
    it = day(("cafe", "09:00", "10:00"), ("plain", "17:00", "18:00"))
    out = check(it, closed={"cafe": {"text": "Maps: tạm đóng cửa", "source": "gmaps", "retrieved_at": FETCHED}},
                window=("08:00", "16:00"))
    assert out["cafe"]["level"] == 3 and out["cafe"]["causes"][0]["factor"] == "closed"
    assert out["plain"]["level"] == 3 and out["plain"]["causes"][0]["factor"] == "window"


def test_a_pass_leg_with_a_severe_notice_cannot_go_and_heavy_rain_on_it_should_change():
    passes = {"plain": [{"name": "Đèo Mimosa", "coords": [[11.85, 108.46], [11.82, 108.47]]}]}
    notice = [{"title": "Sạt lở đèo Mimosa", "severity": "severe", "kind": "landslide", "lat": 11.83, "lng": 108.47,
               "radius_km": 2, "source": "https://example.gov.vn/x"}]
    it = day(("plain", "14:00", "15:00"))
    assert check(it, passes=passes, notices=notice)["plain"]["level"] == 3
    wet = check(it, {"plain": hours(h13=(0.9, 12.0))}, passes=passes)["plain"]
    assert wet["level"] == 2 and wet["causes"][0]["factor"] == "pass"
    assert check(it, passes={}, notices=notice)["plain"]["level"] == 0      # the notice is not on its way


def test_a_cause_the_plan_already_flagged_at_confirm_is_a_note_not_a_new_alarm():
    it = day(("garden", "14:00", "17:00"))
    w = {"garden": hours(h14=(0.8, 3.0))}
    assert check(it, w, known={("garden", "rain")})["garden"]["level"] == 1
    storm = {"garden": hours(h15={"storm": True, "rain_prob": 0.9, "rain_mm": 9.0})}
    assert check(it, storm, known={("garden", "rain")})["garden"]["level"] == 3   # a hard rule is never softened


# ---------- minimal repair (Task 4) ----------

import pytest
from plan_fixtures import CENTRE, SOUTH, decision, fake_matrix, no_geocode, spot
from plan_fixtures import FakeLive as FakeLiveCfg

from planning import Engine
from planning.settings import to_min
from planning.session import Store

DAY2 = "2026-12-13"


def wet(*hs, prob=0.85, mm=3.0):
    return hours(**{f"h{h}": (prob, mm) for h in hs})


@pytest.fixture
def trip():
    recs = [spot("garden", CENTRE, 0, features={"weather_exposed": "present"}, visit=(60, 90, 120)),
            spot("cafe1", CENTRE, 1, features={"setting": "indoor"}), spot("museum", CENTRE, 2, features={"setting": "indoor"}),
            spot("lake", SOUTH, 0, features={"weather_exposed": "present"}),
            spot("cafe2", SOUTH, 1, features={"setting": "indoor"}), spot("shop", SOUTH, 2, features={"setting": "indoor"}),
            spot("gallery", CENTRE, 3, features={"setting": "indoor"})]

    def make(roles=None):
        d = decision([r["id"] for r in recs[:6]], days=2, roles=roles,
                     base={"place_id": None, "text": "home", "lat": CENTRE[0], "lng": CENTRE[1]})
        d["backup_pool"] = [{"id": "gallery", "name": "gallery", "for": "garden", "reason": "trong nhà"}]
        e = Engine(recs, cfg=CFG, live_cfg=FakeLiveCfg(), store=Store(None), geocode_fn=no_geocode,
                   matrix_fn=fake_matrix, sun_fn=lambda *a: (360, 1050), background=False)
        sid = e.create(d)["id"]
        view = e.load(sid)["view"]
        if view["state"]["chosen_variant"] is None:
            view = e.act(sid, {"type": "pick_variant", "id": view["variants"][0]["id"]})["view"]
        return e, sid, view["itinerary"], {r["id"]: r for r in recs}
    return make


def where(itinerary, pid):
    return next((d["day"], i["start"], i["end"]) for d in itinerary for i in d["items"] if i.get("place_id") == pid)


def run_repair(e, sid, itinerary, recs, weather_by_date, must=frozenset()):
    factors = {d["date"]: eve.Factors(date=d["date"], weather=weather_by_date.get(d["date"], {})) for d in itinerary}
    day_of = {d["date"]: d for d in itinerary}
    rows = eve.assess(day_of[DATE], recs, factors[DATE], CFG)
    target = next(r for r in rows if r["level"] >= 2)
    opts = eve.repair(lambda acts: e.eve_trial(sid, acts), itinerary, target, factors, recs, CFG,
                      pool=["gallery"], must=set(must))
    return target, opts


def test_rain_in_the_stops_window_is_first_fixed_by_moving_it_within_the_day(trip):
    e, sid, it, recs = trip()
    day, start, end = where(it, "garden")
    date = it[day - 1]["date"]
    assert date == DATE
    rain = list(range(int(start[:2]), int(end[:2]) + 1))
    target, opts = run_repair(e, sid, it, recs, {DATE: {"garden": wet(*rain)}})
    assert target["level"] == 2
    assert opts[0]["kind"] == "shift" and opts[0]["actions"][0]["type"] == "reorder"
    assert opts[0]["changed"] and "garden" in opts[0]["changed"]
    assert opts[-1]["kind"] == "keep"                                   # level 2: keeping the plan stays the default
    assert all(a["type"] in {"reorder", "move_place", "swap", "drop_place"} for o in opts for a in o["actions"])


def test_rain_all_day_moves_the_stop_to_a_dry_day_by_swapping_with_an_unaffected_one(trip):
    e, sid, it, recs = trip()
    _, opts = run_repair(e, sid, it, recs, {DATE: {"garden": wet(*range(6, 22))}, DAY2: {"garden": hours()}})
    kinds = [o["kind"] for o in opts]
    assert "shift" not in kinds and kinds[0] == "swap_day"
    assert [a["type"] for a in opts[0]["actions"]] == ["move_place", "move_place"]
    _, blind = run_repair(e, sid, it, recs, {DATE: {"garden": wet(*range(6, 22))}, DAY2: {}})
    assert "swap_day" not in [o["kind"] for o in blind]      # no forecast for the stop that day: not a fix


def test_rain_on_every_day_falls_back_to_an_indoor_backup(trip):
    e, sid, it, recs = trip()
    all_day = wet(*range(6, 22))
    _, opts = run_repair(e, sid, it, recs, {DATE: {"garden": all_day}, DAY2: {"garden": all_day}})
    assert opts[0]["kind"] == "backup" and opts[0]["actions"] == [{"type": "swap", "place": "garden", "with": "gallery"}]


def test_a_must_go_place_is_never_replaced(trip):
    e, sid, it, recs = trip(roles={"garden": "anchor"})
    all_day = wet(*range(6, 22))
    _, opts = run_repair(e, sid, it, recs, {DATE: {"garden": all_day}, DAY2: {"garden": all_day}}, must={"garden"})
    assert [o["kind"] for o in opts] == ["keep"]


# ---------- anti-false-alarm + pending store (Task 5) ----------

def plan_two_days():
    return [day(("garden", "14:00", "16:00"), ("cafe", "09:00", "10:00"), d=1, date=DATE),
            day(("roof", "10:00", "11:00"), ("plain", "14:00", "15:00"), d=2, date=DAY2)]


def no_trial(actions):
    raise AssertionError("not asked")


def run_check(weather, previous=None, today="2026-12-11", trial=no_trial):
    it = plan_two_days()
    factors = {d["date"]: eve.Factors(date=d["date"], weather=weather.get(d["date"], {})) for d in it}
    return eve.check(it, RECS, factors, CFG, trial, today=today, previous=previous, pool=[], must=set())


def test_only_tomorrow_is_asked_and_later_days_are_notes():
    rain = {DATE: {"garden": hours(h14=(0.8, 3.0))}, DAY2: {"roof": hours(h10=(0.8, 3.0))}}
    out = run_check(rain, trial=lambda acts: {"confirmable": False})
    assert [a["place_id"] for a in out["ask"]] == ["garden"] and out["notify"] is True
    assert out["ask"][0]["options"][-1]["kind"] == "keep"
    assert [(n["date"], n["place_id"]) for n in out["notes"]] == [(DAY2, "roof")]   # D-2: checked, a note
    two_days_out = run_check({DAY2: {"garden": hours(), "plain": hours(h14=(0.9, 9.0))}}, today="2026-12-11")
    assert two_days_out["ask"] == []


def test_the_same_level_again_or_a_declined_cause_is_not_asked_twice():
    rain = {DATE: {"garden": hours(h14=(0.8, 3.0))}}
    first = run_check(rain, trial=lambda acts: {"confirmable": False})
    again = run_check(rain, previous={"levels": first["levels"], "declined": []})
    assert again["ask"] == [] and again["notify"] is False
    declined = run_check(rain, previous={"levels": {}, "declined": [first["ask"][0]["cause"]["key"]]})
    assert declined["ask"] == [] and declined["notify"] is False


def test_evening_rain_that_misses_every_stop_raises_nothing():
    out = run_check({DATE: {"garden": hours(h20=(0.9, 8.0)), "cafe": hours(h20=(0.9, 8.0))}})
    assert out["ask"] == [] and out["notify"] is False


def test_pending_proposals_are_kept_per_plan_hash(tmp_path):
    store = eve.Store(tmp_path)
    assert store.get("j1", "h1") == {"levels": {}, "declined": [], "pending": [], "notes": []}
    store.save("j1", "h1", {"levels": {"x": 2}, "pending": [{"place_id": "garden"}]})
    store.decline("j1", "rain:garden:2026-12-12")
    assert store.get("j1", "h1")["pending"] == [{"place_id": "garden"}]
    fresh = store.get("j1", "h2")                       # a new plan: nothing pending, declines remembered
    assert fresh["pending"] == [] and fresh["levels"] == {} and fresh["notes"] == [] and fresh["declined"] == ["rain:garden:2026-12-12"]


# ---------- I/O edge: gather + run_eve (Task 7) ----------

from datetime import date as _date


class FakeLive:
    def __init__(self, sky=None, steps=None, fail=False, holidays=None, events=None, notices=None):
        self.sky, self.steps, self.fail, self.asked = sky or {}, steps, fail, []
        self.hol, self.ev, self.adv = holidays or {}, events or {}, notices or {}

    def weather_hourly(self, lat, lng, day, cfg):
        self.asked.append((lat, lng, day))
        if self.fail:
            raise RuntimeError("down")
        return self.sky.get(day)

    def route_steps(self, pts, mode, cfg):
        if self.steps is None:
            raise RuntimeError("osrm down")
        return {"legs": self.steps}

    def events(self, days):
        return self.ev

    def advisories(self, days):
        return self.adv

    def holidays(self, days):
        return self.hol


def gplan():
    return {"itinerary": [day(("garden", "14:00", "16:00"), ("cafe", "17:00", "18:00"))],
            "backups": {"places": [{"place_id": "cafe", "reasons": ["crowd"]}]},
            "lodging": {"chosen": {"id": "roof"}}}


def test_gather_reads_live_once_per_grid_cell_and_turns_sources_into_factors():
    d = _date.fromisoformat(DATE)
    src = FakeLive(sky={DATE: hours(h14=(0.9, 5.0))},
                   steps=[[{"name": "Trần Phú", "coords": [[1, 2]]}], [{"name": "Đèo Mimosa", "coords": [[11.9, 108.4]]}]],
                   holidays={d: "Quốc khánh"}, events={d: [{"name": "Festival", "crowd": "peak", "closure_risk": False}]},
                   notices={d: [{"kind": "landslide", "severity": "severe", "area": {"lat": 11.9, "lng": 108.4, "radius_km": 1},
                                 "note": "Sạt lở", "source": "https://x", "issued": "2026-12-11"}]})
    plan = gplan()
    f = eve.gather(plan["itinerary"], plan, RECS, CFG, None, {"pace": {"crowd_tolerance": "avoid"}}, [DATE], src)[DATE]
    assert f.weather["garden"]["hours"][14]["rain_prob"] == 0.9
    assert len(set(src.asked)) == len(src.asked)                # one read per 0.02° cell and day
    assert list(f.passes) == ["cafe"] and f.passes["cafe"][0]["name"] == "Đèo Mimosa"   # leg 2 (roof->garden->cafe)
    assert f.notices[0]["lat"] == 11.9 and f.notices[0]["severity"] == "severe"
    assert f.holiday == "Quốc khánh" and f.crowd_averse and ("cafe", "crowd") in f.known
    assert f.closed == {}


def test_gather_leaves_a_failed_source_unknown():
    plan = gplan()
    f = eve.gather(plan["itinerary"], plan, RECS, CFG, None, {}, [DATE], FakeLive(fail=True))[DATE]
    assert f.weather == {"garden": None, "cafe": None} and f.passes == {}
    rows = {r["place_id"]: r for r in eve.assess(plan["itinerary"][0], RECS, f, CFG)}
    assert rows["garden"]["level"] == 0


def test_closed_now_needs_verified_hours_that_miss_the_visit():
    r = rec("x", 1, 1, hours={"sat": [["08:00", "12:00"]]})
    assert eve.closed_now(r, DATE, "14:00", "15:00")["source"] == "corpus"     # 2026-12-12 is a Saturday
    assert eve.closed_now(r, DATE, "09:00", "10:00") is None
    assert eve.closed_now(rec("y", 1, 1, hours={"sat": [["08:00", "12:00"]]}, status="UNCERTAIN"), DATE, "14:00", "15:00") is None
    assert eve.closed_now(rec("z", 1, 1, hours=None), DATE, "14:00", "15:00") is None


def test_a_holiday_is_a_note_for_shaky_hours_never_a_closure():
    r = {**RECS, "shaky": rec("shaky", 1, 1, status="UNCERTAIN")}
    f = eve.Factors(date=DATE, holiday="Tết Dương lịch")
    rows = {x["place_id"]: x for x in eve.assess(day(("shaky", "10:00", "11:00"), ("cafe", "12:00", "13:00")), r, f, CFG)}
    assert rows["shaky"]["level"] == 1 and rows["shaky"]["causes"][0]["factor"] == "holiday"
    assert rows["cafe"]["level"] == 0


def test_run_eve_restores_the_journey_session_asks_and_keeps_it_pending(trip, tmp_path):
    e, sid, it, recs = trip()
    e.route_fn = lambda *a: None
    plan = e.confirm(sid)
    snapshot = e.store.get(sid).model_dump(mode="json")
    g_day, start, end = where(plan["itinerary"], "garden")
    when = plan["itinerary"][g_day - 1]["date"]
    rain = hours(**{f"h{h}": (0.9, 5.0) for h in range(int(start[:2]), int(end[:2]) + 1)})
    src = FakeLive(sky={when: rain}, steps=None)
    e2 = Engine(list(recs.values()), cfg=CFG, live_cfg=FakeLiveCfg(), store=Store(None), geocode_fn=no_geocode,
                matrix_fn=fake_matrix, sun_fn=lambda *a: (360, 1050), background=False)
    eve_of = (_date.fromisoformat(when).toordinal() - 1)
    today = _date.fromordinal(eve_of).isoformat()
    out = eve.run_eve(e2, snapshot, plan, journey="j1", plan_hash="h1", today=today, store_root=tmp_path, live_cfg=None, src=src)
    assert out["notify"] and out["ask"][0]["place_id"] == "garden"
    assert all("itinerary" not in o for o in out["ask"][0]["options"])
    assert eve.Store(tmp_path).get("j1", "h1")["pending"][0]["place_id"] == "garden"
    again = eve.run_eve(e2, snapshot, plan, journey="j1", plan_hash="h1", today=today, store_root=tmp_path, live_cfg=None, src=src)
    assert again["notify"] is False and eve.Store(tmp_path).get("j1", "h1")["pending"][0]["place_id"] == "garden"


def test_the_runner_is_off_while_the_flag_is_off(tmp_path):
    from dataclasses import replace
    off = replace(CFG, eve_replan={**CFG.eve_replan, "enabled": False})
    assert eve.eve_runner([], None, tmp_path, cfg=off) is None


def test_a_new_arrival_set_after_the_confirm_is_seen_by_the_evening_check(trip, tmp_path):
    """DP5 + DP6: the Planning session holds a later start for day 1 (the harness `times` event); the evening check
    before that day turns every stop that now starts before it into a level-3 `window` question."""
    e, sid, it, recs = trip()
    e.route_fn = lambda *a: None
    plan = e.confirm(sid)
    first = plan["itinerary"][0]
    visits = [i for i in first["items"] if i.get("kind") == "visit"]
    e.act(sid, {"type": "set_day_window", "day": 0, "start": "23:00", "end": "23:30"})
    snapshot = e.store.get(sid).model_dump(mode="json")
    e2 = Engine(list(recs.values()), cfg=CFG, live_cfg=FakeLiveCfg(), store=Store(None), geocode_fn=no_geocode,
                matrix_fn=fake_matrix, sun_fn=lambda *a: (360, 1050), background=False)
    today = _date.fromordinal(_date.fromisoformat(first["date"]).toordinal() - 1).isoformat()
    out = eve.run_eve(e2, snapshot, plan, journey="j2", plan_hash="h2", today=today, store_root=tmp_path,
                      live_cfg=None, src=FakeLive(steps=None))
    asked = {a["place_id"]: a for a in out["ask"]}
    assert visits and set(asked) >= {visits[0]["place_id"]}
    assert asked[visits[0]["place_id"]]["cause"]["factor"] == "window" and asked[visits[0]["place_id"]]["level"] == 3


# ---------- words for people (replan-expert Task 1) ----------

NOISY = "ĐÔI DÉP Camellia Tea Spa, Massage | Đà Lạt (달랏 마사지 스파)"


def test_cause_text_is_for_a_person_the_source_stays_in_its_own_fields():
    out = check(day(("garden", "14:00", "17:00")), {"garden": hours(h14=(0.8, 3.0), h15=(0.85, 2.0), h16=(0.8, 3.0))})
    cause = out["garden"]["causes"][0]
    assert cause["text"] == "dự báo mưa 85% lúc 14–17h"
    assert cause["source"] == "open-meteo" and cause["retrieved_at"] == FETCHED
    assert "Open-Meteo" not in cause["text"] and "mm" not in cause["text"]
    fog = check(day(("cloud", "06:00", "08:00")), {"cloud": hours(h6={"fog": True})})["cloud"]["causes"][0]
    assert fog["text"] == "dự báo sương mù lúc 6–8h, khó thấy cảnh"


def test_the_row_and_the_option_titles_use_the_short_clean_name(trip):
    e, sid, it, recs = trip()
    recs["garden"]["identity"]["name"] = NOISY
    recs["gallery"]["identity"]["name"] = "Moon Spa Dalat (문스파 달랏)"
    for d in it:
        for i in d["items"]:
            if i.get("place_id") == "garden":
                i["name"] = NOISY
    target, opts = run_repair(e, sid, it, recs, {DATE: {"garden": wet(*range(6, 22))}, DAY2: {"garden": wet(*range(6, 22))}})
    assert target["name"] == "ĐÔI DÉP Camellia Tea Spa"
    texts = {o["kind"]: o["text"] for o in opts}
    assert texts["backup"] == "Ghé Moon Spa Dalat (có mái che) thay cho ĐÔI DÉP Camellia Tea Spa"
    assert all("달랏" not in t and "|" not in t for t in texts.values())
    assert texts["keep"] == "Giữ nguyên lịch"


def test_a_shift_title_says_the_new_time_and_the_option_photo_is_the_substitute_it_names(trip):
    e, sid, it, recs = trip()
    day_no, start, end = where(it, "garden")
    rain = list(range(int(start[:2]), int(end[:2]) + 1))
    target, opts = run_repair(e, sid, it, recs, {DATE: {"garden": wet(*rain)}})
    shift = opts[0]
    assert shift["kind"] == "shift" and shift["text"].startswith("Đi garden lúc ") and f"thay vì {start}" in shift["text"]
    new_start = shift["text"].split(" lúc ")[1].split(" thay")[0]
    assert new_start != start
    _, back = run_repair(e, sid, it, recs, {DATE: {"garden": wet(*range(6, 22))}, DAY2: {"garden": wet(*range(6, 22))}})
    sub = next(o for o in back if o["kind"] == "backup")
    assert sub["place"] == "gallery" and sub["text"].startswith("Ghé gallery")


# ---------- DP5: arrival / departure changed on the Trip side ----------

def _frame(arrive=None, leave=None):
    return {"context": {"frame": {"arrive": {"at": arrive} if arrive else None, "leave": {"at": leave} if leave else None}}}


TWO_DAY = {"itinerary": [day(("garden", "09:00", "11:00"), d=1, date=DATE), day(("cafe", "15:00", "16:00"), d=2, date=DAY2)],
           "time_budget": {"per_day": [{"from": "08:00", "to": "21:00"}, {"from": "08:00", "to": "17:00"}]}}


def test_a_later_arrival_and_an_earlier_departure_become_day_windows_with_the_planning_buffers():
    old = _frame("2026-12-12T09:00", "2026-12-13T18:00")
    new = _frame("2026-12-12T13:30", "2026-12-13T15:00")
    assert eve.trip_windows(old["context"], new["context"], TWO_DAY, CFG) == {0: (13 * 60 + 30, 21 * 60), 1: (8 * 60, 14 * 60 + 15)}


def test_an_unchanged_earlier_or_unknown_time_opens_nothing():
    old = _frame("2026-12-12T09:00", "2026-12-13T15:00")
    for new in (_frame("2026-12-12T09:00", "2026-12-13T15:00"),      # same
                _frame("2026-12-12T07:00", "2026-12-13T20:00"),      # arrive earlier, leave later: nothing becomes infeasible
                _frame(None, None),                                  # the Trip side no longer says: unknown is not a cause
                _frame("2026-12-14T13:00", None)):                   # a different date is another trip, not a new window
        assert eve.trip_windows(old["context"], new["context"], TWO_DAY, CFG) == {}
    assert eve.trip_windows(old["context"], None, TWO_DAY, CFG) == {}


def test_without_a_frame_the_plain_arrive_at_and_leave_at_count_on_day_one_and_the_last_day():
    old, new = {"arrive_at": "09:00", "leave_at": "18:00"}, {"arrive_at": "12:00", "leave_at": "16:00"}
    assert eve.trip_windows(old, new, TWO_DAY, CFG) == {0: (12 * 60, 21 * 60), 1: (8 * 60, 15 * 60 + 15)}


def test_a_trip_side_arrival_change_asks_about_the_stop_that_no_longer_fits_and_options_respect_it(trip, tmp_path):
    e, sid, it, recs = trip()
    e.route_fn = lambda *a: None
    plan = e.confirm(sid)
    snapshot = e.store.get(sid).model_dump(mode="json")
    first = plan["itinerary"][0]
    early = next(i for i in first["items"] if i.get("kind") == "visit")
    assert to_min(early["start"]) < 10 * 60          # the day opens in the morning
    new_trip = {"context": {"frame": {"arrive": {"at": f"{first['date']}T10:00"}, "leave": None}}}
    e2 = Engine(list(recs.values()), cfg=CFG, live_cfg=FakeLiveCfg(), store=Store(None), geocode_fn=no_geocode,
                matrix_fn=fake_matrix, sun_fn=lambda *a: (360, 1050), background=False)
    today = _date.fromisoformat(first["date"]).toordinal() - 1
    out = eve.run_eve(e2, snapshot, plan, journey="j2", plan_hash="h2", today=_date.fromordinal(today).isoformat(),
                      store_root=tmp_path, live_cfg=None, src=FakeLive(steps=None), trip_input=new_trip)
    row = next(a for a in out["ask"] if a["place_id"] == early["place_id"])
    assert row["level"] == 3 and row["cause"]["factor"] == "window" and "10:00" in row["cause"]["text"]
    assert row["options"][0]["kind"] == "relay", "the first way out lays the same stops out again inside the new window"
    assert row["options"][0]["text"] == "Xếp lại ngày 1 trong khung 10:00–21:00"
    assert all(o["actions"][0]["type"] == "set_day_window" and o["actions"][0]["day"] == 0 for o in row["options"] if o["kind"] != "keep")
    assert all(o["kind"] != "keep" for o in row["options"])       # level 3: no "keep"
    again = eve.Store(tmp_path).get("j2", "h2")["pending"][0]
    assert again["options"][0]["actions"][0]["type"] == "set_day_window"


# ---------- DP6: holidays (CalendarDay) ----------

def test_a_holiday_alone_is_not_evidence_of_a_closure_verified_hours_that_cover_the_visit_stay_quiet():
    r = {**RECS, "open": rec("open", 1, 1, hours={"sat": [["08:00", "18:00"]]})}      # 2026-12-12 is a Saturday
    f = eve.Factors(date=DATE, holiday="Quốc khánh", closed={})
    rows = {x["place_id"]: x for x in eve.assess(day(("open", "10:00", "11:00")), r, f, CFG)}
    assert rows["open"]["level"] == 0


def test_a_holiday_closes_a_stop_only_with_evidence_the_current_hours_or_a_closed_record():
    miss = rec("late", 1, 1, hours={"sat": [["08:00", "12:00"]]})
    shut = {**rec("shut", 1, 1), "status": "DISABLED", "status_reason": "closure_permanent"}
    assert eve.closed_now(miss, DATE, "14:00", "15:00")["text"] == "giờ mở cửa mới nhất không phủ 14:00–15:00"
    assert eve.closed_now(shut, DATE, "10:00", "11:00")["text"] == "theo dữ liệu mới nhất, nơi này đã đóng cửa"
    f = eve.Factors(date=DATE, holiday="Quốc khánh", closed={"shut": eve.closed_now(shut, DATE, "10:00", "11:00")})
    r = {**RECS, "shut": shut}
    row = eve.assess(day(("shut", "10:00", "11:00")), r, f, CFG)[0]
    assert row["level"] == 3 and row["causes"][0]["factor"] == "closed"


def test_the_holiday_comes_from_calendar_day_through_live_and_a_tet_closure_period_counts_as_one():
    import live
    assert live.holidays([_date(2026, 9, 2)]) == {_date(2026, 9, 2): "Quốc khánh"}     # the CalendarDay view, not a table here
    src = FakeLive(events={_date.fromisoformat(DATE): [{"name": "Tết Nguyên Đán", "crowd": "peak", "closure_risk": True}]})
    plan = gplan()
    f = eve.gather(plan["itinerary"], plan, RECS, CFG, None, {}, [DATE], src)[DATE]
    assert f.holiday == "Tết Nguyên Đán"
    rows = {x["place_id"]: x for x in eve.assess(day(("plain", "10:00", "11:00")), {**RECS, "plain": rec("plain", 1, 1, hours=None)}, f, CFG)}
    assert rows["plain"]["level"] == 1 and rows["plain"]["causes"][0]["text"].startswith("Dịp Tết Nguyên Đán")


def test_what_the_check_sees_but_does_not_ask_is_kept_as_notes_for_the_plan(trip, tmp_path):
    e, sid, it, recs = trip()
    e.route_fn = lambda *a: None
    plan = e.confirm(sid)
    snapshot = e.store.get(sid).model_dump(mode="json")
    g_day, start, end = where(plan["itinerary"], "garden")
    when = plan["itinerary"][g_day - 1]["date"]
    drizzle = hours(**{f"h{h}": (0.4, 0.3) for h in range(int(start[:2]), int(end[:2]) + 1)})
    e2 = Engine(list(recs.values()), cfg=CFG, live_cfg=FakeLiveCfg(), store=Store(None), geocode_fn=no_geocode,
                matrix_fn=fake_matrix, sun_fn=lambda *a: (360, 1050), background=False)
    today = _date.fromordinal(_date.fromisoformat(when).toordinal() - 1).isoformat()
    out = eve.run_eve(e2, snapshot, plan, journey="j3", plan_hash="h3", today=today, store_root=tmp_path, live_cfg=None,
                      src=FakeLive(sky={when: drizzle}, steps=None))
    assert out["ask"] == [] and out["notify"] is False
    notes = eve.Store(tmp_path).get("j3", "h3")["notes"]
    note = next(n for n in notes if n["place_id"] == "garden")
    assert note["level"] == 1 and note["factor"] == "rain" and note["text"].startswith("dự báo mưa 40%") and note["date"] == when
    assert eve.Store(tmp_path).get("j3", "other")["notes"] == []          # notes belong to one confirmed plan


def test_the_tool_gate_turns_a_physically_impossible_hour_into_unknown_not_an_alarm():
    bad = hours(h14={"rain_prob": 1.7, "rain_mm": 900.0, "gust_kmh": 400.0}, h15=(0.9, 5.0))
    plan = gplan()
    f = eve.gather(plan["itinerary"], plan, RECS, CFG, None, {}, [DATE], FakeLive(sky={DATE: bad}))[DATE]
    assert 14 not in f.weather["garden"]["hours"] and 15 in f.weather["garden"]["hours"]
    rows = {r["place_id"]: r for r in eve.assess(day(("garden", "14:00", "15:00")), RECS, f, CFG)}
    assert rows["garden"]["level"] == 0                  # the only hour of the visit was a bad reading: unknown


def test_a_late_arrival_that_empties_the_morning_offers_one_trim_that_drops_what_cannot_fit(trip, tmp_path):
    e, sid, it, recs = trip()
    e.route_fn = lambda *a: None
    plan = e.confirm(sid)
    snapshot = e.store.get(sid).model_dump(mode="json")
    first = plan["itinerary"][0]
    new_trip = {"context": {"frame": {"arrive": {"at": f"{first['date']}T17:00"}, "leave": None}}}
    e2 = Engine(list(recs.values()), cfg=CFG, live_cfg=FakeLiveCfg(), store=Store(None), geocode_fn=no_geocode,
                matrix_fn=fake_matrix, sun_fn=lambda *a: (360, 1050), background=False)
    today = _date.fromordinal(_date.fromisoformat(first["date"]).toordinal() - 1).isoformat()
    out = eve.run_eve(e2, snapshot, plan, journey="j4", plan_hash="h4", today=today, store_root=tmp_path, live_cfg=None,
                      src=FakeLive(steps=None), trip_input=new_trip)
    assert len(out["ask"]) == 1 and out["ask"][0]["level"] == 3          # one question for the day, not one per stop
    a = out["ask"][0]
    assert a["cause"]["factor"] == "window" and a["also"]                  # the other stops it covers
    trim = next(o for o in a["options"] if o["kind"] == "trim")
    drops = [x["place"] for x in trim["actions"] if x["type"] == "drop_place"]
    assert trim["actions"][0]["type"] == "set_day_window" and len(drops) >= 2
    assert "garden" not in drops                    # the stop that fits once re-laid in the window stays
    assert all(o["kind"] != "keep" for o in a["options"])


# ---------- ClimateNormal gap: a forecast far from the month's normal is doubtful unless both models agree ----------

DRY = {"rain_prob": 0.05}


def _garden_rain(disagree, normal=DRY):
    w = hours(h14=(0.85, 3.0), h15=(0.85, 2.0))
    for r in w["hours"].values():
        r["disagree"] = disagree
    return check(day(("garden", "14:00", "17:00")), {"garden": w}, normal=normal)["garden"]


def test_85_percent_rain_in_the_dry_season_with_both_models_agreeing_still_alerts():
    assert _garden_rain(False)["level"] == 2


def test_the_same_forecast_with_only_one_model_is_doubtful_a_note_not_an_alarm():
    assert _garden_rain(None)["level"] == 1


def test_models_disagreeing_stays_a_note_and_no_normal_means_no_gap_check():
    assert _garden_rain(True)["level"] == 1
    assert _garden_rain(None, normal=None)["level"] == 2          # unknown normal: nothing to compare, the old rule
    assert _garden_rain(None, normal={"rain_prob": 0.7})["level"] == 2   # close to the month's normal: not doubtful


def test_store_keeps_the_experts_notes_beside_the_evening_notes(tmp_path):
    store = eve.Store(tmp_path)
    store.save_expert("j1", "h1", {"status": "ok", "tries": 1}, [{"date": DATE, "place_id": "garden", "name": "G", "level": 1,
                                                                   "factor": "local_expert", "text": "Hết mùa."}])
    store.save("j1", "h1", {"levels": {}, "pending": [], "notes": [{"factor": "rain"}]})     # an evening saves its own notes
    assert [n["factor"] for n in store.get("j1", "h1")["notes"]] == ["rain", "local_expert"]
    assert store.expert("j1", "h1")["status"] == "ok"
    assert store.get("j1", "h2")["notes"] == [] and store.expert("j1", "h2") == {}          # a new plan starts clean
