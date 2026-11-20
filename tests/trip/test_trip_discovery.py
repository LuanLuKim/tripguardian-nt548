"""Discovery chat leaves logistics to the gate and explores only real, safe photos."""
from datetime import date

import pytest
from dataclasses import replace
from trip.infrastructure.settings import load

from trip import TripState
from trip.agent.prompt import build_messages
from trip.agent.tools import TurnTools
from trip.api.engine import Engine, TurnInput
from trip.domain import drill
from trip.infrastructure.sessions import SessionStore
from trip_fixtures import ScriptedChat, say
from test_redesign_drill import FakeLooks, big, ids


@pytest.fixture
def cfg():
    return replace(load(), discovery=True, n_min=1, assistant=replace(load().assistant, enabled=False))


def test_chat_context_does_not_assign_missing_logistics(catalog):
    messages = build_messages(TripState(), 'đi Đà Lạt', [], None, date(2026, 11, 4), [], still_needed={'care': 'x'}, discovery=True)
    context = messages[-2]['content']
    assert '"still_needed"' not in context


def test_chat_required_tool_is_not_offered(catalog):
    tools = TurnTools(TripState(), 'đi Đà Lạt', 1, catalog, date(2026, 11, 4), discovery=True)
    assert 'ask_required' not in tools.tool_names()
    assert 'error' in tools.run('ask_required', {'topic': 'care', 'question': 'Lưu ý gì?'})


def discovery_looks(cfg):
    return FakeLooks({v['cues'][0]: [(p, .5) for p in ids(1, 61)]
                      for spec in cfg.drills.values() for v in spec['variants']})


def test_no_taste_opens_real_photos_not_required_question(big, cfg, tmp_path):
    engine = Engine(big, cfg, SessionStore(tmp_path), ScriptedChat(say('Mình thử vài góc nhìn nhé.')),
                    looks=discovery_looks(cfg))
    sid = engine.create('first', 'nothing')['id']
    engine.turn(sid, TurnInput(kind='text', text='đi Đà Lạt'), lambda *_: None)
    tab = engine.load(sid)['card']['tabs'][0]
    assert tab['kind'] == 'drill'
    assert all(o.get('photo') for o in tab['options'] if o['id'] not in ('other', 'skip'))


def test_proactive_cards_never_repeat_topics_or_representative_photos(big, cfg):
    looks = discovery_looks(cfg)
    state = drill.discover(TripState(), big, looks, cfg, 1)
    first = next(d for d in state.drills if d.tab)
    state = drill.finish(state, first.topic, 'done')
    state = drill.discover(state, big, looks, cfg, 2)
    second = next(d for d in state.drills if d.status == 'pending' and d.tab)
    assert first.topic != second.topic
    assert not ({o.photo for o in first.tab.options if o.photo} & {o.photo for o in second.tab.options if o.photo})


def test_create_dialog_specific_subtag_is_not_asked_again():
    assert drill.topics('cà phê sân vườn yên tĩnh', discovery=True) == []


def test_multiple_heard_topics_do_not_share_photos(big, cfg):
    state = drill.note(TripState(), 'săn mây, ngắm đồi', 1, discovery=True)
    state = drill.build(state, big, discovery_looks(cfg), cfg)
    photos = [o.photo for d in state.drills if d.tab for o in d.tab.options if o.photo]
    assert len([d for d in state.drills if d.tab]) == 2
    assert len(photos) == len(set(photos))


def test_known_create_subtag_closes_prebuilt_broad_topics(big, cfg):
    from trip.domain.state import Evidence, Update, apply
    text = 'Quán cà phê săn mây'
    heard = drill.note(TripState(), text, 1, discovery=True)
    built = drill.build(heard, big, discovery_looks(cfg), cfg)
    known = apply(heard, Update(field='soft', op='add', value=('cloud_hunting=present', 'love'),
                               source='user', confidence='high', evidence=Evidence(turn=1, quote=text)))
    state = drill.discover(drill.adopt(known, built), big, discovery_looks(cfg), cfg, 1)
    assert not any(d.status == 'pending' and d.topic in ('cà phê', 'săn mây') for d in state.drills)
    assert any(d.status == 'pending' and d.tab for d in state.drills)


