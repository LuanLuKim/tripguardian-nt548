"""Production latency and fail-closed recovery regressions."""
from datetime import date
from types import SimpleNamespace

from planning.assistant import PlanTurn, build_messages
from test_planning_r12 import engine
from plan_fixtures import CENTRE, decision, spot


def test_diet_day_with_free_meals_stays_confirmable_and_names_what_is_open():
    from test_planning_diet_days import setup
    d, records = setup()
    e = engine(records)
    created = e.create(d)
    view = created['view']
    assert view['variants'] and view['back_to_decision'] is None
    assert view['active_variant']['confirmable']
    assert not view['violations']
    assert any(w['code'] == 'diet_meal_open' and 'mẹ' in w['text'] and '2026-12-13' in w['text']
               for w in view['warnings'])


def test_diet_day_meal_slots_suggest_only_verified_options_and_the_plan_confirms():
    from test_planning_diet_days import setup
    from plan_fixtures import all_days
    d, records = setup()
    d['trip_context']['context']['frame'] = {'days': [
        {'date': date, 'start': '11:30', 'end': '14:30', 'busy': []}
        for date in ('2026-12-12', '2026-12-13', '2026-12-14')]}
    records[1]['operation']['hours']['value'] = all_days('11:30', '14:30')
    e = engine(records)
    created = e.create(d)
    sid, view = created['id'], created['view']
    meals = [i['place_id'] for g in view['ghosts'] if g['day'] == 1 and g['kind'] != 'free' for i in g['items']]
    assert set(meals) <= {'mixed'}
    assert [w['meal'] for w in view['warnings'] if w['code'] == 'diet_meal_open'] == ['lunch']
    assert e.confirm(sid)


def test_meal_recovery_cannot_commit_a_forged_noncompliant_candidate():
    from test_planning_diet_days import setup
    from planning.session import ActionError
    import pytest
    d, records = setup()
    e = engine(records)
    created = e.create(d)
    before = e._get(created['id']).model_dump()
    with pytest.raises(ActionError):
        e.act(created['id'], {'type': 'repair_meals', 'acts': [
            {'type': 'add_from_backup', 'place': 'meat', 'day': 1}]})
    assert e._get(created['id']).model_dump() == before



def _invalid_clock(e, sid):
    e._get(sid).states[e._get(sid).position].start_time_override['a'] = 23 * 60
    e._schedules[sid] = [None] * len(e._get(sid).states)
    base = e._base[sid]
    results = e._card_results(base, 'main')
    results = e._repair_pass(e._get(sid), e._ctxs_for(base.trip, e._places_for(e._get(sid), base), None, e._get(sid).state)[1], results, set(range(2)))
    e._schedules[sid][e._get(sid).position] = results


def test_recovery_never_offers_to_drop_a_trip_must_place():
    recs = [spot('a', CENTRE, 0), spot('b', CENTRE, 1)]
    d = decision(['a', 'b'], days=2)
    d['trip_context']['anchors'] = [{'place_id': 'a', 'priority': 'must'}]
    e = engine(recs)
    created = e.create(d)
    _invalid_clock(e, created['id'])
    assert e.load(created['id'])['view']['recovery_actions'] == []


def test_invalid_edit_offers_a_verified_single_drop_recovery():
    recs = [spot('a', CENTRE, 0), spot('b', CENTRE, 1)]
    e = engine(recs)
    created = e.create(decision(['a', 'b'], days=2))
    sid = created['id']
    _invalid_clock(e, sid)
    view = e.load(sid)['view']
    assert view['violations'] and view['recovery_actions']   # the user may still confirm; the way out is offered
    action = view['recovery_actions'][0]
    assert action['reason'] and action['confirmable']
    repaired = e.act(sid, action['action'])['view']
    assert not repaired['violations']
    assert repaired['active_variant']['confirmable']
    assert e.confirm(sid)



def test_edit_messages_do_not_scan_corpus_evidence_before_the_first_model_call():
    e = engine([spot('cafe', CENTRE, 0, group='cafe')])
    d = decision(['cafe'], days=1)
    created = e.create(d)
    binding = {'region': 'dalat', 'release_id': 'r-release', 'manifest_sha256': 'a' * 64,
               'snapshot_version': 'snapshot', 'index_version': 'index'}
    e._get(created['id']).decision['corpus_binding'] = binding
    e.retrieval = SimpleNamespace(binding=SimpleNamespace(**binding))
    scans = []
    def slow_evidence(*args, **kwargs):
        scans.append(args)
        return []
    e._grounded_context = slow_evidence
    turn = PlanTurn(e, created['id'], 'Chuyển quán cà phê sang 15:00', date(2026, 11, 4))
    messages = build_messages(turn, [])
    assert messages[-1]['content'] == 'Chuyển quán cà phê sang 15:00'
    assert 'cafe' in str(turn.context)
    assert scans == []
