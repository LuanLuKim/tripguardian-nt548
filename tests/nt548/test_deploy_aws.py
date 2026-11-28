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
        out |= {k: {"value": v} for k, v in {
            "target_group_arn_blue": "arn:tg/blue", "target_group_arn_green": "arn:tg/green",
            "alb_arn_suffix": "app/nt548-alb/1", "target_group_arn_suffix_blue": "targetgroup/nt548-blue/1",
            "target_group_arn_suffix_green": "targetgroup/nt548-green/2",
            "asg_name_blue": "nt548-blue", "asg_name_green": "nt548-green"}.items()}
    print(json.dumps(out))
elif "apply" in args:
    v = dict(a.split("=", 1) for a in (args[i + 1] for i, x in enumerate(args) if x == "-var"))
    v["weight_blue"] = int(v["weight_blue"])
    s["vars"] = v
    s["applies"].append(v)
    state.write_text(json.dumps(s))
'''

# canary_watch.py cloudwatch stand-in: records its arguments, exits FAKE_CANARY (0 promote, 1 roll back)
FAKE_CANARY = r'''
import json, os, sys
from pathlib import Path
state = Path(sys.argv[1]); args = sys.argv[2:]
s = json.loads(state.read_text())
s["canary"].append(args)
state.write_text(json.dumps(s))
sys.exit(int(os.environ.get("FAKE_CANARY", "0")))
'''

FAKE_AWS = r'''
import json, os, sys
from pathlib import Path
state = Path(sys.argv[1]); args = sys.argv[2:]
s = json.loads(state.read_text())
if "describe-instance-refreshes" in args:
    asg = args[args.index("--auto-scaling-group-name") + 1]
    s["refresh_calls"].append(asg)
    state.write_text(json.dumps(s))
    print(os.environ.get("FAKE_REFRESH_" + asg.rsplit("-", 1)[-1].upper(), "Successful"))
    sys.exit(0)
