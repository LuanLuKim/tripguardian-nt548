"""The "đang hot" label (Nhịp Đà Lạt, docs/CORPUS.md §Nhịp) is shown on a card and nothing else: no score, rank or filter reads it."""
from fixtures import si, srec

from decision import cards
from decision.model import Cand
from decision.settings import default

CFG = default()
HOT = {"label": "Đang hot", "newest": "2026-10-27", "videos": 4, "authors": 3, "window_days": 30, "as_of": "2026-10-29"}


def test_card_carries_the_label_with_its_dates(monkeypatch):
    monkeypatch.setattr(cards, "pulse_hot", lambda: {"A": HOT})
    assert cards.card(Cand(srec("A"), "experience"), si(), CFG)["hot"] == HOT
    assert cards.card(Cand(srec("B"), "experience"), si(), CFG)["hot"] is None


def test_the_label_changes_no_score_and_no_other_field(monkeypatch):
    monkeypatch.setattr(cards, "pulse_hot", lambda: {})
    plain = cards.card(Cand(srec("A"), "experience"), si(), CFG)
    monkeypatch.setattr(cards, "pulse_hot", lambda: {"A": HOT})
    marked = cards.card(Cand(srec("A"), "experience"), si(), CFG)
    assert {k: v for k, v in marked.items() if k != "hot"} == {k: v for k, v in plain.items() if k != "hot"}
