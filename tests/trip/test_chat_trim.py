"""Chat stays brief; recorded context belongs on the right-hand board."""
from datetime import date

import pytest

from trip.agent.prompt import SYSTEM
from trip.agent.tools import TurnTools, lookups
from trip.api.engine import Engine, TurnInput
from trip.domain import deck
from trip.domain.state import TripState
from trip.infrastructure.catalog import Catalog
from trip.infrastructure.sessions import SessionStore
from trip_fixtures import ScriptedChat, served

SEED = ('Mình đi Đà Lạt 2 người từ 14 đến 16/11/2026 bằng ô tô có tài xế, '
        'mẹ mình đau gối nên không leo bậc thang và không đi bộ xa được, thích cà phê yên tĩnh.')


def test_prompt_keeps_recorded_facts_off_chat_but_preserves_disambiguation():
    assert 'Do not repeat or summarize facts already recorded' in SYSTEM
    assert 'say what you understood, in the user\'s own terms' not in SYSTEM
    assert 'Keep explicit confirmation of a specific interpretation of an ambiguous word' in SYSTEM
    assert 'Mình hiểu “retro”' in SYSTEM


@pytest.fixture
def menu():
    row = served('cafe', 'Quán kiểm thử', {}, group='restaurant', category='Quán cà phê')
    row['menu'] = {'dishes': [{'name': name} for name in ('Cà phê yên', 'Cà phê sữa đá', 'Bánh căn')]}
    return Catalog.from_records([], 1, evidence={'cafe': row})


def test_exact_owner_seed_does_not_turn_quiet_cafe_into_dish(menu):
    assert lookups(SEED, menu)['dishes'] == []


def test_model_cannot_write_truncated_venue_trait_as_dish(menu):
    turn = TurnTools(TripState(), SEED, 1, menu, date(2026, 11, 4))
    out = turn.run('record_fact', {'field': 'dish', 'op': 'add', 'value': 'cà phê yên',
                                 'quote': 'cà phê yên tĩnh', 'how': 'said'})
    assert 'error' in out
    assert not turn.state.wishes.dishes


@pytest.mark.parametrize('text,expected', [('Tìm quán có cà phê sữa đá', 'cà phê sữa đá'),
                                         ('Muốn ăn bánh căn', 'bánh căn')])
def test_specific_drink_and_food_still_lookup(menu, text, expected):
    assert [row['dish'] for row in lookups(text, menu)['dishes']] == [expected]


def test_mock_model_cannot_make_dish_block_from_exact_owner_seed(make_assistant, menu):
    from trip_fixtures import call, reply, say
    from test_assistant_turn import run_turn
    chat = ScriptedChat(reply(call('record_fact', facts=[
        {'field': 'dish', 'op': 'add', 'value': 'cà phê yên', 'quote': 'cà phê yên tĩnh', 'how': 'said'}],
        say='Bạn thích ngồi trong nhà hay ngoài trời?')), say('Bạn thích ngồi trong nhà hay ngoài trời?'))
    engine = make_assistant(chat)
    engine.catalog = menu
    session = run_turn(engine, SEED)
    assert not session.state.wishes.dishes
    assert not any(t.get('kind') == 'block' and t['block']['kind'] == 'dish' for t in session.transcript)


def test_skip_remains_model_free_and_one_short_sentence(catalog, cfg):
    chat = ScriptedChat()
    engine = Engine(catalog, cfg, SessionStore(None), chat, today=lambda: date(2026, 11, 4))
    sid = engine.create('first', 'nothing')['id']
    session = engine.store.get(sid)
    session.card = deck.build(session.state, catalog, cfg, ask='trip')
    events = []
    engine.turn(sid, TurnInput(kind='deck', answers={'trip': ['skip']}), lambda *e: events.append(e))
    reply = next(payload['replace'] for kind, payload in events if kind == 'say')
    assert reply == 'Mình bỏ qua ý này nhé.'
    assert chat.calls == 0
    assert 'trip' in session.state.meta.declined
    assert session.card.qid == 'conversation'
