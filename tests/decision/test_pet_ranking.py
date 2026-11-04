"""Evidence-backed pet access precedes unknown policies within matching suggestions."""

from datetime import date
from types import SimpleNamespace

import pytest

from decision import Data, Engine, Store, Tools, load_settings
from decision.assistant import DecisionTurn
from fixtures import feat, si, srec


def ranked_engine():
    return Engine(Data([
        srec("unknown", name="Unknown Cafe", voices=1000),
        srec("allowed", name="Allowed Cafe", voices=1, features={"pets": "allowed"}),
        srec("unbacked", name="Unbacked Cafe", voices=900,
             features={"pets": {**feat("allowed"), "evidence": []}}),
        srec("uncertain", name="Uncertain Cafe", voices=800,
             features={"pets": feat("allowed", status="UNCERTAIN")}),
        srec("mixed", name="Mixed Cafe", voices=700,
             features={"pets": feat("allowed", dist={"allowed": 3, "not_allowed": 1})}),
        srec("banned", name="Banned Cafe", voices=2000, features={"pets": "not_allowed"}),
        srec("walk", name="Allowed Park", group="nature", category="Công viên",
             features={"pets": "allowed"}),
    ]), load_settings(), Store(None))


@pytest.mark.parametrize("explicit_wish", [False, True])
def test_pet_cafe_search_prefers_evidenced_access_and_keeps_unknown(explicit_wish):
    e = ranked_engine()
    wishes = {"kinds": [{"kind": "quán cà phê", "quote": "quán cho chó vào",
                           "place_ids": ["allowed", "unknown", "unbacked", "uncertain", "mixed", "banned"]}]} if explicit_wish else {}
    out = e.create(si(context={"companions": ["partner", "pet"]}, wishes=wishes).model_dump(mode="json"))
    cards = e.search(out["id"], "Cafe")["cards"]
    assert cards[0]["id"] == "allowed"
    assert {c["id"] for c in cards} == {"allowed", "unknown", "unbacked", "uncertain", "mixed"}
    assert "walk" not in {c["id"] for c in cards}
    assert cards[0]["why"][0]["sid"] == "pets"
    assert next(c for c in cards if c["id"] == "unknown")["unverified"] == ["Chưa rõ có cho mang thú cưng không"]


def test_pet_tab_prefers_backed_access_over_unbacked_served_value():
    e = ranked_engine()
    out = e.create(si(context={"companions": ["pet"]}).model_dump(mode="json"))
    cafe = next(g for g in out["view"]["groups"] if g["id"] == "cafe")
    assert cafe["cards"][0]["id"] == "allowed"
    assert "unbacked" in {c["id"] for c in cafe["cards"]}


def test_pet_chat_cards_prefer_backed_access_before_card_limit():
    e = ranked_engine()
    sid = e.create(si(context={"companions": ["pet"]}).model_dump(mode="json"))["id"]
    s = e.store.get(sid)
    reader = SimpleNamespace(knowledge=SimpleNamespace(view=lambda pid, *args: {"id": pid}))
    turn = DecisionTurn(e, s, e._result(s), {}, "gợi ý Cafe", date(2026, 11, 21), reader=reader)
    turn.seen_ids = ["banned", "unknown", "unbacked", "allowed"]
    got = turn.cards("Banned Cafe, Unknown Cafe, Unbacked Cafe và Allowed Cafe", most=2)
    assert got["ids"] == ["allowed", "unknown"]


def test_adding_and_removing_pet_rebases_search_priority_without_losing_places():
    e = ranked_engine()
    sid = e.create(si().model_dump(mode="json"))["id"]
    assert e.search(sid, "Cafe")["cards"][0]["id"] == "banned"
    tools = Tools(e)
    tools.rebase(sid, {"search_input": si(context={"companions": ["pet"]}).model_dump(mode="json")})
    assert e.search(sid, "Cafe")["cards"][0]["id"] == "allowed"
    tools.rebase(sid, {"search_input": si().model_dump(mode="json")})
    assert e.search(sid, "Cafe")["cards"][0]["id"] == "banned"
