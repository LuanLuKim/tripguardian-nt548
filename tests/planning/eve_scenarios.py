"""D.3 measure (spec §D.3 "Đo"): the synthetic scenario set, run through the real Engine + eve.check.

    .venv/bin/python tests/planning/eve_scenarios.py      -> table + logs/planning_eve/scenarios_<time>.json

Each scenario is one evening before day 1 of the same 2-day trip. A scenario says whether a proposal is needed;
the run passes when: every needed one is asked with at least one real option (level 3: no "keep"), no unneeded
one is asked, every option re-runs through Engine.eve_trial as confirmable with no new level-2 stop, and each
offered option changes at most `max_changed` stops."""

import json
import sys
import time
from datetime import date as date_cls, datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parents[1] / "src")]

from plan_fixtures import CENTRE, SOUTH, CFG, FakeLive, decision, fake_matrix, no_geocode, spot  # noqa: E402

from planning import Engine, eve  # noqa: E402
from planning.session import Store  # noqa: E402

AT = "2026-12-11T20:00:00+07:00"


def hours(at=None):
    at = at or {}
    out = {}
    for h in range(24):
        row = {"rain_prob": 0.0, "rain_mm": 0.0, "gust_kmh": 10.0, "storm": False, "fog": False, "disagree": False}
        row.update(at.get(h, {}))
        out[h] = row
    return {"hours": out, "source": "open-meteo", "fetched_at": AT}


def rain(window, prob=0.85, mm=3.0, **more):
    return hours({h: {"rain_prob": prob, "rain_mm": mm, **more} for h in window})


def records():
    return [spot("garden", CENTRE, 0, name="Vườn dâu", features={"weather_exposed": "present"}, visit=(60, 90, 120)),
            spot("cloud", CENTRE, 1, name="Đồi săn mây", features={"cloud_hunting": "present"}),
            spot("cafe", CENTRE, 2, name="Quán cà phê", features={"setting": "indoor"}),
            spot("busy", SOUTH, 0, name="Chợ đêm", features={"crowd": "high", "setting": "indoor"}),
            spot("far", SOUTH, 1, name="Thác qua đèo", features={"setting": "indoor"}),
            spot("museum", SOUTH, 2, name="Bảo tàng", features={"setting": "indoor"}),
            spot("gallery", CENTRE, 3, name="Phòng tranh", features={"setting": "indoor"})]


def engine():
    recs = records()
    d = decision([r["id"] for r in recs[:6]], days=2, base={"place_id": None, "text": "home", "lat": CENTRE[0],
                                                             "lng": CENTRE[1]})
    d["backup_pool"] = [{"id": "gallery", "name": "Phòng tranh", "for": "garden", "reason": "trong nhà"}]
    e = Engine(recs, cfg=CFG, live_cfg=FakeLive(), store=Store(None), geocode_fn=no_geocode, matrix_fn=fake_matrix,
               sun_fn=lambda *a: (360, 1050), background=False)
    sid = e.create(d)["id"]
    view = e.load(sid)["view"]
    if view["state"]["chosen_variant"] is None:
        view = e.act(sid, {"type": "pick_variant", "id": view["variants"][0]["id"]})["view"]
    return e, sid, view["itinerary"], {r["id"]: r for r in recs}


def window(itinerary, pid):
    s, t = next((i["start"], i["end"]) for d in itinerary for i in d["items"] if i.get("place_id") == pid)
    return list(range(int(s[:2]), int(t[:2]) + 1)), next(d["date"] for d in itinerary for i in d["items"]
                                                          if i.get("place_id") == pid)


