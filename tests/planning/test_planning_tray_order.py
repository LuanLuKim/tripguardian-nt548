"""The tray of places that did not fit must list them in the order the user selected them, in every process:
iterating a `set` of place ids would reorder it with PYTHONHASHSEED (docs/PLANNING.md)."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parent
SRC = TESTS.parents[1] / "src"
IDS = ["zeta", "alpha", "mu", "omega", "beta", "kappa", "gamma", "pi", "delta", "rho"]

SCRIPT = f"""
import json
from types import SimpleNamespace
from plan_fixtures import CFG, FakeLive, LODGING, fake_matrix, no_geocode
from planning.engine import Engine
from planning.session import State, Store

e = Engine(LODGING, cfg=CFG, live_cfg=FakeLive(), store=Store(None), geocode_fn=no_geocode, matrix_fn=fake_matrix,
           sun_fn=lambda *a: (360, 1050))
ids = {IDS!r}
by_place = {{pid: SimpleNamespace(name=pid.upper()) for pid in ids}}
e._active_place = lambda s, base, pid: by_place[pid]
base = SimpleNamespace(trip=SimpleNamespace(by_place=by_place, unplaced=[]), leftover=(), variants=[])
session = SimpleNamespace(state=State(), decision={{}})
active = {{"results": [SimpleNamespace(order=["pi"])]}}
print(json.dumps([p["place_id"] for p in e._unplaced(session, base, active)]))
"""


@pytest.mark.parametrize("seed", ["0", "1", "42"])
def test_the_tray_keeps_the_selection_order_under_any_hash_seed(seed):
    env = {**os.environ, "PYTHONHASHSEED": seed, "PYTHONPATH": os.pathsep.join([str(SRC), str(TESTS)])}
    out = subprocess.run([sys.executable, "-c", SCRIPT], env=env, capture_output=True, text=True, cwd=TESTS, timeout=120)
    assert out.returncode == 0, out.stderr[-800:]
    assert out.stdout.strip() == str([p for p in IDS if p != "pi"]).replace("'", '"')
