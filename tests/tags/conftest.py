"""Exercise pending membership in isolation; rollout tests explicitly select both modes."""
import copy

import pytest

from corpus.tags import vocab


@pytest.fixture(autouse=True)
def pending_membership(monkeypatch, request):
    if request.node.path.name == "test_rollout_v2.py":
        return
    cfg = copy.deepcopy(vocab.raw_config())
    cfg["membership"]["enabled"] = True
    # Single-reader unit fixtures exercise the builder in isolation; rollout tests inspect shipped policy.
    cfg["membership"]["reader"] = "primary"
    monkeypatch.setattr(vocab, "raw_config", lambda: cfg)
