"""The overview heading: facts from the itinerary, a checked Agent answer, a plain fallback."""

from planning import summary

DAYS = [
    {"day": 1, "items": [{"kind": "visit", "place_id": "a", "name": "Chợ Đà Lạt", "start": "08:00"},
                         {"kind": "travel", "name": None},
                         {"kind": "visit", "place_id": "b", "name": "Hồ Xuân Hương", "start": "10:00"}]},
    {"day": 2, "items": [{"kind": "meal_free", "name": "lunch"}]},
    {"day": 3, "items": [{"kind": "visit", "place_id": "c", "name": "Đồi Mộng Mơ", "start": "09:00"}]},
]
AREAS = {"a": "Trung tâm", "b": "Trung tâm", "c": None}


def test_facts_keep_visits_in_order_and_drop_empty_days():
    plan = summary.facts(DAYS, AREAS)
    assert [d["day"] for d in plan] == [1, 3]
    assert [s["name"] for s in plan[0]["stops"]] == ["Chợ Đà Lạt", "Hồ Xuân Hương"]
    assert plan[0]["stops"][0]["area"] == "Trung tâm" and plan[1]["stops"][0]["area"] is None


def test_plain_names_only_the_planned_stops():
    out = summary.plain(summary.facts(DAYS, AREAS), 3)
    assert out["source"] == "plain" and out["title"] == "Đà Lạt 3 ngày"
    assert "Chợ Đà Lạt" in out["text"] and "Đồi Mộng Mơ" in out["text"] and "quanh Trung tâm" in out["text"]


def test_checked_rejects_unusable_answers():
    assert summary.checked({"title": "Sương sớm, cà phê đồi", "text": "Ngày đầu quanh chợ."})["source"] == "agent"
    assert summary.checked({"title": "", "text": "x"}) is None
    assert summary.checked({"title": "a\nb", "text": "x"}) is None
    assert summary.checked({"title": "ok", "text": "x" * 500}) is None


def test_summarize_falls_back_when_the_model_fails(monkeypatch):
    async def down(plan):
        raise RuntimeError("no key")
    monkeypatch.setattr(summary, "_ask", down)
    out = summary.summarize(summary.facts(DAYS, AREAS), 3)
    assert out["source"] == "plain" and out["text"]


def test_summarize_uses_the_agent_answer(monkeypatch):
    async def up(plan):
        return {"title": "Một vòng quanh hồ và đồi", "text": "Ngày 1 quanh chợ và hồ."}
    monkeypatch.setattr(summary, "_ask", up)
    assert summary.summarize(summary.facts(DAYS, AREAS), 3)["source"] == "agent"
