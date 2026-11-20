"""Time of Lựa chọn's map preview (Engine.preview) and of the plan made right after it (Engine.create on the same
engine, as the harness does: it takes the preview and waits for an overload's direction search), a fresh engine per run,
no network. --gap: seconds the user spends between the two.

    .venv/bin/python tests/planning/bench_preview.py --runs 3 [--gap 2] [--case family_12_in_3]
"""

import argparse
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from realistic_cases import CASES, decision, engine  # noqa: E402


def p90(xs: list[float]) -> float:
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(0.9 * (len(xs) - 1))))]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--case", action="append", help="only these case ids")
    parser.add_argument("--gap", type=float, default=0.0, help="seconds between the preview and the create")
    args = parser.parse_args()
    cases = [c for c in CASES if not args.case or c["id"] in args.case]
    from planning.overload import warm
    warm()                              # the harness starts the direction workers at warm-up
    previews, creates = [], []
    print(f"{'case':24} {'places':>6} {'days':>4} {'overload':>8} {'preview_ms':>10} {'create_ms':>9}")
    for c in cases:
        p_ms, c_ms, over = [], [], None
        for _ in range(args.runs):
            eng = engine()
            eng.background = True       # as the harness runs it: an overload's directions are searched behind
            d = decision(c)
            t = time.perf_counter()
            out = eng.preview(d)
            p_ms.append((time.perf_counter() - t) * 1000)
            if args.gap:
                time.sleep(args.gap)    # the user reads the map before making the plan
            eng.background = False
            t = time.perf_counter()
            view = eng.create(decision(c))["view"]     # takes the preview (and its direction search)
            c_ms.append((time.perf_counter() - t) * 1000)
            over = bool(view.get("overload"))
            del out
        previews += p_ms
        creates += c_ms
        print(f"{c['id']:24} {len(c['places']):>6} {c['days']:>4} {str(over):>8} "
              f"{statistics.median(p_ms):>10.0f} {statistics.median(c_ms):>9.0f}")
    print(f"preview p50 {statistics.median(previews):.0f} ms, p90 {p90(previews):.0f} ms, max {max(previews):.0f} ms")
    print(f"create  p50 {statistics.median(creates):.0f} ms, p90 {p90(creates):.0f} ms, max {max(creates):.0f} ms")


if __name__ == "__main__":
    main()