def scenarios(it):
    """name -> (needed, the target stop or None, {date: Factors kwargs}). Every stop of the trip gets a dry
    forecast unless the scenario says otherwise, so unknown weather never hides or fakes a result."""
    def on(pid, **kw):
        w, date = window(it, pid)
        return pid, date, w
    out = {}
    pid, date, w = on("garden")
    out["mưa chiều trên điểm ngoài trời"] = (True, pid, date, {"weather": {pid: rain(w)}})
    pid, date, w = on("cloud")
    out["sương mù sáng ở điểm săn mây"] = (True, pid, date, {"weather": {pid: hours({h: {"fog": True} for h in w})}})
    pid, date, _ = on("cafe")
    out["quán đóng cửa"] = (True, pid, date, {"closed": {pid: {"text": "Maps: tạm đóng cửa", "source": "gmaps",
                                                              "retrieved_at": AT}}})
    pid, date, _ = on("far")
    out["đèo có cảnh báo"] = (True, pid, date, {
        "passes": {pid: [{"name": "Đèo Mimosa", "coords": [[11.85, 108.46], [11.84, 108.465]]}]},
        "notices": [{"title": "Sạt lở", "severity": "severe", "kind": "landslide", "lat": 11.845, "lng": 108.46,
                     "radius_km": 2, "source": "advisories.yaml", "retrieved_at": AT}]})
    pid, date, _ = on("busy")
    out["lễ hội đông"] = (True, pid, date, {"events": [{"name": "Festival Hoa", "crowd": "peak",
                                                         "source": "config/events.yaml"}], "crowd_averse": True})
    pid, date, w = on("garden")
    late = [h for h in range(19, 23) if h not in w]
    out["mưa tối không ảnh hưởng"] = (False, None, date, {"weather": {p: rain(late, mm=8.0) for p in
                                                                         ("garden", "cloud", "cafe", "busy", "far", "museum")}})
    out["mưa phùn 98% 0,3 mm"] = (False, None, date, {"weather": {"garden": rain(w, prob=0.98, mm=0.3)}})
    out["hai model lệch"] = (False, None, date, {"weather": {"garden": rain(w, disagree=True)}})
    return out


def run() -> dict:
    rows, ok = [], True
    for name in scenarios(engine()[2]):
        e, sid, it, recs = engine()                        # a fresh trip each time: nothing leaks between cases
        needed, target, date, kw = scenarios(it)[name]
        dry = {i["place_id"]: hours() for d in it for i in d["items"] if i.get("place_id")}
        factors = {}
        for d in it:
            extra = kw if d["date"] == date else {}
            factors[d["date"]] = eve.Factors(date=d["date"], **{**extra, "weather": {**dry, **extra.get("weather", {})}})
        t = time.perf_counter()
        eve_of = (date_cls.fromisoformat(date) - timedelta(days=1)).isoformat()   # the evening before that day
        out = eve.check(it, recs, factors, CFG, lambda acts: e.eve_trial(sid, acts), today=eve_of, previous=None,
                        pool=["gallery"], must=set())
        ms = round((time.perf_counter() - t) * 1000)
        asked = [a["place_id"] for a in out["ask"]]
        problems = []
        if needed and asked != [target]:
            problems.append(f"asked {asked}, wanted [{target}]")
        if not needed and asked:
            problems.append(f"false alarm {asked}")
        options = [o for a in out["ask"] for o in a["options"]]
        real = [o for o in options if o["kind"] != "keep"]
        if needed and not real:
            problems.append("no real option")
        for a in out["ask"]:
            if a["level"] >= 3 and any(o["kind"] == "keep" for o in a["options"]):
                problems.append("level 3 offered keep")
        before = eve.levels(it, recs, factors, CFG)
        for o in real:
            again = e.eve_trial(sid, o["actions"])
            after = eve.levels(again["itinerary"], recs, factors, CFG)
            if not again["confirmable"]:
                problems.append(f"{o['kind']} not confirmable")
            if any(r["level"] >= 2 and before.get(p, {}).get("level", 0) < 2 for p, r in after.items()):
                problems.append(f"{o['kind']} makes a new level-2 stop")
            if any(a["type"] not in {"reorder", "move_place", "swap", "drop_place"} for a in o["actions"]):
                problems.append(f"{o['kind']} uses a forbidden action")
            if len(o["changed"]) > MAX_CHANGED:
                problems.append(f"{o['kind']} changes {len(o['changed'])} stops")
        ok &= not problems
        rows.append({"scenario": name, "needed": needed, "asked": asked,
                     "level": [a["level"] for a in out["ask"]],
                     "options": [{"kind": o["kind"], "changed": o["changed"], "shifted": o["shifted"], "text": o["text"]}
                                 for o in options],
                     "ms": ms, "problems": problems})
    return {"ok": ok, "rows": rows, "max_changed": MAX_CHANGED}


MAX_CHANGED = 2                # shift = 1 stop, a day swap or a backup = 2


def main():
    result = run()
    for r in result["rows"]:
        opts = ", ".join(f"{o['kind']}({len(o['changed'])})" for o in r["options"]) or "-"
        print(f"{'OK ' if not r['problems'] else 'BAD'} {r['scenario']:<34} needed={r['needed']!s:<5} "
              f"asked={r['asked']} level={r['level']} options={opts} {r['ms']} ms {'; '.join(r['problems'])}")
    print("PASS" if result["ok"] else "FAIL")
    out = HERE.parents[1] / "logs" / "planning_eve"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"scenarios_{datetime.now():%Y%m%d-%H%M%S}.json").write_text(json.dumps(result, ensure_ascii=False, indent=1))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
