"""When the chat shows tags, subtags or a plain list (domain/tag_policy.py, Browse.subtags modes, the `tag` tap)."""

from datetime import date

import pytest
from test_reads import make
from trip_fixtures import ScriptedChat, call, reply, say, served

from trip.api.engine import TurnInput
from trip.domain import tag_policy as policy
from trip.domain.state import TripState
from trip.infrastructure.catalog import Catalog

S = TripState()
PHOTO = [{"url": "/media/gmaps/x/a.jpg"}]
CLOUD = {"must": [["cloud_hunting", "present"]]}


def records():
    """54 places in five kinds; 20 of them have cloud_hunting (spread over four kinds)."""
    out = []
    for g, cat, n, cloud in (("cafe", "Quán cà phê", 14, 6), ("restaurant", "Nhà hàng", 12, 5), ("nature", "Đồi", 10, 5),
                             ("attraction", "Điểm tham quan", 10, 4), ("camping", "Cắm trại", 8, 0)):
        for i in range(n):
            feats = {"cloud_hunting": "present"} if i < cloud else {}
            out.append(served(f"0x{g[:3]}{i}:0x1", f"{cat} {g} {i}", feats, group=g, category=cat, voices=200 - len(out), photos=PHOTO))
    return out


@pytest.fixture
def k():
    return make(records())


@pytest.fixture
def engine(tmp_path, k):
    from trip.api.engine import Engine
    from trip.infrastructure.sessions import SessionStore
    from trip.infrastructure.settings import Assistant, Settings
    cat = Catalog.from_records([], 1, evidence={r["id"]: r for r in records()})
    k.catalog = cat

    def build(chat):
        cfg = Settings(n_min=1, top_k=4, enough_factor=1.0, assistant=Assistant(enabled=True), gaps_path=str(tmp_path / "gaps.jsonl"))
        return Engine(cat, cfg, SessionStore(None), chat, today=lambda: date(2026, 10, 30), knowledge=k)
    return build


def talk(e, sid, text):
    events = []
    e.turn(sid, TurnInput(kind="text", text=text), lambda ev, d: events.append((ev, d)))
    return events


# ---------- the pure policy ----------

def test_dimensions_count_what_the_ask_names_and_a_mood_is_not_one():
    assert policy.dimensions((), (), None, None) == 0
    assert policy.dimensions(("cafe",), (), None, "") == 1
    assert policy.dimensions(("cafe", "bar"), (("a", "present"), ("b", "present")), None, None) == 2  # groups once, musts once
    assert policy.dimensions((), (), "phở", "view đồi") == 2


def test_first_pick_by_dimensions_and_size():
    assert policy.first_pick(0, 80) == ("tags", "vague")
    assert policy.first_pick(0, 10) == ("places", "few_places")
    assert policy.first_pick(1, 80) == ("subtags", "interest")
    assert policy.first_pick(2, 500) == ("places", "specific")


def test_a_block_is_not_repeated_within_the_last_few():
    sig = policy.signature("tags", "", ["category:cafe", "category:nature"])
    assert sig == policy.signature("tags", "", ["category:nature", "category:cafe"])  # order does not matter
    assert policy.repeated(sig, [sig]) and policy.repeated(sig, ["x", sig])
    assert not policy.repeated(sig, ["x", "y", sig]) and not policy.repeated(sig, [])


# ---------- the three modes on real data ----------

def test_a_vague_ask_gets_tags_a_named_interest_gets_subtags_a_specific_ask_the_list(k):
    vague = k.browse.subtags({}, S)
    assert vague["mode"] == "tags" and vague["why"] == "vague" and vague["total"] == 54
    assert len(vague["subtags"]) >= 3 and {s["id"].split(":")[0] for s in vague["subtags"]} <= {"category", "experience"}
    assert vague["_split"]["level"] == "tags"
    interest = k.browse.subtags(CLOUD, S)
    assert interest["mode"] == "subtags" and interest["_split"]["level"] == "subtags" and interest["axis"] == "category"
    cafe = k.browse.subtags({"groups": ["cafe"], **CLOUD}, S)  # "cho xem thêm quán cà phê săn mây"
    assert cafe["mode"] == "places" and cafe["why"] == "specific" and cafe["subtags"] == [] and cafe["_cards"]
    mood = k.browse.subtags({"groups": ["restaurant"], "prefer": [["cloud_hunting", "present"]]}, S)  # a mood is not a dimension
    assert mood.get("why") != "specific"


