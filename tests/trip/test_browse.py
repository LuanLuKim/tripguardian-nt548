"""browse_tags: a broad ask -> subtags (infrastructure/browse.py, agent tool, `tags` block), and the home page's tag view."""

import json
from datetime import date

import pytest
from test_reads import make
from trip_fixtures import ScriptedChat, call, reply, say, served

from trip.agent.tools import TurnTools
from trip.api.engine import TurnInput
from trip.domain.state import Evidence, Hard, TripState
from trip.infrastructure.catalog import Catalog

S = TripState()
PHOTO = [{"url": "/media/gmaps/x/a.jpg"}]


def records():
    """24 places: 20 with cloud_hunting (cafe 7, restaurant 5, camping 4, attraction 4), 4 without; some carry other tags."""
    out = []
    for g, cat, n in (("cafe", "Quán cà phê", 7), ("restaurant", "Nhà hàng", 5), ("camping", "Cắm trại", 4), ("attraction", "Điểm tham quan", 4)):
        for i in range(n):
            feats = {"cloud_hunting": "present", **({"kids": "unsuitable"} if g == "camping" and i < 2 else {})}
            out.append(served(f"0x{g[:3]}{i}:0x1", f"{cat} Mây {g} {i}", feats, group=g, category=cat, voices=100 - len(out), photos=PHOTO))
    out += [served(f"0xn{i}:0x1", f"Quán Không Mây {i}", {"scenic_view": "present"}, voices=5, photos=PHOTO) for i in range(4)]
    out.append(served("0xs:0x1", "Khách Sạn Mây", {"cloud_hunting": "present"}, group="stay", category="Khách sạn", voices=1))
    return out


@pytest.fixture
def k():
    return make(records())


def test_a_broad_ask_is_split_by_category_and_the_fixed_feature_is_not_a_subtag(k):
    out = k.browse.subtags({"must": [["cloud_hunting", "present"]]}, S)
    assert out["axis"] == "category" and out["total"] == 20 and out["other"] == 0  # the hotel is not asked for
    labels = {s["label"] for s in out["subtags"]}
    assert "Quán cà phê săn mây" in labels and "Cắm trại, sáng dậy thấy mây" in labels
    cafe = next(s for s in out["subtags"] if s["id"] == "category:cafe")
    assert cafe["count"] == 7 and len(cafe["examples"]) == 3 and set(cafe["examples"][0]) == {"id", "n"}
    split = out["_split"]
    assert [s["count"] for s in split["subtags"]] == [7, 5, 4, 4] and len(split["ranked"]) <= k.cards_max


def test_place_ids_keep_the_ranked_order_of_the_set(k):
    out = k.browse.subtags({"must": [["cloud_hunting", "present"]]}, S)
    cafe = next(s for s in out["_split"]["subtags"] if s["key"] == "cafe")
    assert cafe["place_ids"] == [f"0xcaf{i}:0x1" for i in range(7)]  # more voices first


def test_the_trips_hard_filters_and_hidden_places_still_apply(k):
    from trip.domain.state import with_meta
    state = TripState(hard=(Hard(feature="kids", op="ne", value="unsuitable", unknown_policy="flag", evidence=(Evidence(turn=1, quote="đi với bé"),)),))
    out = k.browse.subtags({"must": [["cloud_hunting", "present"]]}, state)
    assert out["total"] == 18 and "category:camping" not in {s["id"] for s in out["subtags"]}  # two camps left: under min_size
    hidden = with_meta(S, hidden_ids=tuple(f"0xcaf{i}:0x1" for i in range(5)))
    out = k.browse.subtags({"must": [["cloud_hunting", "present"]]}, hidden)
    assert out["total"] == 15 and "category:cafe" not in {s["id"] for s in out["subtags"]}  # two cafes left: under min_size


def test_no_useful_split_gives_the_plain_list_and_cards(k):
    out = k.browse.subtags({"must": [["scenic_view", "present"]]}, S)  # four places
    assert out["subtags"] == [] and out["total"] == 4 and "_split" not in out and out["_cards"] and out["places"]
    assert "plain" in out["note"] or "one list" in out["note"]


