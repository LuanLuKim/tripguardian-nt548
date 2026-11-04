"""Prod e2e 2026-11-03: facts the agent was told to keep in a field, not as notes (N4)."""

from datetime import date

from test_redesign_drill import big  # noqa: F401  (fixture)

from trip.agent.tools import TurnTools
from trip.domain.state import TripState

TEXT = ("Mình đi với bạn thân, 3 triệu mỗi người chưa tính vé xe. Đi xe khách từ TP.HCM, không tự lái xe máy, sợ lạnh.")


def _tools(catalog, tmp_path):
    return TurnTools(TripState(), TEXT, 1, catalog, date(2026, 11, 3), gaps=tmp_path / "g.jsonl")


def test_cold_fear_and_not_driving_have_fields(served_catalog, tmp_path):
    t = _tools(served_catalog, tmp_path)
    out = t.run("record_fact", {"facts": [
        {"field": "soft", "op": "add", "value": "heater=present:love", "quote": "sợ lạnh", "how": "said"},
        {"field": "soft", "op": "add", "value": "cold=present:avoid", "quote": "sợ lạnh", "how": "said"},
        {"field": "driver", "op": "set", "value": "hired", "quote": "không tự lái xe máy", "how": "said"}]})
    assert not any("error" in r for r in out["results"]), out
    assert t.state.driver.value == "hired" and {"cold=present", "heater=present"} <= set(t.state.soft)


def test_a_skipped_photo_card_stays_gone_after_a_reload(big, cfg, tmp_path):
    """N5: Bỏ qua on a photo-style card; loading the session again must not open it."""
    from dataclasses import replace

    from test_redesign_drill import FakeLooks, ids, variant
    from trip_fixtures import ScriptedChat, say

    from trip.api.engine import Engine, TurnInput
    from trip.infrastructure.sessions import SessionStore
    cfg = replace(cfg, drills={"săn mây": {"header": "Kiểu săn mây", "question": "Săn mây kiểu nào?", "variants": [
        variant(label, cue) for label, cue in (("Sương sớm", "sương"), ("Trời trong", "trong"))]}})
    looks = FakeLooks({cue: [(p, .2) for p in ids(1, 41)] for cue in ("sương", "trong")})
    engine = Engine(big, cfg, SessionStore(tmp_path), ScriptedChat(say("Săn mây nhé."), say("Rõ rồi.")),
                    today=lambda: date(2026, 10, 15), looks=looks)
    sid = engine.create("first", "nothing")["id"]
    engine.turn(sid, TurnInput(kind="text", text="muốn săn mây"), lambda *_: None)
    assert [t["kind"] for t in engine.load(sid)["card"]["tabs"]] == ["drill"]
    engine.turn(sid, TurnInput(kind="deck", answers={"drill.săn mây": ["skip"]}), lambda *_: None)
    again = Engine(big, cfg, SessionStore(tmp_path), ScriptedChat(), today=lambda: date(2026, 10, 15), looks=looks)
    card = again.load(sid)["card"]
    assert not any(t["kind"] == "drill" for t in (card or {}).get("tabs", []))
