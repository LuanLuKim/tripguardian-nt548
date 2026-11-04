"""corpus tiktok place_web: a web search per place without a clip -> TikTok video URLs whose title names the place
(no network)."""

import json

import httpx

from corpus.crawl.tiktok import place_web


def result(video_id, title, author="u", host="www.tiktok.com"):
    return {"url": f"https://{host}/@{author}/video/{video_id}?lang=vi", "title": title}


def test_title_must_carry_every_distinctive_word():
    assert place_web.names_place("Review Mê Linh Coffee Garden Đà Lạt - TikTok", "Mê Linh Coffee Garden")
    assert not place_web.names_place("Quán cà phê vườn ở Đà Lạt", "Mê Linh Coffee Garden")
    assert place_web.names_place("Thác Datanla mùa hoa", "Khu du lịch Thác Datanla")
    assert not place_web.names_place("Khách sạn đẹp ở Đà Lạt", "Khách sạn Đà Lạt")  # nothing distinctive: never matches
    assert not place_web.names_place("Cafe ABC", "Quán Cà Phê ABC")  # one distinctive word under 4 letters


def test_clean_name_drops_notes_and_taglines():
    assert place_web.clean_name("Quán ăn gia đình TIẾN HIỀN(Cơm-bún-phở-lẩu)") == "Quán ăn gia đình TIẾN HIỀN"
    assert place_web.clean_name("Bánh Mì Xíu Mại Phúc Hân - Hoàng Diệu") == "Bánh Mì Xíu Mại Phúc Hân"
    assert place_web.clean_name("ĐÔI DÉP Camellia Tea Spa | Đà Lạt") == "ĐÔI DÉP Camellia Tea Spa"


def test_videos_of_keeps_named_tiktok_videos_only_once_and_capped():
    rs = [result("1", "Thác Datanla"), result("1", "Thác Datanla"), result("2", "Thác Datanla 2"),
          result("3", "Thác Datanla 3"), result("4", "Thác Datanla 4"), result("5", "Chuyện khác"),
          {"url": "https://example.com/@u/video/9", "title": "Thác Datanla"},
          {"url": "https://www.tiktok.com/discover/thac-datanla", "title": "Thác Datanla"}]
    found, kept = place_web.videos_of(rs, "Thác Datanla")
    assert found == 5 and [k["video_id"] for k in kept] == ["1", "2", "3"]
    assert kept[0]["url"] == "https://www.tiktok.com/@u/video/1"


def setup(tmp_path, monkeypatch, answers):
    gl = tmp_path / "gmaps" / "list"
    gl.mkdir(parents=True)
    gl.joinpath("dalat.json").write_text(json.dumps({"items": [
        {"fid": "f1", "name": "Thác Datanla", "reviews": 10}, {"fid": "f2", "name": "Mê Linh Coffee Garden", "reviews": 99},
        {"fid": "f3", "name": "Quán X", "reviews": 5}]}), encoding="utf-8")
    gl.joinpath("dalat_stay.json").write_text(json.dumps({"items": [
        {"fid": "s1", "name": "Villa Hoa Sen Đà Lạt", "reviews": 1000}]}), encoding="utf-8")
    asked = []

    def search(client, query):
        asked.append(query)
        results, blocked = answers(query)
        return results, blocked, False
    monkeypatch.setattr(place_web, "search", search)
    monkeypatch.setattr(place_web, "evidence_pairs", lambda: {("v0", "f3")})
    (tmp_path / "tiktok" / "videos" / "v0").mkdir(parents=True)
    (tmp_path / "tiktok" / "videos" / "v0" / "video.mp4").write_bytes(b"x")
    return asked


def rows(path):
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def test_run_asks_places_without_a_clip_lodging_last_and_never_twice(tmp_path, monkeypatch):
    asked = setup(tmp_path, monkeypatch, lambda q: ([result("1" if "Datanla" in q else "2", "Thác Datanla Mê Linh Coffee Garden Villa Hoa Sen")], False))
    stats = place_web.run("dalat", sleep=lambda s: None)
    assert asked == ["site:tiktok.com Mê Linh Coffee Garden Đà Lạt", "site:tiktok.com Thác Datanla Đà Lạt",
                     "site:tiktok.com Villa Hoa Sen Đà Lạt"]  # f3 has a clip; most reviewed first; stay last
    assert stats["asked"] == 3
    got = rows(tmp_path / "tiktok" / "place_web" / "dalat.jsonl")
    assert sorted((r["fid"], r["video_id"]) for r in got if r["video_id"] == "1") == [("f1", "1")]
    place_web.run("dalat", sleep=lambda s: None)
    assert len(asked) == 3  # asked places are not asked again