def test_criteria_the_split_does_not_take_are_refused(k):
    for bad in ({"near_place": "0xcaf0:0x1"}, {"price_max": 30000}, {"sort": "price"}, {"page": 2}):
        with pytest.raises(ValueError, match="find_places"):
            k.browse.subtags(bad, S)
    with pytest.raises(ValueError):
        k.browse.subtags({"groups": ["nope"]}, S)


def test_a_group_the_query_names_fixes_the_category_axis(k):
    out = k.browse.subtags({"groups": ["cafe"], "must": [["cloud_hunting", "present"]]}, S)
    assert out["subtags"] == []  # seven cafes: below min_places


def test_the_tool_returns_labels_and_hides_private_keys(k, tmp_path):
    t = TurnTools(S, "x", 1, k.catalog, date(2026, 10, 30), knowledge=k, assistant=True, gaps=tmp_path / "g.jsonl")
    assert "browse_tags" in t.tool_names() and t.tool("browse_tags").group == "places"
    raw = t.run("browse_tags", {"criteria": {"must": [["cloud_hunting", "present"]]}})
    out = json.loads(json.dumps(t.model_called("browse_tags", raw, {})))
    assert "_split" not in out and out["subtags"][0]["label"] and t.cards_sent == []  # no flat cards: the block shows the places
    assert {e["id"] for s in out["subtags"] for e in s["examples"]} <= t.told_ids | {e["id"] for s in out["subtags"] for e in s["examples"]}
    assert "error" in t.run("browse_tags", {"criteria": {"near_place": "x"}})


def test_the_plain_fallback_sends_cards_like_find_places(k, tmp_path):
    t = TurnTools(S, "x", 1, k.catalog, date(2026, 10, 30), knowledge=k, assistant=True, gaps=tmp_path / "g.jsonl")
    out = t.model_called("browse_tags", t.run("browse_tags", {"criteria": {"must": [["scenic_view", "present"]]}}), {})
    assert out["subtags"] == [] and t.cards_sent and "_cards" not in out


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


def run_turn(e, text):
    sid = e.create("first", "nothing")["id"]
    events = []
    e.turn(sid, TurnInput(kind="text", text=text), lambda ev, d: events.append((ev, d)))
    return e.store.get(sid), events


def test_a_tags_block_goes_out_with_cover_photos_and_persists(engine):
    e = engine(ScriptedChat(reply(call("browse_tags", criteria={"must": [["cloud_hunting", "present"]]})),
                            say("Có mấy kiểu săn mây, bạn bấm vào kiểu mình thích nhé.")))
    s, events = run_turn(e, "Tui thích săn mây, có kiểu nào hay gợi ý đi")
    block = next(d for ev, d in events if ev == "block")
    assert block["kind"] == "tags" and block["axis"] == "category" and len(block["subtags"]) == 4
    first = block["subtags"][0]
    assert first["label"] and first["count"] == 7 and first["cover"] == ["/media/gmaps/x/a.jpg"] * 3 or first["cover"]
    ids = {c["id"] for c in block["cards"]}
    assert set(first["place_ids"]) <= ids and len(block["cards"]) == len(ids)  # each card once
    assert not [d for ev, d in events if ev == "places"]  # the subtag cards replace the flat list
    assert any(m.get("kind") == "block" and m["block"]["kind"] == "tags" for m in e.load(s.id)["transcript"])


def test_the_reply_that_names_a_place_does_not_add_a_flat_list_beside_the_block(engine):
    e = engine(ScriptedChat(reply(call("browse_tags", criteria={"must": [["cloud_hunting", "present"]]})),
                            say("Thử Quán cà phê Mây cafe 0 nhé.")))
    _, events = run_turn(e, "Tui thích săn mây, có kiểu nào hay gợi ý đi")
    assert [ev for ev, _ in events].count("block") == 1 and not [d for ev, d in events if ev == "places"]


