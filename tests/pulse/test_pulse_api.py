import json
from datetime import UTC, datetime

from corpus import pulse
from corpus.pulse import signals, store

HOT = {"id": "hot:p1", "kind": "hot", "subject": {"type": "place", "id": "p1", "name": "Quán Một"},
       "signals": {"videos": 4, "authors": 3, "newest": "2026-10-27", "window_days": 30}, "dates": {},
       "evidence": [{"type": "tiktok_video", "id": "v1", "url": "https://t/1", "date": "2026-10-27"}]}
SEASON = {"id": "season:da-quy", "kind": "season", "subject": {"type": "season", "id": None, "name": "Dã quỳ"},
          "signals": {"months": [10, 11], "sources": 2, "status": "kept", "latest_video": None}, "dates": {},
          "evidence": [{"type": "web_document", "id": "d", "url": "https://x.vn/a", "domain": "x.vn", "date": "2026-10-28", "quote": "q"}]}


def snap(day="2026-10-29", items=(HOT, SEASON)):
    return {"city": "dalat", "generated_at": f"{day}T06:00:00+00:00", "day": day, "counts": {}, "inputs": {}, "items": list(items)}


def at(day):
    return datetime.fromisoformat(f"{day}T08:00:00+00:00").astimezone(UTC)


def test_store_roundtrip_and_prune(tmp_path):
    for d in range(10, 16):
        store.write("dalat", snap(f"2026-10-{d}"), keep=3, root=tmp_path)
    files = sorted(p.name for p in (tmp_path / "dalat" / "pulse").glob("2*.json"))
    assert files == ["20261013T060000Z.json", "20261014T060000Z.json", "20261015T060000Z.json"]
    assert store.load("dalat", tmp_path)["day"] == "2026-10-15"
    assert store.load("nowhere", tmp_path) is None


def test_bulletin_sections_follow_item_order_and_flag_stale(tmp_path):
    store.write("dalat", snap(), keep=5, root=tmp_path)
    b = pulse.bulletin("dalat", now=at("2026-10-30"), root=tmp_path)
    assert [s["kind"] for s in b["sections"]] == ["hot", "season"] and b["stale"] is False
    assert b["sections"][0]["items"][0]["place_id"] == "p1"
    assert pulse.bulletin("dalat", now=at("2026-11-05"), root=tmp_path)["stale"] is True
    assert pulse.bulletin("nowhere", root=tmp_path) is None


def test_hot_label_is_display_only_and_expires(tmp_path):
    store.write("dalat", snap(), keep=5, root=tmp_path)
    assert pulse.hot("dalat", now=at("2026-10-30"), root=tmp_path) == {
        "p1": {"label": "Đang hot", "newest": "2026-10-27", "videos": 4, "authors": 3, "window_days": 30, "as_of": "2026-10-29"}}
    assert pulse.hot("dalat", now=at("2026-12-01"), root=tmp_path) == {}
    assert pulse.hot("nowhere", root=tmp_path) == {}


def test_trends_cites_sources_and_filters(tmp_path):
    store.write("dalat", snap(), keep=5, root=tmp_path)
    t = pulse.trends("dalat", now=at("2026-10-30"), root=tmp_path)
    assert t["as_of"] == "2026-10-29" and [i["kind"] for i in t["items"]] == ["hot", "season"]
    assert t["items"][0]["sources"] == [{"type": "tiktok_video", "label": "Video TikTok", "url": "https://t/1", "date": "2026-10-27"}]
    assert [i["kind"] for i in pulse.trends("dalat", kind="season", root=tmp_path)["items"]] == ["season"]
    assert pulse.trends("dalat", month=3, root=tmp_path)["items"][0]["kind"] == "hot"  # the season is not March's
    assert "tháng 10" in pulse.trends("dalat", month=3, root=tmp_path)["note"]
    assert pulse.trends("nowhere", root=tmp_path) is None


def test_signals_read_dates_in_city_time_and_skip_unusable_rows(tmp_path):
    poi = tmp_path / "tiktok" / "poi_crawl"
    poi.mkdir(parents=True)
    # 2026-10-27T18:00Z is already 28/10 in Vietnam (UTC+7)
    ts = int(datetime(2026, 10, 27, 18, tzinfo=UTC).timestamp())
    (poi / "a.json").write_text(json.dumps({"fid": "p1", "videos": [
        {"video_id": 1, "url": "u", "author_id": "x", "desc": "d", "created_at": ts}, {"video_id": 2, "author_id": "y"}]}))
    (poi / "b.json").write_text(json.dumps({"fid": "other", "videos": [{"video_id": 3, "author_id": "z", "created_at": ts}]}))
    out = signals.tiktok_videos(tmp_path, {"p1"}, 7)
    assert out == {"p1": [{"id": "1", "url": "u", "author": "x", "date": "2026-10-28", "text": "d"}]}
