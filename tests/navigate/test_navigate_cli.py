import sys

import pytest

from corpus import __main__ as cli
from corpus import navigate


def test_cli_plan_passes_city_and_no_latest(monkeypatch):
    calls = []

    async def fake_plan(city, *, latest=True, **kw):
        calls.append((city, latest))
        return type("M", (), {"aspects": [1, 2], "general_claims": [1], "rejected": [], "model": "m"})()
    monkeypatch.setattr(navigate, "plan", fake_plan)
    monkeypatch.setattr(sys, "argv", ["corpus", "navigate", "plan", "--city", "dalat", "--no-latest"])
    cli.main()
    assert calls == [("dalat", False)]


def test_cli_compare_prints_the_table_for_the_map(monkeypatch, capsys, tmp_path):
    seen = []
    monkeypatch.setattr(navigate, "load_map", lambda city, path=None: seen.append(path) or "MAP")
    monkeypatch.setattr(navigate, "compare_map", lambda city, m: {"city": city, "map": m})
    monkeypatch.setattr(navigate, "table", lambda report: f"TABLE {report['city']} {report['map']}")
    f = tmp_path / "m.json"
    monkeypatch.setattr(sys, "argv", ["corpus", "navigate", "compare", "--city", "dalat", "--map", str(f)])
    cli.main()
    assert seen == [f] and "TABLE dalat MAP" in capsys.readouterr().out


def test_cli_compare_without_a_map_says_so(monkeypatch):
    monkeypatch.setattr(navigate, "load_map", lambda city, path=None: None)
    monkeypatch.setattr(sys, "argv", ["corpus", "navigate", "compare"])
    with pytest.raises(SystemExit) as e:
        cli.main()
    assert "navigate plan" in str(e.value)


def test_cli_refuses_an_unknown_phase(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["corpus", "navigate", "mine"])
    with pytest.raises(SystemExit):
        cli.main()
