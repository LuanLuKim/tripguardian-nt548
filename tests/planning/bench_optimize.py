""""Tối ưu lịch" (Engine.recommend) on every realistic case: the objective's terms before and after, and how long it took.
No network, no model.

    .venv/bin/python tests/planning/bench_optimize.py [--case seven_days]
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from realistic_cases import CASES, decision, engine, pick  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", action="append", help="only these case ids")
    parser.add_argument("--shuffle", action="store_true",
                        help="first move each day's last place to the next day, as a user dragging places around")
    args = parser.parse_args()
    print(f"{'case':22} {'status':14} {'travel':>13} {'spread':>11} {'timing':>13} {'value':>15} {'ms':>6}")
    rows = []
    for c in CASES:
        if args.case and c["id"] not in args.case:
            continue
        eng = engine()
        out = eng.create(decision(c))
        sid = out["id"]
        view = pick(eng, sid, out["view"])
        if args.shuffle:
            days = [[i["place_id"] for i in d["items"] if i["kind"] == "visit" and i.get("place_id")]
                    for d in view.get("itinerary") or []]
            for k, ids in enumerate(days):
                if ids and len(days) > 1:
                    try:
                        eng.act(sid, {"type": "move_place", "place": ids[-1], "day": (k + 1) % len(days)})
                    except Exception:  # noqa: BLE001 - a refused move leaves the plan as it was
                        pass
        t = time.perf_counter()
        got = eng.recommend(sid, "all")
        ms = (time.perf_counter() - t) * 1000
        p = got["proposal"]
        if "before" not in p:
            print(f"{c['id']:22} {p['status'] + ':' + ','.join(p['diagnostics']):14}")
            continue
        b, a = p["before"], p["after"]
        rows.append((b, a, ms))
        tag = ("changed" if p.get("changed") else p["diagnostics"][0])[:14]
        print(f"{c['id']:22} {tag:14} {b['travel_min']:>5}->{a['travel_min']:<6} {b['spread_min']:>4}->{a['spread_min']:<5} "
              f"{b['time_penalty']:>5}->{a['time_penalty']:<6} {b['value']:>6}->{a['value']:<7} {ms:>6.0f}")
        assert (a["problems"], a["meals_missed"], a["value"]) <= (b["problems"], b["meals_missed"], b["value"])
    if rows:
        print(f"travel {sum(b['travel_min'] for b, _, _ in rows)} -> {sum(a['travel_min'] for _, a, _ in rows)}, "
              f"value {sum(b['value'] for b, _, _ in rows):.0f} -> {sum(a['value'] for _, a, _ in rows):.0f}, "
              f"max {max(ms for *_, ms in rows):.0f} ms")


if __name__ == "__main__":
    main()
