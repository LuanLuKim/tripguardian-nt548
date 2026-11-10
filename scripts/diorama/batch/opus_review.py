"""opus_review.py <slug> <ok|needs_kit|needs_human|redo> "<reason>": record the coordinator's photo verdict.

The checklist judge drifts by +-0.25, so the real gate is the coordinator looking at batch/review_sheet.py output.
ok -> stage ready; needs_kit / needs_human -> that stage; redo -> needs_human with the reason, to be rerun with
`auto3d.py run <slug> --redo --note "<reason>"`. Appends history {step: opus_review} and sets `reason`.
Never run it on a place whose auto3d run is still in progress (the runner owns its state file then).
"""
import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from auto3d import Place

STAGES = {"ok": "ready", "needs_kit": "needs_kit", "needs_human": "needs_human", "redo": "needs_human"}


def main() -> None:
    if len(sys.argv) != 4 or sys.argv[2] not in STAGES or not sys.argv[3].strip():
        raise SystemExit(__doc__)
    slug, verdict, reason = sys.argv[1], sys.argv[2], sys.argv[3].strip()
    place = Place(slug)
    if not place.state_file.exists():
        raise SystemExit(f"no auto3d state for {slug}")
    stage = STAGES[verdict]
    reason = f"Opus {datetime.date.today():%Y-%m-%d}: {reason}"
    place.s["reason"] = reason
    result = "ok" if verdict == "ok" else f"reject -> {stage}"
    place.s["stage"] = stage
    place.log("opus_review", result=result, reason=reason)
    print(f"{slug}: {stage}")


if __name__ == "__main__":
    main()
