"""corpus.pulse.signals reading the reviews `gmaps refresh` wrote beside the first crawl's."""

import json

from corpus.pulse import signals

FID = "0x1:0x2"


def write(path, doc):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")


def test_refreshed_reviews_join_the_first_crawls_one_row_per_author_and_the_count_maps_shows_now(tmp_path):
    write(tmp_path / "gmaps" / "observations" / "0x1_0x2.json", {"ratings": [
        {"author": "a", "observed_at": "2026-09-01", "stars": 3}, {"author": "b", "observed_at": "2026-08-01", "stars": 5}]})
    write(tmp_path / "gmaps" / "reviews_recent" / "0x1_0x2.json", {
        "at": "2026-11-15T05:00:00+00:00", "fid": FID, "review_count": "1.250 bài đánh giá", "status": None,
        "reviews": [{"author_hash": "a", "rating": "5/5", "published_text": "3 tuần trước trên Google"},
                    {"author_hash": "c", "rating": "4/5", "published_text": "2 ngày trước"},
                    {"author_hash": "d", "rating": "", "published_text": "1 ngày trước"}]})
    write(tmp_path / "gmaps" / "places" / "0x1_0x2" / "place.json", {"fid": FID, "name": "Quán", "reviews": 1200})
    rows = {r["author"]: r for r in signals.maps_reviews(tmp_path, {FID})[FID]}
    assert rows["a"] == {"date": "2026-10-25", "author": "a", "stars": 5}      # the later reading wins
    assert rows["c"]["date"] == "2026-11-13" and rows["b"]["stars"] == 5 and "d" not in rows   # no stars: no row
    totals, status = signals.maps_places(tmp_path, {FID}, 7)
    assert totals == {FID: 1250} and status == {}


def test_a_place_maps_now_shows_closed_is_closed_as_of_the_refresh(tmp_path):
    write(tmp_path / "gmaps" / "places" / "0x1_0x2" / "place.json", {"fid": FID, "name": "Quán", "reviews": 80})
    write(tmp_path / "gmaps" / "reviews_recent" / "0x1_0x2.json", {"at": "2026-11-15T05:00:00+00:00", "fid": FID,
                                                                  "status": signals.CLOSED, "reviews": []})
    _, status = signals.maps_places(tmp_path, {FID}, 7)
    assert status[FID]["as_of"] == "2026-11-15" and status[FID]["reviews"] == 80
