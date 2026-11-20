"""Assistant settings and the session fields it adds (plan 2026-10-28-trip-decision-chatbot Task 1)."""

from trip.api.tools import Snapshot, _upgrade
from trip.domain.state import TripState
from trip.infrastructure.settings import Assistant, city_center, load


def test_old_snapshot_loads_with_new_meta():
    raw = Snapshot(id="0" * 12, state=TripState(), card=None, transcript=[]).model_dump(mode="json")
    for k in ("shown_ids", "told_numbers", "intent", "invited"):
        raw["state"]["meta"].pop(k)
    assert Snapshot.model_validate(_upgrade(raw)).state.meta.shown_ids == ()


def test_assistant_flag_and_defaults():
    cfg = load()
    assert Assistant().enabled is False  # a bare Assistant is off; config/trip.yaml turned it on 2026-10-29 (bench passed)
    assert cfg.assistant.enabled is True and cfg.assistant.clef_threshold == 0.35
    assert cfg.assistant.prefetch_wait_s == 3.0 and cfg.assistant.max_candidates == 6 and cfg.assistant.reply_words == 60


def test_assistant_speed_settings_are_declared():
    a = load().assistant
    assert a.service_tier == "priority" and a.ask_words == 40 and a.ask_words < a.reply_words
    assert "preamble" in a.reply_style and "one" in a.reply_style
    assert a.hide_prepared_lookup is True and Assistant().hide_prepared_lookup is False
    assert Assistant().service_tier == "" and Assistant().reply_style == ""  # a bare Assistant sends nothing extra
    assert a.covered_tools == "write" and Assistant().covered_tools == "all"  # round 6: on in config, today's behaviour in code


def test_city_center_is_declared():
    name, lat, lng = city_center()
    assert name == "Chợ Đà Lạt" and abs(lat - 11.9429) < 1e-6 and abs(lng - 108.4372) < 1e-6


def test_warm_runs_one_find_after_looks_and_marks_the_engine_warm(make_assistant):
    import threading
    from trip.api.tools import warm_assistant
    from trip_fixtures import ScriptedChat
    engine = make_assistant(ScriptedChat())
    assert engine.warmed.is_set()  # an engine nobody warms is ready at once
    seen = []
    engine.looks = type("L", (), {"warmed": threading.Event()})()
    engine.looks.warmed.set()
    find = engine.knowledge.find
    engine.knowledge.find = lambda criteria, state, limit=None: (seen.append(criteria), find(criteria, state, limit))[1]
    engine.warmed.clear()
    warm_assistant(engine)
    assert engine.warmed.is_set() and len(seen) == 1 and "text" in seen[0]
