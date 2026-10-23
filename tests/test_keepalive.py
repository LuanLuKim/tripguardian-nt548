"""Public availability checks must not mistake an edge error for a healthy app."""
import importlib.util
import json
import subprocess
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "keepalive.py"


def load_probe():
    assert SCRIPT.exists(), "The production keepalive script is missing"
    spec = importlib.util.spec_from_file_location("keepalive", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("status,body,healthy", [
    (401, '{"error":"sign in first"}', True),
    (401, '<html>Access denied</html>', False),
    (502, '{"error":"journey server unavailable"}', False),
    (200, '{"error":"sign in first"}', False),
])
def test_backend_requires_expected_anonymous_response(monkeypatch, status, body, healthy):
    probe = load_probe()
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, f"{body}\n{status}\n0.123", "")

    monkeypatch.setattr(probe.subprocess, "run", run)
    result = probe.check("https://example.com", "/api/harness/me")
    assert result["ok"] is healthy
    assert calls[0][-1].startswith("https://example.com/api/harness/me?tg_keepalive=")
    assert "--max-time" in calls[0]
    assert not any("cookie" in arg.lower() for arg in calls[0])


def test_network_failure_is_logged_without_response_contents(monkeypatch):
    probe = load_probe()
    monkeypatch.setattr(probe.subprocess, "run", lambda *a, **kw:
                        subprocess.CompletedProcess(a[0], 28, "", "private upstream detail"))
    result = probe.check("https://example.com", "/app")
    assert result["ok"] is False
    assert result["curl_exit"] == 28
    assert "private upstream detail" not in json.dumps(result)


@pytest.mark.parametrize("status,body,healthy", [
    (200, '<!doctype html><div id="root"></div>', True),
    (200, '<html>Cloudflare challenge</html>', False),
    (302, '', False),
])
def test_frontend_requires_app_shell(monkeypatch, status, body, healthy):
    probe = load_probe()
    monkeypatch.setattr(probe.subprocess, "run", lambda *a, **kw:
                        subprocess.CompletedProcess(a[0], 0, f"{body}\n{status}\n0.1", ""))
    assert probe.check("https://example.com", "/app")["ok"] is healthy


def test_curl_process_timeout_is_unhealthy(monkeypatch):
    probe = load_probe()

    def timed_out(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], 20)

    monkeypatch.setattr(probe.subprocess, "run", timed_out)
    assert probe.check("https://example.com", "/app")["ok"] is False


def test_probe_uses_machine_readable_numbers_under_vietnamese_cron_locale(monkeypatch):
    probe = load_probe()
    monkeypatch.setenv("LC_NUMERIC", "vi_VN")

    def run(command, **kwargs):
        elapsed = "0.123" if kwargs.get("env", {}).get("LC_ALL") == "C" else "0,123"
        return subprocess.CompletedProcess(command, 0, '{"error":"sign in first"}\n401\n' + elapsed, "")

    monkeypatch.setattr(probe.subprocess, "run", run)
    result = probe.check("https://example.com", "/api/harness/me")
    assert result["ok"] is True
    assert result["seconds"] == 0.123
