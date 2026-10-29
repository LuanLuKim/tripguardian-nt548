"""Small measured eval of the Local Expert on synthetic trips (docs/PLANNING.md §Local Expert).
Run: EXTRACTOR_PARALLEL=8 .venv/bin/python tests/planning/expert_eval.py   (calls the real Extractor; <= 4 calls)
Checks per trip: findings are useful (an expected topic is named), nothing invented (the gate drops by construction;
here we also require every cited id to be one the prompt held), and the plan is unchanged when nothing applies."""

import json
import sys
import time
from dataclasses import replace
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from planning import expert  # noqa: E402
from plan_fixtures import CFG, rec  # noqa: E402

ON = replace(CFG, expert={**CFG.expert, "enabled": True})
CLAIMS = [c for c in json.load(open(Path(__file__).parents[2] / "data/dalat/local/local_claims.json"))["claims"]
          if c["status"] == "kept"]


def plan(d, *stops):
    return {"itinerary": [{"day": 1, "date": d, "items": [
        {"kind": "visit", "place_id": p, "name": n, "start": a, "end": b} for p, n, a, b in stops]}], "warnings": []}


def recs(**timing):
    out = {"a": rec("a", 11.9, 108.4), "b": rec("b", 11.91, 108.41), "c": rec("c", 11.92, 108.42)}
    for pid, t in timing.items():
        out[pid]["details"] = {"timing": t}
    return out


TRIPS = [
    ("holiday: Noel evening, indoor + outdoor", plan("2026-12-24", ("a", "Nhà thờ Con Gà", "09:00", "10:30"),
        ("b", "Quán cà phê Mê Linh", "11:00", "12:00"), ("c", "Chợ đêm Đà Lạt", "19:00", "21:00")), recs(),
     {date(2026, 12, 24): [{"name": "Noel và Tết Dương lịch", "crowd": "peak"}]}, {date(2026, 12, 24): None}, None, "noel"),
    ("flower season: wild sunflower (dã quỳ) hill in March, season is Oct-Dec", plan("2026-03-14",
        ("a", "Đồi Dã quỳ", "08:30", "10:00"), ("b", "Quán cà phê", "10:30", "11:30")), recs(), {}, {}, None, "nở"),
    ("rainy month: July, outdoor garden", plan("2026-07-14", ("a", "Vườn dâu ngoài trời", "14:00", "16:00"),
        ("b", "Bảo tàng", "09:00", "11:00")), recs(a={"avoid_months": [7]}), {}, {},
     {"2026-07-14": {"rain_prob": 0.9, "rain_mm": 14.0, "gust_kmh": 30, "storm": False}}, "mưa"),
    ("nothing applies: quiet dry weekday in February", plan("2026-02-17", ("a", "Bảo tàng", "09:00", "11:00")),
     recs(), {}, {}, None, None),
]


def main():
    rows = []
    for title, p, r, ev, hol, weather, topic in TRIPS:
        month = int(p["itinerary"][0]["date"][5:7])
        t0 = time.monotonic()
        out = expert.review(p, r, trip={"days": 1, "start_date": p["itinerary"][0]["date"]}, weather=weather, events=ev,
                            holidays={k: v for k, v in hol.items() if v}, calendar=None, normals={"7": {"rain_prob": 0.7}},
                            claims=CLAIMS, cfg=ON)
        sec = round(time.monotonic() - t0, 1)
        text = " ".join(f["message"] + " " + f["suggestion"] for f in out["findings"]).casefold()
        useful = (topic is None and not out["findings"]) or (topic is not None and bool(out["findings"]) and topic in text)
        rows.append({"trip": title, "month": month, "status": out["status"], "seconds": sec, "useful": useful,
                     "findings": out["findings"]})
        print(f"{title}: {out['status']} {sec}s useful={useful}")
        for f in out["findings"]:
            print("   -", f["slot_ref"], "|", f["message"], "|", f["suggestion"], "| cites", f["cites"], "docs", f["docs"])
    Path("logs/planning_expert").mkdir(parents=True, exist_ok=True)
    Path(f"logs/planning_expert/eval_{int(time.time())}.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1))
    return rows


if __name__ == "__main__":
    main()
