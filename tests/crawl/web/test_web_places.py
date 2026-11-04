"""web places: fee / hours queries through SearXNG -> data/web/<city>/place_snippets.jsonl, read by search observe."""
import json

from corpus.crawl import gsearch, web
from corpus.crawl.web import places


def setup(tmp_path, monkeypatch, answers):
    monkeypatch.setattr(places, "data_dir", lambda: tmp_path)
    monkeypatch.setattr(places, "load_config", lambda city: ("Đà Lạt", None), raising=False)
    monkeypatch.setattr(gsearch.places, "queries", lambda city, kind: [f"{kind} q1", f"{kind} q2"])
    asked = []

    def ask(client, query):
        asked.append(query)
        return answers(query)
    monkeypatch.setattr(places, "ask", ask)
    return asked


def result(url="https://a.vn/x"):
    return {"rank": 1, "url": url, "title": "t", "snippet": "vé 50.000đ", "engines": ["yahoo"]}


def test_every_query_is_written_once_and_never_asked_again(tmp_path, monkeypatch):
    asked = setup(tmp_path, monkeypatch, lambda q: ([result()], False))
    stats = places.run("dalat", sleep=lambda s: None)
    assert asked == ["fee q1", "fee q2", "hours q1", "hours q2"] and stats["asked"] == 4
    rows = [json.loads(x) for x in (tmp_path / "web" / "dalat" / "place_snippets.jsonl").read_text(encoding="utf-8").splitlines()]
    assert rows[0]["kind"] == "fee" and rows[0]["source"] == "searxng" and rows[0]["key"] == gsearch.key("fee q1")
    places.run("dalat", sleep=lambda s: None)
    assert len(asked) == 4
    assert set(places.load("dalat")) == {gsearch.key(q) for q in ("fee q1", "fee q2", "hours q1", "hours q2")}


def test_a_query_with_no_result_is_recorded_a_blocked_one_is_not_and_six_in_a_row_stop(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch, lambda q: ([], False))
    places.run("dalat", sleep=lambda s: None)
    assert len(places.load("dalat")) == 4  # empty rows count as tried
    (tmp_path / "web" / "dalat" / "place_snippets.jsonl").unlink()
    asked = setup(tmp_path, monkeypatch, lambda q: ([], True))
    stats = places.run("dalat", sleep=lambda s: None)
    assert stats["asked"] == 0 and stats["blocked"] == len(asked) and not places.path("dalat").exists()


def test_shards_split_the_queries(tmp_path, monkeypatch):
    asked = setup(tmp_path, monkeypatch, lambda q: ([result()], False))
    places.run("dalat", shard=(1, 2), sleep=lambda s: None)
    assert asked == ["fee q2", "hours q2"]


def test_search_observe_falls_back_to_the_searxng_row_but_google_wins():
    from corpus.observe import search as obs
    q = gsearch.places.query_for("fee", "Thác X", "Đà Lạt")
    sx = {gsearch.key(q): {"at": "2026-10-30T00:00:00+00:00", "results": [result()]}}
    recs = obs._records("nocity", "Thác X", "Đà Lạt", sx)
    assert recs["fee"] is sx[gsearch.key(q)] and recs["hours"] is None and recs["panel"] is None
