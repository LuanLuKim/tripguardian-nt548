"""ops/nt548/aiops/detect.py on synthetic series: faults are found, stable stretches stay quiet."""

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("sklearn")

spec = importlib.util.spec_from_file_location("detect", Path(__file__).resolve().parents[2] / "ops/nt548/aiops/detect.py")
detect = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = detect  # dataclasses look their module up there
spec.loader.exec_module(detect)


def test_synth_is_repeatable_and_labels_one_fault():
    a, b = detect.synth("spike", seed=3), detect.synth("spike", seed=3)
    assert np.array_equal(a.values, b.values) and len(a.faults()) == 1
    start, end = a.faults()[0]
    assert end - start == 5 and start >= len(a.values) // 3
    assert detect.synth("quiet", seed=3).faults() == []


def test_runs_and_alarms_need_consecutive_points():
    flags = np.array([0, 1, 0, 1, 1, 1, 0, 1], dtype=bool)
    assert detect.runs(flags) == [(1, 2), (3, 6), (7, 8)]
    assert detect.alarms(flags, 2).tolist() == [False, False, False, False, True, True, False, False]


@pytest.mark.parametrize("name", ["static", "ewma", "iforest"])
def test_every_detector_finds_a_spike_quickly(name):
    series = detect.synth("spike", seed=1)
    alarm = detect.detect(series, train=200)[name]
    s = detect.score(alarm, series.faults())
    assert s.detected == 1 and s.delays[0] <= 2


def test_ewma_is_quiet_on_a_series_with_no_fault():
    for seed in range(5):
        series = detect.synth("quiet", seed=seed)
        assert not detect.detect(series, train=200)["ewma"].any(), seed


def test_static_line_misses_a_spike_under_the_cycle_peak_that_ewma_or_iforest_catches():
    """The point of #36: a spike at a trough stays under any line drawn above the daily peak."""
    series = detect.synth("seasonal_spike", seed=2)
    got = detect.detect(series, train=240, period=120)
    faults = series.faults()
    assert detect.score(got["static"], faults).detected == 0
    assert detect.score(got["iforest"], faults).detected == 1


def test_score_counts_a_late_alarm_within_grace_and_a_stray_one_as_false():
    alarm = np.zeros(100, dtype=bool)
    alarm[52:54] = True  # 2 points after the fault [45, 50) ended: within grace
    alarm[80:82] = True  # nowhere near a fault
    s = detect.score(alarm, [(45, 50)], grace=10)
    assert (s.detected, s.delays, s.false_alarms) == (1, [7], 1)


def test_compare_covers_every_scenario_and_detector():
    rows = detect.compare(seeds=2)
    assert {(r["scenario"], r["detector"]) for r in rows} == {(s, d) for s in detect.SCENARIOS for d in ("static", "ewma", "iforest", "combined")}
    assert all(r["faults"] == (0 if r["scenario"] == "quiet" else 2) for r in rows)
    assert detect.table(rows).startswith("| scenario | detector |")


def test_csv_round_trip_and_cli(tmp_path, capsys):
    path = tmp_path / "s.csv"
    assert detect.main(["synth", "spike", "--seed", "1", "--out", str(path)]) == 0
    back = detect.read_csv(path)
    assert back.faults() == detect.synth("spike", seed=1).faults()
    assert detect.main(["run", str(path)]) == 0
    out = capsys.readouterr().out
    assert "ewma:" in out and "detected 1/1" in out