def test_broad_multi_topic_taste_still_offers_refinement(big, cfg):
    from trip.domain.state import Evidence, Update, apply
    text = 'săn mây, ngắm đồi'
    state = drill.note(TripState(), text, 1, discovery=True)
    state = apply(state, Update(field='soft', op='add', value=('cloud_hunting=present', 'love'),
                                source='user', confidence='high', evidence=Evidence(turn=1, quote=text)))
    state = drill.discover(state, big, discovery_looks(cfg), cfg, 1)
    assert {d.topic for d in state.drills if d.status == 'pending' and d.tab} == {'săn mây', 'ngắm đồi'}


def test_discovery_fail_closed_on_new_health_constraint(big, cfg):
    state = TripState.model_validate({'hard': [{'feature': 'long_walk', 'op': 'ne', 'value': 'present',
                                              'evidence': [{'turn': 1, 'quote': 'đau gối'}]}]})
    state = drill.discover(state, big, discovery_looks(cfg), cfg, 1)
    assert not any(d.tab for d in state.drills)


def test_prebuilt_photos_are_rechecked_after_new_health_fact(big, cfg):
    built = drill.discover(TripState(), big, discovery_looks(cfg), cfg, 1)
    assert any(d.tab for d in built.drills)
    limited = TripState.model_validate({'hard': [{'feature': 'long_walk', 'op': 'ne', 'value': 'present',
                                                'evidence': [{'turn': 1, 'quote': 'đau gối'}]}]})
    state = drill.refresh(drill.adopt(limited, built), big, cfg)
    assert not any(d.status == 'pending' and d.tab for d in state.drills)


def test_pick_learns_soft_and_opens_another_unseen_aspect(big, cfg, tmp_path):
    chat = ScriptedChat(say('Thử xem kiểu nào hợp nhé.'), say('Có vẻ bạn thích nhìn ra thiên nhiên.'))
    engine = Engine(big, cfg, SessionStore(tmp_path), chat, looks=discovery_looks(cfg))
    sid = engine.create('first', 'nothing')['id']
    engine.turn(sid, TurnInput(kind='text', text='đi Đà Lạt'), lambda *_: None)
    first = engine.load(sid)['card']['tabs'][0]
    option = next(o for o in first['options'] if o.get('photo'))
    engine.turn(sid, TurnInput(kind='deck', answers={first['qid']: [option['id']]}), lambda *_: None)
    second = engine.load(sid)['card']['tabs'][0]
    assert second['kind'] == 'drill' and second['qid'] != first['qid']
    assert any(f.known and f.source == 'user' for f in engine.store.get(sid).state.soft.values())
    reply = next(t['text'] for t in reversed(engine.load(sid)['transcript']) if t['role'] == 'agent' and t['text'])
    assert reply == 'Có vẻ bạn thích nhìn ra thiên nhiên.'
    assert all(t['kind'] != 'required' for t in engine.load(sid)['card']['tabs'])


def test_removing_learned_soft_removes_its_photo_ranking(big, cfg, tmp_path):
    chat = ScriptedChat(say('Thử xem kiểu nào hợp nhé.'), say('Có vẻ bạn thích góc này.'))
    engine = Engine(big, cfg, SessionStore(tmp_path), chat, looks=discovery_looks(cfg))
    sid = engine.create('first', 'nothing')['id']
    engine.turn(sid, TurnInput(kind='text', text='đi Đà Lạt'), lambda *_: None)
    tab = engine.load(sid)['card']['tabs'][0]
    option = next(o for o in tab['options'] if o.get('photo'))
    engine.turn(sid, TurnInput(kind='deck', answers={tab['qid']: [option['id']]}), lambda *_: None)
    for key in tuple(engine.store.get(sid).state.soft):
        engine.turn(sid, TurnInput(kind='edit', target=f'soft:{key}', value=None), lambda *_: None)
    assert not engine.store.get(sid).state.soft
    assert not engine.store.get(sid).state.vibes


def test_removing_drill_soft_preserves_other_photo_tastes(big, cfg, tmp_path):
    from trip.domain.state import Evidence, Update, Vibe, apply
    engine = Engine(big, cfg, SessionStore(tmp_path), ScriptedChat())
    sid = engine.create('first', 'nothing')['id']
    session = engine.store.get(sid)
    state = apply(session.state, Update(field='soft', op='add', value=('scenic_view=present', 'love'),
                                       source='user', confidence='high',
                                       evidence=Evidence(turn=2, tool='deck:drill.chill')))
    other = Vibe(phrase='ảnh mình gửi', turn=1, status='done', places=tuple(ids(1, 3)), image=True)
    session.state = state.model_copy(update={'vibes': (other, Vibe(phrase='chill', turn=2, status='done', places=tuple(ids(3, 5))))})
    engine.turn(sid, TurnInput(kind='edit', target='soft:scenic_view=present', value=None), lambda *_: None)
    assert engine.store.get(sid).state.vibes == (other,)


