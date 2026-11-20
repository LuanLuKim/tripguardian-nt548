"""gmaps refresh: which places a run opens, in what order."""

import os

from corpus.crawl.gmaps import refresh


def test_served_places_only_lodging_last_refreshed_longest_ago_first(tmp_path):
    items = [{"fid": f, "reviews": n} for f, n in (("a", "50"), ("b", "900"), ("hotel", "5000"), ("gone", "10"), ("old", "60"))]
    groups = {"a": "cafe", "b": "nature", "hotel": "stay", "old": "attraction"}
    (tmp_path / "reviews_recent").mkdir()
    for name, at in (("old", 1_000), ("b", 2_000)):
        f = tmp_path / "reviews_recent" / f"{name}.json"
        f.write_text("{}")
        os.utime(f, (at, at))
    assert [r["fid"] for r in refresh.todo(tmp_path, items, groups, 10)] == ["a", "old", "b", "hotel"]
    assert [r["fid"] for r in refresh.todo(tmp_path, items, groups, 2)] == ["a", "old"]
