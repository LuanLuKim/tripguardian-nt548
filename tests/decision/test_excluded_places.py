"""Explicit Trip exclusions suppress suggestions, not intentional name searches or choices."""
from datetime import date
from types import SimpleNamespace

from fixtures import hard, si, srec
from decision import Data, DecisionOutput, Engine, Store, Tools, load_settings, run_pipeline
from decision.assistant import DecisionTurn
from decision.session import Session, State

CFG = load_settings()


def search_input(**over):
    return si(excluded_places=[{"place_id": "gone", "name": "Quán Tao Ngộ", "source": "user", "evidence": []},
                               {"place_id": "unknown", "name": "Quán Chưa Rõ", "source": "user", "evidence": []}], **over)


def data():
    return Data([srec("open", name="Quán đang mở", dup=1, features={"steep_or_stairs": "absent"}),
                 srec("gone", name="Quán Tao Ngộ", dup=1, features={"steep_or_stairs": "absent"}),
                 srec("unknown", name="Quán Chưa Rõ", dup=1)])


def test_exclusions_leave_every_suggestion_surface_and_alternatives():
    inp = search_input(hard_filters=[hard("steep_or_stairs", "present", policy="flag")])
    res = run_pipeline(Session(id="0123456789ab", search_input=inp, state=State(selected=["open"])), data(), CFG)
    assert res.view["shortlist"] == ["open"]
    assert not ({"gone", "unknown"} & {p for ids in res.ranked.values() for p in ids})
    assert res.unverified == []
    assert res.alternatives.get("open", []) == []


def test_why_not_explains_the_trip_exclusion_not_a_constraint():
    e = Engine(data(), CFG, Store(None))
    sid = e.create(search_input().model_dump(mode="json"))["id"]
    assert e.why_not(sid, "gone")["reasons"] == ["Bạn đã yêu cầu không gợi ý nơi này"]


def test_user_name_search_and_selection_need_no_reminder_and_keep_planning_context():
    tools = Tools(Engine(data(), CFG, Store(None)))
    inp = search_input()
    sid = tools.create({"search_input": inp.model_dump(mode="json")})["id"]
    assert not ({"gone", "unknown"} & {c["id"] for c in tools.read(sid, "search", {"q": "cà phê"})["cards"]})
    found = tools.read(sid, "search", {"q": "Tao Ngộ"})
    assert [c["id"] for c in found["cards"]] == ["gone"] and found["outside"] == []
    view = tools.apply(sid, "act", {"type": "select", "place_id": "gone"}, lambda *_: None)["view"]
    assert "gone" in view["selected"] and view["pending"] is None
    output = DecisionOutput.model_validate(tools.read(sid, "draft", {"any": True})["output"])
    assert output.trip_context.excluded_places == inp.excluded_places
    assert "gone" in {p.id for p in output.confirmed}
    assert not ({"gone", "unknown"} & {p.id for p in output.backup_pool})


def test_category_search_does_not_count_as_an_explicit_name_lookup():
    e = Engine(Data([srec("gone", name="Cà Phê Tao Ngộ")]), CFG, Store(None))
    sid = e.create(search_input().model_dump(mode="json"))["id"]
    assert e.search(sid, "cà phê")["cards"] == []
    assert e.search(sid, "Tao Ngộ")["cards"][0]["id"] == "gone"


def test_chat_cards_suppress_exclusions_unless_user_named_them():
    e = Engine(data(), CFG, Store(None))
    sid = e.create(search_input().model_dump(mode="json"))["id"]
    s = e.store.get(sid)
    reader = SimpleNamespace(knowledge=SimpleNamespace(view=lambda p, *_: {"id": p}))
    for text, expected in [("gợi ý quán tương tự", ["open"]), ("xem Quán Tao Ngộ", ["gone", "open"])]:
        turn = DecisionTurn(e, s, e._result(s), {}, text, date(2026, 11, 4), reader)
        turn.seen_ids = ["gone", "unknown", "open"]
        cards = turn.cards("Quán Tao Ngộ, Quán Chưa Rõ, Quán đang mở")
        assert cards["ids"] == expected
