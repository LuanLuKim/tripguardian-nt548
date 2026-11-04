"""Exact second-round production regressions; model and live reads stay mocked."""
from datetime import date

import pytest
from trip_fixtures import ScriptedChat, say, served

from trip import TripState, compile_search_input
from trip.agent.tools import TurnTools, lookups
from trip.api.engine import Engine, TurnInput
from trip.domain.guard import record_fact
from trip.infrastructure.catalog import Catalog
from trip.infrastructure.sessions import SessionStore
from test_trip_r7 import understand

SEED = ('Đi Đà Lạt chục lần rồi, khỏi giới thiệu mấy chỗ nổi tiếng. Tôi 38 tuổi, đi với vợ ngày '
        '10-11/11/2026, tự chạy xe máy. Ở homestay quen dốc Nhà Làng, sáng 8h đi tối 20h về đó. '
        'Bỏ Hồ Xuân Hương, chợ đêm, Thung lũng Tình Yêu và điểm check-in đông. '
        'Hồ Tuyền Lâm từng đi và vẫn thích. Muốn ăn sáng địa phương, cà phê vắng nhìn rừng thông, '
        'chạy cung Tà Nung hoặc Cầu Đất, lẩu gà lá é, bánh căn Nhà Chung. '
        'Ngân sách 2 triệu hai người không gồm chỗ ở. Không có lưu ý sức khỏe.')
MULTI = 'Đà Lạt tháng này lạnh không? Ăn gì rẻ mà ngon? Đi lại bằng gì nếu không chạy xe máy?'
CLOSED = 'Tao Ngộ đóng cửa rồi mà. Đừng gợi ý hay xếp quán đó nữa.'
CORRECTION = ('Không có lưu ý gì. Đi vừa phải, 3 nơi mỗi ngày thôi. Ngày 10 và 11 tháng 11, '
              'cả hai ngày đi từ 8h đến 20h. Đã ở dốc Nhà Làng từ hôm trước. '
              'Tìm đúng quán bánh căn Nhà Chung được không?')


@pytest.fixture
def e(catalog, cfg, tmp_path):
    return Engine(catalog, cfg, SessionStore(tmp_path), ScriptedChat(), today=lambda: date(2026, 11, 4))


@pytest.fixture
def places():
    names = ['Lẩu Gà Lá É Tao Ngộ', 'Lẩu Gà Lá É Tao Ngộ 5', 'Hồ Xuân Hương',
             'Công viên Hồ Xuân Hương', 'Hồ Tuyền Lâm']
    return Catalog.from_records([], 1, evidence={str(i): served(str(i), n) for i, n in enumerate(names)})


def tools(catalog, text, state=None):
    return TurnTools(state or TripState(), text, 1, catalog, date(2026, 11, 4))


@pytest.mark.parametrize('name,quote,expected', [
    ('Tao Ngộ', CLOSED, {'0', '1'}),
    ('Hồ Xuân Hương', SEED, {'2', '3'}),
])
def test_exclusion_is_real_data_and_roundtrips(places, name, quote, expected):
    turn = tools(places, quote)
    out = turn.run('record_fact', {'field': 'excluded_place', 'op': 'add', 'value': name, 'quote': quote, 'how': 'said'})
    assert 'error' not in out
    restored = TripState.model_validate_json(turn.state.model_dump_json())
    assert {p.place_id for p in compile_search_input(restored).excluded_places} == expected
    assert all(p.source == 'user' and p.evidence[0].quote == quote for p in restored.excluded_places)


def test_visited_is_not_excluded_and_unknown_cannot_be_promised(places):
    turn = tools(places, 'Hồ Tuyền Lâm từng đi và vẫn thích')
    out = turn.run('record_fact', {'field': 'excluded_place', 'op': 'add', 'value': 'Hồ Tuyền Lâm',
                                 'quote': turn.text, 'how': 'said'})
    assert 'error' in out
    missing = tools(places, 'Bỏ Mây Lang Thang 2')
    out = missing.run('record_fact', {'field': 'excluded_place', 'op': 'add', 'value': 'Mây Lang Thang 2',
                                    'quote': missing.text, 'how': 'said'})
    assert out.get('recorded') is False
    assert 'chưa áp dụng' in missing.finalize_reply('Mình sẽ không gợi ý hay xếp Mây Lang Thang 2 nữa.').lower()
    assert 'sẽ không' not in missing.finalize_reply('Mình sẽ không gợi ý hay xếp Mây Lang Thang 2 nữa.').lower()


def test_model_cannot_shift_an_explicit_two_day_range(places):
    turn = tools(places, 'Ngày 10 và 11 tháng 11')
    out = turn.run('record_fact', {'field': 'start_date', 'op': 'set', 'value': '2026-11-11',
                                 'quote': turn.text, 'how': 'said'})
    assert 'error' in out
    assert not turn.state.start_date.known


