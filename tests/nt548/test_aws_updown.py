"""ops/nt548/aws.sh (#27) against a fake terraform (state = the last applied -var values, emptied by destroy) and a
fake aws (one ops machine whose state start / stop change): up starts the ops machine and applies, down destroys and
stops it, up -> down -> up repeats."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "ops/nt548/aws.sh"
BASH = shutil.which("bash")
if not BASH or (os.name == "nt" and "system32" in BASH.lower()):  # WSL's bash.exe cannot see these paths
    pytest.skip("needs a POSIX bash", allow_module_level=True)

FAKE_TF = r'''
import json, sys
from pathlib import Path
state = Path(sys.argv[1]); args = sys.argv[2:]
s = json.loads(state.read_text())
s["calls"].append([a for a in args if not a.startswith("-chdir")])
def out(name):
    if name == "alb_dns_name":
        return "alb-1.elb.amazonaws.com" if s["vars"] else ""
    return str(s["vars"].get(name, "") if name != "asg_name_blue" and name != "asg_name_green" else
               ("nt548-" + name.rsplit("_", 1)[1] if s["vars"] else ""))
if "output" in args:
    v = out(args[-1])
    state.write_text(json.dumps(s))
    if v == "":
        sys.exit(1)  # terraform: no such output
    print(v, end="")
    sys.exit(0)
if "apply" in args:
    s["vars"] = dict(a.split("=", 1) for a in (args[i + 1] for i, x in enumerate(args) if x == "-var"))
if "destroy" in args:
    s["vars"] = {}
state.write_text(json.dumps(s))
'''

FAKE_AWS = r'''
import json, sys
from pathlib import Path
state = Path(sys.argv[1]); args = sys.argv[2:]
s = json.loads(state.read_text())
s["aws"].append(" ".join(a for a in args if a not in ("--region", "us-east-1", "--output", "text")))
cmd = [a for a in args if not a.startswith("--")]
op = " ".join(cmd[2:4]) if cmd[:2] == ["us-east-1", "text"] else " ".join(cmd[:2])
def done(text=""):
    state.write_text(json.dumps(s)); print(text); sys.exit(0)
if op == "sts get-caller-identity":
    done("111111111111")
if op == "ec2 describe-instances":
    if "--instance-ids" in args:
        done(s["ops"])
    done("i-ops" if s["ops"] != "none" else "")
if op == "ec2 start-instances":
    s["ops"] = "running"; done()
if op == "ec2 stop-instances":
    s["ops"] = "stopped"; done()
if op == "ec2 wait":
    done()
if op == "autoscaling describe-auto-scaling-groups":
    done("1\t1")
sys.exit("unexpected aws call: " + " ".join(args))
'''


@pytest.fixture
def env(tmp_path):
    state = tmp_path / "state.json"
    state.write_text(json.dumps({"vars": {}, "calls": [], "aws": [], "ops": "stopped"}))
    py = Path(sys.executable).as_posix()
    for name, src in (("terraform", FAKE_TF), ("aws", FAKE_AWS)):
        (tmp_path / f"{name}.py").write_text(src)
        wrapper = tmp_path / name
        wrapper.write_text(f'#!/usr/bin/env bash\nexec "{py}" "{(tmp_path / name).as_posix()}.py" '
                           f'"{state.as_posix()}" "$@"\n', newline="\n")
        wrapper.chmod(0o755)
    e = dict(os.environ, TERRAFORM=(tmp_path / "terraform").as_posix(), AWS=(tmp_path / "aws").as_posix(),
             TF_DIR="envs/demo", NAME_PREFIX="nt548")
    e.pop("GITHUB_STEP_SUMMARY", None)
    return {"state": state, "env": e}


def run(env, *args, **extra) -> subprocess.CompletedProcess:
    return subprocess.run([BASH, SCRIPT.as_posix(), *args], env=dict(env["env"], **extra), capture_output=True,
                          text=True, timeout=60)


def state(env) -> dict:
    return json.loads(env["state"].read_text())


def test_up_starts_ops_inits_the_bootstrap_bucket_and_deploys_the_sha(env):
    r = run(env, "up", "abc1234")
    assert r.returncode == 0, r.stderr
    s = state(env)
    assert s["ops"] == "running"
    init = next(c for c in s["calls"] if "init" in c)
    assert "-backend-config=bucket=nt548-tfstate-111111111111" in init
    assert "-backend-config=key=envs/demo/nt548.tfstate" in init
    assert s["vars"] == {"name_prefix": "nt548", "region": "us-east-1", "image_tag_blue": "abc1234",
                         "image_tag_green": "abc1234", "weight_blue": "100"}
    assert "http://alb-1.elb.amazonaws.com/" in r.stdout


def test_up_without_sha_keeps_what_runs(env):
    assert run(env, "up", "abc1234").returncode == 0
    data = json.loads(env["state"].read_text())
    data["vars"].update(image_tag_green="def5678", weight_blue="0")
    env["state"].write_text(json.dumps(data))
    assert run(env, "up").returncode == 0
    v = state(env)["vars"]
    assert (v["image_tag_blue"], v["image_tag_green"], v["weight_blue"]) == ("abc1234", "def5678", "0")


def test_down_destroys_then_stops_ops(env):
    assert run(env, "up", "abc1234").returncode == 0
    r = run(env, "down")
    assert r.returncode == 0, r.stderr
    s = state(env)
    assert s["vars"] == {} and s["ops"] == "stopped"
    assert any("destroy" in c for c in s["calls"])
    assert "ops stopped" in r.stdout


def test_keep_ops_leaves_the_runner_up(env):
    assert run(env, "up", "abc1234").returncode == 0
    r = run(env, "down", KEEP_OPS="1")
    assert r.returncode == 0, r.stderr
    assert state(env)["ops"] == "running" and "left running" in r.stdout
    assert not any(c.startswith("ec2 stop-instances") for c in state(env)["aws"])


def test_up_down_up_repeats(env):
    for _ in range(2):
        assert run(env, "up", "abc1234").returncode == 0
        assert run(env, "down").returncode == 0
    assert run(env, "up", "abc1234").returncode == 0
    s = state(env)
    assert s["ops"] == "running" and s["vars"]["image_tag_blue"] == "abc1234"
    assert sum("apply" in c for c in s["calls"]) == 3 and sum("destroy" in c for c in s["calls"]) == 2


def test_tf_args_reach_apply(env):
    assert run(env, "up", "abc1234", TF_ARGS="-var real_harness=false").returncode == 0
    assert state(env)["vars"]["real_harness"] == "false"


def test_no_ops_machine_means_no_bootstrap(env):
    data = json.loads(env["state"].read_text())
    data["ops"] = "none"
    env["state"].write_text(json.dumps(data))
    r = run(env, "up", "abc1234")
    assert r.returncode == 1 and "run the bootstrap first" in r.stderr
    assert not any("apply" in c for c in state(env)["calls"])


def test_bad_sha_is_refused(env):
    r = run(env, "up", "abc;rm -rf /")
    assert r.returncode == 2 and "not an image tag" in r.stderr


def test_status_when_down(env):
    r = run(env, "status")
    assert r.returncode == 0, r.stderr
    assert "envs/demo: down" in r.stdout and "ops: i-ops stopped" in r.stdout
