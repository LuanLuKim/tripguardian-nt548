"""Request-local read diagnostics, never part of retrieval results."""
from contextlib import contextmanager
from contextvars import ContextVar
from time import monotonic
from typing import Callable, Iterator

_SINK: ContextVar[Callable[[str], None] | None] = ContextVar('retrieval_trace', default=None)


@contextmanager
def trace_reads(sink: Callable[[str], None]) -> Iterator[None]:
    """Collect nested read spans on the calling thread/task through the public API."""
    token = _SINK.set(sink)
    try:
        yield
    finally:
        _SINK.reset(token)


@contextmanager
def read_span(stage: str, **labels) -> Iterator[None]:
    started = monotonic()
    try:
        yield
    finally:
        sink = _SINK.get()
        if sink is not None:
            extra = ''.join(f' {key}={value}' for key, value in labels.items())
            sink(f't_read stage={stage} seconds={monotonic() - started:.6f}{extra}')
