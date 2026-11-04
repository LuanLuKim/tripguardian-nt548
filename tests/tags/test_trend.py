"""corpus.tags.trending: tags ranked by the TikTok clips of the last 30 days (home page topics)."""

from datetime import date

from corpus.tags import PlaceTags, trending

TODAY = date(2026, 10, 30)


def clip(i, author, day="2026-10-20"):
    return {"id": f"v{i}", "author": author, "date": day}


def world():
    """30 places with cloud_hunting (8 also korean), 4 with sunset_view (too few), 200 with nothing."""
    places = [PlaceTags(f"p{i}", "cafe", frozenset({"cloud_hunting"}), frozenset({"korean"} if 10 <= i < 18 else ()), frozenset())
              for i in range(30)]
    places += [PlaceTags(f"s{i}", "cafe", frozenset({"sunset_view"})) for i in range(4)]
    return places + [PlaceTags(f"z{i}", "spa") for i in range(200)]


def test_ranks_by_clips_tempered_by_size_and_counts_distinct_clips_and_posters():
    videos = {f"p{i}": [clip(i * 10 + j, f"a{i}{j}") for j in range(2)] for i in range(10)}  # 20 clips on cloud places
    videos["p10"] = [clip(900, "a1"), clip(900, "a1")] + [clip(901 + j, f"b{j}") for j in range(7)]  # a clip twice counts once
    out = trending(world(), videos, TODAY)
    top = out[0]
    assert top["ref"] == "experience:cloud_hunting" and top["clips"] == 28 and top["places"] == 30
    korean = next(t for t in out if t["ref"] == "style:korean")
    assert korean["clips"] == 8 and korean["authors"] == 8  # the same clip id at one place: one clip
    assert top["top"] and top["top"][0].startswith("p")
    assert top["newest"] == "2026-10-20" and top["label"] == "Săn mây"


def test_old_clips_do_not_count_and_thin_tags_are_dropped():
    old = {f"p{i}": [clip(i, f"a{i}", day="2026-08-01")] for i in range(10)}
    assert trending(world(), old, TODAY) == []
    few = {f"s{i}": [clip(i + 500, f"z{i}")] for i in range(4)}  # 4 places: under min_places
    assert all(t["ref"] != "experience:sunset_view" for t in trending(world(), few, TODAY))
    one_poster = {f"p{i}": [clip(i + 700, "same")] for i in range(10)}
    assert trending(world(), one_poster, TODAY) == []  # one account posting is not a trend


def test_a_tag_held_by_most_places_is_no_topic_and_generic_tags_are_skipped():
    common = [PlaceTags(f"c{i}", "cafe", frozenset({"photo_spot"})) for i in range(60)] + [PlaceTags(f"z{i}", "spa") for i in range(100)]
    videos = {f"c{i}": [clip(i, f"a{i}"), clip(i + 100, f"b{i}")] for i in range(60)}
    refs = [t["ref"] for t in trending(common, videos, TODAY)]
    assert "experience:photo_spot" not in refs and "category:cafe" not in refs  # 60 and 60 of 160 places: no topic
    generic = [PlaceTags(f"g{i}", "restaurant", frozenset(), frozenset(), frozenset({"com"})) for i in range(30)] \
        + [PlaceTags(f"h{i}", "cafe") for i in range(100)]
    vids = {f"g{i}": [clip(i + 1000, f"g{i}")] for i in range(30)}
    assert all(t["ref"] != "dish:com" for t in trending(generic, vids, TODAY))  # config: home false


def test_retired_or_unknown_membership_keys_never_become_trending_topics():
    places = [PlaceTags(f"p{i}", "cafe", frozenset({"heritage_architecture", "removed_unknown"}))
              for i in range(8)] + [PlaceTags(f"q{i}", "spa") for i in range(80)]
    videos = {f"p{i}": [clip(i * 3 + j, f"a{i}{j}") for j in range(3)] for i in range(8)}
    assert not [t for t in trending(places, videos, TODAY) if t["axis"] == "experience"]


def test_each_axis_has_a_cap():
    places = [PlaceTags(f"p{i}", "cafe", frozenset({"cloud_hunting", "sunset_view", "flower_garden", "scenic_view", "hiking", "camping"}))
              for i in range(8)] + [PlaceTags(f"q{i}", "spa") for i in range(80)]  # 8 of 88 places carry six tags
    videos = {f"p{i}": [clip(i * 3 + j, f"a{i}{j}") for j in range(3)] for i in range(8)}
    out = trending(places, videos, TODAY)
    assert sum(t["axis"] == "experience" for t in out) == 4 and len(out) <= 8
