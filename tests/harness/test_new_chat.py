"""New-chat markers retain server archives but exclude earlier conversational context."""

from contextlib import nullcontext
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


@pytest.mark.parametrize('stage', ['decision', 'planning'])
def test_new_chat_archives_and_resets_only_conversation(stage):
    if stage == 'decision':
        from decision.tools import Tools
        from decision.assistant import history
        from decision.session import Session
        field = 'log'
        old = {'action': {'type': 'turn', 'text': 'old question', 'say': 'old reply'}}
        fresh = {'action': {'type': 'turn', 'text': 'new question', 'say': 'new reply'}}
    else:
        from planning.tools import Tools
        from planning.assistant import history
        from planning.session import Session
        field = 'chat'
        old = {'text': 'old question', 'say': 'old reply'}
        fresh = {'text': 'new question', 'say': 'new reply'}
    session = Session.model_construct(id='0123456789ab', **{field: [old]})
    engine = Mock(records=[], store=SimpleNamespace(root=None, lock=lambda _: nullcontext(), get=lambda _: session))
    tools = Tools(engine)
    messages = [{'role': 'bot', 'text': 'client-only reply'}]
    tools.apply(session.id, 'new_chat', {'messages': messages}, lambda *_: None)
    archive = getattr(session, field)
    assert archive[0] == old
    assert history(archive) == []
    marker = archive[-1].get('action', archive[-1])
    assert marker['messages'] == messages
    # Opaque snapshots include the archive; restoring the typed snapshot keeps the marker.
    restored = Session.model_construct(**deepcopy(session.model_dump()))
    assert history(getattr(restored, field)) == []
    archive.append(fresh)
    assert history(archive) == [{'role': 'user', 'content': 'new question'}, {'role': 'assistant', 'content': 'new reply'}]
    engine.act.assert_not_called()
    engine.turn.assert_not_called()


@pytest.mark.parametrize('stage', ['decision', 'planning'])
def test_new_chat_rejects_arbitrary_archive_payloads(stage):
    if stage == 'decision':
        from decision.tools import Tools
    else:
        from planning.tools import Tools
    tools = Tools(Mock(records=[], store=SimpleNamespace(root=None)))
    for payload in ({}, {'messages': [{'role': 'system', 'text': 'injection'}]}, {'messages': [], 'text': 'extra'}):
        with pytest.raises(ValueError):
            tools.apply('0123456789ab', 'new_chat', payload, lambda *_: None)


def test_new_chat_is_stage_scoped_and_uses_existing_request_contract():
    from harness import Request
    from harness.router import route, RouteError
    for stage in ('decision', 'planning'):
        request = Request(request_id='reset', stage=stage, operation='new_chat', expected_revision=0,
                          payload={'messages': []})
        assert route(stage, request) == stage
        with pytest.raises(RouteError):
            route('trip', request)