def test_two_named_days_keep_the_first_day(e):
    st = understand(e, TripState(), 'Đi ngày 10-11/11/2026')
    st = understand(e, st, 'Ngày 10 và 11 tháng 11', turn=2)
    assert (st.start_date.value, st.days.value) == (date(2026, 11, 10), 2)


@pytest.fixture
def food_catalog():
    r = served('food', 'Quán Bánh Căn', {}, group='restaurant', category='Quán ăn')
    r['menu'] = {'dishes': [{'name': x} for x in ('Bánh căn', 'Cà phê săn mây', 'Cà phê rang',
                                                'Combo bánh mì cả hai', 'Cocktail gợi ý hôm nay')]}
    city = served('city', 'Đà Lạt', {}, group='stay', category='Lưu trú nhà dân')
    return Catalog.from_records([], 1, evidence={'food': r, 'city': city})


@pytest.mark.parametrize('text', [CLOSED, 'cả hai ngày đều đi nhẹ nhàng', 'Cà phê, dạo hồ', 'cà phê sân vườn'])
def test_lookup_never_uses_partial_menu_tokens_as_food(food_catalog, text):
    assert lookups(text, food_catalog)['dishes'] == []


def test_food_span_stops_at_conjunction_and_city_is_not_a_kind(food_catalog):
    out = lookups('Còn câu đi lại thì sao? Hai đứa không chạy xe máy, đi taxi nhé. '
                  'Chọn giúp quán bánh căn và cà phê đẹp, giá sinh viên.', food_catalog)
    assert [x['dish'] for x in out['dishes']] == ['bánh căn']
    assert lookups(MULTI, food_catalog)['kinds'] == []


@pytest.mark.parametrize('phrase', ['gợi ý', 'cả hai', 'ca phe san', 'ca phe dao', 'bánh căn và'])
def test_model_cannot_write_invalid_food_span(food_catalog, phrase):
    turn = tools(food_catalog, phrase)
    out = turn.run('record_fact', {'field': 'dish', 'op': 'add', 'value': phrase, 'quote': phrase, 'how': 'said'})
    assert 'error' in out
    assert turn.state.wishes.dishes == ()


@pytest.mark.parametrize('text', ['Không có lưu ý sức khỏe', 'không có gì cần lưu ý', 'Không có lưu ý gì'])
def test_explicit_no_care_is_complete_without_prior_question(e, text):
    assert understand(e, TripState(), text).care.value == 'none'


def test_venue_avoidance_cannot_answer_care(places):
    st, note = record_fact(TripState(), 'care', 'set', 'listed', 'Không bar hay nhạc', 'said',
                           'Không bar hay nhạc', 1, places)
    assert not st.care.known and note.startswith('refused')


def test_local_daily_hours_survive_compile_and_no_physical_arrival(e):
    st = understand(e, TripState(), SEED)
    si = compile_search_input(st)
    assert [(d.start, d.end) for d in si.context.frame.days] == [('08:00', '20:00')] * 2
    assert not st.frame.arrive.known and not st.frame.leave.known
    assert st.checkin_at.source == st.checkout_at.source == 'user'


def test_cold_preference_readback_is_not_both_liked_and_avoided(places):
    from trip.domain.readback import build
    turn = tools(places, 'sợ lạnh')
    for value in ('heater=present:love', 'cold=present:avoid'):
        assert 'error' not in turn.run('record_fact', {'field': 'soft', 'op': 'add', 'value': value,
                                                     'quote': 'sợ lạnh', 'how': 'said'})
    texts = [l.text for l in build(compile_search_input(turn.state)).lines]
    assert not any('Thích: sợ lạnh' in t for t in texts)
    assert any('Tránh:' in t for t in texts)


def test_multi_question_omission_is_explicit_not_silent(places):
    turn = tools(places, MULTI)
    out = turn.finalize_reply('Khí hậu tháng này chưa rõ. Ăn bánh căn có thể tiết kiệm.')
    assert 'đi lại' in out.lower() and 'chưa' in out.lower()


def test_missing_named_dish_answer_is_preserved_and_return_hour_is_not_nightlife(food_catalog):
    turn = tools(food_catalog, SEED)
    out = turn.finalize_reply('Mình hiểu. Bạn thích buổi tối sôi động hay yên tĩnh vì về đêm?')
    assert 'Nhà Chung' in out and 'không thấy' in out
    assert 'sôi động' not in out


def test_exact_anaphoric_exclusion_and_explicit_daily_range(e, places):
    turn = tools(places, CLOSED)
    out = turn.run('record_fact', {'field': 'excluded_place', 'op': 'add', 'value': 'Tao Ngộ',
                                 'quote': CLOSED, 'how': 'said'})
    assert 'error' not in out
    st = understand(e, TripState(), SEED)
    st = understand(e, st, CORRECTION, turn=2)
    assert [(d.start, d.end) for d in compile_search_input(st).context.frame.days] == [('08:00', '20:00')] * 2


