"""corpus.events.seasons: the model's grouping of season names, and only what code can check of it stands."""

import json
from datetime import date

from corpus.events import seasons
from corpus.events.gate import clean_name

NAMES = [{"name": n, "sources": 3, "quote": ""} for n in ("dâu tây", "mùa dâu", "dâu tằm", "thác Datanla", "hoa dã quỳ", "mùa khô")]


def test_a_group_keeps_numbers_that_exist_and_names_that_share_a_word_with_the_first():
    got = seasons.check({"groups": [[0, 1, 4, 99], [2, 2], [5]], "not_seasons": [3, 0, 77]}, NAMES)
    assert got["groups"] == [["dâu tây", "mùa dâu"]]           # "hoa dã quỳ" shares nothing with "dâu tây"; 99 is no name; one name is no group
    assert got["not_seasons"] == ["thác Datanla"]              # "dâu tây" is in a group: the model cannot drop it too


def test_a_name_in_two_groups_goes_to_the_first():
    got = seasons.check({"groups": [[0, 1], [1, 2]], "not_seasons": []}, NAMES)
    assert got["groups"] == [["dâu tây", "mùa dâu"]]


def test_the_call_is_cached_by_the_names_and_a_failed_call_is_none(tmp_path):
    calls = []

    async def ask(**f):
        calls.append(f)
        return {"groups": [[0, 1]], "not_seasons": [3]}
    today = date(2026, 11, 16)
    first = seasons.group(NAMES, "Đà Lạt", today, tmp_path, ask)
    again = seasons.group(NAMES, "Đà Lạt", today, tmp_path, ask)
    assert first == again == {"groups": [["dâu tây", "mùa dâu"]], "not_seasons": ["thác Datanla"]} and len(calls) == 1
    assert "0. dâu tây (3 trang)" in calls[0]["names"]

    async def broken(**f):
        raise TimeoutError
    assert seasons.group(NAMES[:3], "Đà Lạt", today, tmp_path, broken) is None


def test_a_hedge_word_before_a_number_leaves_a_title_and_nothing_else_does():
    assert clean_name("Triển lãm khoảng 150 tranh cổ động tấm lớn") == "Triển lãm 150 tranh cổ động tấm lớn"
    assert clean_name("Hơn 30 nghệ sĩ  Đà Lạt") == "30 nghệ sĩ Đà Lạt"
    assert clean_name("Khoảng lặng của Đà Lạt") == "Khoảng lặng của Đà Lạt"      # not before a number
    assert clean_name("Chợ đêm Đà Lạt") == "Chợ đêm Đà Lạt"
