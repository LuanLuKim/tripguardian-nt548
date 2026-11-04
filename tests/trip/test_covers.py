from trip.domain.covers import assign

PHOTO = {"a": "A.jpg", "b": "B.jpg", "c": "C.jpg", "d": "D.jpg"}


def test_cards_that_share_their_best_place_get_different_covers():
    groups = [["a", "b", "c"], ["a", "b"], ["a", "c", "d"]]
    out = assign(groups, PHOTO.get)
    assert len(set(out)) == 3 and None not in out


def test_the_smallest_group_picks_first_so_nobody_is_left_without():
    out = assign([["a", "b", "c"], ["a"]], PHOTO.get)
    assert out == ["B.jpg", "A.jpg"]


def test_a_place_without_a_photo_is_skipped_and_a_group_without_any_is_none():
    out = assign([["x", "a"], ["y"]], PHOTO.get)
    assert out == ["A.jpg", None]


def test_a_repeat_only_when_every_place_is_taken():
    out = assign([["a"], ["a"]], PHOTO.get)
    assert out == ["A.jpg", "A.jpg"]


def test_two_places_with_one_photo_are_one_cover():
    out = assign([["p", "q"], ["r"]], {"p": "S.jpg", "q": "S.jpg", "r": "S.jpg"}.get)
    assert out[0] == "S.jpg" and out[1] == "S.jpg"  # only one photo exists: unavoidable


def test_a_photo_that_shows_the_card_wins_over_a_better_ranked_place():
    views = {"b": "B-view.jpg"}
    out = assign([["a", "b"], ["a"]], PHOTO.get, fits=[views.get, None])
    assert out == ["B-view.jpg", "A.jpg"]


def test_a_card_with_no_fitting_photo_keeps_a_plain_one():
    assert assign([["a"]], PHOTO.get, fits=[{}.get]) == ["A.jpg"]
