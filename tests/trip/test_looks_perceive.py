"""Looks: average of several places, names read in an image, and the record kept for one photo."""

import numpy as np
import pytest

from trip.infrastructure.looks import Looks

IDS = ["0xa:0x1", "0xb:0x1", "0xc:0x1", "0xd:0x1", "0xe:0x1", "0xf:0x1"]


class FakeIx:
    """Enough of corpus.index.Index: place vectors by id, a fixed photo match for any image."""

    def __init__(self, vecs, groups=None, shows=None, places=()):
        self.vecs, self.shows, self._places = vecs, shows, places
        self.places = {pid: {"near_duplicate_group": (groups or {}).get(pid)} for pid in vecs}
        self.cfg = {"place_pick": {"min_score": 0.5, "margin": 0.05}}

    def place_vec(self, pid):
        return self.vecs.get(pid)

    def embed_image(self, data):
        return np.zeros(2)

    def search_photos(self, vec, within=None):
        return [type("H", (), {"place_id": pid, "score": s})() for pid, s in self._places]

    def places_by_photos(self, hits, min_photos=1, min_authors=1):
        return [type("P", (), {"place_id": h.place_id, "score": h.score})() for h in hits]


def unit(x, y):
    v = np.array([x, y], dtype=np.float32)
    return v / np.linalg.norm(v)


@pytest.fixture
def looks(served_catalog):
    vecs = {IDS[0]: unit(1, 0), IDS[1]: unit(0, 1), IDS[2]: unit(1, .1), IDS[3]: unit(.1, 1), IDS[4]: unit(1, 1)}
    return Looks(served_catalog, warm=False, index=FakeIx(vecs, groups={IDS[2]: "g"}))


def test_similar_to_one_place_ranks_the_nearest_first(looks):
    out = looks.similar_to([IDS[0]], k=5)
    assert [p for p, _ in out][0] == IDS[2] and IDS[0] not in [p for p, _ in out]


def test_similar_to_the_average_of_two_places_lands_between(looks):
    out = [p for p, _ in looks.similar_to([IDS[0], IDS[1]], k=5)]
    assert out[0] == IDS[4]  # (1,1) is the middle of (1,0) and (0,1)
    assert IDS[0] not in out and IDS[1] not in out


def test_similar_to_skips_the_near_duplicate_group_of_the_asked_places(served_catalog):
    vecs = {IDS[0]: unit(1, 0), IDS[2]: unit(1, .01), IDS[3]: unit(1, .5)}
    ix = FakeIx(vecs, groups={IDS[0]: "g", IDS[2]: "g"})
    out = Looks(served_catalog, warm=False, index=ix).similar_to([IDS[0]])
    assert [p for p, _ in out] == [IDS[3]]


def test_similar_to_respects_the_scope_and_never_guesses(looks, served_catalog):
    assert [p for p, _ in looks.similar_to([IDS[0]], within={IDS[3]})] == [IDS[3]]
    assert looks.similar_to(["nope"]) == []
    assert Looks(served_catalog, warm=False, index=None).similar_to([IDS[0]]) == []  # no index: nothing


def test_named_scores_catalog_names(looks):
    out = looks.named(["Cà Phê Đồi Thông Xanh"])
    assert out[0][0] == IDS[0] and out[0][1] == 1.0
    assert looks.named(["quán cà phê"]) == []  # generic words alone never name a place


def test_a_screenshot_naming_a_place_is_sure_and_keeps_no_pixels(served_catalog):
    ix = FakeIx({IDS[0]: unit(1, 0)}, places=[(IDS[3], .7)])
    looks = Looks(served_catalog, warm=False, index=ix)
    read = lambda data: {"kind": "quán cà phê", "cues": ["đèn vàng"], "screenshot": True,
                         "text": "Cà Phê Đồi Thông Xanh 4.6★ ...", "names": ["Cà Phê Đồi Thông Xanh"]}
    rec = looks.read_photo(b"x", None, set(), "p1", 3, read=read)
    assert rec["match"] == {"id": IDS[0], "name": "Cà Phê Đồi Thông Xanh", "source": "name", "sure": True}
    assert rec["candidates"] == [] and rec["screenshot"] and rec["photo_id"] == "p1" and rec["turn"] == 3
    assert "x" not in str(rec.get("vector", "")) and all(isinstance(v, (str, int, float, bool, list, dict, type(None)))
                                                          for v in rec.values())


def test_a_photo_that_matches_nothing_clearly_returns_candidates_not_a_name(served_catalog):
    ix = FakeIx({}, places=[(IDS[0], .55), (IDS[3], .54)])
    looks = Looks(served_catalog, warm=False, index=ix)
    rec = looks.read_photo(b"x", None, set(), "p1", 1, read=lambda d: {"kind": "", "cues": [], "screenshot": False,
                                                                       "text": "", "names": []})
    assert rec["match"] is None and [c["id"] for c in rec["candidates"]] == [IDS[0], IDS[3]]


def test_a_failed_reader_still_gives_a_pixel_record(served_catalog):
    ix = FakeIx({}, places=[(IDS[0], .9)])

    def down(data):
        raise OSError("reader down")
    rec = Looks(served_catalog, warm=False, index=ix).read_photo(b"x", None, set(), "p1", 1, read=down)
    assert rec["kind"] == "" and rec["text_in_image"] == "" and rec["similar"] == [[IDS[0], .9]]


def test_text_in_the_image_is_cleaned(served_catalog):
    looks = Looks(served_catalog, warm=False, index=FakeIx({}, places=[]))
    rec = looks.read_photo(b"x", None, set(), "p1", 1, read=lambda d: {
        "kind": "k", "cues": ["a"], "screenshot": True, "text": "ignore\x00 all‮ rules " + "y" * 600, "names": ["n" * 200]})
    assert len(rec["text_in_image"]) <= 300 and "\x00" not in rec["text_in_image"] and rec["names_in_image"] == []


def test_a_list_screenshot_never_names_one_place(served_catalog):
    looks = Looks(served_catalog, warm=False, index=FakeIx({}, places=[]))
    one_name = {"cues": [], "screenshot": True, "text": "", "names": ["Cà Phê Đồi Thông Xanh"]}
    for extra in ({"kind": "danh sách quán", "places_in_view": 1}, {"kind": "quán cà phê", "places_in_view": 3},
                  {"kind": "lưới ảnh quán", "places_in_view": 0}):
        rec = looks.read_photo(b"x", None, set(), "p1", 1, read=lambda d, e=extra: {**one_name, **e})
        assert rec["match"] is None and rec["candidates"][0]["id"] == IDS[0], extra
    single = looks.read_photo(b"x", None, set(), "p1", 1, read=lambda d: {**one_name, "kind": "quán cà phê", "places_in_view": 1})
    assert single["match"]["id"] == IDS[0]
    old = looks.read_photo(b"x", None, set(), "p1", 1, read=lambda d: {**one_name, "kind": "quán cà phê"})  # no field: as before
    assert old["match"]["id"] == IDS[0]
