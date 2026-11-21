"""Knowledge: the assistant's corpus and live reads (plan 2026-10-28-trip-decision-chatbot Task 2)."""

from datetime import date

import pytest

from trip.domain.coverage import admissible
from trip.domain.state import TripState


def test_find_places_applies_hard_fail_closed(knowledge, kids_hard_state):
    out = knowledge.find({"groups": ["cafe"]}, kids_hard_state)
    assert out["places"] and all(admissible(knowledge.catalog.by_id[p["id"]], kids_hard_state.hard, None)
                                 for p in out["places"])
    ids = {p["id"] for p in out["places"]}
    assert "0xb:0x1" not in ids and "0xc:0x1" not in ids  # unsuitable, and unknown under policy exclude


def test_find_places_returns_short_cards(knowledge):
    out = knowledge.find({"groups": ["cafe"]}, TripState(), limit=2)
    assert len(out["places"]) == 2 and out["places"][0]["n"] == "Cà Phê Đồi Thông Xanh"
    assert {"maybe", "unknown"} <= set(out)


def test_find_bad_criteria_raises(knowledge):
    with pytest.raises(ValueError, match="unknown criteria"):
        knowledge.find({"color": "red"}, TripState())


def test_place_and_similar(knowledge, kids_hard_state):
    assert knowledge.place("0xa:0x1")["n"] == "Cà Phê Đồi Thông Xanh"
    assert knowledge.place("nope") is None
    assert knowledge.similar("0xa:0x1", kids_hard_state) == []  # no photo index in the fixture: nothing, never a guess


def test_weather_at_the_center(knowledge):
    from corpus.views import climate_normals
    if not climate_normals("dalat"):
        pytest.skip("no built climate view (data/ is not in git): python -m corpus views climate dalat")
    out = knowledge.weather(date(2026, 11, 1))
    assert out == {"date": "2026-11-01", "rain_prob": 0.4, "rain_mm": 2.5, "source": "open-meteo",
                   "fetched_at": "2026-10-28T08:00:00Z",
                   # the forecast row has no temperature: the month's long-run figures ride along, named as usual ones
                   "usual_temp_of_month": {"tmax_c": 22, "tmin_c": 15}}  # whole degrees, as a reply says them


def test_weather_unavailable_is_an_error_result(knowledge_no_live):
    assert knowledge_no_live.weather(date(2026, 11, 1)) == {"error": "weather unavailable"}


def test_weather_that_raises_is_an_error_result(make_knowledge):
    from trip.infrastructure.knowledge import LiveTools

    def down(lat, lng, days):
        raise OSError("open-meteo down")
    assert make_knowledge(LiveTools(weather=down)).weather(date(2026, 11, 1)) == {"error": "weather unavailable"}


def test_distance_by_id_and_center(knowledge, knowledge_no_live):
    out = knowledge.distance("center", "0xd:0x1")
    assert out["minutes"] == 25 and out["source"] == "osrm" and out["km_line"] > 0
    assert knowledge_no_live.distance("center", "0xd:0x1") == {"error": "distance unavailable"}
    assert "error" in knowledge.distance("center", "nope")


def test_ranked_keeps_good_places_in_score_order_cut_at_a_share_of_the_best(served_catalog):
    from corpus.retrieval import FindHit, FindResult
    from trip.infrastructure.knowledge import Knowledge

    class Ranked:  # a retrieval whose find returns these scores (best first, as corpus.retrieval.find does)
        def find(self, criteria, limit=8):
            scores = {"0xa:0x1": 1.0, "0xc:0x1": 0.9, "0xd:0x1": 0.8, "0xf:0x1": 0.7, "0xb:0x1": 0.65, "0xe:0x1": 0.5}
            return FindResult(tuple(FindHit(pid, s, (), {"id": pid, "n": pid}) for pid, s in scores.items()), (), 0, "r")
    k = Knowledge(Ranked(), served_catalog, None, ("Chợ Đà Lạt", 11.9429, 108.4372), data_places=2, cards_max=10,
                  cards_ratio=0.6)
    out = k.find({}, TripState())
    assert [p["id"] for p in out["places"]] == ["0xa:0x1", "0xc:0x1"]  # the model reads the top data_places
    assert out["ranked"] == ["0xa:0x1", "0xc:0x1", "0xd:0x1", "0xf:0x1", "0xb:0x1"]  # >= 0.6 x best, score order
    small = Knowledge(Ranked(), served_catalog, None, ("c", 0, 0), data_places=2, cards_max=3, cards_ratio=0.6)
    assert len(small.find({}, TripState())["ranked"]) == 3


def _viewer(retrieval_photos):
    from trip.infrastructure.knowledge import Knowledge
    record = {"identity": {"name": "X"}, "media": {"photos": [{"url": "/media/gmaps/x/old1.jpg"}, {"url": "/media/gmaps/x/old2.jpg"}]}}

    class R:
        def get_place(self, pid):
            return record
        if retrieval_photos is not None:
            def scene_photos(self, pid):
                return retrieval_photos
    k = Knowledge.__new__(Knowledge)
    k.retrieval = R()
    return k


def test_view_photos_are_scene_photos_when_labelled():
    k = _viewer([{"scene": "exterior", "photo_id": "a", "file": "gmaps/places/x/a.jpg"},
                 {"scene": "food", "photo_id": "b", "file": "gmaps/places/x/b.jpg"}])
    assert k.view("p")["photos"] == ["/media/gmaps/x/a.jpg", "/media/gmaps/x/b.jpg"]


def test_view_photos_keep_the_record_photos_without_labels():
    assert _viewer([]).view("p")["photos"] == ["/media/gmaps/x/old1.jpg", "/media/gmaps/x/old2.jpg"]
    assert _viewer(None).view("p")["photos"] == ["/media/gmaps/x/old1.jpg", "/media/gmaps/x/old2.jpg"]
