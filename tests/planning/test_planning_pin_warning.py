"""pin_dropped warning text: short, in the user's voice, and never blames opening hours a place does not have."""

from types import SimpleNamespace as NS

from planning.build import pin_warnings


def ctx(hours):
    return NS(day=NS(index=1), places={"p": NS(name="Đồi Ngô Quyền", hours=hours)})


def result(*reasons):
    return NS(unpinned=("p",), pin_conflicts=(("p", tuple(reasons)),))


def test_unknown_hours_are_never_named_as_the_reason():
    [w] = pin_warnings([ctx(None)], [result("hours")])
    assert "mở cửa" not in w["text"] and w["text"].startswith("Ngày 2: Đồi Ngô Quyền")
    assert w["reason"] == "hours"          # the machine field keeps what the scheduler found


def test_known_hours_are_named_and_the_text_is_short():
    [w] = pin_warnings([ctx({"mon": [(360, 1080)]})], [result("hours")])
    assert "giờ mở cửa" in w["text"] and len(w["text"]) < 140 and "cửa sổ" not in w["text"]


def test_another_reason_is_kept_when_hours_are_unknown():
    [w] = pin_warnings([ctx(None)], [result("hours", "day_window")])
    assert "khung ngày" in w["text"] and "mở cửa" not in w["text"]
