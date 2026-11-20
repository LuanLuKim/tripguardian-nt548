"""The online Embedder gives the GPU back: parked in RAM after idle or while a job holds the lease, back on the next call."""

import fcntl
import os
import time
import types

import torch

from corpus.index import embedder as emb_mod
from corpus.index.embedder import Embedder, gpu_leased


class FakeModel:
    def __init__(self):
        self.device, self.dtype = torch.device("cuda:0"), torch.float16

    def parameters(self):
        yield types.SimpleNamespace(device=self.device, dtype=self.dtype)

    def to(self, device, dtype=None):
        self.device, self.dtype = torch.device(device), dtype or self.dtype
        return self


def _embedder(tmp_path, **extra):
    cfg = {"embedder": {"image_model": "i", "text_model": "t", "online_device": "cuda:0", "online_text_device": "cuda:0",
                        "gpu_lease": str(tmp_path / "gpu.lease"), **extra}}
    e = Embedder(cfg=cfg)
    e.__dict__["_siglip"], e.__dict__["_bge"] = (FakeModel(), None), (FakeModel(), None)
    e.__dict__["_torch"] = torch
    e._trim = lambda: None
    return e


def _hold(path):
    fd = os.open(path, os.O_CREAT | os.O_RDONLY, 0o666)
    fcntl.flock(fd, fcntl.LOCK_EX)
    return fd


def test_lease_is_seen_only_while_held(tmp_path):
    path = str(tmp_path / "gpu.lease")
    assert not gpu_leased(path)  # no file: nobody holds it
    fd = _hold(path)
    assert gpu_leased(path)
    os.close(fd)
    assert not gpu_leased(path)


def test_leased_gpu_parks_encoders_in_ram_and_a_call_runs_on_cpu(tmp_path):
    e = _embedder(tmp_path)
    fd = _hold(str(tmp_path / "gpu.lease"))
    e._park_if_due()
    assert all(e.__dict__[k][0].device.type == "cpu" and e.__dict__[k][0].dtype == torch.float32 for k in ("_siglip", "_bge"))
    assert e._settle() == ("cpu", "cpu")
    os.close(fd)
    assert e._settle() == ("cuda:0", "cuda:0")  # lease gone: the next call brings them back, in half precision
    assert all(e.__dict__[k][0].device.type == "cuda" and e.__dict__[k][0].dtype == torch.float16 for k in ("_siglip", "_bge"))


def test_idle_parks_and_zero_never_does(tmp_path):
    e = _embedder(tmp_path, idle_park_s=60)
    e._last_used = time.monotonic() - 30
    e._park_if_due()
    assert e.__dict__["_bge"][0].device.type == "cuda"  # not idle long enough
    e._last_used = time.monotonic() - 61
    e._park_if_due()
    assert e.__dict__["_bge"][0].device.type == "cpu" and e.__dict__["_bge"][0].dtype == torch.float16  # no precision change
    never = _embedder(tmp_path, idle_park_s=0)
    never._last_used = time.monotonic() - 10_000
    never._park_if_due()
    assert never.__dict__["_bge"][0].device.type == "cuda"


def test_offline_embedder_never_parks(tmp_path):
    e = Embedder(device="cuda:0", cfg={"embedder": {"image_model": "i", "text_model": "t", "online_device": "cuda:0",
                                                    "gpu_lease": str(tmp_path / "gpu.lease"), "idle_park_s": 1}})
    e.__dict__["_torch"] = torch
    fd = _hold(str(tmp_path / "gpu.lease"))
    assert e._settle() == ("cuda:0", "cuda:0")
    os.close(fd)
