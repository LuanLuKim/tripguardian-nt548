"""Checked timeout drafts stay editable without bypassing final validation."""

import pytest

from plan_fixtures import CENTRE, CFG, FakeLive, decision, fake_matrix, no_geocode, spot
from planning.engine import Engine, NotConfirmable
from planning.session import Store
import planning.overload as overload


def timeout_engine(monkeypatch):
    monkeypatch.setattr(overload, "_in_children", lambda *a, **kw: {})
    records = [spot(f"c{i}", CENTRE, i, visit=(180, 210, 240)) for i in range(4)]
    e = Engine(records, cfg=CFG, live_cfg=FakeLive(), store=Store(None), geocode_fn=no_geocode,
               matrix_fn=fake_matrix, sun_fn=lambda *a: (360, 1050), background=False)
    sid = e.create(decision([r["id"] for r in records], days=1))['id']
    return e, sid


def test_timeout_draft_accepts_drop_before_a_variant_was_chosen(monkeypatch):
    e, sid = timeout_engine(monkeypatch)
    with pytest.raises(NotConfirmable):
        e.confirm(sid)
    view = e.act(sid, {"type": "drop_place", "place": "c0"})["view"]
    assert 'c0' not in {i.get('place_id') for d in view['itinerary'] for i in d['items']}
    assert view['state']['chosen_variant'] == 'main'
    if not e._view_confirmable(view):
        with pytest.raises(NotConfirmable):
            e.confirm(sid)
    e._base.clear()
    e._schedules.clear()
    assert e.load(sid)['view']['state'] == view['state']


@pytest.mark.parametrize('metadata', [[], [{'place_id': 'p7', 'name': 'p7', 'reason': None}]])
def test_rebuilt_plan_drop_has_explicit_reason_when_card_metadata_is_missing(metadata):
    from test_planning_overload_edits import overloaded_started
    e, sid = overloaded_started()
    s = e._get(sid)
    assert s.state.plan_dropped
    base = e._ensure_base(sid)
    for card in base.variants:
        card['dropped'] = metadata
    base.offers.clear()
    base.active.clear()
    view = e.load(sid)['view']
    drops = view['active_variant']['dropped']
    assert drops and all(d.get('reason') for d in drops)
    assert all(d.get('text') not in (None, 'None') for d in view['active_variant']['dropped_by_plan'])


def test_edit_reports_remaining_violation_even_when_its_key_already_existed():
    from datetime import date
    from planning.assistant import PlanTurn
    from test_planning_edit_confirm_regressions import started
    e, sid = started()
    e.act(sid, {'type': 'move_place', 'place': 'horizon', 'day': 0})
    e.act(sid, {'type': 'set_day_window', 'day': 0, 'start': '20:50', 'end': '21:00'})
    turn = PlanTurn(e, sid, 'bắt đầu muộn hơn', date(2026, 11, 4))
    result = turn.commit({'type': 'set_day_window', 'day': 0, 'start': '20:55', 'end': '21:00'})
    assert result.get('flagged') and 'fixed' in result['note']
    assert e.confirm(sid)['violations']   # flagged, not gated: the user may still confirm


def test_timeout_draft_preview_is_read_only_and_its_token_can_apply(monkeypatch):
    e, sid = timeout_engine(monkeypatch)
    before = e._get(sid).model_dump()
    action = {'type': 'drop_place', 'place': 'c0'}
    preview = e.preview_act(sid, action)
    assert e._get(sid).model_dump() == before
    applied = e.act(sid, {**action, '_preview_token': preview['token']})['view']
    assert applied['itinerary'] == preview['view']['itinerary']


def test_rejected_first_draft_edit_does_not_choose_or_change_history(monkeypatch):
    from planning.session import ActionError
    e, sid = timeout_engine(monkeypatch)
    before = e._get(sid).model_dump()
    with pytest.raises(ActionError):
        e.act(sid, {'type': 'drop_place', 'place': 'not-a-place'})
    assert e._get(sid).model_dump() == before


def test_assistant_persists_tool_model_and_build_spans_with_one_trace():
    from test_planning_edit_confirm_regressions import started
    from test_planning_assistant import Script, call, reply, say, turn
    e, sid = started()
    e.assistant = Script(reply(call('plan')), say('Đây là lịch của bạn.'))
    turn(e, sid, 'cho mình xem lịch')
    trace = e._get(sid).turn_traces[-1]
    assert trace['id'] and trace['total_ms'] >= 0
    assert any('t_call_span' in item for item in trace['log'])
    assert any('t_tool_span tool=plan' in item for item in trace['log'])
    assert any('build_messages' in item for item in trace['log'])
    assert any('serialization' in item for item in trace['log'])
