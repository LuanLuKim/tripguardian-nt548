import sys

import pytest

from corpus import __main__ as cli
from corpus import views


def test_views_cli_builds_the_named_view_for_the_city(monkeypatch):
    calls = []
    monkeypatch.setattr(views, "VIEWS", {"climate": lambda c: calls.append(("climate", c)) or {"months": {}},
                                         "calendar": lambda c: calls.append(("calendar", c)) or {"days": []}})
    monkeypatch.setattr(sys, "argv", ["corpus", "views", "climate", "--city", "dalat"])
    cli.main()
    assert calls == [("climate", "dalat")]


def test_views_cli_all_runs_every_view_in_order(monkeypatch):
    calls = []
    monkeypatch.setattr(views, "VIEWS", {n: (lambda c, n=n: calls.append(n) or {"days": []}) for n in ("climate", "calendar", "restricted")})
    monkeypatch.setattr(sys, "argv", ["corpus", "views", "all"])
    cli.main()
    assert calls == ["climate", "calendar", "restricted"]


def test_views_cli_refuses_an_unknown_view(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["corpus", "views", "weather"])
    with pytest.raises(SystemExit):
        cli.main()
