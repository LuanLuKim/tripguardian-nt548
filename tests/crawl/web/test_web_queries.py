"""corpus.crawl.web.queries: where the web search phase's queries come from, in what order."""

import json

from corpus.crawl.web.queries import Query, gap_queries, plan, query_hash, seed_queries, slug_queries

CFG = {"slug_queries_per_run": 25, "gap_queries_per_run": 20}


def test_seed_queries_shape():
    qs = seed_queries("Đà Lạt")
    assert len(qs) == 69
    assert qs[0].text == "site:tiktok.com/discover Đà Lạt"
    assert qs[1].text == "site:tiktok.com/discover du lịch Đà Lạt"
    assert all("Đà Lạt" in q.text for q in qs)
    assert len({query_hash(q.text) for q in qs}) == 69
    assert all(len(q.text) <= 200 for q in qs)
    assert sum(q.text.startswith("site:tiktok.com/discover ") for q in qs) == 2
    assert sum(q.text.startswith("site:tiktok.com ") for q in qs) == 15 + 9
    transport = [q.text for q in qs if q.group == "transport"]
    assert transport[4] == "từ Nha Trang lên Đà Lạt đi đường nào mất bao lâu"
    assert {q.source for q in qs} == {"seed"}


def test_query_hash_ignores_case_and_spaces():
    assert query_hash(" Bánh  Căn ") == query_hash("bánh căn")


def _mining(root, payload):
    path = root / "dalat" / "navigate" / "mining_map.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(payload, ensure_ascii=False) if not isinstance(payload, str) else payload,
                    encoding="utf-8")


def test_mining_map_replaces_seeds(tmp_path):
    _mining(tmp_path, {"aspects": [
        {"key": "cloud_sea", "queries": ["săn mây", "mây Đà Lạt sáng sớm"], "sources": ["web", "TikTok"]},
        {"key": "pine", "queries": ["đồi thông"], "sources": ["web"]},
    ]})
    qs = plan("dalat", "Đà Lạt", CFG, tmp_path)
    assert [q.text for q in qs] == ["săn mây Đà Lạt", "site:tiktok.com săn mây Đà Lạt", "mây Đà Lạt sáng sớm",
                                    "site:tiktok.com mây Đà Lạt sáng sớm", "đồi thông Đà Lạt"]
    assert [q.group for q in qs] == ["cloud_sea"] * 4 + ["pine"]
    assert {q.source for q in qs} == {"mining_map"}


def test_bad_mining_map_falls_back_to_seeds(tmp_path, capsys):
    _mining(tmp_path, {"aspects": "x"})
    qs = plan("dalat", "Đà Lạt", CFG, tmp_path)
    assert [q.text for q in qs[:2]] == ["site:tiktok.com/discover Đà Lạt", "site:tiktok.com/discover du lịch Đà Lạt"]
    assert "mining_map" in capsys.readouterr().out


def test_slug_queries_skip_done_and_cap(tmp_path):
    web_root = tmp_path / "web" / "dalat"
    (web_root / "search").mkdir(parents=True)
    rows = [{"slug": f"da-lat-{i}", "text": f"đà lạt {i}"} for i in range(30)]
    (web_root / "discover_slugs.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    for i in (0, 3, 7, 8, 20):
        (web_root / "search" / f"{query_hash(f'site:tiktok.com đà lạt {i}')}.json").write_text("{}")
    qs = slug_queries(web_root, "dalat", limit=25)
    expected = [f"site:tiktok.com đà lạt {i}" for i in range(30) if i not in (0, 3, 7, 8, 20)]
    assert [q.text for q in qs] == expected
    assert {(q.group, q.source) for q in qs} == {("slug", "slug")}
    assert len(slug_queries(web_root, "dalat", limit=3)) == 3


def test_gap_queries_sorted_and_filtered(tmp_path):
    gaps = tmp_path / "gaps.jsonl"
    rows = [{"phrase": "quán một", "kind": "no_data", "count": 1},
            {"phrase": "quán năm", "kind": "no_data", "count": 5},
            {"phrase": "khác", "kind": "other", "count": 9},
            {"phrase": "quán ba", "kind": "no_data", "count": 3},
            {"phrase": "x" * 121, "kind": "no_data", "count": 7}]
    gaps.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows) + "not json\n", encoding="utf-8")
    qs = gap_queries(gaps, "Đà Lạt", limit=20)
    assert [q.text for q in qs] == ["quán năm Đà Lạt", "quán ba Đà Lạt", "quán một Đà Lạt"]
    assert {(q.group, q.source) for q in qs} == {("gap", "gap")}
    assert [q.text for q in gap_queries(gaps, "Đà Lạt", limit=2)] == ["quán năm Đà Lạt", "quán ba Đà Lạt"]
    assert gap_queries(tmp_path / "missing.jsonl", "Đà Lạt", limit=5) == []


def test_plan_adds_slugs_and_gaps_after_seeds_without_duplicates(tmp_path):
    web_root = tmp_path / "web" / "dalat"
    web_root.mkdir(parents=True)
    (web_root / "discover_slugs.jsonl").write_text(json.dumps({"slug": "x", "text": "săn mây Đà Lạt"}) + "\n",
                                                   encoding="utf-8")
    (tmp_path / "trip").mkdir()
    (tmp_path / "trip" / "gaps.jsonl").write_text(
        json.dumps({"phrase": "bánh căn", "kind": "no_data", "count": 2}) + "\n", encoding="utf-8")
    qs = plan("dalat", "Đà Lạt", CFG, tmp_path)
    # the gap "bánh căn Đà Lạt" repeats the banh_can seed: the seed (first) stays
    assert len(qs) == 69 + 1
    assert qs[-1] == Query("site:tiktok.com săn mây Đà Lạt", "slug", "slug")
    assert [q.group for q in qs if q.text == "bánh căn Đà Lạt"] == ["banh_can"]
    assert len({query_hash(q.text) for q in qs}) == len(qs)


def test_hot_groups_go_first(tmp_path):
    base = plan("dalat", "Đà Lạt", CFG, tmp_path)
    qs = plan("dalat", "Đà Lạt", CFG, tmp_path, hot={"cloud"})
    cloud = [q for q in base if q.group == "cloud"]
    assert qs[:len(cloud)] == cloud
    assert qs[len(cloud):] == [q for q in base if q.group != "cloud"]
