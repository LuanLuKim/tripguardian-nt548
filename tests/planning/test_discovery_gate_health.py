"""Late gate health notes retain selections and cannot silently become safe visits."""
import pytest
from corpus import load_ontology

from decision import Data, Engine as DecisionEngine, Store as DecisionStore, Tools as DecisionTools, load_settings
from plan_fixtures import CENTRE, FakeLive, decision as planning_input, fake_matrix, no_geocode, rec
from planning import Engine, Tools
from agents import ToolError


@pytest.mark.parametrize('value', ['present', None])
@pytest.mark.parametrize('policy', ['flag', 'exclude'])
def test_late_effort_constraint_is_visible_in_actual_planning(value, policy):
    record = rec('hill', *CENTRE, name='Đồi đã chọn', group='scenic',
                 features={'long_walk': value} if value else {})
    record['provenance'] = {'voices': 3, 'as_of': '2026-11-04', 'coverage': {}, 'inputs': []}
    if value:
        record['effort']['long_walk'].update(reason=None, mention_rate=1.0, by_context={}, precision=None,
            evidence=['review:1'], confidence={'independent_sources': 3, 'agreement': 1.0,
                                             'freshness_days': 1, 'source_types': ['provider']})
    decision = DecisionTools(DecisionEngine(Data([record]), load_settings(), DecisionStore(None)))
    search = planning_input([], days=1)['trip_context']
    search['ontology_version'] = load_ontology().version
    sid = decision.create({'search_input': search})['id']
    decision.apply(sid, 'act', {'type': 'select', 'place_id': 'hill'}, lambda *_: None)
    requirement = {'feature': 'long_walk', 'op': 'ne', 'value': 'present', 'unknown_policy': policy}
    changed = {**search, 'hard_filters': [requirement]}
    assert decision.rebase(sid, {'search_input': changed})['view']['selected'] == ['hill']
    output = decision.apply(sid, 'confirm', {'for_planning': True}, lambda *_: None)
    engine = Engine([record], live_cfg=FakeLive(), geocode_fn=no_geocode, matrix_fn=fake_matrix,
                    sun_fn=lambda *_: (360, 1050), route_fn=lambda *_: None, background=False)
    created = engine.create(output)
    view = created['view']
    scheduled = {i.get('place_id') for d in view['itinerary'] or [] for i in d['items']}
    unplaced = {p['place_id'] for p in view['unplaced'] or []}
    blocked = set((view.get('back_to_decision') or {}).get('places', []))
    assert 'hill' in scheduled | unplaced | blocked
    warnings = [w for w in view['warnings'] if 'Đồi đã chọn' in w.get('text', '')]
    assert warnings, {'warnings': view['warnings'], 'back_to_decision': view.get('back_to_decision')}
    if value is None:
        assert any(w.get('code') == 'safety_unknown' and 'Chưa rõ' in w['text'] for w in warnings)
    else:
        if 'hill' in scheduled:
            assert any(v['kind'] == 'hard' and v['place_id'] == 'hill' for v in view['violations'])
        assert view['ok'] is False
        if 'hill' in scheduled:   # a warning, never a gate: the user may confirm the plan that carries it
            confirmed = Tools(engine).apply(created['id'], 'confirm', {}, lambda *_: None)
            assert any(v['kind'] == 'hard' and v['place_id'] == 'hill' for v in confirmed['violations'])
        else:
            with pytest.raises(ToolError) as exc:
                Tools(engine).apply(created['id'], 'confirm', {}, lambda *_: None)
            assert exc.value.status == 409
