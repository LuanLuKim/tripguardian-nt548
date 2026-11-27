"""ops/nt548/deploy_aws.sh against a fake terraform (state = the last applied -var values) and a fake aws (target
health): the idle color gets the new sha, traffic moves only after it is healthy, a failed canary goes back, and
rollback flips the weight without touching the images."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "ops/nt548/deploy_aws.sh"
BASH = shutil.which("bash")
if not BASH or (os.name == "nt" and "system32" in BASH.lower()):  # WSL's bash.exe cannot see these paths
    pytest.skip("needs a POSIX bash", allow_module_level=True)

FAKE_TF = r'''
import json, sys
from pathlib import Path
state = Path(sys.argv[1]); args = sys.argv[2:]
s = json.loads(state.read_text())
if "output" in args:
    out = {k: {"value": v} for k, v in s["vars"].items()}
    if s["vars"]:
        out |= {"target_group_arn_blue": {"value": "arn:tg/blue"}, "target_group_arn_green": {"value": "arn:tg/green"}}
    print(json.dumps(out))
elif "apply" in args:
    v = dict(a.split("=", 1) for a in (args[i + 1] for i, x in enumerate(args) if x == "-var"))
    v["weight_blue"] = int(v["weight_blue"])
    s["vars"] = v
    s["applies"].append(v)
    state.write_text(json.dumps(s))
'''

FAKE_AWS = r'''
import json, os, sys
from pathlib import Path
state = Path(sys.argv[1]); args = sys.argv[2:]
s = json.loads(state.read_text())
color = args[args.index("--target-group-arn") + 1].rsplit("/", 1)[-1]
s["health_calls"][color] = s["health_calls"].get(color, 0) + 1
state.write_text(json.dumps(s))
bad_after = os.environ.get("FAKE_UNHEALTHY_" + color.upper())
print("unhealthy" if bad_after is not None and s["health_calls"][color] > int(bad_after) else "healthy\thealthy")
'''


@pytest.fixture
def env(tmp_path):
    state = tmp_path / "state.json"
    state.write_text(json.dumps({"vars": {}, "applies": [], "health_calls": {}}))
    py = Path(sys.executable).as_posix()
    for name, src in (("terraform", FAKE_TF), ("aws", FAKE_AWS)):
        (tmp_path / f"{name}.py").write_text(src)
        wrapper = tmp_path / name
        wrapper.write_text(f'#!/usr/bin/env bash\nexec "{py}" "{(tmp_path / name).as_posix()}.py" '
                           f'"{state.as_posix()}" "$@"\n')
        wrapper.chmod(0o755)
    return {"state": state, "env": {**os.environ, "TERRAFORM": (tmp_path / "terraform").as_posix(),
                                    "AWS": (tmp_path / "aws").as_posix(), "PYTHON": py, "CANARY_SECONDS": "0",
                                    "HEALTH_TIMEOUT": "1", "HEALTH_POLL": "0", "GITHUB_STEP_SUMMARY": ""}}


def run(env, *args, **extra):
    p = subprocess.run([BASH, SCRIPT.as_posix(), *args], capture_output=True, text=True,
                       env={**env["env"], **extra}, cwd=ROOT)
    s = json.loads(env["state"].read_text())
    return p, s


def weights(s):
    return [(a["image_tag_blue"], a["image_tag_green"], a["weight_blue"]) for a in s["applies"]]


def test_first_deploy_puts_the_sha_on_both_colors(env):
    p, s = run(env, "deploy", "sha1")
    assert p.returncode == 0, p.stderr
    assert weights(s) == [("sha1", "sha1", 100)]
    assert s["applies"][0]["data_release_blue"] == "r-a"


def test_deploy_goes_idle_then_canary_then_promote(env):
    run(env, "deploy", "sha1")
    p, s = run(env, "deploy", "sha2")
    assert p.returncode == 0, p.stderr
    # blue is live: green gets sha2 at 0 %, then 10 %, then 100 %; blue keeps sha1 for a rollback
    assert weights(s)[1:] == [("sha1", "sha2", 100), ("sha1", "sha2", 90), ("sha1", "sha2", 0)]
    assert "promoted green" in p.stdout
    p, s = run(env, "deploy", "sha3")  # now green is live, so blue is the idle one
    assert weights(s)[-3:] == [("sha3", "sha2", 0), ("sha3", "sha2", 10), ("sha3", "sha2", 100)]


def test_unhealthy_idle_color_never_gets_traffic(env):
    run(env, "deploy", "sha1")
    p, s = run(env, "deploy", "sha2", FAKE_UNHEALTHY_GREEN="0")
    assert p.returncode == 1
    assert weights(s)[1:] == [("sha1", "sha2", 100)]
    assert "never got healthy" in p.stdout


def test_failed_canary_rolls_back_to_the_live_color(env):
    run(env, "deploy", "sha1")
    p, s = run(env, "deploy", "sha2", FAKE_UNHEALTHY_GREEN="1")  # healthy once, then fails during the canary
    assert p.returncode == 1
    assert weights(s)[1:] == [("sha1", "sha2", 100), ("sha1", "sha2", 90), ("sha1", "sha2", 100)]
    assert "rolled back to blue" in p.stdout


def test_manual_rollback_only_moves_traffic(env):
    run(env, "deploy", "sha1")
    run(env, "deploy", "sha2")
    p, s = run(env, "rollback")
    assert p.returncode == 0, p.stderr
    assert weights(s)[-1] == ("sha1", "sha2", 100)
    assert "rollback: green -> blue in" in p.stdout
    p, _ = run(env, "status")
    assert p.stdout.strip() == "live=blue blue=sha1 green=sha2 weight_blue=100"


def test_rollback_with_nothing_deployed_fails(env):
    p, s = run(env, "rollback")
    assert p.returncode == 1 and s["applies"] == []


def test_usage_and_bad_tags(env):
    p, _ = run(env, "deploy")
    assert p.returncode == 2
    p, s = run(env, "deploy", "x; rm -rf /")
    assert p.returncode == 2 and s["applies"] == []
