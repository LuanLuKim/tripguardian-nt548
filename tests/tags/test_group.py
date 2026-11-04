"""corpus.tags.split: one axis chosen for a ranked set, evidence rules, the axes a query fixes (docs/PLACE_DECISION.md §Tag và subtag)."""

from corpus.tags import Fixed, PlaceTags, kinds, split
from corpus.tags.group import compose


def place(i, group="cafe", features=(), styles=(), dishes=()):
    return PlaceTags(f"p{i}", group, frozenset(features), frozenset(styles), frozenset(dishes))


def many(n, start, **kw):
    return [place(start + i, **kw) for i in range(n)]


def cloud_set():
    """20 places that all carry cloud_hunting, by Maps category."""
    return [p for g, n in (("cafe", 7), ("restaurant", 5), ("camping", 4), ("attraction", 4))
            for p in many(n, len(g) * 100, group=g, features={"cloud_hunting"})]


def test_a_category_split_names_the_kinds_with_the_fixed_feature():
    s = split(cloud_set(), Fixed(features=frozenset({"cloud_hunting"})))
    assert s.axis == "category" and s.covered == s.total == 20
    labels = {x.key: x.label for x in s.subtags}
    assert labels["cafe"] == "Quán cà phê săn mây"
    assert labels["camping"] == "Cắm trại, sáng dậy thấy mây"  # a configured override reads better than the composed one
    assert [x.count for x in s.subtags] == [7, 5, 4, 4] and all(x.id == f"category:{x.key}" for x in s.subtags)


def test_the_axis_the_query_fixed_is_never_a_split():
    places = cloud_set()
    assert split(places, Fixed(groups=frozenset({"cafe"}))) is None or split(places, Fixed(groups=frozenset({"cafe"}))).axis != "category"
    s = split([p for p in places for _ in (0,)], Fixed())
    assert s.axis == "category"  # nothing fixed: the category split is on offer
    only_feature = [place(i, group="cafe", features={"cloud_hunting", "sunset_view"} if i % 2 else {"cloud_hunting", "photo_spot"})
                    for i in range(12)]
    s = split(only_feature, Fixed(groups=frozenset({"cafe"}), features=frozenset({"cloud_hunting"})))
    assert s is None  # cloud_hunting is the query, and two features of six places each are not three groups


def test_experience_axis_splits_a_one_category_set_and_labels_with_the_noun():
    ps = many(8, 0, features={"scenic_view"}) + many(6, 20, features={"animals"}) + many(5, 40, features={"sunset_view"}) \
        + many(3, 60, features={"scenic_view", "animals"})
    s = split(ps, Fixed(groups=frozenset({"cafe"})))
    assert s.axis == "experience"
    assert {x.label for x in s.subtags} == {"Quán cà phê có view đẹp", "Quán cà phê có thú nuôi", "Quán cà phê ngắm hoàng hôn"}
    both = next(x for x in s.subtags if x.key == "scenic_view")
    assert set(both.place_ids) >= {"p60", "p61", "p62"}  # a place that carries two tags is in both lists


def test_unknown_is_not_a_group_and_leftovers_are_not_a_fake_group():
    ps = many(6, 0, features={"scenic_view"}) + many(6, 10, features={"animals"}) + many(6, 20, features={"sunset_view"}) \
        + many(7, 30)  # seven places with no evidence of any kind
    s = split(ps, Fixed(groups=frozenset({"cafe"})))
    assert s.total == 25 and s.covered == 18
    assert not {f"p{n}" for n in range(30, 37)} & {pid for x in s.subtags for pid in x.place_ids}
    assert all(x.key in ("scenic_view", "animals", "sunset_view") for x in s.subtags)  # no "other" subtag


def test_a_feature_held_by_most_of_the_set_is_no_split():
    ps = many(20, 0, features={"photo_spot"}) + many(4, 30, features={"animals"}) + many(4, 40, features={"hiking"})
    assert split(ps, Fixed(groups=frozenset({"cafe"}))) is None  # photo_spot holds 71%; the others cover too little


