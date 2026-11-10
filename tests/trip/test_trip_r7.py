"""Day-scoped diets, withdrawn budgets and partial day-window answers."""
from datetime import date

import pytest

from trip import TripState, compile_search_input, plan_digest
from trip.api.engine import Engine, TurnInput
from trip.domain import readiness
from trip.domain.prepass import prepass
from trip.domain.required import tabs
from trip.domain.state import Evidence, Update, apply, with_meta
from trip.infrastructure.sessions import SessionStore
from trip_fixtures import ScriptedChat
from test_redesign_gate import build, said


def put(state, field, value):
    return apply(state, Update(field=field, value=value, source="user", confidence="high",
                               evidence=Evidence(turn=3, quote="new answer")))


def test_skipped_guessed_budget_is_unknown_then_new_answer_wins():
    st = with_meta(build(budget_vnd=said(2_000_000, source="inferred"), budget_scope={}), declined=("budget",))
    assert compile_search_input(st).context.budget_vnd is None
    assert compile_search_input(st).context.budget_intent is None
    st = put(st, "budget_vnd", 6_000_000)
    assert "budget" not in st.meta.declined
    assert "budget" in dict(readiness.missing(st))
    st = put(st, "budget_scope", "trip_total")
    assert compile_search_input(st).context.budget_vnd == 1_000_000


def test_skip_tap_removes_old_budget_fields(catalog, cfg, tmp_path):
    e = Engine(catalog, cfg, SessionStore(tmp_path), ScriptedChat(), today=lambda: date(2026, 11, 3))
    sid = e.create("first", "nothing")["id"]
    s = e.store.get(sid)
    s.state = build(budget_vnd=said(2_000_000, source="inferred"), budget_scope=said("trip_total", source="inferred"))
    from trip.domain import deck
    s.card = deck.build(s.state, e.catalog, e.cfg, ask="budget")
    e.store.save(s)
    e.turn(sid, TurnInput(kind="deck", answers={"budget": ["skip"]}), lambda *_: None)
    st = e.store.get(sid).state
    assert not st.budget_vnd.known and not st.budget_scope.known
    assert compile_search_input(st).context.budget_vnd is None


def test_explicit_day_windows_answer_gate_without_checkin(cfg):
    st = build(drop=("checkin_at", "checkout_at"), frame={"days": [
        {"index": 0, "start": "09:00"}, {"index": 2, "end": "17:00"}]})
    assert "trip" not in dict(readiness.missing(st))
    assert not any(t.qid == "trip" for t in tabs(st, cfg))


def test_companion_outside_enum_does_not_ask_count_again(cfg):
    st = build(drop=("companions",), companions_other=["hai anh em"])
    assert "companions" not in dict(readiness.missing(st))


def test_partial_frame_only_asks_missing_end_and_prefills_physical_bound(cfg):
    st = build(drop=("checkin_at", "checkout_at"), frame={"arrive": said({"at": "2026-11-20T22:00", "how": "bus"})})
    tab = next(t for t in tabs(st, cfg) if t.qid == "trip")
    assert tab.inputs == ("end",)
    assert all(not o.id.startswith("start.") for o in tab.options)
    st = build(drop=("checkin_at", "checkout_at"), frame={"days": [{"index": 0, "start": "09:00"}],
        "leave": said({"at": "2026-11-22T10:00", "how": "plane"}, source="inferred")})
    tab = next(t for t in tabs(st, cfg) if t.qid == "trip")
    assert tab.inputs == ("end",)
    opt = next(o for o in tab.options if o.id == "end.default")
    # 2026-11-04: the inferred airport is routed; only the hub margin closes the day.
    assert opt.prefilled and opt.writes[0].value == "09:15"
    from trip import compile_search_input
    context = compile_search_input(st).context
    assert context.exit_point is not None and context.exit_point.text == "Sân bay Liên Khương"
    assert (context.exit_point.lat, context.exit_point.lng) == (11.7502, 108.3672)


def understand(e, st, text, turn=1):
    from trip.domain.derive import derive
    return derive(e._deterministic(st, text, prepass(text, e.today()), turn), e.catalog, turn)


@pytest.fixture
def e(catalog, cfg, tmp_path):
    return Engine(catalog, cfg, SessionStore(tmp_path), ScriptedChat(), today=lambda: date(2026, 11, 3))


def test_day_two_member_diet_is_public_date_constraint_not_whole_trip(e):
    st = understand(e, build(), "Mẹ ăn chay ngày 2, hai ngày kia ăn bình thường.")
    si = compile_search_input(st)
    assert not any(h.feature == "vegetarian_options" for h in si.hard_filters)
    rule, = si.context.diet_days
    assert rule.date == date(2026, 11, 21)
    assert (rule.subject, rule.member, rule.feature, rule.unknown_policy) == ("member", "Mẹ", "vegetarian_options", "exclude")
    assert rule.evidence[0].quote
    assert type(si).model_validate(si.model_dump(mode="json")).context.diet_days == si.context.diet_days
    assert plan_digest(si) != plan_digest(compile_search_input(build()))


