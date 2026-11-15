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
    s = sig(claims=[claim("season", "cỏ", [10])], videos={"p1": [video(1, "a", "2026-10-27", "cỏ xanh đẹp")]})
    assert compute.seasons(s, CFG, NOW, city_name="Đà Lạt")[0]["signals"]["latest_video"] is None


def test_one_season_however_pages_name_it_the_most_sources_first_and_no_weather_or_place_best_time():
    s = sig(claims=[claim("season", "hoa dã quỳ", [10, 11], sources=47), claim("best_time", "Mùa hoa dã quỳ ở Đà Lạt", [10], sources=15),
                    claim("season", "săn mây ở Đà Lạt", [10], status="kept", sources=2),
                    claim("season", "Mùa khô", [10, 11], sources=10), claim("season", "hồng", [10], sources=9),
                    claim("best_time", "Thác Datanla", [10], subject_kind="poi", sources=11),
                    claim("season", "Làng hoa Vạn Thành", [10], subject_kind="poi", status="kept", sources=4)])
    items = compute.seasons(s, CFG, NOW, city_name="Đà Lạt")
    assert [i["subject"]["name"] for i in items] == ["hoa dã quỳ", "Làng hoa Vạn Thành", "săn mây ở Đà Lạt"]
    assert items[0]["signals"]["sources"] == 47 and items[0]["signals"]["status"] == "unverified"


# ---- trending: one 0-100 score over every signal ----

def place(name, group="cafe", direction=None):
    return {"name": name, "category": "x", "group": group, "area": "a1", "rating_direction": direction}


def clips(prefix, n, day="2026-10-20"):
    return [video(f"{prefix}{i}", f"{prefix}-a{i}", day) for i in range(n)]


def test_trending_ranks_by_score_not_by_source_order():
    s = sig(places={"hot": place("Hot"), "warm": place("Warm"), "cold": place("Cold")},
            videos={"hot": clips("h", 8, "2026-10-27"), "warm": clips("w", 6), "cold": clips("c", 2)})
    items = compute.trending(s, CFG, NOW)
    assert [i["subject"]["id"] for i in items] == ["hot", "warm"]  # "cold": 2 authors is not a crowd
    assert items[0]["signals"]["score"] > items[1]["signals"]["score"] >= CFG["trending"]["min_score"]
    assert items[0]["signals"]["tiktok_recent_authors"] == 8


def test_trending_momentum_lifts_a_place_with_the_same_volume():
    s = sig(places={"new": place("New"), "old": place("Old")}, videos={"new": clips("n", 6, "2026-10-28"), "old": clips("o", 6, "2026-10-05")})
    ids = [i["subject"]["id"] for i in compute.trending(s, CFG, NOW)]
    assert ids == ["new", "old"]


def test_trending_reviews_count_against_the_places_own_history():
    revs = lambda n: [review("2026-10-2%d" % (i % 9), f"r{i}") for i in range(n)]
    s = sig(places={"big": place("Big", direction="rising"), "small": place("Small", direction="rising")},
            reviews={"big": revs(30), "small": revs(30)}, review_totals={"big": 30000, "small": 300})
    items = compute.trending(s, CFG, NOW)
    assert [i["subject"]["id"] for i in items] == ["small"]  # 30 of 30000 is a busy month of a busy place, 30 of 300 is a jump


def test_trending_never_ranks_a_place_to_stay_or_a_place_without_evidence():
    s = sig(places={"inn": place("Inn", group="stay")}, videos={"inn": clips("i", 8, "2026-10-27")})
    assert compute.trending(s, CFG, NOW) == []
    assert compute.trending(sig(), CFG, NOW) == []
    for i in compute.trending(sig(places={"p1": place("Quán Một")}, videos={"p1": clips("p", 5)}), CFG, NOW):
        assert i["evidence"]  # an item without evidence is never made


