"""`schedule_calls` counts every schedule_trip the overload search makes, in forked children too."""

from functools import partial

from plan_fixtures import CENTRE, spot
from test_planning_overload_parallel import a_little_short, trip_of, workers

from planning.overload import _in_children, _Runs, plan_or_directions


def work(run, name):
    run.count()
    run.count()
    return name


def test_a_forked_task_adds_its_schedule_calls_to_the_parents_count():
    run = _Runs(None)
    run.count()
    got = _in_children({n: partial(work, run, n) for n in ("a", "b", "c")})
    assert got == {"a": "a", "b": "b", "c": "c"} and run.calls == 1 + 3 * 2


def test_the_forked_search_counts_at_least_what_the_serial_one_does():
    trip = trip_of([spot(f"c{i}", CENTRE, i, visit=(120, 150, 180)) for i in range(10)], days=2)
    serial = plan_or_directions(workers(trip, 1))["schedule_calls"]
    forked = plan_or_directions(workers(trip, 3))["schedule_calls"]
    assert serial > 1 and forked >= serial        # the children share no memo, so they never make fewer calls


def test_the_two_widest_longer_day_trials_are_counted_once_each():
    trip = a_little_short()
    out = plan_or_directions(workers(trip, 3))
    assert out["overload"]["extend"] and out["schedule_calls"] >= plan_or_directions(workers(trip, 1))["schedule_calls"]
