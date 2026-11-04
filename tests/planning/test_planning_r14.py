"""Accuracy and replay regressions for planning."""

import copy
from dataclasses import replace

import pytest

from plan_fixtures import CFG, CENTRE, FakeLive, LODGING, decision, fake_matrix, no_geocode, rec, spot
from planning import Engine
from planning.session import Session, Store


def make_engine(records, output, store=None):
    engine = Engine(records + LODGING, cfg=CFG, live_cfg=FakeLive(), store=store or Store(None),
                    geocode_fn=no_geocode, matrix_fn=fake_matrix, sun_fn=lambda *a: None,
                    route_fn=lambda *a: None, background=False)
    return engine, engine.create(output)['id'] if store is None else None


def test_restart_and_undo_preserve_offered_cards_when_search_budget_expires(monkeypatch):
    import planning.variants as variants
    records = [spot(f'p{i}', CENTRE, i % 3, price={'typical_vnd': 10000}) for i in range(16)]
    engine, sid = make_engine(records, decision([r['id'] for r in records]))
    before = copy.deepcopy(engine.load(sid)['view']['variants'])
    engine.act(sid, {'type': 'set_lodging', 'text': 'Hotel', 'lat': CENTRE[0] + .01, 'lng': CENTRE[1]})
    persisted = Session.model_validate_json(engine.store.get(sid).model_dump_json())
    store = Store(None)
    store.restore(persisted)
    restarted, _ = make_engine(records, persisted.decision, store)
    real_search = variants.plan_or_directions

    def expired(trip, **kwargs):
        out = real_search(trip, **kwargs)
        for card in out['variants']:
            card.update(available=False, status='unavailable', confirmable=False,
                        unavailable_reason='Search budget expired')
        return out

    monkeypatch.setattr(variants, 'plan_or_directions', expired)
    undone = restarted.act(sid, {'type': 'undo'})['view']
    assert undone['variants'] == before


@pytest.mark.parametrize('pet,allowed', [(True, False), (True, True), (False, False)])
def test_pet_uncertainty_is_on_visit_in_view_replay_and_confirm(pet, allowed):
    records = [spot('a', CENTRE, 0, features={'pets': 'allowed'} if allowed else {})]
    output = decision(['a'], days=1)
    output['trip_context']['context']['companions'] = ['pet'] if pet else []
    engine, sid = make_engine(records, output)
    for view in [engine.load(sid)['view'], engine.act(sid, {'type': 'lock_slot', 'place': 'a'})['view']]:
        visit = next(i for d in view['itinerary'] for i in d['items'] if i['kind'] == 'visit')
        assert ('Chưa rõ có cho mang thú cưng không' in visit.get('note', '')) == (pet and not allowed)
    engine._base.clear()
    engine._schedules.clear()
    view = engine.load(sid)['view']
    out = engine.confirm(sid)
    for itinerary in [view['itinerary'], out['itinerary']]:
        visit = next(i for d in itinerary for i in d['items'] if i['kind'] == 'visit')
        assert ('Chưa rõ có cho mang thú cưng không' in visit.get('note', '')) == (pet and not allowed)


def test_evaluate_selects_a_confirmable_direction_not_an_unavailable_first_card(monkeypatch):
    import planning.evaluate as evaluate
    records = [spot(f'p{i}', CENTRE, i % 3, price={'typical_vnd': 10000}) for i in range(16)]
    real_create = Engine.create

    def unavailable_first(engine, *args, **kwargs):
        created = real_create(engine, *args, **kwargs)
        cards = created['view']['variants']
        available = next(v for v in cards if v['status'] == 'available')
        created['view']['variants'] = [{**available, 'id': 'unavailable', 'status': 'unavailable',
                                        'confirmable': False}, *cards]
        return created

    monkeypatch.setattr(Engine, 'create', unavailable_first)
    result = evaluate.plan_results(decision([r['id'] for r in records]), records, CFG, FakeLive(),
                                   no_geocode, fake_matrix, lambda *a: None, lambda *a: None)
    assert result['ok'], result