def test_skip_stops_without_repeating_or_logistics(big, cfg, tmp_path):
    chat = ScriptedChat(say('Thử xem kiểu nào hợp nhé.'))
    engine = Engine(big, cfg, SessionStore(tmp_path), chat, looks=discovery_looks(cfg))
    sid = engine.create('first', 'nothing')['id']
    engine.turn(sid, TurnInput(kind='text', text='đi Đà Lạt'), lambda *_: None)
    tab = engine.load(sid)['card']['tabs'][0]
    calls = chat.calls
    engine.turn(sid, TurnInput(kind='deck', answers={tab['qid']: ['skip']}), lambda *_: None)
    assert engine.load(sid)['card']['qid'] == 'conversation'
    assert chat.calls == calls
    assert next(d for d in engine.store.get(sid).state.drills if tab['qid'] == f'drill.{d.topic}').status == 'skipped'


def test_the_next_photo_card_pairs_with_the_topic_just_chosen(big, cfg):
    looks = discovery_looks(cfg)
    state = drill.build(drill.note(TripState(), 'nhiều quán cà phê đẹp', 1, discovery=True), big, looks, cfg)
    state = drill.discover(drill.finish(state, 'cà phê', 'done'), big, looks, cfg, 2)
    upcoming = next(d for d in state.drills if d.status == 'pending' and d.tab)
    assert upcoming.topic == drill.AFTER['cà phê'][0]  # the hills after a cafe, not the fixed first food card
    assert upcoming.tab.question == ''  # no stock question: the agent words the card


def test_a_photo_pick_reaches_the_agent_with_what_was_kept_and_the_card_its_reply_leads_into(big, cfg, tmp_path):
    chat = ScriptedChat(say('Đà Lạt nhiều kiểu quán lắm, xem thử vài kiểu nhé.'), say('Ngồi vườn sáng sớm còn sương.'))
    engine = Engine(big, cfg, SessionStore(tmp_path), chat, looks=discovery_looks(cfg))
    sid = engine.create('first', 'nothing')['id']
    engine.turn(sid, TurnInput(kind='text', text='Mình muốn sống chậm, nhiều quán cà phê đẹp'), lambda *_: None)
    context = lambda call: '\n'.join(m['content'] for m in chat.seen[call][0] if m['role'] == 'user')  # noqa: E731
    assert '"next_card"' in context(0) and '"about": "cà phê"' in context(0)  # the first reply knows the card under it
    tab = engine.load(sid)['card']['tabs'][0]
    options = [o for o in tab['options'] if o.get('photo')]
    engine.turn(sid, TurnInput(kind='deck', answers={tab['qid']: [options[0]['id']]}), lambda *_: None)
    picked = context(-1)
    assert '"chosen"' in picked and options[0]['label'] in picked
    assert '"not_chosen_this_time"' in picked and options[1]['label'] in picked
    assert f'"about": "{drill.AFTER["cà phê"][0]}"' in picked  # and the next card it leads into
    assert engine.load(sid)['card']['tabs'][0]['qid'] == f'drill.{drill.AFTER["cà phê"][0]}'


def test_an_offer_of_the_next_card_keeps_its_question_and_the_card_waits_under_it_in_one_call(big, cfg, tmp_path):
    chat = ScriptedChat(say('Đà Lạt nhiều kiểu quán lắm. Bạn muốn xem thử vài kiểu không?'))
    engine = Engine(big, cfg, SessionStore(tmp_path), chat, looks=discovery_looks(cfg))
    sid = engine.create('first', 'nothing')['id']
    engine.turn(sid, TurnInput(kind='text', text='Mình muốn sống chậm, nhiều quán cà phê đẹp'), lambda *_: None)
    reply = next(t['text'] for t in reversed(engine.load(sid)['transcript']) if t['role'] == 'agent' and t['text'])
    tab = engine.load(sid)['card']['tabs'][0]
    assert chat.calls == 1 and reply.endswith('xem thử vài kiểu không?')  # the offer is not dropped for the photos
    assert tab['kind'] == 'drill' and tab['question'] == ''  # the card waits under it; no stock or borrowed heading
