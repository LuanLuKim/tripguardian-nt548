"""ops/nt548/aiops/log_patterns.py on synthetic compose logs: injected LLM errors come out on top as a new pattern."""

import importlib.util
import json
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

pytest.importorskip("drain3")

spec = importlib.util.spec_from_file_location(
    "log_patterns", Path(__file__).resolve().parents[2] / "ops/nt548/aiops/log_patterns.py")
lp = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = lp  # dataclasses look their module up there
spec.loader.exec_module(lp)

T0 = datetime(2026, 11, 26, 11, 0, tzinfo=timezone.utc)


def compose_log(minutes: int = 20, fault_from: int | None = 10, error_rate: float = 0.3, seed: int = 0) -> list[str]:
    """Lines as `docker compose logs --timestamps` prints them: llm-fake and model-gateway, 6 requests a minute.

    From `fault_from` on, `error_rate` of the completions fail like FAKE_ERROR_RATE makes llm_fake fail."""
    rng = random.Random(seed)
    out = []
    for i in range(minutes * 6):
        t = T0 + timedelta(seconds=10 * i)
        ts = t.strftime("%Y-%m-%dT%H:%M:%S.%f") + "123Z"  # docker prints nanoseconds
        ip = f"172.18.0.{rng.randint(2, 9)}:{rng.randint(30000, 60000)}"
        failed = fault_from is not None and i >= fault_from * 6 and rng.random() < error_rate
        if failed:
            out.append(f"llm-fake-v1-1  | {ts} {t:%Y-%m-%d %H:%M:%S},{rng.randint(100, 999)} ERROR llm_fake "
                       f"injected error status=500 model=fake-model version=v1")
            out.append(f'llm-fake-v1-1  | {ts} INFO:     {ip} - "POST /v1/chat/completions HTTP/1.1" 500 '
                       f"Internal Server Error")
        else:
            out.append(f"llm-fake-v1-1  | {ts} {t:%Y-%m-%d %H:%M:%S},{rng.randint(100, 999)} INFO llm_fake "
                       f"completion model=fake-model version=v1 stream=False")
            out.append(f'llm-fake-v1-1  | {ts} INFO:     {ip} - "POST /v1/chat/completions HTTP/1.1" 200 OK')
        out.append(f"model-gateway-1  | {ts} request {rng.randint(1000, 9999)} took {rng.randint(40, 900)} ms")
    return out


def test_parse_reads_compose_prefix_nanoseconds_and_continuation_lines():
    lines = lp.parse([
        "web-1  | 2026-11-26T11:00:00.123456789Z GET / 200",
        "2026-11-26 11:00:01,500 ERROR boom",
        "  File \"x.py\", line 3, in f",
        "",
    ])
    assert [x.service for x in lines] == ["web-1", "", ""]
    assert lines[0].t == datetime(2026, 11, 26, 11, 0, 0, 123456, tzinfo=timezone.utc)
    assert lines[2].t == lines[1].t and lines[2].message.startswith("File")


@pytest.mark.parametrize("message, expected", [
    ("ERROR llm_fake injected error status=500 model=x", "ERROR"),
    ('INFO:     1.2.3.4:5 - "POST /v1/chat/completions HTTP/1.1" 503 Service Unavailable', "ERROR"),
    ("WARNING slow upstream", "WARNING"),
    ('INFO:     1.2.3.4:5 - "GET / HTTP/1.1" 200 OK', "INFO"),
])
def test_level(message, expected):
    assert lp.level(message) == expected


def test_injected_errors_are_the_top_new_patterns():
    patterns = lp.top(lp.parse(compose_log()), window_min=10)
    first_two = patterns[:2]
    assert all(p["anomaly"] == "new" and p["level"] == "ERROR" and p["baseline"] == 0 for p in first_two)
    text = " ".join(p["pattern"] for p in first_two)
    assert "injected error" in text and "500 Internal Server Error" in text
    assert 0.2 * 60 <= first_two[0]["count"] <= 0.4 * 60  # ~30 % of 60 requests in the window
    normal = [p for p in patterns if "200 OK" in p["pattern"]]
    assert normal and normal[0]["anomaly"] is None and normal[0]["baseline"] > 0


def test_variable_parts_are_masked_into_one_template():
    patterns = lp.top(lp.parse(compose_log(fault_from=None)), window_min=10)
    gateway = [p for p in patterns if p["pattern"].startswith("[model-gateway]")]
    assert len(gateway) == 1 and "<NUM>" in gateway[0]["pattern"]


def test_quiet_logs_have_no_anomaly():
    assert all(p["anomaly"] is None for p in lp.top(lp.parse(compose_log(fault_from=None)), window_min=10))


def test_no_baseline_means_nothing_is_new():
    patterns = lp.top(lp.parse(compose_log(minutes=10, fault_from=0)), window_min=10)
    assert patterns and all(p["anomaly"] != "new" for p in patterns)
    assert any(p["anomaly"] == "spike" for p in patterns)  # errors still count against a baseline of 1


def test_error_spike_against_a_small_baseline():
    log = compose_log(fault_from=10, error_rate=0.3)
    log.insert(10, "llm-fake-v1-1  | 2026-11-26T11:01:00.000000000Z 2026-11-26 11:01:00,001 ERROR llm_fake "
                   "injected error status=500 model=fake-model version=v1")
    patterns = lp.top(lp.parse(log), window_min=10)
    injected = next(p for p in patterns if "injected error" in p["pattern"])
    assert injected["anomaly"] == "spike" and injected["baseline"] == 1
    assert patterns.index(injected) < 2  # still above every normal pattern


def test_cli_writes_the_incident_input(tmp_path):
    log = tmp_path / "blue.log"
    log.write_text("\n".join(compose_log()), encoding="utf-8")
    out = tmp_path / "patterns.json"
    assert lp.main(["top", str(log), "--window-min", "10", "--out", str(out)]) == 0
    patterns = json.loads(out.read_text(encoding="utf-8"))
    assert {"pattern", "count", "baseline", "level"} <= set(patterns[0])
    assert patterns[0]["anomaly"] == "new"