def test_named_tail_stops_at_sentence_and_daily_range_works_alone(e, food_catalog):
    found = lookups(SEED, food_catalog)
    assert found['dishes'][0]['also_named'] == 'Nhà Chung'
    st = understand(e, TripState(), CORRECTION)
    assert [(d.start, d.end) for d in compile_search_input(st).context.frame.days] == [('08:00', '20:00')] * 2


@pytest.mark.parametrize('tool,args', [('find_dishes', {'dish': 'ca phe san'}),
                                      ('find_places', {'criteria': {'dish': 'ca phe san'}})])
def test_wider_model_tools_share_food_validation(turn_tools, tool, args):
    turn = turn_tools(text='ca phe san')
    assert 'error' in turn.run(tool, args)


def test_city_only_name_is_not_a_place_candidate(food_catalog):
    from trip.agent.prefetch import candidates
    assert not candidates(MULTI, food_catalog)


def test_exclusion_changes_plan_confirmation_digest(places):
    from trip.domain.readback import plan_digest
    turn = tools(places, CLOSED)
    before = plan_digest(compile_search_input(turn.state))
    turn.run('record_fact', {'field': 'excluded_place', 'op': 'add', 'value': 'Tao Ngộ',
                            'quote': CLOSED, 'how': 'said'})
    assert plan_digest(compile_search_input(turn.state)) != before


def test_public_snapshot_restore_keeps_exclusions(places, cfg, tmp_path):
    from trip.api.tools import Tools
    turn = tools(places, CLOSED)
    turn.run('record_fact', {'field': 'excluded_place', 'op': 'add', 'value': 'Tao Ngộ',
                           'quote': CLOSED, 'how': 'said'})
    engine = Engine(places, cfg, SessionStore(None), ScriptedChat())
    sid = engine.create('first', 'nothing')['id']
    session = engine.store.get(sid)
    session.state = turn.state
    engine.store.save(session)
    api = Tools(engine)
    snapshot = api.snapshot(sid)
    api.restore(snapshot)
    assert {p.place_id for p in compile_search_input(engine.store.get(sid).state).excluded_places} == {'0', '1'}


def test_old_exclusion_cannot_back_a_new_unsaved_promise(places):
    first = tools(places, 'Bỏ Hồ Xuân Hương')
    first.run('record_fact', {'field': 'excluded_place', 'op': 'add', 'value': 'Hồ Xuân Hương',
                              'quote': first.text, 'how': 'said'})
    turn = tools(places, CLOSED, first.state)
    assert 'chưa áp dụng' in turn.finalize_reply('Mình sẽ không gợi ý hay xếp Tao Ngộ nữa.').lower()


def test_paired_daily_hours_do_not_need_repeated_lodging(e):
    st = understand(e, TripState(), 'Đi 2 ngày 10-11/11/2026, sáng 8h đi, 20h về.')
    assert [(d.start, d.end) for d in compile_search_input(st).context.frame.days] == [('08:00', '20:00')] * 2


def test_model_promise_without_exclusion_write_is_not_shown(places):
    turn = tools(places, CLOSED)
    out = turn.finalize_reply('Mình sẽ không gợi ý hay xếp Tao Ngộ nữa.')
    assert 'chưa áp dụng' in out.lower() and 'sẽ không' not in out.lower()


def test_mock_model_partial_answer_and_name_omission_reach_final_reply(make_assistant, food_catalog):
    from trip_fixtures import call, reply
    from test_assistant_turn import last_say, run_turn
    partial = make_assistant(ScriptedChat(say('Khí hậu tháng này chưa rõ. Ăn bánh căn có thể tiết kiệm.')))
    session = run_turn(partial, MULTI)
    assert 'đi lại' in last_say(session).lower()
    omitted = make_assistant(ScriptedChat(say('Mình hiểu. Bạn thích buổi tối sôi động hay yên tĩnh vì về đêm?')))
    omitted.catalog = food_catalog
    session = run_turn(omitted, SEED)
    assert 'Nhà Chung' in last_say(session) and 'không thấy' in last_say(session)
    assert 'sôi động' not in last_say(session)


def test_mock_model_writes_exclusions_and_cannot_write_bad_dish(make_assistant, places):
    from trip_fixtures import call, reply
    from test_assistant_turn import run_turn
    chat = ScriptedChat(reply(call('record_fact', facts=[
        {'field': 'excluded_place', 'op': 'add', 'value': 'Tao Ngộ', 'quote': CLOSED, 'how': 'said'}],
        say='Mình sẽ không gợi ý hay xếp Tao Ngộ nữa.')))
    engine = make_assistant(chat)
    engine.catalog = places
    session = run_turn(engine, CLOSED)
    assert {p.place_id for p in session.state.excluded_places} == {'0', '1'}


def test_prompt_exposes_each_question_and_time_semantics(places):
    import json
    from trip.agent.prompt import build_messages
    messages = build_messages(TripState(), MULTI, [], None, date(2026, 11, 4), [])
    context = json.loads(messages[-2]['content'].split('\n', 1)[-1])
    assert len(context['answer_obligations']) == 3
    assert 'return time' in messages[0]['content']
