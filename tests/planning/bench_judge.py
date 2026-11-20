"""Every realistic case as the user reads it, before and after "Tối ưu lịch", on the first plan ("fresh") and after
moving each day's last place to the next day ("shuffle", a user dragging places around); the realism checks
(realistic_checks.CHECKS) on each. One text file per case in OUT_DIR, to read side by side.

    .venv/bin/python tests/planning/bench_judge.py OUT_DIR [case ...]
"""
import sys, time
from pathlib import Path
root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / "tests/planning")); sys.path.insert(0, str(root / "src"))
from realistic_cases import CASES, Run, decision, engine, pick, render, pid as pid_of, by_id, _unplaced
from realistic_checks import CHECKS

def as_run(c, eng, sid, view, seconds=0.0):
    lodge = by_id()[pid_of(c["lodging"])]["identity"]
    ids = {n: pid_of(n) for n in c["places"]}
    return Run(c, view, view.get("itinerary") or [], _unplaced(view), ids, (lodge["lat"], lodge["lng"]), seconds, [], view.get("ghosts") or [])

def checks(run):
    bad = []
    for name, f in CHECKS.items():
        try:
            r = f(run)
        except Exception as e:  # noqa
            r = [f"crash {type(e).__name__}: {e}"]
        if r:
            bad.append(f"{name}: {r if isinstance(r, str) else '; '.join(map(str, r))[:300]}")
    return bad

def main():
    OUT = Path(sys.argv[1])
    cases = [c for c in CASES if len(sys.argv) < 3 or c["id"] in sys.argv[2:]]
    for c in cases:
        if c["edits"]:
            continue
        blocks = []
        for mode in ("fresh", "shuffle"):
            eng = engine(); out = eng.create(decision(c)); sid = out["id"]
            view = pick(eng, sid, out["view"])
            if mode == "shuffle":
                days = [[i["place_id"] for i in d["items"] if i["kind"] == "visit" and i.get("place_id")] for d in view.get("itinerary") or []]
                for k, ids in enumerate(days):
                    if ids and len(days) > 1:
                        try: view = eng.act(sid, {"type": "move_place", "place": ids[-1], "day": (k + 1) % len(days)})["view"]
                        except Exception: pass
            before = as_run(c, eng, sid, view)
            t = time.perf_counter(); got = eng.recommend(sid, "all"); ms = (time.perf_counter() - t) * 1000
            after = as_run(c, eng, sid, got["view"])
            p = got["proposal"]
            blocks.append(f"===== {mode}: BEFORE  checks={checks(before)}\n{render(before)}")
            blocks.append(f"===== {mode}: AFTER optimize {p['status']}/{p['diagnostics']} {ms:.0f} ms  "
                          f"before={p.get('before')} after={p.get('after')}\n  checks={checks(after)}\n{render(after)}")
        (OUT / f"{c['id']}.txt").write_text("\n\n".join(blocks))
        print(c["id"], "done", flush=True)


if __name__ == "__main__":
    main()
