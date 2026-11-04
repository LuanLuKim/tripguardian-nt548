"""Explicit lodging survives the production mobility restrictions at handoff."""

import pytest
from decision import Data, Engine, Store, load_settings
from fixtures import hard, si, srec

YORI = "0x31711306e76823df:0x5a4fd92d57d365cd"


@pytest.mark.parametrize("booked", [True, False])
@pytest.mark.parametrize("stairs", [None, "present"])
def test_explicit_lodging_is_preserved_with_two_physical_filters(booked, stairs):
    safe = {"long_walk": "absent", "steep_or_stairs": "absent"}
    records = [srec("a", features=safe), srec("b", features=safe),
               srec(YORI, group="stay", category="Khách sạn", features={"steep_or_stairs": stairs} if stairs else {})]
    own = {"kind": "corpus", "place_id": YORI, "text": "Yori House", "lat": 11.94, "lng": 108.44}
    search = si(hard_filters=[hard("long_walk", "present"), hard("steep_or_stairs", "present")],
                context={"lodging_booked": "yes", "lodging": own} if booked else {})
    e = Engine(Data(records), load_settings(), Store(None))
    sid = e.create(search.model_dump(mode="json"))["id"]
    for pid in ("a", "b"):
        e.act(sid, {"type": "select", "place_id": pid})
    if not booked:
        e.act(sid, {"type": "set_lodging", "lodging": {"kind": "corpus", "id": YORI}})
    out = e.confirm(sid, for_planning=True)
    assert {c["id"] for c in out["confirmed"]} == {"a", "b"}
    if not booked:
        assert out["lodging"]["id"] == YORI
    else:
        assert out["trip_context"]["context"]["lodging"]["place_id"] == YORI