def test_a_set_too_small_or_too_lopsided_is_a_flat_list():
    assert split(cloud_set()[:8], Fixed()) is None  # fewer than min_places
    lop = many(30, 0, group="cafe") + many(3, 100, group="restaurant") + many(3, 200, group="attraction") + many(3, 300, group="spa")
    assert split(lop, Fixed()) is None  # 30 / 3 / 3 / 3: not an even split, and cafe holds more than max_share


def test_style_axis_and_the_parent_is_not_counted_with_its_child():
    ps = many(7, 0, styles={"retro_saigon", "retro"}) + many(6, 10, styles={"korean"}) + many(5, 20, styles={"minimal"}) \
        + many(3, 30, styles={"retro"})
    s = split(ps, Fixed(groups=frozenset({"cafe"})))
    assert s.axis == "style"
    keys = {x.key: x for x in s.subtags}
    assert keys["retro_saigon"].label == "Quán cà phê kiểu Sài Gòn xưa"
    assert "retro" not in keys or set(keys["retro"].place_ids) == {"p30", "p31", "p32"}  # only places without the finer tag


def test_dish_axis_for_a_food_set_and_finer_kinds_for_a_named_dish():
    food = many(6, 0, group="restaurant", dishes={"banh_can"}) + many(6, 10, group="restaurant", dishes={"nem_nuong"}) \
        + many(5, 20, group="restaurant", dishes={"pho"}) + many(4, 30, group="restaurant", dishes={"bun_bo"})
    s = split(food, Fixed())
    assert s.axis == "dish" and {x.label for x in s.subtags} == {"Bánh căn", "Nem nướng", "Phở", "Bún bò"}
    hot = many(6, 0, group="restaurant", dishes={"lau"}) + many(6, 10, group="restaurant", dishes={"lau", "lau_ga_la_e"}) \
        + many(5, 20, group="restaurant", dishes={"lau", "lau_thai"}) + many(5, 30, group="restaurant", dishes={"lau", "lau_thai", "lau_ga_la_e"})
    assert split(hot, Fixed(dish="lẩu")) is None  # two finer kinds are not enough groups, and "lẩu" is not a split of itself
    variants = {p.id: frozenset({"bo"}) for p in hot[:4] + hot[22:]}
    s = split(hot, Fixed(dish="lẩu"), variants)
    assert s.axis == "dish"
    assert {x.key for x in s.subtags} == {"lau_ga_la_e", "lau_thai", "v:bo"}
    assert next(x for x in s.subtags if x.key == "lau_thai").count == 10
    assert {x.label for x in s.subtags} >= {"Lẩu gà lá é", "Lẩu Thái", "Lẩu bò"}


def test_a_dish_query_splits_by_what_the_dish_comes_with():
    ps = many(14, 0, group="restaurant", dishes={"banh_can"})
    variants = {f"p{i}": frozenset({"trung_cut"} if i < 6 else {"xiu_mai"} if i < 11 else {"tom", "xiu_mai"} if i < 13 else {"tom"})
                for i in range(14)}
    s = split(ps, Fixed(dish="bánh căn"), variants)
    labels = {x.label for x in s.subtags}
    assert s.axis == "dish" and {"Bánh căn trứng cút", "Bánh căn xíu mại", "Bánh căn tôm"} <= labels
    assert split(ps, Fixed(dish="bánh căn")) is None  # no variant evidence: no split


def test_the_dish_axis_is_offered_only_for_a_set_of_eateries():
    nature = many(20, 0, group="nature", dishes={"banh_can"}) + many(6, 30, group="nature", dishes={"pho"}) + many(6, 50, group="nature", dishes={"bun_bo"})
    assert split(nature, Fixed(groups=frozenset({"nature"}))) is None