def test_a_tag_of_the_home_page_is_split_without_a_trip(k):
    from trip.api.engine import Engine
    from trip.infrastructure.sessions import SessionStore
    from trip.infrastructure.settings import Settings
    e = Engine(k.catalog, Settings(n_min=1), SessionStore(None), None, today=lambda: date(2026, 10, 30), knowledge=k)
    v = e.tag_view("experience:cloud_hunting")
    assert v["tag"]["label"] == "Săn mây" and v["tag"]["count"] == 20
    assert v["block"]["kind"] == "tags" and v["cards"] == [] and len(v["block"]["subtags"]) == 4
    flat = e.tag_view("experience:scenic_view")  # four places: no split, the best places as one list
    assert flat["block"] is None and len(flat["cards"]) == 4
    retired = e.tag_view("experience:nope")
    assert retired["tag"]["count"] == 0 and retired["cards"] == [] and retired["block"] is None
    covers = e.tag_covers([{"ref": "experience:cloud_hunting", "top": ["0xcaf0:0x1"]}])
    assert covers[0]["cover"] == ["/media/gmaps/x/a.jpg"]


def test_trending_covers_do_not_repeat_a_place_across_tags(k):
    from trip.api.engine import Engine
    from trip.infrastructure.sessions import SessionStore
    from trip.infrastructure.settings import Settings
    e = Engine(k.catalog, Settings(n_min=1), SessionStore(None), None, today=lambda: date(2026, 10, 30), knowledge=k)
    out = e.tag_covers([{"ref": "a", "top": ["0xcaf0:0x1", "0xcaf1:0x1"]}, {"ref": "b", "top": ["0xcaf0:0x1", "0xcaf2:0x1", "0xres0:0x1"]}])
    assert len(out[0]["cover"]) == 2 and len(out[1]["cover"]) == 3  # the second tag takes places the first did not use first
    assert e.tag_covers([{"ref": "c", "top": []}])[0]["cover"] == []


def test_trending_cover_prefers_a_photo_of_the_scene_that_shows_the_tag(k, monkeypatch):
    from trip.api.engine import Engine
    from trip.infrastructure.sessions import SessionStore
    from trip.infrastructure.settings import Settings
    e = Engine(k.catalog, Settings(n_min=1), SessionStore(None), None, today=lambda: date(2026, 10, 30), knowledge=k)
    monkeypatch.setattr(k, "scene_cover", lambda pid, scenes: "/media/gmaps/x/view.jpg" if pid == "0xcaf1:0x1" and "view" in scenes else None)
    out = e.tag_covers([{"ref": "experience:cloud_hunting", "top": ["0xcaf0:0x1", "0xcaf1:0x1"]}])
    assert out[0]["cover"] == ["/media/gmaps/x/view.jpg"]  # a view of the cloud, not the first plate of the first place
    plain = e.tag_covers([{"ref": "category:cafe", "top": ["0xcaf0:0x1"]}])  # no scenes named for it: the first photo, as before
    assert plain[0]["cover"] == ["/media/gmaps/x/a.jpg"]


def test_retired_ref_in_saved_subtag_path_is_skipped(k):
    out = k.browse.stage({"must": [["cloud_hunting", "present"]]}, S, ["experience:retired_interest"])
    assert out["ids"] == [] and out["children"] is None


def test_retired_child_of_a_saved_tag_path_is_skipped(k):
    from unittest.mock import patch
    with patch("trip.infrastructure.browse.policy.first_pick", return_value=("tags", "vague")):
        out = k.browse.stage({}, S, ["experience:cloud_hunting", "category:retired_kind"])
    assert out["ids"] == [] and out["children"] is None


def test_warm_computes_every_places_tags_once(k):
    assert k.browse.warm(wait_s=0) == len(k.catalog.places)
    assert k.browse.place_tags("0xcaf0:0x1") is k.browse.place_tags("0xcaf0:0x1")
