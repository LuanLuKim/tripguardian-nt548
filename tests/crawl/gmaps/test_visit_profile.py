import asyncio
import json
from contextlib import asynccontextmanager

from corpus.crawl.gmaps import visit


class Stop(Exception):
    pass


def _world(tmp_path, monkeypatch, n=4):
    root = tmp_path / "gmaps"
    items = []
    for i in range(n):
        d = root / "places" / f"p{i}"
        d.mkdir(parents=True)
        (d / "place.json").write_text(json.dumps({"url": f"u{i}", "popular_times": [[1]]}), encoding="utf-8")
        items.append({"fid": f"p{i}"})
    (root / "list").mkdir()
    (root / "list" / "dalat.json").write_text(json.dumps({"items": items}), encoding="utf-8")
    monkeypatch.setattr(visit, "data_dir", lambda: tmp_path)
    return root


def _run(profile, **kw):
    try:
        asyncio.run(visit.run("dalat", profile=profile, **kw))
    except* Stop:
        pass


def test_visit_opens_the_named_profile(tmp_path, monkeypatch):
    _world(tmp_path, monkeypatch)
    seen = []

    @asynccontextmanager
    async def profile(name, headed):
        seen.append(name)
        raise Stop
        yield

    _run(profile, profile_name="gmaps_b2")
    _run(profile)
    assert seen == ["gmaps_b2", "gmaps"]


def test_visit_shard_takes_every_nth_place(tmp_path, monkeypatch, capsys):
    _world(tmp_path, monkeypatch)

    @asynccontextmanager
    async def profile(name, headed):
        raise Stop
        yield

    _run(profile, shard=(1, 2))
    assert "visit dalat: 2 places left (shard 1/2)" in capsys.readouterr().out


class _FakePage:
    def __init__(self):
        self.waits = []

    async def goto(self, *a, **k):
        pass

    async def wait_for_selector(self, selector, **k):
        self.waits.append((selector, k.get("state", "visible")))

    def locator(self, *a, **k):
        class L:
            async def count(self):
                return 0
        return L()

    async def wait_for_timeout(self, ms):
        pass

    async def evaluate(self, js):
        return None

    async def close(self):
        pass


def test_read_visit_waits_for_the_graph_attached_not_visible():
    """Maps gives the popular-times block (div.C7xf8b) height 0 (its bars overflow), so a 'visible' wait never succeeds (2026-10-28)."""
    page = _FakePage()

    class Ctx:
        async def new_page(self):
            return page

    res = asyncio.run(visit.read_visit(Ctx(), "https://maps.example/x"))
    graph_waits = [w for w in page.waits if "C7xf8b" in w[0]]
    assert graph_waits and all(state == "attached" for _, state in graph_waits)
    assert res["complete"] is True
