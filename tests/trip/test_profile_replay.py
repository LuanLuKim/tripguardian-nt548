"""Replay eval of the profile (docs/TRIP_UNDERSTANDING.md §17): synthetic personas over many trips; every invariant
must hold in every session."""

from datetime import date

import pytest

from trip.api.profile_replay import PERSONAS, replay
from trip.infrastructure.settings import PatternSettings

TODAY = date(2026, 10, 28)
PCFG = PatternSettings(enabled=True, min_sessions=3, window=8, agreement=0.75, stale_days=365, max_places=2)


@pytest.fixture
def report(catalog, tmp_path):
    return replay(PERSONAS, cfg=PCFG, catalog=catalog, today=TODAY, root=tmp_path)


def test_every_invariant_holds_in_every_check(report):
    inv = report["invariants"]
    assert set(inv) == {"explicit_only", "only_used_entries_seed", "no_constraint_from_profile", "current_trip_wins",
                        "every_vote_visible", "delete_removes_effect", "pause_stops_use",
                        "need_is_silent_prior"}
    for name, r in inv.items():
        assert r["checked"] > 0 and r["failed"] == 0, (name, r["examples"])
    assert report["ok"] is True


def test_a_changed_taste_retires_the_old_entry(report):
    final = report["personas"]["changer"]["final"]
    assert final["pace=packed"] == "retired" and final["pace=slow"] == "active"


def test_stale_and_one_off_entries_never_seed(report):
    assert report["personas"]["stale"]["seeded"][-1] == []
    assert all(not s for s in report["personas"]["one_off"]["seeded"])
    assert "soft:scenic_view=present=love" not in report["personas"]["one_off"]["final"]  # a guess is no entry


def test_a_deleted_entry_never_seeds_again(report):
    p = report["personas"]["deleter"]
    assert "pace=slow" in p["seeded"][3] and all("pace=slow" not in s for s in p["seeded"][4:])
    assert "pace=slow" not in p["final"]


def test_metrics_are_reported(report):
    m = report["metrics"]
    assert m["sessions"] == sum(len(p.trips) for p in PERSONAS)
    assert 0 <= m["prior_hit"] <= 1 and 0 <= m["prior_overridden"] <= 1 and m["priors"] > 0


def test_a_stored_need_is_a_silent_prior_and_a_filter_only_in_the_trip_that_says_it(report):
    p = report["personas"]["dieter"]
    assert p["seeded"][1] == ["need:vegetarian=yes"]  # applied silently after the trip that said it
    assert p["need_filter"] == [True, False, False, False, False]  # only the trip that said it has a filter
    assert all("need:vegetarian=yes" not in s for s in p["seeded"][4:])  # deleted after trip 3
    assert "need:vegetarian=yes" not in p["final"]


def test_a_corrected_need_stops_seeding(report):
    p = report["personas"]["corrector"]
    assert p["seeded"][1] == ["need:vegetarian=yes"] and p["seeded"][2] == [] and p["seeded"][3] == []
    assert p["final"]["need:vegetarian=yes"] == "weak" and p["final"]["need:vegetarian=no"] == "active"


def test_a_need_said_about_someone_else_is_never_stored(report):
    p = report["personas"]["carer"]
    assert all(not s for s in p["seeded"]) and not any(k.startswith("need:") for k in p["final"])
