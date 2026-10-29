from datetime import date

import yaml
from pathlib import Path

from corpus.pulse import compute

CFG = yaml.safe_load((Path(__file__).resolve().parents[2] / "config" / "pulse.yaml").read_text(encoding="utf-8"))
NOW = date(2026, 10, 29)


def video(i, author, day, text=""):
    return {"id": f"v{i}", "url": f"https://tiktok.test/{i}", "author": author, "date": day, "text": text}


def sig(**kw):
    base = {"places": {"p1": {"name": "Quán Một", "category": "Cà phê", "area": "a1", "rating_direction": None}},
            "videos": {}, "reviews": {}, "review_totals": {}, "web": {}, "status": {}, "claims": [], "holidays": []}
    base.update(kw)
    return base


def test_hot_needs_distinct_authors_and_videos_in_window():
    vids = [video(1, "a", "2026-10-27"), video(2, "b", "2026-10-20"), video(3, "c", "2026-10-02"), video(4, "a", "2026-10-01")]
    items = compute.hot(sig(videos={"p1": vids}), CFG, NOW)
    assert [i["id"] for i in items] == ["hot:p1"]
    s = items[0]["signals"]
    assert (s["videos"], s["authors"], s["newest"], s["window_days"]) == (4, 3, "2026-10-27", 30)
    assert {e["id"] for e in items[0]["evidence"]} == {"v1", "v2", "v3", "v4"}


def test_hot_drops_old_videos_and_two_authors():
    vids = [video(1, "a", "2026-10-27"), video(2, "b", "2026-10-26"), video(3, "c", "2026-08-01")]
    assert compute.hot(sig(videos={"p1": vids}), CFG, NOW) == []


def test_hot_ignores_places_outside_the_corpus():
    vids = [video(i, f"a{i}", "2026-10-27") for i in range(4)]
    assert compute.hot(sig(videos={"zzz": vids}), CFG, NOW) == []


def review(day, author, stars=5):
    return {"date": day, "author": author, "stars": stars}


def test_top_needs_two_sources():
    revs = [review("2026-10-2%d" % (i % 9), f"r{i}") for i in range(12)]
    only_reviews = compute.top(sig(reviews={"p1": revs}), CFG, NOW)
    assert only_reviews == []
    vids = [video(1, "a", "2026-10-27"), video(2, "b", "2026-10-26")]
    items = compute.top(sig(reviews={"p1": revs}, videos={"p1": vids}), CFG, NOW)
    assert len(items) == 1 and items[0]["kind"] == "top"
    assert items[0]["signals"]["sources"] == ["tiktok", "reviews"]
    assert items[0]["signals"]["reviews"]["authors"] == 12


def test_top_counts_rising_rating_and_web_domains_without_dates():
    s = sig(web={"p1": ["a.vn", "b.vn"]})
    s["places"]["p1"]["rating_direction"] = "rising"
    items = compute.top(s, CFG, NOW)
    assert items[0]["signals"]["sources"] == ["rating_up", "web"]
    assert items[0]["signals"]["web_domains"] == ["a.vn", "b.vn"]


def test_new_requires_full_coverage_and_recent_first_review():
    revs = [review("2026-10-10", "a"), review("2026-10-20", "b"), review("2026-10-25", "c")]
    items = compute.new(sig(reviews={"p1": revs}, review_totals={"p1": 3}), CFG, NOW)
    assert items[0]["signals"] == {"first_review": "2026-10-10", "reviews": 3, "total": 3, "exact": True}
    assert compute.new(sig(reviews={"p1": revs}, review_totals={"p1": 40}), CFG, NOW) == []
    old = [review("2026-01-10", "a")] * 3
    assert compute.new(sig(reviews={"p1": old}, review_totals={"p1": 3}), CFG, NOW) == []


def test_closed_only_known_places_and_marks_new_since_last_run():
    st = {"x": {"name": "Quán Cũ", "status": "Bị đóng vĩnh viễn", "as_of": "2026-10-13", "reviews": 120},
          "y": {"name": "Nhỏ", "status": "Bị đóng vĩnh viễn", "as_of": "2026-10-13", "reviews": 4},
          "z": {"name": "Mở", "status": "Đang mở", "as_of": "2026-10-13", "reviews": 500}}
    first = compute.closed(sig(status=st), CFG, NOW, previous=None)
    assert [i["id"] for i in first] == ["closed:x"] and first[0]["signals"]["new_since_last"] is None
    again = compute.closed(sig(status=st), CFG, NOW, previous={"items": [{"id": "closed:x"}]})
    assert again[0]["signals"]["new_since_last"] is False
    fresh = compute.closed(sig(status=st), CFG, NOW, previous={"items": []})
    assert fresh[0]["signals"]["new_since_last"] is True


def claim(kind, subject, months, status="unverified", sources=1, subject_kind="phenomenon", text="quote"):
    return {"claim_id": f"c-{subject}", "kind": kind, "subject": subject, "subject_kind": subject_kind, "status": status,
            "when": {"months": months, "days": []}, "sources": sources, "confidence": 0.9, "text": text,
            "evidence": [{"doc_id": "d", "source_url": "https://x.vn/a", "domain": "x.vn", "retrieved_at": "2026-10-28T09:00:00+00:00", "quote": text}]}


def test_events_from_holidays_and_dated_claims_inside_horizon():
    s = sig(holidays=[{"date": "2026-11-20", "name": "Ngày Nhà giáo"}, {"date": "2026-12-25", "name": "Giáng sinh"}],
            claims=[claim("event", "Festival Hoa", [12], status="kept"), claim("event", "Cỏ hồng", []),
                    claim("event", "Cũ", [3])])
    items = compute.events(s, CFG, NOW)
    assert [i["subject"]["name"] for i in items] == ["Ngày Nhà giáo", "Festival Hoa"]
    assert items[0]["dates"]["on"] == "2026-11-20"
    assert items[1]["evidence"][0]["url"] == "https://x.vn/a"


def test_season_current_month_best_claim_per_subject_and_latest_video():
    s = sig(claims=[claim("season", "Dã quỳ", [10, 11], status="kept", sources=3),
                    claim("season", "Dã quỳ", [10], status="unverified"),
                    claim("season", "Đà Lạt", [10], subject_kind="city"),
                    claim("season", "Cỏ hồng", [11, 12]),
                    claim("season", "Xung đột", [10], status="conflict")],
            videos={"p1": [video(1, "a", "2026-10-25", "Dã quỳ nở rộ ở Đà Lạt"), video(2, "b", "2026-10-28", "dã quỳ đẹp quá")]})
    items = compute.seasons(s, CFG, NOW, city_name="Đà Lạt")
    assert [i["subject"]["name"] for i in items] == ["Dã quỳ"]
    it = items[0]
    assert it["signals"]["months"] == [10, 11] and it["signals"]["sources"] == 3
    assert it["signals"]["latest_video"] == {"id": "v2", "date": "2026-10-28", "url": "https://tiktok.test/2"}


def test_no_evidence_no_item():
    s = sig()
    assert compute.build(s, CFG, NOW, city_name="Đà Lạt") == []


def test_event_named_only_by_the_city_is_dropped():
    s = sig(claims=[claim("event", "Đà Lạt", [12])])
    assert compute.events(s, CFG, NOW, city_name="Đà Lạt") == []


def test_short_season_subject_gets_no_video():
    s = sig(claims=[claim("season", "hồng", [10])], videos={"p1": [video(1, "a", "2026-10-27", "màu hồng đẹp")]})
    assert compute.seasons(s, CFG, NOW, city_name="Đà Lạt")[0]["signals"]["latest_video"] is None
