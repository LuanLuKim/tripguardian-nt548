import pytest

from harness import Harness, Store
from harness.__main__ import create_read_tools_factory
from decision import Data, Engine as DecisionEngine, Store as DecisionStore, Tools as DecisionTools, load_settings
from planning import Engine as PlanningEngine, Tools as PlanningTools
from trip import Catalog, Engine as TripEngine, SessionStore, Settings, Tools as TripTools
from fixtures import srec
from plan_fixtures import CFG, FakeLive, fake_matrix, no_geocode
from test_dispatch import run


@pytest.mark.parametrize('days,people', [(1, 1), (2, 2), (3, 4)])
def test_detached_reader_preserves_real_views_across_three_trips(days, people):
    records = [srec('place-1', name='Synthetic Place')]
    trip = TripTools(TripEngine(Catalog.from_records([], 1), Settings(), SessionStore(None), chat=None))
    decision = DecisionTools(DecisionEngine(Data(records), load_settings(), DecisionStore(None)))
    planning = PlanningTools(PlanningEngine(records, cfg=CFG, live_cfg=FakeLive(), geocode_fn=no_geocode,
        matrix_fn=fake_matrix, sun_fn=lambda *a: (360, 1050), background=False))
    h = Harness(trip, decision, planning, Store(None))
    v = h.create()
    v = run(h, v, 'turn', 'days', {'kind':'edit', 'target':'days', 'value':str(days)})
    v = run(h, v, 'turn', 'people', {'kind':'edit', 'target':'people', 'value':str(people)})
    # Use a valid compiled input without calling an assistant.
    from fixtures import si
    session = h.store.get(v['id'])
    session.outputs['trip'] = si(context={'days':days, 'people':people}).model_dump(mode='json')
    h.store.save(session)
    v = run(h, v, 'advance', 'decision')
    v = run(h, v, 'act', 'select', {'type':'select', 'place_id':'place-1'})
    v = run(h, v, 'advance', 'planning')
    before = {stage: h.load(v['id'], stage) for stage in ('trip', 'decision', 'planning')}
    h.read_tools_for_binding = create_read_tools_factory(h)
    after = {stage: h.load(v['id'], stage) for stage in ('trip', 'decision', 'planning')}
    assert after == before
    assert h.load(v['id'], 'planning') == after['planning']
