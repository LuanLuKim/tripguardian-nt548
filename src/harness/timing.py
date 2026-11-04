"""Request-local timings shared by dispatch and the HTTP response."""

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
import time
import uuid


@dataclass
class Trace:
    request_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    spans: dict[str, float] = field(default_factory=dict)


_current: ContextVar[Trace | None] = ContextVar('harness_request_trace', default=None)


def current() -> Trace | None:
    return _current.get()


@contextmanager
def request_trace():
    trace = Trace()
    token = _current.set(trace)
    try:
        yield trace
    finally:
        _current.reset(token)


@contextmanager
def span(name: str, spans: dict | None = None):
    trace = current()
    target = spans if spans is not None else trace.spans if trace else None
    started = time.monotonic() if target is not None else 0
    try:
        yield
    finally:
        if target is not None:
            target[name] = target.get(name, 0) + (time.monotonic() - started) * 1000
