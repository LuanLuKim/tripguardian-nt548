import pytest

from auto3d import verdict, next_action, kit_blocked


def test_pass_ratio():
    assert verdict([{"status": "ok"}] * 4 + [{"status": "weak"}] * 2) == (True, 5 / 6)


@pytest.mark.parametrize("status, score", [("ok", 1.0), ("weak", 0.5), ("missing", 0.0), ("wrong", 0.0)])
def test_status_weights(status, score):
    assert verdict([{"id": "s1", "status": status}]) == (score >= 0.8, score)


@pytest.mark.parametrize("status", ["ok", "weak", "missing", "wrong"])
@pytest.mark.parametrize("blocking", [False, True])
def test_extra_items_do_not_score_but_can_block(status, blocking):
    items = [{"id": f"s{i}", "status": "ok"} for i in range(6)]
    items += [{"id": f"x{i}", "status": status, "blocking": blocking} for i in range(1, 4)]
    assert verdict(items) == (not blocking, 1.0)


def test_only_extra_items_cannot_pass():
    assert verdict([{"id": "x1", "status": "ok"}]) == (False, 0.0)


@pytest.mark.parametrize("status", ["weak", "missing", "wrong"])
def test_blocking_signature_fails_even_with_high_score(status):
    passed, score = verdict([{"status": "ok"}] * 9 + [{"status": status, "blocking": True}])
    assert score >= 0.8
    assert not passed


def test_blocking_wrong():
    assert verdict([{"status": "ok"}] * 5 + [{"status": "wrong", "blocking": True}]) == (False, 5 / 6)


def test_empty_checklist():
    assert verdict([]) == (False, 0.0)


@pytest.mark.parametrize("scores, expected", [
    ([.5, .6, .6, .6], "stop"), ([.5, .6, .7], "continue"),
    ([.1, .2, .3, .4, .5], "stop"), ([.6, .5, .55], "stop"),
    ([.6, .6], "continue"), ([], "continue"),
])
def test_next_action(scores, expected):
    assert next_action(scores, 5, 2) == expected


@pytest.mark.parametrize("status, cause, blocking, expected", [
    ("missing", "kit", True, True), ("wrong", "kit", True, True),
    ("weak", "kit", True, False), ("missing", "data", True, False),
    ("missing", "kit", False, False), ("ok", "kit", True, False),
])
def test_kit_blocked(status, cause, blocking, expected):
    assert kit_blocked([dict(status=status, cause=cause, blocking=blocking)]) is expected
