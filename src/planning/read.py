"""Capture an isolated in-process read engine, including non-persisted capability identity."""

import copy
import threading

from .engine import Engine
from .session import Store


def fork_readonly(engine: Engine, sid: str) -> Engine:
    """Capture under the module lock; render outside journey/writer locks on the returned private engine.

    Records/config/callbacks are shared read dependencies. Session, base, schedules and capability caches are
    owned by the fork. Mutating the fork never commits to the writer; newly minted preview tokens belong only
    to the fork and must not be sent to writer actions. Callers recheck the journey revision before publishing.
    """
    with engine.store.lock(sid):
        session = engine._get(sid)
        base = engine._ensure_base(sid)
        # As on load(), a cold writer must own a real suggestion job before a snapshot can report pending.
        engine._queue_suggestions(session)
        reader = copy.copy(engine)
        # Trip.by_id spans the entire corpus, not just this journey. Never copy immutable serving data.
        shared = [engine.records, engine.by_id, base.trip.by_id, engine.cfg, base.trip.cfg, engine.live_cfg]
        memo = {id(value): value for value in shared}
        memo.update((id(record), record) for record in engine.records)
        # Preserve aliases between base artifacts and edited schedules within the isolated runtime.
        session, base, schedules, tokens = copy.deepcopy((
            session, base, engine._schedules.get(sid), engine._preview_tokens.get(sid)), memo)
        reader.store = Store(None)
        reader.store.restore(session)
        reader._base = {sid: base}
        reader._schedules = {sid: schedules} if schedules is not None else {}
        reader._epochs = {sid: engine._epochs.get(sid, 0)}
        reader._preview_tokens = {sid: tokens} if tokens is not None else {}
        reader._previews, reader._lodging_options = {}, {}
        reader._previews_lock = threading.Lock()
        reader._suggestion_slots = threading.BoundedSemaphore(max(1, engine.cfg.suggestion_workers))
        reader.turn_log, reader.timings = {}, {}
        reader._readonly = True
        return reader