def test_sparse_three_day_trip_has_real_safe_ghosts_in_every_empty_day():
    from plan_fixtures import all_days
    hard = [{'feature': fid, 'op': 'ne', 'value': 'present', 'unknown_policy': 'exclude'}
            for fid in ('steep_or_stairs', 'long_walk')]
    features = {'steep_or_stairs': 'absent', 'long_walk': 'absent'}
    records = [rec(pid, CENTRE[0] + n * .001, CENTRE[1], features=features,
                   hours=all_days('06:00', '23:00')) for n, pid in enumerate(('a', 'b', 'c', 'd', 'e', 'f'))]
    records += [rec('unsafe', *CENTRE, features={'steep_or_stairs': 'present', 'long_walk': 'absent'})]
    output = decision(['a', 'b'], days=3, hard=hard)
    output['trip_context']['context'].update(lodging_booked='yes', lodging={
        'text': 'Booked hotel', 'lat': CENTRE[0], 'lng': CENTRE[1]})
    engine, sid = make_engine(records, output)
    view = engine.load(sid)['view']
    assert view['itinerary'] and len(view['itinerary']) == 3
    for day in view['itinerary']:
        if not any(i['kind'] == 'visit' for i in day['items']):
            suggestions = [g for g in view['ghosts'] if g['day'] == day['day'] - 1 and g['items']]
            assert suggestions, (day, view['ghosts'])
            assert all(i['place_id'] in {'c', 'd', 'e', 'f'} for g in suggestions for i in g['items'])


def test_two_days_spread_selected_places_instead_of_leaving_short_last_day_empty():
    from plan_fixtures import all_days
    records = [rec(pid, CENTRE[0] + n * .001, CENTRE[1], hours=all_days('08:00', '23:00'))
               for n, pid in enumerate(('a', 'b', 'c', 'd'))]
    output = decision(['a', 'b', 'c', 'd'], days=2, leave_at='12:00')
    engine, sid = make_engine(records, output)
    view = engine.load(sid)['view']
    assert all(any(i['kind'] == 'visit' for i in d['items']) for d in view['itinerary'])
    assert {i['place_id'] for d in view['itinerary'] for i in d['items'] if i['kind'] == 'visit'} == {'a','b','c','d'}


def test_unmet_dish_is_explained_instead_of_counting_a_selected_but_unplaced_venue():
    records = [rec('a', *CENTRE), rec('nem', *CENTRE, group='restaurant', usable=('meal', 'backup'),
                                       name='Nem nướng thật')]
    output = decision(['a'], days=1, base={'text': 'home', 'lat': CENTRE[0], 'lng': CENTRE[1]})
    output['trip_context']['wishes'] = {'dishes': [{'dish': 'nem nướng', 'place_ids': ['nem']} ]}
    engine, sid = make_engine(records, output)
    view = engine.load(sid)['view']
    assert any(i['place_id'] == 'nem' for g in view['ghosts'] if g['kind'] in {'lunch','dinner'} for i in g['items'])
    output['trip_context']['wishes']['dishes'].append({'dish': 'lẩu gà lá é', 'place_ids': []})
    engine, sid = make_engine(records, output)
    view = engine.load(sid)['view']
    assert any(w.get('code') == 'wish_unplaced' and 'lẩu gà lá é' in w['text'] for w in view['warnings'])


def test_offered_search_snapshot_never_persists_a_trial_history(tmp_path):
    records = [spot(f'p{i}', CENTRE, i % 3, price={'typical_vnd': 10000}) for i in range(16)]
    store = Store(tmp_path)
    engine, _ = make_engine(records, decision([r['id'] for r in records]), store)
    sid = engine.create(decision([r['id'] for r in records]))['id']
    session = store.get(sid)
    state = session.state.model_copy(deep=True)
    state.lodging_touched = True
    state.lodging_id = None
    state.pace_override = 'slow'
    trial = session.model_copy(update={'states': [state], 'position': 0})
    engine._offered_variants(trial, engine._base[sid])
    restored = Store(tmp_path).get(sid)
    assert restored.states == session.states
    assert restored.position == session.position


def test_spawn_worker_counter_does_not_allocate_a_named_semaphore(monkeypatch):
    import planning.overload as overload
    from plan_fixtures import prepared
    trip = prepared(decision(['a'], days=1), [rec('a', *CENTRE)])

    def no_semaphore(*args):
        raise AssertionError('spawn planning must not allocate a shared counter')

    monkeypatch.setattr(overload.mp, 'get_context', no_semaphore)
    result = overload.plan_or_directions(trip)
    assert result['ok']
    assert result['schedule_calls'] == 1