def test_blocked_query_is_not_recorded_and_stops_after_five(tmp_path, monkeypatch):
    asked = setup(tmp_path, monkeypatch, lambda q: ([], True))
    stats = place_web.run("dalat", sleep=lambda s: None)
    assert stats["asked"] == 0 and stats["blocked"] == len(asked) < 5 + 1
    assert not (tmp_path / "tiktok" / "place_web" / "dalat_tried.jsonl").exists()


def test_no_result_is_recorded_as_tried(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch, lambda q: ([], False))
    place_web.run("dalat", sleep=lambda s: None)
    tried = rows(tmp_path / "tiktok" / "place_web" / "dalat_tried.jsonl")
    assert len(tried) == 3 and all(t["tiktok"] == 0 and t["kept"] == 0 for t in tried)


def test_pace_shrinks_after_a_clean_run_never_below_the_floor_and_doubles_when_refused():
    pace = place_web.Pace(5.0)
    for _ in range(place_web.RAMP_AFTER):
        pace.ok()
    assert pace.pause == 5.0 * place_web.RAMP_DOWN
    for _ in range(place_web.RAMP_AFTER * 20):
        pace.ok()
    assert pace.pause == place_web.MIN_PAUSE_S
    pace.refused()
    assert pace.pause == place_web.MIN_PAUSE_S * place_web.BACK_OFF
    for _ in range(10):
        pace.refused()
    assert pace.pause == place_web.MAX_PAUSE_S


def test_run_sleeps_the_paces_pause_and_backs_off_on_a_refusing_engine(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch, lambda q: ([result("1", "Thác Datanla")], False))
    refusing = iter([True, False, False])
    monkeypatch.setattr(place_web, "search", lambda c, q: ([result("1", "Thác Datanla")], False, next(refusing)))
    naps = []
    place_web.run("dalat", sleep=naps.append, pause=2.0)
    assert naps == [4.0, 4.0, 4.0]


def test_search_counts_only_a_new_refusal_not_a_held_suspension():
    class Client:
        def __init__(self, down):
            self.down = down

        def get(self, *a, **kw):
            down = self.down

            class R:
                def raise_for_status(self): pass
                def json(self): return {"results": [{"url": "u"}], "unresponsive_engines": down}
            return R()
    assert place_web.search(Client([["yandex", "CAPTCHA"]]), "q")[2] is True
    assert place_web.search(Client([["duckduckgo", "Suspended: access denied"]]), "q")[2] is False
    assert place_web.search(Client([]), "q") == ([{"url": "u"}], False, False)


# --- gsearch backend (Google through signed-in windows) ---

from corpus.crawl.web import SearchPage, SearchResult


def g(video_id, title, snippet="", author="u"):
    return SearchResult(url=f"https://www.tiktok.com/@{author}/video/{video_id}", title=title, snippet=snippet, engines=("google-browser",))


def gsetup(tmp_path, monkeypatch, answer):
    setup(tmp_path, monkeypatch, lambda q: ([], False))
    asked = []

    def search_pages(queries, city="dalat", pages=1, headed=False, **kw):
        asked.append((list(queries), kw))
        return [answer(q) for q in queries]
    monkeypatch.setattr(place_web.gsearch, "search_pages", search_pages)
    return asked


def test_gsearch_query_quotes_the_clean_name_and_adds_the_city_once():
    assert place_web.gsearch_query("Mê Linh Coffee Garden", "Đà Lạt") == 'site:tiktok.com "Mê Linh Coffee Garden" Đà Lạt'
    assert place_web.gsearch_query("Villa Hoa Sen Đà Lạt (Biệt thự)", "Đà Lạt") == 'site:tiktok.com "Villa Hoa Sen Đà Lạt"'
    assert place_web.gsearch_query("ĐÔI DÉP Camellia Tea Spa | Đà Lạt", "Đà Lạt") == 'site:tiktok.com "ĐÔI DÉP Camellia Tea Spa" Đà Lạt'
    assert place_web.gsearch_query("a b c d e f g h", "Đà Lạt") == 'site:tiktok.com "a b c d e f" Đà Lạt'