color = args[args.index("--target-group-arn") + 1].rsplit("/", 1)[-1]
s["health_calls"][color] = s["health_calls"].get(color, 0) + 1
state.write_text(json.dumps(s))
bad_after = os.environ.get("FAKE_UNHEALTHY_" + color.upper())
print("unhealthy" if bad_after is not None and s["health_calls"][color] > int(bad_after) else "healthy\thealthy")
'''


@pytest.fixture
def env(tmp_path):
    state = tmp_path / "state.json"
    state.write_text(json.dumps({"vars": {}, "applies": [], "health_calls": {}, "refresh_calls": [], "canary": []}))
    py = Path(sys.executable).as_posix()
    for name, src in (("terraform", FAKE_TF), ("aws", FAKE_AWS), ("canary", FAKE_CANARY)):
        (tmp_path / f"{name}.py").write_text(src)
        wrapper = tmp_path / name
        wrapper.write_text(f'#!/usr/bin/env bash\nexec "{py}" "{(tmp_path / name).as_posix()}.py" '
                           f'"{state.as_posix()}" "$@"\n')
        wrapper.chmod(0o755)
    return {"state": state, "env": {**os.environ, "TERRAFORM": (tmp_path / "terraform").as_posix(),
                                    "AWS": (tmp_path / "aws").as_posix(), "PYTHON": py, "CANARY_SECONDS": "0",
                                    "CANARY_CMD": (tmp_path / "canary").as_posix(),
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


def test_automatic_run_skips_an_environment_that_is_down(env):
    # nt548-deploy-aws.yml sets FIRST_DEPLOY=0 after a merge: an empty state is a torn-down lab, not a first deploy
    p, s = run(env, "deploy", "sha1", FIRST_DEPLOY="0")
    assert p.returncode == 0, p.stderr
    assert s["applies"] == []
    assert "envs/demo is down: nothing to deploy" in p.stdout


def test_automatic_run_still_releases_onto_a_running_environment(env):
    run(env, "deploy", "sha1")
    p, s = run(env, "deploy", "sha2", FIRST_DEPLOY="0")
    assert p.returncode == 0, p.stderr
    assert weights(s)[1:] == [("sha1", "sha2", 100), ("sha1", "sha2", 90), ("sha1", "sha2", 0)]


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
    assert p.stdout.strip() == "live=blue blue=sha1 green=sha2 weight_blue=100 data_blue=r-a data_green=r-a"


def test_rollback_with_nothing_deployed_fails(env):
    p, s = run(env, "rollback")
    assert p.returncode == 1 and s["applies"] == []


def test_usage_and_bad_tags(env):
    p, _ = run(env, "deploy")
    assert p.returncode == 2
    p, s = run(env, "deploy", "x; rm -rf /")
    assert p.returncode == 2 and s["applies"] == []


def test_canary_compares_the_new_target_group_with_the_live_one(env):
    run(env, "deploy", "sha1")
    p, s = run(env, "deploy", "sha2")
    assert p.returncode == 0, p.stderr
    args = s["canary"][-1]
    assert args[args.index("cloudwatch") + 1:] == ["--lb", "app/nt548-alb/1", "--old-tg", "targetgroup/nt548-blue/1",
                                                   "--new-tg", "targetgroup/nt548-green/2"]
    assert args[:2] == ["--step-seconds", "0"]


def test_canary_verdict_rollback_goes_back(env):
    run(env, "deploy", "sha1")
    p, s = run(env, "deploy", "sha2", FAKE_CANARY="1")
    assert p.returncode == 1
    assert weights(s)[1:] == [("sha1", "sha2", 100), ("sha1", "sha2", 90), ("sha1", "sha2", 100)]
    assert "rolled back to blue" in p.stdout


def test_waits_for_the_instance_refresh_of_the_idle_color(env):
    run(env, "deploy", "sha1")
    p, s = run(env, "deploy", "sha2")
    assert p.returncode == 0, p.stderr
    assert "nt548-green" in s["refresh_calls"] and "nt548-blue" not in s["refresh_calls"]


def test_failed_refresh_never_gets_traffic(env):
    run(env, "deploy", "sha1")
    p, s = run(env, "deploy", "sha2", FAKE_REFRESH_GREEN="Failed")
    assert p.returncode == 1
    assert weights(s)[1:] == [("sha1", "sha2", 100)]
    assert "never got healthy" in p.stdout


def data(s):
    return [(a["image_tag_blue"], a["image_tag_green"], a["weight_blue"], a["data_release_blue"],
             a["data_release_green"]) for a in s["applies"]]


def test_data_release_goes_idle_then_canary_then_promote_with_the_live_image(env):
    run(env, "deploy", "sha1")
    run(env, "deploy", "sha2")  # green live on sha2, blue idle on sha1
    p, s = run(env, "data", "r-b")
    assert p.returncode == 0, p.stderr
    # blue (idle) gets r-b and green's image sha2, not its own old sha1; green keeps r-a for a rollback
    assert data(s)[-3:] == [("sha2", "sha2", 0, "r-b", "r-a"), ("sha2", "sha2", 10, "r-b", "r-a"),
                            ("sha2", "sha2", 100, "r-b", "r-a")]
    assert "data r-b: promoted blue" in p.stdout
    p, s = run(env, "rollback")  # back to the old data in one apply
    assert data(s)[-1] == ("sha2", "sha2", 0, "r-b", "r-a")


def test_code_deploy_after_a_data_release_keeps_the_new_data(env):
    run(env, "deploy", "sha1")
    run(env, "data", "r-b")  # green live: sha1 + r-b
    p, s = run(env, "deploy", "sha3")
    assert p.returncode == 0, p.stderr
    # blue (idle, still r-a) must get green's r-b with sha3, else the code deploy would undo the data release
    assert data(s)[-1] == ("sha3", "sha1", 100, "r-b", "r-b")


def test_data_release_that_never_gets_healthy_keeps_the_old_data_live(env):
    # on AWS the instance runs data_check before the app: a refused release never becomes a healthy target
    run(env, "deploy", "sha1")
    p, s = run(env, "data", "r-b-drop", FAKE_UNHEALTHY_GREEN="0")
    assert p.returncode == 1
    assert data(s)[1:] == [("sha1", "sha1", 100, "r-a", "r-b-drop")]
    assert "data r-b-drop: green never got healthy, traffic stayed on blue" in p.stdout


def test_data_release_needs_a_running_environment_and_a_release_name(env):
    p, s = run(env, "data", "r-b")
    assert p.returncode == 1 and s["applies"] == []
    assert "envs/demo is down" in p.stdout
    run(env, "deploy", "sha1")
    for bad in ("b", "r-b; rm -rf /", ""):
        p, s = run(env, "data", bad)
        assert p.returncode == 2 and len(s["applies"]) == 1


def test_name_prefix_reaches_terraform(env):
    p, s = run(env, "deploy", "sha1", NAME_PREFIX="nt548-dl")
    assert p.returncode == 0, p.stderr
    assert s["applies"][0]["name_prefix"] == "nt548-dl"
