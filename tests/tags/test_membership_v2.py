"""Travel-motive tags are stricter than feature mentions or dish lookup."""
import pytest

from corpus import tags
from corpus.serving import dishes


def record(name="Test cafe", feature="animals", n=1, rate=.003, quote=""):
    return {"id": "test:place", "identity": {"name": name, "category_group": "cafe"},
            "experience": {feature: {"value": "present", "status": "VERIFIED", "n": n,
                                      "mention_rate": rate, "evidence": ["review:1"], "quote": quote}}}


@pytest.mark.parametrize("name,quote,feature", [
    ("oday bar", "trước quán có nhiều chuột to lắm!", "animals"),
    ("Nhà Hàng Chay Từ Hạnh", "chó mèo bẩn thỉu chạy lung tung giữa các bàn", "animals"),
    ("Quán Chay Gấu Trúc", "cho em cún của mình 1 chén nước", "animals"),
    ("Cloud cafe", "mưa khó săn mây", "cloud_hunting"),
    ("Phê La", "cực kỳ nhiều cây xanh", "nature"),
])
def test_unjudged_single_mentions_are_not_travel_motives(name, quote, feature):
    assert feature not in tags.of_record(record(name, feature, quote=quote)).features


def test_unjudged_fallback_needs_both_count_and_rate():
    assert "animals" not in tags.of_record(record(n=3, rate=.009)).features
    assert "animals" not in tags.of_record(record(n=2, rate=.02)).features
    assert "animals" in tags.of_record(record(n=3, rate=.01)).features


@pytest.mark.parametrize("text", ["bánh nướng", "Bánh mì nướng bơ caramel", "Trà sữa nướng", "Trà nướng"])
def test_grill_tag_never_means_baked_pastry_or_roasted_tea(text):
    r = record()
    r["identity"]["category_group"] = "restaurant"
    r["menu"] = {"dishes": [{"name": text, "popular": True}]}
    assert "nuong" not in tags.of_record(r).dishes


def test_dish_lookup_stays_broader_than_discovery_tags():
    r = record()
    r["menu"] = {"dishes": [{"name": "Lẩu gà lá é"}]}
    assert dishes.search([r], "lẩu gà lá é")
    assert "lau_ga_la_e" not in tags.of_record(r).dishes


def test_tag_category_overlay_does_not_change_maps_group():
    r = record("Karaoke ABC")
    r["identity"]["category_group"] = "bar"
    assert tags.of_record(r).group == "karaoke"
    assert r["identity"]["category_group"] == "bar"
    r["identity"].update(name="Bánh Căn Nhà Cổ", category_group="dessert")
    assert tags.of_record(r).group == "restaurant"


def test_religious_places_do_not_receive_cafe_decor_styles():
    r = record("Chùa Trúc Lâm")
    r["identity"]["category_group"] = "religious"
    assert not tags.of_record(r, ["korean", "boho", "minimal"]).styles


def test_unknown_old_ref_can_be_resolved_without_breaking_saved_trip():
    assert tags.resolve_ref("experience:heritage_architecture") == ("experience", "historical_site")
    assert tags.resolve_ref("experience:removed_unknown") is None


def test_no_mechanical_subtags_for_animals_at_temples():
    ps = [tags.PlaceTags(str(i), g, frozenset({"animals"})) for g in ("religious", "bar", "museum") for i in range(6)]
    assert tags.split(ps, tags.Fixed(features=frozenset({"animals"}))) is None


@pytest.mark.parametrize("group", ["bar", "shop", "religious"])
def test_category_parent_does_not_reintroduce_unapproved_experience_pairs(group):
    ps = [tags.PlaceTags(f"{feature}:{i}", group, frozenset({feature}))
          for feature in ("animals", "long_stay_chill", "hiking") for i in range(6)]
    assert tags.split(ps, tags.Fixed(groups=frozenset({group}))) is None


def test_style_parent_only_splits_into_design_relevant_categories():
    ps = [tags.PlaceTags(f"{group}:{i}", group, styles=frozenset({"minimal"}))
          for group in ("religious", "nature", "museum") for i in range(6)]
    assert tags.split(ps, tags.Fixed(styles=frozenset({"minimal"}))) is None