def test_a_feature_parent_does_not_split_by_unrelated_meals():
    ps = (many(6, 0, group="restaurant", features={"cloud_hunting"}, dishes={"banh_can"})
          + many(6, 10, group="restaurant", features={"cloud_hunting"}, dishes={"pho"})
          + many(6, 20, group="restaurant", features={"cloud_hunting"}, dishes={"bun_bo"}))
    assert split(ps, Fixed(features=frozenset({"cloud_hunting"}))) is None


def test_the_best_scoring_axis_wins():
    ps = [p for g, n in (("cafe", 6), ("restaurant", 6), ("camping", 6)) for p in many(n, len(g) * 100, group=g, features={"scenic_view"})]
    ps += many(3, 900, group="cafe", styles={"korean"})
    s = split(ps, Fixed(features=frozenset({"scenic_view"})))
    assert s.axis == "category" and s.score > 0.5


def test_labels_compose_from_the_fixed_context():
    f = Fixed(groups=frozenset({"cafe"}))
    assert compose("experience", "sunset_view", f) == "Quán cà phê ngắm hoàng hôn"
    assert compose("experience", "sunset_view", Fixed()) == "Ngắm hoàng hôn"
    assert compose("experience", "sunrise_view", Fixed()) == "Đón bình minh"
    assert compose("style", "korean", Fixed()) == "Không gian kiểu Hàn"
    assert compose("category", "nature", Fixed(features=frozenset({"sunset_view"}))) == "Điểm thiên nhiên ngắm hoàng hôn"
    assert compose("category", "restaurant", Fixed(dish="bánh căn")) == "Quán ăn có món bánh căn"


def test_features_every_place_has_are_not_a_split():
    """Five features, each on most places: the groups overlap so much that no place says which kind it is."""
    feats = ["scenic_view", "animals", "sunset_view", "photo_spot", "hiking"]
    ps = [place(i, features=set(feats[: 3 + i % 2])) for i in range(30)]
    assert split(ps, Fixed(groups=frozenset({"cafe"}))) is None


def test_a_noun_that_already_says_the_feature_is_not_repeated():
    assert compose("category", "camping", Fixed(features=frozenset({"camping"}))) == "Khu cắm trại"
    assert compose("category", "cafe", Fixed(features=frozenset({"camping"}))) == "Quán cà phê cắm trại được"


def test_kinds_are_the_biggest_tags_a_few_per_axis_and_none_held_by_most():
    places = (many(12, 100, group="cafe", features={"cloud_hunting"}) + many(10, 200, group="restaurant")
              + many(8, 300, group="nature", features={"scenic_view"}) + many(6, 400, group="attraction"))
    got = kinds(places)
    assert got.axis == "tags" and got.total == 36
    assert [s.id for s in got.subtags][:3] == ["category:cafe", "category:restaurant", "category:nature"]
    assert "experience:scenic_view" not in {s.id for s in got.subtags}  # the same places as "nature": a repeat
    assert "experience:cloud_hunting" not in {s.id for s in got.subtags}  # the same places as the cafes
    assert len(got.subtags) <= 6 and got.subtags[0].label == "Quán cà phê"
    assert "category:cafe" not in {s.id for s in kinds(places, skip=["category:cafe"]).subtags}  # a picked kind is not offered again


def test_kinds_need_enough_places_and_kinds():
    assert kinds(many(8, 0, group="cafe")) is None  # too few places
    assert kinds(many(20, 0, group="cafe") + many(8, 50, group="nature")) is None  # one kind holds most, one is too few


def test_kinds_leave_out_plain_features():
    places = many(12, 100, group="cafe", features={"cozy_decor"}) + many(10, 200, group="restaurant") + many(10, 300, group="nature") + many(8, 400, group="attraction")
    assert "experience:cozy_decor" not in {s.id for s in kinds(places).subtags}  # home: false in config/tags.yaml
