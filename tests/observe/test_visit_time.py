import pytest

from corpus.observe import bucket, distribution, parse_minutes


@pytest.mark.parametrize("quote,expected", [
    ("ở đây khoảng 2 tiếng", (120, 120)),
    ("đi hết 45 phút", (45, 45)),
    ("đi 1-2 tiếng", (60, 120)),
    ("1h30-2h", (90, 120)),
    ("1 tiếng 30 phút", (90, 90)),
    ("một tiếng rưỡi", (90, 90)),
    ("hai tiếng", (120, 120)),
    ("1,5 giờ", (90, 90)),
    ("nửa tiếng", (30, 30)),
    ("mất nửa ngày", (180, 300)),
    ("chơi cả ngày", (360, 600)),
    ("tầm 20’", (20, 20)),
    ("tầm 2h là hết", (120, 120)),
])
def test_parse_minutes_reads_a_stated_duration(quote, expected):
    assert parse_minutes(quote) == expected


@pytest.mark.parametrize("quote", [
    "lúc 7h sáng", "đến lúc 7h", "Đi 7h-9h sáng", "trước 5 giờ", "khoảng 2 giờ chiều", "mở cửa 8h",
    "đi nhanh 30 phút, kỹ thì 2 tiếng",  # two different durations: no single reading
    "trải nghiệm 1 ngày ở đây", "trong một ngày rưỡi", "vài tiếng", "rất lâu", "",
])
def test_parse_minutes_refuses_clock_times_vague_and_double_figures(quote):
    assert parse_minutes(quote) is None


def test_bucket_follows_the_ontology_boundaries():
    assert [bucket(m) for m in (30, 60, 61, 120, 121, 300, 480)] == [
        "under_1h", "under_1h", "1_to_2h", "1_to_2h", "half_day", "half_day", "full_day"]


CFG = {"min_n": 1, "outlier_min_n": 4, "outlier_ratio": 2.5, "single_short": 0.75, "single_long": 1.5, "round_to": 15}


def test_distribution_median_quartiles_and_outliers():
    got = distribution([(60, 60), (90, 90), (120, 120), (120, 120), (600, 600)], CFG)  # 600 is > 2.5x the median
    assert got == {"short": 90, "typical": 105, "long": 120, "n": 4, "outliers": 1}


def test_distribution_one_figure_widens_a_point_and_keeps_a_range():
    assert distribution([(120, 120)], CFG)["short"] == 90 and distribution([(120, 120)], CFG)["long"] == 180
    got = distribution([(60, 120)], CFG)
    assert (got["short"], got["typical"], got["long"]) == (60, 90, 120)
    assert distribution([], CFG) is None
    assert distribution([(60, 60)], {**CFG, "min_n": 2}) is None