def test_a_vague_ask_over_few_allowed_places_is_the_list(k):
    from trip.domain.state import with_meta
    hidden = with_meta(S, hidden_ids=tuple(r["id"] for r in records()[:30]))
    out = k.browse.subtags({}, hidden)
    assert out["mode"] == "places" and out["why"] == "few_places" and out["total"] == 24


def test_the_same_block_is_not_shown_twice_and_a_picked_tag_is_not_offered_again(k):
    first = k.browse.subtags({}, S)
    again = k.browse.subtags({}, S, seen=[first["_split"]["sig"]])
    assert again["mode"] == "places" and again["why"] == "repeat" and again["_cards"]
    other = k.browse.subtags({}, S, seen=[first["_split"]["sig"]], picked=["category:cafe"])  # another set of tags is no repeat
    assert other["mode"] == "tags" and "category:cafe" not in {s["id"] for s in other["subtags"]}
    sub = k.browse.subtags(CLOUD, S)
    assert k.browse.subtags(CLOUD, S, seen=[sub["_split"]["sig"]])["why"] == "repeat"


def test_hidden_places_and_hard_limits_shape_the_tags(k):
    from trip.domain.state import with_meta
    hidden = with_meta(S, hidden_ids=tuple(f"0xcaf{i}:0x1" for i in range(14)))
    labels = {s["id"] for s in k.browse.subtags({}, hidden)["subtags"]}
    assert "category:cafe" not in labels  # every cafe is hidden: no tag for them


# ---------- the chat ----------

def test_the_chat_shows_tags_once_then_the_list(engine):
    e = engine(ScriptedChat(reply(call("browse_tags", criteria={})), say("Đà Lạt có mấy hướng này, bạn bấm một hướng nhé."),
                            reply(call("browse_tags", criteria={})), say("Đây là các nơi nổi bật.")))
    sid = e.create("first", "nothing")["id"]
    first = talk(e, sid, "Gợi ý gì hay ở Đà Lạt đi")
    block = next(d for ev, d in first if ev == "block")
    assert block["kind"] == "tags" and block["level"] == "tags" and block["all"] == [] and block["sig"]
    assert len(block["subtags"]) >= 3 and all(len(s["place_ids"]) >= 2 for s in block["subtags"])
    second = talk(e, sid, "Còn gì nữa không")  # the same tags again would be the same block: the list instead
    assert not [d for ev, d in second if ev == "block"] and [d for ev, d in second if ev == "places"]


def test_tapping_a_tag_opens_its_subtags_or_places_without_a_model_call(engine):
    e = engine(ScriptedChat(reply(call("browse_tags", criteria={})), say("Có mấy hướng, bạn chọn một nhé.")))
    sid = e.create("first", "nothing")["id"]
    talk(e, sid, "Chưa biết đi đâu")
    events = []
    e.turn(sid, TurnInput(kind="tag", target="experience:cloud_hunting"), lambda ev, d: events.append((ev, d)))
    block = next(d for ev, d in events if ev == "block")  # 20 places by category: a split
    assert block["level"] == "subtags" and block["title"] == "Săn mây" and len(block["subtags"]) == 4
    s = e.store.get(sid)
    tapped = [t for t in s.transcript if t.get("kind") == "tag"]
    assert tapped and tapped[0]["ref"] == "experience:cloud_hunting" and tapped[0]["role"] == "user"
    assert set(block["subtags"][0]["place_ids"]) <= set(s.state.meta.shown_ids)  # Thích works on them
    flat = []
    e.turn(sid, TurnInput(kind="tag", target="category:camping"), lambda ev, d: flat.append((ev, d)))  # 8 places: no split
    assert [d for ev, d in flat if ev == "places"] and not [d for ev, d in flat if ev == "block"]
    retired = []
    e.turn(sid, TurnInput(kind="tag", target="experience:nope"), lambda ev, d: retired.append((ev, d)))
    assert not [d for ev, d in retired if ev == "block"]
    assert not [p for ev, d in retired if ev == "places" for p in d.get("places", [])]


def test_a_reply_with_subtags_closes_the_photo_question_of_the_same_taste(engine):
    e = engine(ScriptedChat(reply(call("browse_tags", criteria=CLOUD)), say("Có mấy kiểu săn mây, bạn bấm một kiểu nhé.")))
    sid = e.create("first", "nothing")["id"]
    events = talk(e, sid, "Tui thích săn mây, có kiểu nào hay gợi ý đi")
    assert [d for ev, d in events if ev == "block"]
    s = e.store.get(sid)
    assert s.state.drills and all(d.status == "none" for d in s.state.drills)  # the subtags are the question
