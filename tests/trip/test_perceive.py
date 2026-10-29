"""Pure reading of what a user shows or pastes (src/trip/domain/perceive.py): links and who a photo shows."""

import pytest

from trip.domain.perceive import (pick_name, clean_names, clean_text, decide_identity, fid_of_cid, parse_link)

FID = "0x317112ab5cd1:0x3a5b9c01"


@pytest.mark.parametrize("url,kind,fid", [
    (f"https://www.google.com/maps/place/Ph%C3%AA+Cafe/@11.94,108.44,17z/data=!3m1!4b1!4m6!3m5!1s{FID}!8m2", "maps", FID),
    (f"https://www.google.com/maps/place/Ph%C3%AA/data=!4m2!3m1!1s{FID}", "maps", FID),
    ("https://maps.google.com/?cid=4202139649", "maps", None),
    ("https://www.google.com/maps/search/cafe+da+lat/@11.9,108.4,14z", "maps", None),
    ("https://maps.app.goo.gl/AbCd123", "maps", None),
])
def test_maps_links(url, kind, fid):
    link = parse_link(url)
    assert link.kind == kind and link.fid == fid


def test_maps_link_keeps_the_place_name_and_cid():
    link = parse_link("https://www.google.com/maps/place/Ph%C3%AA+Cafe/@11.94,108.44,17z/data=!4m2")
    assert link.name == "Phê Cafe"
    cid = parse_link("https://maps.google.com/?cid=4202139649")
    assert cid.cid == "4202139649"
    assert parse_link("https://www.google.com/maps?q=Pho+Bo+Da+Lat").name == "Pho Bo Da Lat"


def test_short_links_need_a_redirect_first():
    assert parse_link("https://maps.app.goo.gl/AbCd123").short is True
    assert parse_link("https://vt.tiktok.com/ZSabc/").short is True
    assert parse_link("https://www.google.com/maps/place/X/@1,2,3z").short is False


def test_tiktok_links():
    link = parse_link("https://www.tiktok.com/@dalatfood/video/7565853238147255573?lang=vi-VN")
    assert link.kind == "tiktok" and link.video_id == "7565853238147255573"
    assert parse_link("https://www.tiktok.com/@a/photo/123").kind == "tiktok"
    assert parse_link("https://www.tiktok.com/discover/an-gi-da-lat").video_id is None


def test_other_links():
    assert parse_link("https://dalat.vn/diem-den/ho-xuan-huong").kind == "web"
    assert parse_link("https://www.instagram.com/p/xyz/").kind == "social"
    assert parse_link("https://www.facebook.com/x/posts/1").kind == "social"
    assert parse_link("javascript:alert(1)").kind == "bad"
    assert parse_link("http://127.0.0.1/admin").kind == "bad"
    assert parse_link("not a link").kind == "bad"


def test_cid_is_the_second_half_of_the_fid():
    assert fid_of_cid("4202430465", ["0xa:0xfa7c0001", "0xb:0x1"]) == "0xa:0xfa7c0001"
    assert fid_of_cid("999", ["0xb:0x1"]) is None
    assert fid_of_cid("not a number", ["0xb:0x1"]) is None


# ---------- who a photo shows ----------

def test_pixel_match_alone_is_sure_for_a_camera_photo():
    r = decide_identity(shows="A", pixel=[("A", .9), ("B", .8)], named=[], screenshot=False, shown=set())
    assert r.sure and r.place_id == "A" and r.source == "pixel"


def test_name_read_in_a_screenshot_is_sure_without_pixels():
    r = decide_identity(shows=None, pixel=[("X", .7)], named=[("A", 1.0)], screenshot=True, shown=set())
    assert r.sure and r.place_id == "A" and r.source == "name"


def test_a_screenshot_without_a_name_is_never_sure_by_pixels():
    r = decide_identity(shows="A", pixel=[("A", .9)], named=[], screenshot=True, shown=set())
    assert not r.sure and r.place_id is None and r.candidates == ("A",)


def test_a_screenshot_of_a_place_the_app_just_showed_is_that_place():
    r = decide_identity(shows="A", pixel=[("A", .9)], named=[], screenshot=True, shown={"A"})
    assert r.sure and r.place_id == "A" and r.source == "shown"


def test_name_and_pixels_agree():
    r = decide_identity(shows="A", pixel=[("A", .9)], named=[("A", .9)], screenshot=False, shown=set())
    assert r.sure and r.source == "name+pixel"


def test_name_and_pixels_disagree_ask():
    r = decide_identity(shows="B", pixel=[("B", .9)], named=[("A", 1.0)], screenshot=False, shown=set())
    assert not r.sure and r.place_id is None and set(r.candidates) == {"A", "B"}


