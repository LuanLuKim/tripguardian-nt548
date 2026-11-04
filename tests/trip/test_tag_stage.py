"""The tag stage (Engine.tag_stage, Browse.stage): one node of tag -> subtag -> place at a time, read only; a like from the
stage; a wish for a whole kind. Same fixtures as test_browse."""

import pytest
from test_browse import engine, k, records, run_turn  # noqa: F401 - fixtures
from trip_fixtures import ScriptedChat, call, reply, say

from trip.api.engine import TurnInput
from trip.domain.state import Hard, Evidence, TripState, with_meta

CLOUD = {"must": [["cloud_hunting", "present"]]}


def shown(engine):
    e = engine(ScriptedChat(reply(call("browse_tags", criteria=CLOUD)), say("Có mấy kiểu săn mây.")))
    s, events = run_turn(e, "Tui thích săn mây, có kiểu nào hay gợi ý đi")
    return e, s, next(d for ev, d in events if ev == "block")


def test_the_block_remembers_its_ask_so_the_stage_can_reopen_it(engine):
    _, _, block = shown(engine)
    assert block["criteria"] == CLOUD and block["sig"]


def test_a_subtag_opens_its_places_with_cards_and_nothing_is_written(engine):
    e, s, block = shown(engine)
    before = (len(s.transcript), s.state)
    out = e.tag_stage(s.id, block["sig"], "category:cafe")
    assert out["label"] == "Quán cà phê săn mây" and out["count"] == 7
    assert [n["id"] for n in out["nodes"]] == [f"0xcaf{i}:0x1" for i in range(7)]  # ranked as the set was
    assert all(n["kind"] == "place" and n["card"]["name"] and n["ref"] == f"place:{n['id']}" for n in out["nodes"])
    assert (len(s.transcript), s.state) == before  # a read, no chat turn


def test_the_trips_hard_limits_and_hidden_places_hold_on_the_stage(engine):
    e, s, block = shown(engine)
    s.state = with_meta(s.state, hidden_ids=("0xcaf0:0x1", "0xcaf1:0x1"))
    out = e.tag_stage(s.id, block["sig"], "category:cafe")
    assert out["count"] == 5 and "0xcaf0:0x1" not in {n["id"] for n in out["nodes"]}


def test_a_path_that_is_not_a_node_is_refused(engine):
    e, s, block = shown(engine)
    retired = e.tag_stage(s.id, block["sig"], "category:nope")
    assert retired["count"] == 0 and retired["nodes"] == []
    for sig, path in (("nosuchsig", "category:cafe"), (block["sig"], "category:cafe/x/y"), (block["sig"], "")):
        with pytest.raises(ValueError):
            e.tag_stage(s.id, sig, path)


def test_the_root_all_card_lists_the_ranked_places(engine):
    e, s, block = shown(engine)
    out = e.tag_stage(s.id, block["sig"], "*")
    assert {n["id"] for n in out["nodes"]} == set(block["all"])


def test_a_like_from_the_stage_needs_no_earlier_showing_but_still_the_trips_limits(engine):
    e, s, block = shown(engine)
    pid = "0xres4:0x1"  # a restaurant of the stage's list, not one the chat showed
    s.state = with_meta(s.state, shown_ids=())
    with pytest.raises(ValueError):
        e.turn(s.id, TurnInput(kind="like", target=pid, value="on"), lambda *a: None)
    e.turn(s.id, TurnInput(kind="like", target=pid, value="on", qid="stage"), lambda *a: None)
    after = e.store.get(s.id).state
    assert any(a.place_id == pid and a.priority == "want" for a in after.anchors)
    hidden = with_meta(after, hidden_ids=("0xres3:0x1",))
    s.state = hidden
    with pytest.raises(ValueError):
        e.turn(s.id, TurnInput(kind="like", target="0xres3:0x1", value="on", qid="stage"), lambda *a: None)


def test_wishing_a_whole_kind_is_a_soft_kind_wish_without_a_model_call(engine):
    e, s, block = shown(engine)
    calls = e.chat.calls
    e.turn(s.id, TurnInput(kind="wish", qid=block["sig"], target="category:cafe", value="on"), lambda *a: None)
    st = e.store.get(s.id).state
    (w,) = st.wishes.kinds
    assert w.kind == "Quán cà phê săn mây" and len(w.place_ids) == 7 and e.chat.calls == calls and not st.hard
    assert e.tag_stage(s.id, block["sig"], "category:cafe")["wished"] is True
    e.turn(s.id, TurnInput(kind="wish", qid=block["sig"], target="category:cafe", value="off"), lambda *a: None)
    assert not e.store.get(s.id).state.wishes.kinds
    before = e.store.get(s.id).state.wishes
    e.turn(s.id, TurnInput(kind="wish", qid=block["sig"], target="category:nope", value="on"), lambda *a: None)
    assert e.store.get(s.id).state.wishes == before