def test_dated_web_events_replace_the_month_only_claims():
    from datetime import date
    from corpus.pulse import compute
    now = date(2026, 11, 13)
    cfg = {"event": {"horizon_days": 45, "max_items": 2, "web_fresh_days": 3}}
    web = {"day": "2026-11-13", "events": [
        {"name": "Festival Âm nhạc quốc tế Lang Biang", "start": "2026-11-13", "end": "2026-11-15", "time": "19:00",
         "venue": "Quảng trường Lâm Viên", "summary": "Đêm chính 14/11", "image": "",
         "sources": [{"url": "https://a.vn", "domain": "a.vn", "quote": "q", "read": "2026-11-13"},
                     {"url": "https://b.vn", "domain": "b.vn", "quote": "q", "read": "2026-11-13"}]},
        {"name": "Acoustic dưới tán anh đào", "start": "2026-11-14", "end": "2026-11-14", "time": "", "venue": "", "summary": "",
         "image": "", "sources": [{"url": "https://c.vn", "domain": "c.vn", "quote": "q", "read": "2026-11-13"}]},
        {"name": "Giải chạy vì Đà Lạt xanh", "start": "2026-11-21", "end": "2026-11-21", "time": "", "venue": "",
         "summary": "", "image": "", "sources": [{"url": "https://d.vn", "domain": "d.vn", "quote": "q", "read": "2026-11-13"}]},
        {"name": "Hội chợ đã qua", "start": "2026-11-01", "end": "2026-11-03", "time": "", "venue": "", "summary": "",
         "image": "", "sources": [{"url": "https://e.vn", "domain": "e.vn", "quote": "q", "read": "2026-11-13"}]}]}
    claim = {"kind": "event", "status": "kept", "when": {"months": [11]}, "evidence": [{}], "subject": "phường Lang Biang",
             "claim_id": "x", "sources": 1, "text": ""}
    items = compute.events({"holidays": [], "claims": [claim], "events": web}, cfg, now, "Đà Lạt")
    # the two-site festival and the race (a festive word) beat a one-site acoustic set; the claim and the past fair go
    assert [i["subject"]["name"] for i in items] == ["Festival Âm nhạc quốc tế Lang Biang", "Giải chạy vì Đà Lạt xanh"]
    assert all(i["signals"]["source"] == "web" for i in items) and items[0]["dates"] == {"from": "2026-11-13", "to": "2026-11-15"}
    # the fields a claim event carries, so a reader built before dated events still renders it (prod's frozen render)
    assert items[0]["signals"]["status"] == "confirmed" and items[0]["signals"]["months"] == [11]
    assert items[0]["signals"]["sources"] == 2


def test_a_season_reads_a_pages_own_sentence_and_the_picture_found_for_it():
    long = "Nếu muốn ngắm hoa Mimosa đẹp nhất thì tháng 10 sẽ là một khoảng thời gian hợp lý cho bạn đấy."
    c = claim("season", "hoa Mimosa", [10], status="kept", text="ngắn")
    c["evidence"].append({**c["evidence"][0], "quote": long})
    shot = {"name": "hoa Mimosa", "image": "https://mia.vn/m.jpg", "image_from": {"url": "https://mia.vn/m", "domain": "mia.vn"}}
    s = sig(claims=[c], events={"day": "2026-10-29", "events": [], "seasons": {"hoa mimosa": shot}})
    it = compute.seasons(s, CFG, NOW, city_name="Đà Lạt")[0]
    assert it["signals"]["summary"] == long           # "ngắn" is too short to say anything
    assert it["signals"]["image"] == "https://mia.vn/m.jpg" and it["signals"]["image_from"]["domain"] == "mia.vn"


def test_a_season_without_a_fitting_quote_or_picture_has_neither():
    it = compute.seasons(sig(claims=[claim("season", "Dã quỳ", [10], status="kept", text="ngắn")]), CFG, NOW)[0]
    assert "summary" not in it["signals"] and "image" not in it["signals"]


def test_months_read_as_a_run_even_across_the_new_year():
    from corpus.pulse.render import months
    assert [months(m) for m in ([11], [8, 9, 10, 11, 12], [1, 10, 11, 12], [3, 7])] == \
        ["tháng 11", "tháng 8–12", "tháng 10–1", "tháng 3, 7"]


def test_a_season_is_seen_at_the_places_its_pages_name_beside_it_not_at_common_names_or_cafes():
    pad = " ".join(["chữ"] * 200)
    pages = {f"d{i}": f"Mùa dã quỳ nở vàng trên Đèo Prenn và quanh Thung Lũng Vàng. {pad} Rừng thông" for i in range(3)}
    pages |= {f"o{i}": f"Rừng thông ở khắp nơi. Quán Dã Quỳ Coffee rất đẹp. {pad}" for i in range(20)}
    places = {"prenn": {"name": "Đèo Prenn", "group": "nature"}, "tlv": {"name": "Thung Lũng Vàng", "group": "attraction"},
              "rung": {"name": "Rừng thông", "group": "attraction"}, "cafe": {"name": "Dã Quỳ Coffee", "group": "cafe"},
              "doi": {"name": "Đồi Dã Quỳ Xanh", "group": "attraction"}}
    s = sig(places=places, documents=pages)
    assert compute.see_places(s, "da quy", {"d0", "d1", "d2"}) == ["doi", "prenn", "tlv"]