def test_a_screenshot_name_is_not_vetoed_by_its_interface_pixels():
    r = decide_identity(shows="B", pixel=[("B", .9)], named=[("A", 1.0)], screenshot=True, shown=set())
    assert r.sure and r.place_id == "A"


def test_two_close_names_are_not_sure():
    r = decide_identity(shows=None, pixel=[], named=[("A", .85), ("B", .8)], screenshot=True, shown=set())
    assert not r.sure and r.candidates == ("A", "B")


def test_a_whole_name_written_exactly_is_sure_even_when_a_shorter_place_name_sits_inside_it():
    # "Tiệm Nướng Trạm Ký Ức" is written in full; "Trạm Ký Ức" is another place whose name is part of it (score 0.8)
    r = decide_identity(shows=None, pixel=[], named=[("A", 1.0), ("B", 0.8)], screenshot=True, shown=set())
    assert r.sure and r.place_id == "A"
    # two places with the very same name are still not sure
    r = decide_identity(shows=None, pixel=[], named=[("A", 1.0), ("B", 1.0)], screenshot=True, shown=set())
    assert not r.sure and r.place_id is None


def test_a_screen_with_several_place_cards_is_never_sure_of_one_place():
    # the reader wrote only one name of a carousel / list / grid: the user may mean any card
    r = decide_identity(shows=None, pixel=[], named=[("A", 1.0)], screenshot=True, shown=set(), several=True)
    assert not r.sure and r.place_id is None and r.candidates == ("A",)
    r = decide_identity(shows="B", pixel=[("B", .9)], named=[("A", 1.0), ("C", .9)], screenshot=True, shown={"B"}, several=True)
    assert not r.sure and r.place_id is None and set(r.candidates) == {"A", "C", "B"}


def test_several_cards_do_not_change_a_camera_photo():
    r = decide_identity(shows="A", pixel=[("A", .9)], named=[], screenshot=False, shown=set(), several=True)
    assert r.sure and r.place_id == "A"


def test_a_weak_name_is_a_candidate_not_a_name():
    r = decide_identity(shows=None, pixel=[], named=[("A", .5)], screenshot=True, shown=set())
    assert not r.sure and r.candidates == ("A",)


def test_nothing_known_gives_no_candidates():
    r = decide_identity(shows=None, pixel=[], named=[], screenshot=False, shown=set())
    assert not r.sure and r.candidates == () and r.place_id is None


def test_camera_photo_candidates_come_from_pixels_best_first_at_most_four():
    pixel = [(c, .9 - i / 10) for i, c in enumerate("ABCDEF")]
    r = decide_identity(shows=None, pixel=pixel, named=[], screenshot=False, shown=set())
    assert not r.sure and r.candidates == ("A", "B", "C", "D")


# ---------- text read from the image is data ----------

def test_clean_text_drops_control_characters_and_cuts():
    assert clean_text("a\x00b‮ c\n\td", 10) == "ab c d"
    assert len(clean_text("x" * 500, 300)) == 300


def test_clean_names_keeps_short_distinct_names():
    out = clean_names(["Phê La", " Phê La ", "", "x" * 200, "A", "B", "C", "D", 5])
    assert out[0] == "Phê La" and len(out) <= 4 and all(1 <= len(n) <= 80 for n in out)
    assert len(set(out)) == len(out)


def test_links_in_a_message():
    from trip.domain.perceive import links_in
    out = links_in("xem này https://maps.app.goo.gl/abc, và (https://www.tiktok.com/@a/video/12). https://maps.app.goo.gl/abc")
    assert out == [{"url": "https://maps.app.goo.gl/abc", "kind": "maps"}, {"url": "https://www.tiktok.com/@a/video/12", "kind": "tiktok"}]
    assert links_in("không có link") == []


def test_photo_context_keeps_the_last_two_without_the_pixel_list_and_labels_the_text():
    from trip.domain.perceive import photo_context
    recs = [{"photo_id": f"p{i}", "turn": i, "similar": [["a", .5]], "text_in_image": "hello" if i == 3 else "",
             "match": None, "candidates": []} for i in (1, 2, 3)]
    out = photo_context(recs)
    assert [p["photo_id"] for p in out] == ["p2", "p3"] and all("similar" not in p for p in out)
    assert any("untrusted" in k for k in out[1]) and not any("untrusted" in k for k in out[0])


def test_pick_name_needs_a_clear_winner_or_a_whole_name():
    assert pick_name([]) is None
    assert pick_name([("A", .9)]) == "A" and pick_name([("A", .7)]) is None
    assert pick_name([("A", .85), ("B", .8)]) is None  # too close
    assert pick_name([("A", 1.0), ("B", .8)]) == "A"  # the whole name, with a shorter place name inside it
    assert pick_name([("A", 1.0), ("B", 1.0)]) is None