@pytest.mark.parametrize("enabled", [False, True])
def test_retired_stage_and_wish_are_harmless_in_both_rollout_modes(tmp_path, monkeypatch, enabled):
    import copy
    from corpus.tags import vocab
    cfg = copy.deepcopy(vocab.raw_config())
    cfg["membership"]["enabled"] = enabled
    monkeypatch.setattr(vocab, "raw_config", lambda: cfg)
    e = vague(tmp_path)
    s, events = run_turn(e, "Gợi ý gì hay ở Đà Lạt đi")
    block = next(d for ev, d in events if ev == "block")
    before = e.store.get(s.id).state.wishes
    out = e.tag_stage(s.id, block["sig"], "experience:retired")
    assert out["count"] == 0 and out["nodes"] == []
    e.turn(s.id, TurnInput(kind="wish", qid=block["sig"], target="experience:retired", value="on"), lambda *a: None)
    assert e.store.get(s.id).state.wishes == before


@pytest.mark.parametrize("enabled", [False, True])
def test_known_old_ref_without_current_members_is_harmless(tmp_path, monkeypatch, enabled):
    import copy
    from corpus.tags import vocab
    cfg = copy.deepcopy(vocab.raw_config())
    cfg["membership"]["enabled"] = enabled
    monkeypatch.setattr(vocab, "raw_config", lambda: cfg)
    e = vague(tmp_path)
    s, events = run_turn(e, "Gợi ý gì hay ở Đà Lạt đi")
    block = next(d for ev, d in events if ev == "block")
    before = e.store.get(s.id).state.wishes
    old_ref = "experience:heritage_architecture"
    out = e.tag_stage(s.id, block["sig"], old_ref)
    assert out["count"] == 0 and out["nodes"] == []
    e.turn(s.id, TurnInput(kind="wish", qid=block["sig"], target=old_ref, value="on"), lambda *a: None)
    assert e.store.get(s.id).state.wishes == before


def vague_records():
    """48 places in 3 categories; the first 6 of each carry three experience tags, so every tag's best places are the same."""
    from trip_fixtures import served
    out = []
    for g, cat in (("cafe", "Quán cà phê"), ("restaurant", "Nhà hàng"), ("camping", "Cắm trại")):
        for i in range(16):
            feats = {f: "present" for f in ("cloud_hunting", "scenic_view", "photo_spot")} if i < 6 else {}
            out.append(served(f"0x{g[:3]}{i}:0x1", f"{cat} {i}", feats, group=g, category=cat, voices=100 - i,
                              photos=[{"url": f"/media/{g}{i}.jpg"}]))
    return out


def vague(tmp_path):
    from datetime import date
    from test_reads import make
    from trip.api.engine import Engine
    from trip.infrastructure.catalog import Catalog
    from trip.infrastructure.sessions import SessionStore
    from trip.infrastructure.settings import Assistant, Settings
    kn = make(vague_records())
    cat = Catalog.from_records([], 1, evidence={r["id"]: r for r in vague_records()})
    kn.catalog = cat
    cfg = Settings(n_min=1, top_k=4, enough_factor=1.0, assistant=Assistant(enabled=True), gaps_path=str(tmp_path / "gaps.jsonl"))
    chat = ScriptedChat(reply(call("browse_tags", criteria={})), say("Có mấy hướng."))
    return Engine(cat, cfg, SessionStore(None), chat, today=lambda: date(2026, 10, 30), knowledge=kn)


def test_a_vague_ask_opens_tags_whose_covers_differ_and_a_tag_opens_subtags_then_places(tmp_path):
    e = vague(tmp_path)
    s, events = run_turn(e, "Gợi ý gì hay ở Đà Lạt đi")
    block = next(d for ev, d in events if ev == "block")
    assert block["level"] == "tags" and block["criteria"] == {} and len(block["subtags"]) >= 3
    covers = [x["cover"][0] for x in block["subtags"]]
    assert len(set(covers)) == len(covers)  # no photo twice on one level
    tag = block["subtags"][0]["id"]
    level2 = e.tag_stage(s.id, block["sig"], tag)
    assert level2["count"] == block["subtags"][0]["count"]
    if level2["nodes"][0]["kind"] != "place":
        urls = [n["cover"] for n in level2["nodes"]]
        assert len(set(urls)) == len(urls) and level2["nodes"][-1]["kind"] == "all"  # every sibling its own cover, "Xem tất cả" last
        places = e.tag_stage(s.id, block["sig"], level2["nodes"][0]["ref"])
        assert places["nodes"][0]["kind"] == "place"
        assert e.tag_stage(s.id, block["sig"], level2["nodes"][-1]["ref"])["count"] == level2["count"]
