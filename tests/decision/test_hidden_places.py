"""Trip reports hide recommendations, never the traveller's own choices."""

import pytest
from fixtures import hard, si, srec

from decision import Data, DecisionOutput, Engine, Store, Tools, load_settings, run_pipeline
from decision.session import Session, State


CFG = load_settings()
HIDDEN = ("closed-a", "closed-b", "closed-unknown")


def data():
    return Data([
        srec("open", name="Quán đang mở", dup=1, features={"steep_or_stairs": "absent"}),
        srec("closed-a", name="Quán đã đóng", dup=1, features={"steep_or_stairs": "absent"}),
        srec("closed-b", name="Quán đã đóng", dup=1, features={"steep_or_stairs": "absent"}),
        srec("closed-unknown", name="Quán đã đóng chưa rõ", dup=1),
    ])


def search_input(**over):
    return si(hard_filters=[hard("steep_or_stairs", "present", policy="flag")], **over)


def session(state=None, **over):
    return Session(id="0123456789ab", search_input=search_input(**over), state=state or State(), hidden_ids=HIDDEN)


def test_hidden_branches_leave_lists_unverified_and_alternatives():
    s = session(State(selected=["open"]))
    result = run_pipeline(s, data(), CFG)
    assert set(result.view["shortlist"]) == {"open"}
    assert result.unverified == []
    assert result.alternatives.get("open", []) == []
    assert all(pid not in HIDDEN for ids in result.ranked.values() for pid in ids)


@pytest.mark.parametrize("anchored", [False, True])
def test_hidden_place_stays_when_user_selects_or_anchors_it(anchored):
    s = session(State(selected=["closed-a"]), anchors=[{"place_id": "closed-a", "priority": "must"}] if anchored else [])
    result = run_pipeline(s, data(), CFG)
    assert result.view["selected"] == ["closed-a"]
    assert "closed-a" in result.view["shortlist"]
    assert "closed-b" not in result.view["shortlist"]
    assert result.view["pending"] is None


def test_public_tools_rebase_search_restore_and_output_keep_reported_hides():
    tools = Tools(Engine(data(), CFG, Store(None)))
    created = tools.create({"search_input": search_input().model_dump(mode="json")})
    sid = created["id"]
    tools.apply(sid, "act", {"type": "select", "place_id": "open"}, lambda *_: None)
    # A report added in Trip after Decision was created must invalidate the cached lists.
    view = tools.rebase(sid, {"search_input": search_input().model_dump(mode="json"), "hidden_ids": HIDDEN})["view"]
    assert set(view["shortlist"]) == {"open"}
    found = tools.read(sid, "search", {"q": "Quán đã đóng"})
    assert found["total"] == 0 and found["cards"] == [] and found["outside"] == []
    tools.rebase(sid, {"search_input": search_input().model_dump(mode="json")})
    page = tools.read(sid, "page", {"group": "cafe", "n": 1})["view"]
    assert set(page["shortlist"]) == {"open"}
    tools.apply(sid, "act", {"type": "select", "place_id": "closed-a"}, lambda *_: None)
    output = DecisionOutput.model_validate(tools.read(sid, "draft", {"any": True})["output"])
    assert {p.id for p in output.confirmed} == {"open", "closed-a"}
    assert not (set(HIDDEN) & {p.id for p in output.backup_pool})
    assert set(output.hidden_ids) == set(HIDDEN)
    snapshot = tools.snapshot(sid)
    restored = Tools(Engine(data(), CFG, Store(None)))
    restored.restore(snapshot)
    restored.apply(sid, "act", {"type": "undo"}, lambda *_: None)
    found = restored.read(sid, "search", {"q": "Quán đã đóng"})
    assert found["cards"] == [] and found["outside"] == []


def test_public_create_accepts_hides_without_changing_default_behavior():
    tools = Tools(Engine(data(), CFG, Store(None)))
    payload = {"search_input": search_input().model_dump(mode="json")}
    normal = tools.create(payload)["view"]
    assert {"open", "closed-a", "closed-b"} <= set(normal["shortlist"])
    hidden = tools.create({**payload, "hidden_ids": HIDDEN})["view"]
    assert hidden["shortlist"] == ["open"]
    assert hidden["unverified"]["count"] == 0
