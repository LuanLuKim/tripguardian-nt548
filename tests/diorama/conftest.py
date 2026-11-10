import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/diorama"))


TEST_CONFIG = {"evidence_min": 8, "pass_ok_ratio": 0.8, "max_rounds": 5, "retry_failed": 2, "agent_timeout_s": 3600,
               "stall_rounds": 2, "parallel": 3, "builder": "agent",
               "effort": {"notes": "low", "review": "low", "build": "medium", "build_large": "high", "fix_function": "medium"}}


@pytest.fixture(autouse=True)
def pinned_config(monkeypatch):
    """Tests pin their thresholds; config/diorama.yaml holds the calibrated production values."""
    import importlib

    for name in ("auto3d", "auto3d.checklist", "auto3d.cli", "auto3d.steps", "auto3d.builder", "auto3d.gate",
                 "auto3d.exam", "auto3d.state"):
        module = importlib.import_module(name)
        if hasattr(module, "config"):
            monkeypatch.setattr(module, "config", lambda: TEST_CONFIG)


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    from auto3d import state, gate, prompts, builder, steps, cli

    for module in (state, gate, prompts, builder, steps, cli):
        monkeypatch.setattr(module, "DATA", tmp_path)
    monkeypatch.setattr(gate, "REPO", tmp_path / "repo")

    def forbidden(*args, **kwargs):
        pytest.fail("No external command, model, bridge or publish call is allowed")

    monkeypatch.setattr(steps, "run", forbidden)
    monkeypatch.setattr(steps, "ask", forbidden)
    monkeypatch.setattr(builder, "ask", forbidden)
    monkeypatch.setattr(builder.subprocess, "run", forbidden)
    return tmp_path