def test_restart_does_not_duplicate_trip_warnings():
    records = [rec('a', *CENTRE)]
    engine, sid = make_engine(records, decision(['a'], days=1))
    before = engine.load(sid)['view']['warnings']
    persisted = Session.model_validate_json(engine.store.get(sid).model_dump_json())
    store = Store(None)
    store.restore(persisted)
    restarted, _ = make_engine(records, persisted.decision, store)
    assert restarted.load(sid)['view']['warnings'] == before


def test_pet_visit_note_preserves_existing_text_without_duplicates():
    from plan_fixtures import prepared
    from planning.build import itinerary, schedule_trip
    records = [spot('a', CENTRE, 0)]
    output = decision(['a'], days=1)
    output['trip_context']['context']['companions'] = ['pet']
    trip = prepared(output, records)
    sched = schedule_trip(trip)
    note = 'Existing note; Chưa rõ có cho mang thú cưng không'
    results = [replace(r, items=[replace(i, note=note) if i.kind == 'visit' else i for i in r.items])
               for r in sched.results]
    rendered = itinerary(trip.days, results, sched.ctxs)
    visit = next(i for d in rendered for i in d['items'] if i['kind'] == 'visit')
    assert visit['note'] == note


def test_meal_ghost_cannot_extend_past_the_next_busy_interval():
    from plan_fixtures import prepared
    from planning.build import schedule_trip
    from planning.ghosts import fill, pool
    from planning.model import Item
    records = [rec('a', *CENTRE), rec('r', *CENTRE, group='restaurant',
                                    usable=('meal', 'backup'), name='Cơm thật')]
    output = decision(['a'], days=1, base={'text': 'home', 'lat': CENTRE[0], 'lng': CENTRE[1]})
    trip = prepared(output, records)
    sched = schedule_trip(trip)
    result = replace(sched.results[0], items=[Item('meal_free', 660, 670, name='lunch'),
                                              Item('busy', 670, 780)])
    ghosts = fill(sched.ctxs, [result], pool(records, output, CFG), {'a'}, set(), [], trip.points)
    lunch = next(g for g in ghosts if g['kind'] == 'lunch')
    assert lunch['items'] == []


def test_frame_ghost_cannot_overlap_the_next_visit():
    from plan_fixtures import prepared
    from planning.build import schedule_trip
    from planning.ghosts import fill, pool
    from planning.model import Item
    records = [rec('a', *CENTRE), rec('r', *CENTRE, group='restaurant',
                                    usable=('meal', 'backup'), name='Cơm thật')]
    output = decision(['a'], days=1, base={'text': 'home', 'lat': CENTRE[0], 'lng': CENTRE[1]})
    trip = prepared(output, records)
    sched = schedule_trip(trip)
    result = replace(sched.results[0], items=[Item('meal_free', 660, 670, name='lunch'),
                                              Item('visit', 670, 780, place_id='a')])
    ghosts = fill(sched.ctxs, [result], pool(records, output, CFG), {'a'}, set(), [], trip.points,
                  cover_frame=True)
    assert next(g for g in ghosts if g['kind'] == 'lunch')['items'] == []


def test_arrival_and_departure_buffers_are_explained_without_inventing_airport_legs():
    from plan_fixtures import prepared
    output = decision(['a'], days=1)
    output['trip_context']['context']['frame'] = {
        'days': [{'date': '2026-12-12', 'start': '10:15', 'end': '17:45', 'busy': [], 'intensity': 'normal'}],
        'arrive': {'at': '2026-12-12T09:00', 'how': 'plane'},
        'leave': {'at': '2026-12-12T19:00', 'how': 'plane'}, 'issues': []}
    trip = prepared(output, [rec('a', *CENTRE)])
    assert any(w.get('code') == 'arrival_buffer' and '09:00' in w['text'] and '10:15' in w['text']
               for w in trip.warnings)
    assert any(w.get('code') == 'departure_buffer' and '19:00' in w['text'] and 'chưa' in w['text'].lower()
               for w in trip.warnings)
    assert '@entry' not in trip.travel.ids and '@exit' not in trip.travel.ids