def test_solar_diet_date_does_not_change_trip_dates(e):
    st = understand(e, build(), "Cả nhóm ăn chay ngày 22/11, còn lại ăn bình thường.")
    si = compile_search_input(st)
    assert st.start_date.value == date(2026, 11, 20) and st.days.value == 3
    assert [(r.date, r.subject) for r in si.context.diet_days] == [(date(2026, 11, 22), "group")]


def test_unresolved_lunar_or_subject_asks_instead_of_global_filter(e, cfg):
    st = understand(e, build(), "Mẹ ăn chay ngày rằm.")
    assert "care" in dict(readiness.missing(st))
    tab = next(t for t in tabs(st, cfg) if t.qid == "care")
    assert "ngày dương" in tab.question
    si = compile_search_input(st)
    assert si.context.diet_days == ()
    assert not any(h.feature == "vegetarian_options" for h in si.hard_filters)
    st = understand(e, st, "Ngày 22/11.", turn=2)
    assert st.start_date.value == date(2026, 11, 20) and st.days.value == 3
    assert [r.date for r in compile_search_input(st).context.diet_days] == [date(2026, 11, 22)]


def test_lunar_diet_uses_calendar_evidence(e):
    from types import SimpleNamespace
    rows = [{"date": f"2026-11-{d}", "lunar": {"day": 13 + d - 20, "month": 10, "year": 2026}}
            for d in range(20, 23)]
    e.knowledge = SimpleNamespace(more=SimpleNamespace(feeds=SimpleNamespace(calendar=lambda: rows)))
    st = understand(e, build(), "Mẹ ăn chay ngày rằm.")
    assert [r.date for r in compile_search_input(st).context.diet_days] == [date(2026, 11, 22)]
    assert "care" not in dict(readiness.missing(st))


def test_unspecified_diet_subject_requires_answer_and_only_applies_to_one_day(e, cfg):
    st = understand(e, build(), "Ngày 2 ăn chay.")
    assert "care" in dict(readiness.missing(st))
    assert "ai" in next(t for t in tabs(st, cfg) if t.qid == "care").question.lower()
    st = understand(e, st, "Cả nhóm.", turn=2)
    assert [(r.date, r.subject) for r in compile_search_input(st).context.diet_days] == [(date(2026, 11, 21), "group")]


def test_agent_cannot_promote_a_day_diet_to_global_signal_or_filter(e):
    st = understand(e, build(), "Mẹ ăn chay ngày 2.")
    ev = Evidence(turn=1, quote="ăn chay")
    st = apply(st, Update(field="signal", op="add", value="vegetarian", source="user", confidence="high", evidence=ev))
    st = apply(st, Update(field="hard", op="add", value={"feature": "vegetarian_options", "op": "eq", "value": "yes"},
                          source="user", confidence="high", evidence=ev))
    assert not st.signals and not st.hard
    assert len(compile_search_input(st).context.diet_days) == 1


def test_diet_is_read_back_with_date_and_member(e):
    from trip.domain.readback import build as readback
    text = " ".join(line.text for line in readback(compile_search_input(
        understand(e, build(), "Mẹ ăn chay ngày 2."))).lines)
    assert "21/11" in text and "Mẹ" in text and "món chay" in text


def test_diet_subject_comes_from_its_clause_not_party_introduction(e):
    st = understand(e, build(), "Nhóm mình 2 người, mẹ ăn chay ngày 2.")
    assert compile_search_input(st).context.diet_days[0].member == "mẹ"


def test_invalid_day_stays_pending_without_crashing(e):
    st = understand(e, build(), "Mẹ ăn chay ngày 31.")
    assert "care" in dict(readiness.missing(st))
    assert compile_search_input(st).context.diet_days == ()


def test_date_only_clarification_is_supported(e):
    st = understand(e, build(), "Mẹ ăn chay ngày rằm.")
    st = understand(e, st, "22/11", turn=2)
    assert [r.date for r in compile_search_input(st).context.diet_days] == [date(2026, 11, 22)]


def test_lunar_month_is_not_read_as_solar_date(e):
    st = understand(e, build(), "Mẹ ăn chay ngày 21/11 âm lịch.")
    assert compile_search_input(st).context.diet_days == ()
    assert "care" in dict(readiness.missing(st))


def test_skipped_legacy_unlimited_is_unknown():
    st = with_meta(build(budget_unlimited=said(True)), declined=("budget",))
    assert compile_search_input(st).context.budget_unlimited is None


def test_negated_or_tasting_diet_is_not_a_constraint(e):
    for text in ("Mẹ không ăn chay ngày 2.", "Cả nhóm muốn thử món chay ngày 2."):
        si = compile_search_input(understand(e, build(), text))
        assert si.context.diet_days == ()
        assert not any(h.feature == "vegetarian_options" for h in si.hard_filters)
