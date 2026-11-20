"""Spec §11: every realistic case passes the realism checks. PENDING lists the checks a later task of
git 7c4da01:docs/plans/2026-10-15-planning-realistic-core.md turns green; each task deletes its entries."""

import pytest

from realistic_cases import CASES, SERVING, run_case
from realistic_checks import CHECKS

pytestmark = pytest.mark.skipif(not SERVING.exists(), reason="needs data/serving/places.json")

PENDING: dict[str, str] = {}


@pytest.fixture(scope="module")
def runs():
    return {c["id"]: run_case(c) for c in CASES}


def test_every_case_resolves_to_real_places():
    from realistic_cases import pid
    for c in CASES:
        for name in c["places"] + [c["lodging"]]:
            assert pid(name)


@pytest.mark.parametrize("check", sorted(CHECKS))
def test_realism(check, runs, request):
    if check in PENDING:
        request.applymarker(pytest.mark.xfail(strict=True, reason=PENDING[check]))
    failures = [f"{cid}: {msg}" for cid, run in runs.items() for msg in CHECKS[check](run)]
    assert not failures, "\n".join(failures[:40])


def test_no_refused_edit_or_unpicked_plan(runs, request):
    """Run.errors: an edit the engine refused, or a plan shown without being picked, must not pass silently."""
    if "run_errors" in PENDING:
        request.applymarker(pytest.mark.xfail(strict=True, reason=PENDING["run_errors"]))
    failures = [f"{cid}: {e}" for cid, run in runs.items() for e in run.errors]
    assert not failures, "\n".join(failures)


# The cases where "Tối ưu lịch" once kept, or made, a day the user reads as wrong after they moved places around:
# a missed lunch on a short last morning, a return past the day's end, a sunset place at 09:24 with no reason given.
SCRAMBLED = ["couple_slow_dawn", "friends_packed_bar", "seven_days", "hotel_breakfast"]


@pytest.mark.parametrize("cid", SCRAMBLED)
def test_optimising_a_scrambled_plan_passes_the_realism_checks(cid):
    """Each day's last place moved to the next day (a user dragging places about), then "Tối ưu lịch" on the whole
    plan: what it shows passes every realism check, as the first plan does."""
    from realistic_cases import Run, _unplaced, by_id, decision, engine, pick, pid
    c = next(c for c in CASES if c["id"] == cid)
    eng = engine()
    out = eng.create(decision(c))
    sid = out["id"]
    view = pick(eng, sid, out["view"])
    days = [[i["place_id"] for i in d["items"] if i["kind"] == "visit"] for d in view["itinerary"]]
    for k, ids in enumerate(days):
        if ids:
            eng.act(sid, {"type": "move_place", "place": ids[-1], "day": (k + 1) % len(days)})
    view = eng.recommend(sid, "all")["view"]
    lodge = by_id()[pid(c["lodging"])]["identity"]
    run = Run(c, view, view.get("itinerary") or [], _unplaced(view), {n: pid(n) for n in c["places"]},
              (lodge["lat"], lodge["lng"]), 0.0, [], view.get("ghosts") or [])
    failures = [f"{name}: {msg}" for name, check in CHECKS.items() for msg in check(run)]
    assert not failures, "\n".join(failures)
