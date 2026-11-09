"""Pet safety survives legacy handoffs and cannot be relaxed by Planning."""

import pytest

from agents import ToolError
from plan_fixtures import CFG, CENTRE, FakeLive, decision, fake_matrix, no_geocode, spot, stay, prepared
from planning import Tools
from planning.engine import Engine
from planning.ghosts import pool
from planning.lodging import anywhere
from planning.schedule import simulate
from planning.validate import validate


def pet_decision(ids, **kwargs):
    out = decision(ids, days=1, **kwargs)
    out['trip_context']['context']['companions'] = ['solo', 'pet']
    return out


def engine(records):
    return Engine(records, cfg=CFG, live_cfg=FakeLive(), geocode_fn=no_geocode,
                  matrix_fn=fake_matrix, sun_fn=lambda *a: (360, 1050),
                  route_fn=lambda *a: {'points': [], 'source': 'fixture', 'fetched_at': 't'}, background=False)


@pytest.mark.parametrize('explicit', [False, True])
def test_user_pet_banned_pick_is_retained_warned_and_confirmation_stays_the_users(explicit):
    hard = [{'feature': 'pets', 'op': 'ne', 'value': 'not_allowed', 'unknown_policy': 'flag'}] if explicit else []
    d = pet_decision(['banned'], hard=hard, relaxed={'banned': ['pets']})
    e = engine([spot('banned', CENTRE, 0, features={'pets': 'not_allowed'})])
    created = e.create(d)
    view = created['view']
    assert e._get(created['id']).decision['confirmed'][0]['id'] == 'banned'
    assert any('thú cưng' in w['text'] and w.get('resolution') for w in view['warnings'])
    assert 'banned' in {i.get('place_id') for day in view['itinerary'] or [] for i in day['items']} | {
        p['place_id'] for p in view['unplaced']}
    e._base.clear()
    assert e.load(created['id'])['view']['ok'] is False
    assert e.load(created['id'])['view']['violations']
    confirmed = Tools(e).apply(created['id'], 'confirm', {}, lambda *a: None)   # a warning, never a gate
    assert any(v['kind'] == 'hard' for v in confirmed['violations'])


def test_pet_unknown_is_scheduled_with_explicit_uncertainty():
    e = engine([spot('unknown', CENTRE, 0)])
    view = e.create(pet_decision(['unknown']))['view']
    assert any(i.get('place_id') == 'unknown' for d in view['itinerary'] for i in d['items'])
    assert any('chưa rõ có cho mang thú cưng không' in w['text'].lower() for w in view['warnings'])


def test_validator_derives_pet_requirement_from_legacy_day_context_even_if_relaxed():
    trip = prepared(pet_decision(['banned'], relaxed={'banned': ['pets']}),
                    [spot('banned', CENTRE, 0, features={'pets': 'not_allowed'})])
    cx = trip.ctxs[0]
    violations = validate([cx], [simulate(['banned'], cx)], [], set(), None, None)
    assert any(v.kind == 'hard' and 'pets' in v.detail for v in violations)


def test_legacy_pet_suggestions_exclude_banned_and_flag_unknown():
    records = [spot('chosen', CENTRE, 0), spot('banned', CENTRE, 1, features={'pets': 'not_allowed'}),
               spot('unknown', CENTRE, 1), spot('allowed', CENTRE, 1, features={'pets': 'allowed'})]
    suggestions = pool(records, pet_decision(['chosen']), CFG)
    assert {p.id for p in suggestions} == {'unknown', 'allowed'}
    assert suggestions.unverified == {'unknown': ['pets']}


def test_legacy_pet_lodging_excludes_banned_and_unknown_but_preserves_own_lodging():
    records = [stay('banned', *CENTRE, features={'pets': 'not_allowed'}), stay('unknown', *CENTRE),
               stay('allowed', *CENTRE, features={'pets': 'allowed'})]
    d = pet_decision([])
    assert {c['id'] for c in anywhere(d, CFG, records)} == {'allowed'}
    for pid in ['banned', 'unknown']:
        d['lodging'] = {'id': pid, 'kind': 'corpus', 'lat': CENTRE[0], 'lng': CENTRE[1]}
        created = engine(records).create(d)
        assert created['id']
        assert any(w.get('code') == 'lodging_requirement' and w.get('feature') == 'pets'
                   for w in created['view']['warnings'])


def test_pet_backups_and_recommendations_never_volunteer_a_banned_place():
    from planning.backup import backups
    from planning.build import schedule_trip
    from planning.recommendations import recommend
    from test_planning_context_regressions import family_trip

    records, d = family_trip()
    d['trip_context']['context']['companions'] = ['pet']
    records[0]['operation']['hours']['status'] = 'UNCERTAIN'
    records[0]['identity']['category_group'] = 'bar'
    records[1]['identity']['category_group'] = 'bar'
    records[2]['identity']['category_group'] = 'bar'
    records[1]['suitability']['pets'] = {'value': 'not_allowed', 'status': 'VERIFIED',
                                      'distribution': {'not_allowed': 3}, 'n': 3}
    d['backup_pool'] = [{'id': 'bar'}, {'id': 'cafe'}]
    trip = prepared(d, records)
    sched = schedule_trip(trip)
    # Hours are uncertain at the chosen stop; backups must have reliable hours.
    replacement_rows = backups(sched.ctxs, sched.results, d, trip.by_id)['places']
    alternatives = [a for row in replacement_rows for a in row['alternatives']]
    assert {a['id'] for a in alternatives} == {'cafe'}
    assert any('chưa rõ có cho mang thú cưng không' in w['text']
               for a in alternatives for w in a['warnings'])
    records, d = family_trip()
    d['trip_context']['context']['companions'] = ['pet']
    records[1]['suitability']['pets'] = {'value': 'not_allowed', 'status': 'VERIFIED',
                                      'distribution': {'not_allowed': 3}, 'n': 3}
    d['backup_pool'] = [{'id': 'bar'}, {'id': 'cafe'}]
    trip = prepared(d, records)
    sched = schedule_trip(trip)
    recommended = [a for gap in recommend(sched.ctxs, sched.results, d, trip.by_id) for a in gap['alternatives']]
    assert {a['id'] for a in recommended} == {'cafe'}
    assert all(a['warnings'] for a in recommended)


def test_unknown_pet_ghost_has_human_readable_note():
    from planning.ghosts import fill
    from planning.model import DayResult, Item

    records = [spot('chosen', CENTRE, 0), spot('unknown', CENTRE, 1, group='cafe')]
    d = pet_decision(['chosen'], base={'text': 'home', 'lat': CENTRE[0], 'lng': CENTRE[1]})
    trip = prepared(d, records)
    result = DayResult((Item('free', 900, 1020),), (), (), 0, 0, 1020)
    slots = fill(trip.ctxs, [result], pool(records, d, CFG), {'chosen'}, set(), [], trip.points)
    assert 'chưa rõ có cho mang thú cưng không' in slots[0]['items'][0]['note']


def test_added_unknown_pet_stop_keeps_uncertainty_in_confirmed_output():
    records = [spot('chosen', CENTRE, 0, features={'pets': 'allowed'}), spot('unknown', CENTRE, 1)]
    d = pet_decision(['chosen'])
    d['backup_pool'] = [{'id': 'unknown'}]
    e = engine(records)
    sid = e.create(d)['id']
    e.act(sid, {'type': 'add_from_backup', 'place': 'unknown', 'day': 0})
    out = e.confirm(sid)
    assert any(w.get('place_id') == 'unknown' and 'chưa rõ có cho mang thú cưng không' in w['text']
               for w in out['warnings'])
