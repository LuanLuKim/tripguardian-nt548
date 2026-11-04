import copy
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from test_dispatch import Tools, decision, make, run


@pytest.mark.parametrize('operation', ['load', 'default', 'read'])
def test_slow_snapshot_read_does_not_block_mutation_or_return_stale_view(operation):
    h, tools = make()
    v = decision(h)
    entered, release = threading.Event(), threading.Event()

    class SlowTools(Tools):
        def load(self, sid):
            value = super().load(sid)
            if not entered.is_set():
                entered.set()
                assert release.wait(5)
            return value

        def read(self, sid, operation, payload):
            return self.load(sid)

    def readers(binding):
        return {stage: SlowTools(stage) for stage in tools}

    h.read_tools_for_binding = readers
    # Without detached readers, the real module call also stalls under the journey lock.
    original = tools['decision'].load
    def slow(sid):
        value = original(sid)
        if not entered.is_set():
            entered.set()
            assert release.wait(5)
        return value
    tools['decision'].load = slow
    tools['decision'].read = lambda sid, op, payload: slow(sid)
    with ThreadPoolExecutor(max_workers=2) as pool:
        read = (pool.submit(h.load, v['id'], None if operation == 'default' else 'decision')
                if operation != 'read' else pool.submit(h.read, v['id'], 'decision', 'search'))
        assert entered.wait(3)
        mutation = pool.submit(run, h, v, 'act', 'concurrent')
        try:
            changed = mutation.result(timeout=1)
        finally:
            release.set()
        result = read.result(timeout=5)
    assert changed['revision'] == v['revision'] + 1
    assert (result['result'] if operation != 'read' else result)['view']['value'] == 1
    assert h.load(v['id'], 'decision')['result']['view']['value'] == 1
    assert tools['decision'].states[v['sessions']['decision']]['value'] == 1


def test_snapshot_reader_restores_only_the_requested_stage():
    h, tools = make()
    v = decision(h)
    restored = []

    class Reader(Tools):
        def restore(self, snapshot):
            restored.append(self.stage)
            return super().restore(snapshot)

    h.read_tools_for_binding = lambda binding: {stage: Reader(stage) for stage in tools}
    assert h.load(v['id'], 'decision')['result']['view']['value'] == 0
    assert restored == ['decision']


def test_snapshot_reader_cannot_change_writer_session():
    h, tools = make()
    v = decision(h)
    before = copy.deepcopy(tools['decision'].states)

    class Reader(Tools):
        def load(self, sid):
            self.states[sid]['value'] = 99
            return super().load(sid)

    h.read_tools_for_binding = lambda binding: {stage: Reader(stage) for stage in tools}
    assert h.load(v['id'], 'decision')['result']['view']['value'] == 99
    assert tools['decision'].states == before


def _stall_first(module, method):
    """Make module.<method> pause on its first call until released; returns (entered, release, calls)."""
    entered, release, calls = threading.Event(), threading.Event(), []
    original = getattr(module, method)

    def stalled(*args):
        value = original(*args)
        calls.append(value)
        if not entered.is_set():
            entered.set()
            assert release.wait(5)
        return value
    setattr(module, method, stalled)
    return entered, release, calls


@pytest.mark.parametrize('operation', ['load', 'default', 'read'])
def test_planning_renders_outside_journey_lock_and_rechecks_revision(operation):
    h, tools = make()
    v = run(h, decision(h), 'advance', 'planning')
    entered, release, _ = _stall_first(tools['planning'], 'load')
    tools['planning'].read = lambda sid, op, payload: tools['planning'].load(sid)
    with ThreadPoolExecutor(max_workers=2) as pool:
        pending = (pool.submit(h.load, v['id'], None if operation == 'default' else 'planning')
                   if operation != 'read' else pool.submit(h.read, v['id'], 'planning', 'variants'))
        assert entered.wait(3)
        mutation = pool.submit(run, h, v, 'act', 'planning-change')
        try:
            changed = mutation.result(timeout=1)
        finally:
            release.set()
        result = pending.result(timeout=5)
    assert changed['revision'] == v['revision']+1
    assert (result['result'] if operation != 'read' else result)['view']['value'] == 1
    assert h.load(v['id'], 'planning')['result']['view']['value'] == 1


def test_planning_preview_tokens_are_always_created_on_the_writer():
    h, tools = make()
    v = run(h, decision(h), 'advance', 'planning')
    h.fork_planning = lambda *args: pytest.fail('preview capability minted in a detached reader')
    assert h.read(v['id'], 'planning', 'preview-act', {'action':'{}'})['operation'] == 'preview-act'


def test_slow_planning_render_does_not_block_back_or_publish_old_stage():
    h, tools = make()
    v = run(h, decision(h), 'advance', 'planning')
    h.read_tools_for_binding = lambda binding: {stage: Tools(stage) for stage in tools}
    entered, release, _ = _stall_first(tools['planning'], 'load')
    with ThreadPoolExecutor(max_workers=2) as pool:
        pending = pool.submit(h.load, v['id'])
        assert entered.wait(3)
        mutation = pool.submit(run, h, v, 'back', 'back-during-render')
        try:
            changed = mutation.result(timeout=1)
        finally:
            release.set()
        result = pending.result(timeout=5)
    assert changed['stage'] == 'decision'
    assert result['stage'] == 'decision'
    assert result['revision'] == changed['revision']


def test_planning_render_of_a_write_that_rolls_back_is_never_published():
    """A failed write mutates the module while a render reads it, then restores it without a new revision: that
    render is thrown away (the runtime token changed) and the committed state is rendered again."""
    h, tools = make()
    v = run(h, decision(h), 'advance', 'planning')
    sid = v['sessions']['planning']
    in_render, mutated = threading.Event(), threading.Event()
    seen = []

    def load(sid_):
        if not seen:
            in_render.set()
            assert mutated.wait(5)
        value = {"id": sid_, "view": copy.deepcopy(tools['planning'].states[sid_])}
        seen.append(value['view']['value'])
        return value

    def failing_apply(sid_, operation, payload, emit):
        tools['planning'].states[sid_]['value'] = 99  # the in-flight state the first render reads
        mutated.set()
        time.sleep(0.2)
        raise ValueError('write failed')

    tools['planning'].load = load
    tools['planning'].apply = failing_apply
    with ThreadPoolExecutor(max_workers=2) as pool:
        pending = pool.submit(h.load, v['id'], 'planning')
        assert in_render.wait(3)
        write = pool.submit(run, h, v, 'act', 'failed-change')
        with pytest.raises(ValueError):
            write.result(timeout=5)
        result = pending.result(timeout=5)
    assert seen == [99, 0]
    assert result['revision'] == v['revision']
    assert result['result']['view']['value'] == 0
    assert tools['planning'].states[sid]['value'] == 0
