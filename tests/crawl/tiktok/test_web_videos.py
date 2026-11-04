"""corpus tiktok web_videos: TikTok video URLs found on the web -> their TikTok place (poi) -> the Maps places
place_verify judges them for (no network, no browser)."""

import asyncio
import json
from contextlib import asynccontextmanager

import pytest

from corpus.crawl.common.browser import LoginRequired
from corpus.crawl.tiktok import place_filter, web_videos

MAPPED_POI = {"id": "111", "name": "Tiệm Bánh Căn Nhà Chung", "address": "1 Nhà Chung", "category": "Thực phẩm",
              "ttTypeNameTiny": "Nhà hàng"}
NAMED_POI = {"id": "222", "name": "Quán Lẩu Gà Lá É Tao Ngộ", "address": "5 Tao Ngộ", "category": "Thực phẩm",
             "ttTypeNameTiny": "Nhà hàng"}
CITY_POI = {"id": "333", "name": "Đà Lạt", "address": "", "category": "", "ttTypeNameTiny": "Thành phố"}
PLACES = [{"fid": "f1", "name": "Bánh Căn Nhà Chung", "category": "Quán ăn"},
          {"fid": "f2", "name": "Lẩu Gà Lá É Tao Ngộ", "category": "Nhà hàng"},
          {"fid": "f3", "name": "Hồ Xuân Hương", "category": "Hồ"}]


def item(video_id, poi=None, play="https://v.tiktokcdn.com/x.mp4"):
    it = {"id": video_id, "desc": f"video {video_id}", "createTime": 1700000000, "author": {"uniqueId": "u"},
          "stats": {"diggCount": 5}, "video": {"playAddr": play, "duration": 30}}
    if poi:
        it["poi"] = poi
    return it


def url(video_id):
    return f"https://www.tiktok.com/@u/video/{video_id}"


def setup_data(tmp_path, ids, known=()):
    web = tmp_path / "web" / "dalat"
    web.mkdir(parents=True)
    web.joinpath("tiktok_urls.jsonl").write_text("".join(json.dumps(
        {"url": url(v), "video_id": v, "author": "u", "title": "t", "query": "q", "found_at": "x"}) + "\n"
        for v in ids), encoding="utf-8")
    gl = tmp_path / "gmaps" / "list"
    gl.mkdir(parents=True)
    gl.joinpath("dalat.json").write_text(json.dumps({"items": PLACES}), encoding="utf-8")
    pp = tmp_path / "tiktok" / "place_poi"
    pp.mkdir(parents=True)
    pp.joinpath("dalat.json").write_text(json.dumps({"places": {
        "f1": {"name": "Bánh Căn Nhà Chung", "poi": {k: MAPPED_POI[k] for k in ("id", "name", "address", "category")}},
        "f3": {"name": "Hồ Xuân Hương", "poi": None}}}), encoding="utf-8")
    for v in known:
        (tmp_path / "tiktok" / "videos" / v).mkdir(parents=True)
        (tmp_path / "tiktok" / "videos" / v / "info.json").write_text("{}", encoding="utf-8")


def fake_sessions():
    opened = []

    @asynccontextmanager
    async def sessions(headed=False):
        async def new_session():
            ctx = object()
            opened.append(ctx)
            return ctx
        yield new_session
    return opened, sessions


def run(monkeypatch, items, downloads=None, fail=()):
    opened, sessions = fake_sessions()
    visited = []

    async def open_item(ctx, u):
        visited.append(u)
        vid = u.rsplit("/", 1)[1]
        if vid in fail:
            raise fail[vid]
        return items.get(vid)

    async def download(ctx, play, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"mp4")
        if downloads is not None:
            downloads.append(path.parent.name)
    monkeypatch.setattr(web_videos, "open_item", open_item)
    monkeypatch.setattr(web_videos, "download_video", download)
    monkeypatch.setattr(web_videos, "pause", lambda *a: asyncio.sleep(0))
    out = asyncio.run(web_videos.run("dalat", sessions=sessions))
    return out, visited, opened


def rows(path):
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def test_skips_known_videos_and_routes_each_poi(tmp_path, monkeypatch):
    setup_data(tmp_path, ["1", "2", "3", "4", "5"], known=["5"])
    items = {"1": item("1", MAPPED_POI), "2": item("2", NAMED_POI), "3": item("3"), "4": item("4", CITY_POI)}
    got = []
    stats, visited, opened = run(monkeypatch, items, downloads=got)
    assert [u.rsplit("/", 1)[1] for u in visited] == ["1", "2", "3", "4"]
    assert len(opened) == 1  # one anonymous session for all
    out = {r["video_id"]: r for r in rows(tmp_path / "tiktok" / "web_videos" / "dalat.jsonl")}
    assert out["1"]["poi"]["id"] == "111" and out["1"]["mapped"] == "f1"
    assert [p["fid"] for p in out["1"]["places"]] == ["f1"]
    assert out["2"]["mapped"] is None and [p["fid"] for p in out["2"]["places"]] == ["f2"]
    assert out["3"]["poi"] is None and out["3"]["places"] == []
    assert out["4"]["poi"]["id"] == "333" and out["4"]["places"] == []  # a city is never a place
    assert sorted(got) == ["1", "2"]  # only videos with a place to be judged for are downloaded
    v1 = tmp_path / "tiktok" / "videos" / "1"
    assert json.loads(v1.joinpath("info.json").read_text())["poi"]["id"] == "111"
    doc = json.loads(v1.joinpath("video.json").read_text())
    assert doc["comments_complete"] is None and doc["poi"]["id"] == "111" and v1.joinpath("video.mp4").exists()
    assert stats["with_poi"] == 3 and stats["mapped"] == 1 and stats["named"] == 1 and stats["downloaded"] == 2


