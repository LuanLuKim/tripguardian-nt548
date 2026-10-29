"""corpus.crawl.web.scoring: how much new each query brought, by group."""

import json

from corpus.crawl.web.queries import Query
from corpus.crawl.web.scoring import group_scores, hot_groups, yield_row


def _write(path, totals):
    rows = []
    for group, new in totals.items():
        rows.append(yield_row(Query(f"q {group}", group, "seed"), "h", results=10, videos_total=new, videos_new=new,
                              docs_new=0, slugs_new=0, blocked=[], cached=False))
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


def test_yield_row_new_is_sum():
    row = yield_row(Query("a", "cloud", "seed"), "abc", results=9, videos_total=4, videos_new=2, docs_new=3,
                    slugs_new=1, blocked=["brave"], cached=False)
    assert row["new"] == 6
    assert row["hash"] == "abc" and row["group"] == "cloud" and row["source"] == "seed"
    assert row["blocked_engines"] == ["brave"]
    assert set(row) == {"at", "query", "hash", "group", "source", "results", "videos_total", "videos_new",
                        "docs_new", "slugs_new", "new", "blocked_engines", "cached"}


def test_group_scores_sums_by_group(tmp_path):
    path = tmp_path / "query_yield.jsonl"
    rows = [yield_row(Query("a", "x", "seed"), "1", results=1, videos_total=0, videos_new=2, docs_new=1, slugs_new=0,
                      blocked=[], cached=False),
            yield_row(Query("b", "x", "seed"), "2", results=1, videos_total=0, videos_new=0, docs_new=1, slugs_new=0,
                      blocked=[], cached=False),
            yield_row(Query("c", "y", "seed"), "3", results=1, videos_total=0, videos_new=0, docs_new=0, slugs_new=5,
                      blocked=[], cached=False)]
    path.write_text("".join(json.dumps(r) + "\n" for r in rows) + "{broken\n", encoding="utf-8")
    assert group_scores(path) == {"x": {"queries": 2, "new": 4, "mean_new": 2.0},
                                  "y": {"queries": 1, "new": 5, "mean_new": 5.0}}


def test_hot_groups_two_times_median(tmp_path):
    path = tmp_path / "query_yield.jsonl"
    _write(path, {"a": 10, "b": 4, "c": 3, "d": 2, "e": 1})
    assert hot_groups(path) == {"a"}
    _write(path, {"a": 6, "b": 3, "c": 3})
    assert hot_groups(path) == {"a"}
    _write(path, {"a": 0, "b": 0})
    assert hot_groups(path) == set()


def test_hot_groups_missing_file_is_empty(tmp_path):
    assert hot_groups(tmp_path / "none.jsonl") == set()
