"""Two threads that need the same encoder at once load it once (Trip looks + the assistant's find at start)."""

import sys
import threading
import time
import types

import pytest

from corpus.index.embedder import Embedder

pytest.importorskip("torch")  # the loaders reach torch (dtype, no_grad) even with a fake transformers


def test_two_threads_load_the_text_model_once(monkeypatch):
    loads = []

    class Model:
        @classmethod
        def from_pretrained(cls, *a, **k):
            loads.append(a)
            time.sleep(0.2)  # a slow load: the second thread arrives while the first is still loading
            return cls()

        def to(self, device):
            return self

        def eval(self):
            return self

    fake = types.SimpleNamespace(AutoModel=Model, AutoTokenizer=types.SimpleNamespace(from_pretrained=lambda *a, **k: "tok"),
                                 AutoProcessor=types.SimpleNamespace(from_pretrained=lambda *a, **k: "proc"))
    monkeypatch.setitem(sys.modules, "transformers", fake)
    e = Embedder(device="cpu", cfg={"embedder": {"image_model": "img", "text_model": "txt", "online_device": "cpu"}})
    for name in ("_bge", "_siglip"):
        loads.clear()
        got = []
        threads = [threading.Thread(target=lambda: got.append(getattr(e, name))) for _ in range(3)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        assert len(loads) == 1 and len({id(g) for g in got}) == 1