def test_place_verify_sees_web_video_places(tmp_path, monkeypatch):
    setup_data(tmp_path, ["1", "2"])
    run(monkeypatch, {"1": item("1", MAPPED_POI), "2": item("2", NAMED_POI)})
    by = place_filter.places_by_video("dalat")
    assert [p["fid"] for p in by["1"]] == ["f1"] and [p["fid"] for p in by["2"]] == ["f2"]
    assert set(by["1"][0]) == {"fid", "name", "category", "address"}


def test_rerun_skips_done_and_retries_failures(tmp_path, monkeypatch):
    setup_data(tmp_path, ["1", "2"])
    run(monkeypatch, {"1": item("1", MAPPED_POI)}, fail={"2": RuntimeError("Timeout 30000ms exceeded")})
    assert [r["video_id"] for r in rows(tmp_path / "tiktok" / "web_videos" / "dalat.jsonl")] == ["1"]
    assert "2" in (tmp_path / "tiktok" / "errors.jsonl").read_text()
    _, visited, _ = run(monkeypatch, {"2": item("2")})
    assert [u.rsplit("/", 1)[1] for u in visited] == ["2"]


def test_page_without_item_is_logged_and_asked_again_next_run(tmp_path, monkeypatch):
    setup_data(tmp_path, ["9"])
    stats, _, _ = run(monkeypatch, {})  # no item data: deleted, private, or the onset of an Akamai block
    assert stats["no_item"] == 1 and not (tmp_path / "tiktok" / "web_videos" / "dalat.jsonl").exists()
    assert "no item data" in (tmp_path / "tiktok" / "errors.jsonl").read_text()
    _, visited, _ = run(monkeypatch, {})
    assert visited == [url("9")]


def test_captcha_stops_the_run(tmp_path, monkeypatch):
    setup_data(tmp_path, ["1"])
    with pytest.raises(LoginRequired):
        run(monkeypatch, {}, fail={"1": LoginRequired("tiktok")})


def test_photo_post_is_not_downloaded(tmp_path, monkeypatch):
    setup_data(tmp_path, ["1"])
    got = []
    run(monkeypatch, {"1": item("1", MAPPED_POI, play=None)}, downloads=got)
    assert got == [] and rows(tmp_path / "tiktok" / "web_videos" / "dalat.jsonl")[0]["downloaded"] is False


def test_no_web_file_is_a_clear_stop(tmp_path):
    with pytest.raises(SystemExit):
        asyncio.run(web_videos.run("dalat", sessions=fake_sessions()[1]))


def put_place_web(tmp_path, *pairs):
    d = tmp_path / "tiktok" / "place_web"
    d.mkdir(parents=True, exist_ok=True)
    d.joinpath("dalat.jsonl").write_text("".join(json.dumps(
        {"at": "x", "fid": f, "name": "n", "query": "q", "video_id": v, "url": url(v), "title": "t"}) + "\n"
        for v, f in pairs), encoding="utf-8")


def test_place_web_video_gets_the_searched_place_as_candidate(tmp_path, monkeypatch):
    setup_data(tmp_path, [])  # no tiktok_urls rows: the only video comes from place_web
    put_place_web(tmp_path, ("7", "f3"), ("8", "f3"))
    got = []
    run(monkeypatch, {"7": item("7"), "8": item("8", MAPPED_POI)}, downloads=got)
    out = {r["video_id"]: r for r in rows(tmp_path / "tiktok" / "web_videos" / "dalat.jsonl")}
    assert [p["fid"] for p in out["7"]["places"]] == ["f3"] and out["7"]["poi"] is None  # no poi: still judged
    assert [p["fid"] for p in out["8"]["places"]] == ["f1", "f3"]  # poi mapped place first, then the searched one
    assert sorted(got) == ["7", "8"]


def test_place_web_video_on_disk_is_recorded_without_opening_the_page(tmp_path, monkeypatch):
    setup_data(tmp_path, ["1"])
    run(monkeypatch, {"1": item("1", MAPPED_POI)})
    put_place_web(tmp_path, ("1", "f3"))
    stats, visited, _ = run(monkeypatch, {})
    assert visited == [] and stats["recorded_only"] == 1
    by = place_filter.places_by_video("dalat")
    assert sorted(p["fid"] for p in by["1"]) == ["f1", "f3"]
    _, visited, _ = run(monkeypatch, {})  # nothing new the next time
    assert visited == [] and len(rows(tmp_path / "tiktok" / "web_videos" / "dalat.jsonl")) == 2
