import pytest

from test_dispatch import decision, make, run


def test_metadata_read_returns_committed_context_without_restoring_modules():
    h, tools = make()
    v = run(h, decision(h), 'advance', 'plan')
    before = h.store.state(v['id'])
    h._loaded.clear()
    for tool in tools.values():
        tool.restore = lambda snapshot: pytest.fail('metadata must not restore corpus modules')
        tool.load = lambda sid: pytest.fail('metadata must not render a module view')
    state = h.state(v['id'])
    assert state['revision'] == before.revision
    assert state['outputs'] == before.outputs
    assert state['sessions'] == before.sessions
    assert state['result'] == {}


def test_metadata_read_checks_owner():
    h, _ = make()
    v = h.create(owner='a' * 32)
    with pytest.raises(KeyError):
        h.state(v['id'], owner='b' * 32)