def test_gsearch_keeps_named_videos_by_title_or_snippet_and_writes_the_same_rows(tmp_path, monkeypatch):
    def answer(q):
        if "Datanla" in q:
            return SearchPage(query=q, results=(g("1", "Review Đà Lạt | TikTok", "Thác Datanla mùa hoa"), g("2", "Chuyện khác")))
        return SearchPage(query=q, results=(g("3", "Mê Linh Coffee Garden"),))
    asked = gsetup(tmp_path, monkeypatch, answer)
    stats = place_web.run("dalat", backend="gsearch", pause=0.0)
    assert [q for qs, _ in asked for q in qs] == ['site:tiktok.com "Mê Linh Coffee Garden" Đà Lạt',
                                                   'site:tiktok.com "Thác Datanla" Đà Lạt',
                                                   'site:tiktok.com "Villa Hoa Sen Đà Lạt"']  # f3 has a clip; stay last
    assert stats["asked"] == 3 and stats["kept"] == 2
    got = rows(tmp_path / "tiktok" / "place_web" / "dalat.jsonl")
    assert sorted((r["fid"], r["video_id"]) for r in got) == [("f1", "1"), ("f2", "3")]
    assert {"at", "fid", "name", "query", "video_id", "url", "title"} <= set(got[0])
    tried = rows(tmp_path / "tiktok" / "place_web" / "dalat_tried.jsonl")
    assert sorted((t["fid"], t["kept"]) for t in tried) == [("f1", 1), ("f2", 1), ("s1", 0)]
    assert all({"at", "fid", "name", "query", "results", "tiktok", "kept"} <= set(t) for t in tried)
    place_web.run("dalat", backend="gsearch", pause=0.0)
    assert len(asked) == 1  # asked places are not asked again


def test_gsearch_pacing_goes_to_the_gsearch_pages(tmp_path, monkeypatch):
    asked = gsetup(tmp_path, monkeypatch, lambda q: SearchPage(query=q, results=(g("1", "Thác Datanla"),)))
    place_web.run("dalat", backend="gsearch", pause=5.0, limit=1)
    assert asked[0][1]["pause_s"] == (5.0, 9.0)


def test_gsearch_unreadable_page_is_not_recorded_and_stops_the_window(tmp_path, monkeypatch):
    def answer(q):
        if "Mê Linh" in q:
            return SearchPage(query=q, results=(g("3", "Mê Linh Coffee Garden"),))
        return SearchPage(query=q, results=(), unresponsive=(("google-browser", "captcha"),))
    asked = gsetup(tmp_path, monkeypatch, answer)
    naps: list[float] = []
    stats = place_web.run_gsearch("dalat", chunk=1, pause=0.0, rest=(0.0, 0.0), sleep=naps.append, forbidden_wait=(9.0, 9.0))
    assert naps.count(9.0) == place_web.FORBIDDEN_TRIES  # the unread page is asked again after each long rest
    assert stats["asked"] == 1 and stats["blocked"] == 1 and len(asked) == 2 + place_web.FORBIDDEN_TRIES  # then the window stops
    tried = rows(tmp_path / "tiktok" / "place_web" / "dalat_tried.jsonl")
    assert [t["fid"] for t in tried] == ["f2"]


def test_gsearch_empty_pages_count_as_tried_only_after_a_page_with_results(tmp_path, monkeypatch):
    def answer(q):  # the most reviewed place has results, the rest none
        return SearchPage(query=q, results=(g("3", "Mê Linh Coffee Garden"),) if "Mê Linh" in q else ())
    gsetup(tmp_path, monkeypatch, answer)
    place_web.run("dalat", backend="gsearch", pause=0.0)
    assert len(rows(tmp_path / "tiktok" / "place_web" / "dalat_tried.jsonl")) == 3


def test_gsearch_an_all_empty_run_records_nothing_as_tried(tmp_path, monkeypatch):
    gsetup(tmp_path, monkeypatch, lambda q: SearchPage(query=q, results=()))
    place_web.run("dalat", backend="gsearch", pause=0.0)
    assert not (tmp_path / "tiktok" / "place_web" / "dalat_tried.jsonl").exists()  # nothing proved the window reads results


