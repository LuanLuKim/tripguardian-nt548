"""The rollout switch isolates discovery without changing legacy chat contracts."""
from dataclasses import replace
from datetime import date

import pytest

from trip.agent.prompt import build_messages
from trip.api.engine import Engine, TurnInput
from trip.domain.state import TripState
from trip.infrastructure.sessions import SessionStore
from trip_fixtures import ScriptedChat, say


@pytest.mark.parametrize('enabled', [False, True])
def test_rollout_switch_controls_context_tools_and_required_fallback(catalog, cfg, tmp_path, enabled):
    chat = ScriptedChat(say('Mình nghe bạn.'))
    engine = Engine(catalog, replace(cfg, discovery=enabled), SessionStore(tmp_path), chat)
    sid = engine.create('first', 'nothing')['id']
    engine.turn(sid, TurnInput(kind='text', text='đi Đà Lạt'), lambda *_: None)
    messages, tools = chat.seen[0]
    context = next(m['content'] for m in messages if m['content'].startswith('CURRENT CONTEXT'))
    assert ('"still_needed"' in context) is not enabled
    assert ('ask_required' in str(tools)) is not enabled
    assert engine.load(sid)['discovery'] is enabled
    tab = engine.load(sid)['card']
    if enabled:
        assert tab['qid'] == 'conversation'
    else:
        assert tab['tabs'][0]['kind'] == 'required'


@pytest.mark.parametrize('enabled', [False, True])
def test_prompt_rollout_preserves_legacy_interview_only_when_disabled(enabled):
    messages = build_messages(TripState(), 'đi Đà Lạt', [], None, date(2026, 11, 4), [],
                              still_needed={'care': 'Lưu ý'}, discovery=enabled)
    prompt = messages[0]['content']
    assert ('1b. Taste first, then logistics' in prompt) is not enabled
    assert ('Chat helps the user discover their tastes' in prompt) is enabled


def test_disabled_rollout_keeps_agent_written_required_card(catalog, cfg, tmp_path):
    from trip_fixtures import call, reply
    question = 'Bạn đi lại bằng gì cho tiện?'
    chat = ScriptedChat(reply(call('ask_required', topic='mobility', question=question)))
    engine = Engine(catalog, replace(cfg, discovery=False), SessionStore(tmp_path), chat)
    sid = engine.create('first', 'nothing')['id']
    engine.turn(sid, TurnInput(kind='text', text='đi Đà Lạt'), lambda *_: None)
    tab = engine.load(sid)['card']['tabs'][0]
    assert tab['qid'] == 'mobility' and tab['question'] == question
    engine.turn(sid, TurnInput(kind='deck', answers={'mobility': ['motorbike']}), lambda *_: None)
    assert engine.store.get(sid).state.mobility.value == 'motorbike'
    assert chat.calls == 1
