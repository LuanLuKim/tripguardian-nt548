"""Pet context protects recommendations without restricting explicit selections."""

import pytest

from corpus.snapshot import shared
from decision import Data, Engine, Store, Tools, load_settings
from fixtures import feat, hard, si, srec


def pet_input(**over):
    return si(context={"companions": ["solo", "pet"]}, **over).model_dump(mode="json")


def engine():
    return Engine(Data([
        srec("yes", name="Pet Friendly Cafe", features={"pets": "allowed"}),
        srec("no", name="No Pets Cafe", features={"pets": "not_allowed"}),
        srec("unknown", name="Unknown Policy Cafe"),
        srec("uncertain", features={"pets": feat("allowed", status="UNCERTAIN")}),
    ]), load_settings(), Store(None))


def assert_pet_lists(view):
    cards = [c for g in view["groups"] for c in g["cards"]]
    assert {c["id"] for c in cards} == {"yes"}
    unknown = view["unverified"]["cards"]
    assert {c["id"] for c in unknown} == {"unknown", "uncertain"}
    assert all(c["unverified"] == ["Chưa rõ có cho mang thú cưng không"] for c in unknown)
    assert all("Cho mang thú cưng" not in str(c["why"]) for c in unknown)
    assert [(r["rule"], r["count"]) for r in view["excluded"]["by_rule"]] == [("hard:pets", 1)]


@pytest.mark.parametrize("filters", [[], [hard("pets", "not_allowed", policy="flag")],
                                     [hard("pets", "not_allowed")]])
def test_pet_context_normalizes_missing_filter_without_duplicate(filters):
    e = engine()
    out = e.create(pet_input(hard_filters=filters))
    assert_pet_lists(out["view"])
    assert len(e.store.get(out["id"]).search_input.hard_filters) == 1


def test_pet_rebase_restore_and_legacy_cached_session_are_protected():
    e = engine()
    tools = Tools(e)
    sid = e.create(si().model_dump(mode="json"))["id"]
    assert_pet_lists(tools.rebase(sid, {"search_input": pet_input()})["view"])
    snapshot = tools.snapshot(sid)
    snapshot["search_input"]["hard_filters"] = []
    tools.restore(snapshot)
    assert_pet_lists(tools.load(sid)["view"])
    # A legacy in-memory session may already have a cached result.
    s = e.store.get(sid)
    s.search_input = si(context={"companions": ["pet"]})
    s.output = {"stale": True}
    assert_pet_lists(e.load(sid)["view"])
    assert s.output is None


def test_known_ban_can_be_found_and_selected_without_pet_conflict_or_nudge():
    e = engine()
    sid = e.create(pet_input())["id"]
    found = e.search(sid, "No Pets Cafe")
    assert not found["cards"]
    assert [p["id"] for p in found["outside"]] == ["no"]
    view = e.act(sid, {"type": "select", "place_id": "no"})["view"]
    assert view["selected"] == ["no"]
    assert view["pending"] is None
    assert not any("pets" in str(c) for c in view["feasibility"]["conflicts"])
    assert not any("thú cưng" in w.lower() for w in view["feasibility"]["warnings"])
    selected = next(c for g in view["groups"] for c in g["cards"] if c["id"] == "no")
    assert {"text": "Không cho mang thú cưng, theo 3 người", "sid": "pets"} in selected["tradeoffs"]
    assert not selected["top"] and not selected["suggested"]
    assert e.confirm(sid)["confirmed"][0]["id"] == "no"


def test_unknown_selection_has_only_factual_pet_label_not_a_warning():
    e = engine()
    sid = e.create(pet_input())["id"]
    view = e.act(sid, {"type": "select", "place_id": "unknown"})["view"]
    assert not any("thú cưng" in w.lower() for w in view["feasibility"]["warnings"])
    selected = next(c for g in view["groups"] for c in g["cards"] if c["id"] == "unknown")
    assert selected["unverified"] == ["Chưa rõ có cho mang thú cưng không"]
    assert e.confirm(sid)["confirmed"][0]["id"] == "unknown"


def test_pet_policy_does_not_block_explicit_lodging_selection():
    e = Engine(Data([srec("stay", group="stay", features={"pets": "not_allowed"})]), load_settings(), Store(None))
    sid = e.create(pet_input())["id"]
    view = e.act(sid, {"type": "set_lodging", "lodging": {"kind": "corpus", "id": "stay"}})["view"]
    assert view["lodging"]["chosen"]["id"] == "stay"
    assert e.confirm(sid, for_planning=True)["lodging"]["id"] == "stay"


def test_pet_permission_line_requires_served_evidence_not_fit():
    e = engine()
    view = e.create(pet_input())["view"]
    allowed = next(c for g in view["groups"] for c in g["cards"] if c["id"] == "yes")
    assert {"text": "Cho mang thú cưng, theo 3 người", "sid": "pets"} in allowed["why"]


def test_legacy_relax_cannot_make_a_known_pet_ban_a_recommendation():
    e = engine()
    sid = e.create(pet_input())["id"]
    e.act(sid, {"type": "relax", "place_id": "no", "feature": "pets"})
    assert_pet_lists(e.load(sid)["view"])


@pytest.mark.parametrize("features", [{}, {"pets": feat("allowed", status="UNCERTAIN")},
                                      {"pets": {**feat("allowed"), "evidence": []}},
                                      {"pets": feat("allowed", dist={"allowed": 3, "not_allowed": 1})}])
def test_pet_fit_or_unbacked_matches_cannot_claim_permission(features):
    from decision.cards import card
    from decision.model import Cand

    c = Cand(srec("fit", features=features), "experience")
    c.matches = [("pets", "allowed", 1.0, 3)]
    got = card(c, si(), load_settings())
    assert not any(line["sid"] == "pets" for line in got["why"])


def test_chat_does_not_propose_pet_banned_place_cards():
    from datetime import date
    from types import SimpleNamespace
    from decision.assistant import DecisionTurn

    e = engine()
    sid = e.create(pet_input())["id"]
    s = e.store.get(sid)
    reader = SimpleNamespace(knowledge=SimpleNamespace(view=lambda pid, *args: {"id": pid}))
    turn = DecisionTurn(e, s, e._result(s), {}, "gợi ý quán", date.today(), reader=reader)
    turn.seen_ids = ["no", "yes"]
    got = turn.cards("No Pets Cafe và Pet Friendly Cafe")
    assert got["ids"] == ["yes"]


@pytest.mark.corpus
def test_real_corpus_pet_bans_are_not_recommended():
    region = shared().region().warm()
    pets = region.feature("pets")
    bans = {pid for pid, val, firm in zip(region.ids, pets.value, pets.firm)
            if val == "not_allowed" and firm}
    assert bans, "real corpus must contain evidenced pet bans"
    e = Engine(Data(region=region), load_settings(), Store(None))
    ordinary = e.create(si().model_dump(mode="json"))
    sid = ordinary["id"]
    before = e._result(e.store.get(sid))
    before_ids = {pid for ids in before.ranked.values() for pid in ids} | set(before.unverified)
    assert bans & before_ids, "the control input must recommend at least one pet-banned place"
    out = Tools(e).rebase(sid, {"search_input": pet_input()})
    after = e._result(e.store.get(sid))
    after_ids = {pid for ids in after.ranked.values() for pid in ids} | set(after.unverified)
    assert not bans & after_ids
    assert all(after.cands[pid].status == "excluded" for pid in bans if pid in after.cands)
    assert out["view"]["unverified"]["count"] > 0
    print(f"pet bans: corpus={len(bans)}, recommended before={len(bans & before_ids)}, after={len(bans & after_ids)}")