def test_gsearch_too_many_empty_pages_in_a_row_stop_the_window(tmp_path, monkeypatch):
    monkeypatch.setattr(place_web, "STOP_AFTER_EMPTY", 1)
    asked = gsetup(tmp_path, monkeypatch, lambda q: SearchPage(query=q, results=(g("3", "Mê Linh Coffee Garden"),) if "Mê Linh" in q else ()))
    place_web.run_gsearch("dalat", chunk=1, pause=0.0, rest=(0.0, 0.0))
    assert len(asked) == 2  # f2 has results, f1 is empty -> stop; the stay place is not asked
    tried = rows(tmp_path / "tiktok" / "place_web" / "dalat_tried.jsonl")
    assert [t["fid"] for t in tried] == ["f2"]  # the empty page is asked again next run


def test_gsearch_shards_split_the_todo_and_the_stop_file_ends_the_run(tmp_path, monkeypatch):
    asked = gsetup(tmp_path, monkeypatch, lambda q: SearchPage(query=q, results=(g("1", "Thác Datanla Mê Linh Coffee Garden Villa Hoa Sen"),)))
    place_web.run("dalat", backend="gsearch", shard=(1, 2), pause=0.0)
    assert [q for qs, _ in asked for q in qs] == ['site:tiktok.com "Thác Datanla" Đà Lạt']  # 2nd of 3: shard 1/2 holds index 1
    (tmp_path / "tiktok" / "place_web" / "STOP").write_text("", encoding="utf-8")
    place_web.run("dalat", backend="gsearch", shard=(0, 2), pause=0.0)
    assert len(asked) == 1


class FakeProc:
    def __init__(self, lines, code=0):
        self.stdout, self.code = iter(lines), code

    def wait(self):
        return self.code

    def poll(self):
        return self.code


def test_attach_starts_one_child_per_window_with_its_own_shard_and_port(tmp_path, monkeypatch):
    started, out = [], []

    def popen(cmd, env=None, **kw):
        started.append((cmd, env))
        return FakeProc([f"gsearch: captcha, open chrome://inspect on DevTools port {env['CORPUS_DEBUG_PORT']}\n"],
                        code=len(started) - 1)
    urls = ["http://127.0.0.1:9533", "http://127.0.0.1:9520", "http://127.0.0.1:9521"]
    codes = place_web.run_windows("dalat", urls, 10, 7.0, popen=popen, emit=out.append)
    assert [c[0][c[0].index("--shard") + 1] for c in started] == ["0/3", "1/3", "2/3"]
    assert [e["CORPUS_ATTACH_URL"] for _, e in started] == urls
    assert [e["CORPUS_DEBUG_PORT"] for _, e in started] == ["9533", "9520", "9521"]
    assert all(e["CORPUS_PROFILE_STATE"] == "1" for _, e in started)
    assert all(c[c.index("--limit") + 1] == "4" and c[c.index("--pause") + 1] == "7.0" for c, _ in started)
    assert codes == dict(zip(urls, [0, 1, 2]))
    assert sorted(out) == sorted(f"[{p}] gsearch: captcha, open chrome://inspect on DevTools port {p}" for p in (9533, 9520, 9521))


def test_cli_passes_backend_attach_pause_and_shard(monkeypatch):
    import sys

    import corpus.__main__ as cli
    calls = []
    monkeypatch.setitem(cli.PHASES["tiktok"], "place_web", (lambda city, **kw: calls.append((city, kw)), False))
    monkeypatch.setattr(sys, "argv", ["corpus", "tiktok", "place_web", "--backend", "gsearch", "--attach",
                                      "http://127.0.0.1:9533, http://127.0.0.1:9520", "--pause", "8", "--limit", "30"])
    cli.main()
    monkeypatch.setattr(sys, "argv", ["corpus", "tiktok", "place_web"])
    cli.main()
    assert calls == [("dalat", {"limit": 30, "shard": None, "backend": "gsearch", "pause": 8.0,
                                "attach": ["http://127.0.0.1:9533", "http://127.0.0.1:9520"]}),
                     ("dalat", {"limit": None, "shard": None, "backend": "searxng"})]


def test_gsearch_rests_between_chunks_and_staggers_windows(tmp_path, monkeypatch):
    gsetup(tmp_path, monkeypatch, lambda q: SearchPage(query=q, results=(g("3", "Mê Linh Coffee Garden"),)))
    naps: list[float] = []
    place_web.run_gsearch("dalat", shard=(1, 1), chunk=1, pause=0.0, rest=(7.0, 7.0), sleep=naps.append)
    assert naps[0] == place_web.STAGGER_S  # the second window starts later
    assert naps[1:] and all(n == 7.0 for n in naps[1:])  # a rest between two chunks, none before the first
