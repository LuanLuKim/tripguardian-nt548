"""The Embedder role: an image or a text -> a unit vector. Deterministic for one model; the model ids live in
config/index.yaml, the weights in the repo cache (.cache/hf). Offline for the corpus, online for the user's words or
photo; nothing it embeds is stored by this module."""

from __future__ import annotations

import fcntl
import io
import os
import threading
import time
from functools import cached_property
from pathlib import Path

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[3]
CONFIG = ROOT / "config" / "index.yaml"


def config() -> dict:
    return yaml.safe_load(CONFIG.read_text(encoding="utf-8"))


LEASE = "/tmp/tripguardian-gpu.lease"
WATCH_TICK_S = 3


def gpu_leased(path: str = LEASE) -> bool:
    """True while another process holds the GPU lease (`scripts/gpu_lease.sh`, i.e. `flock -x <path> <cmd>`)."""
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return False
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        fcntl.flock(fd, fcntl.LOCK_UN)
        return False
    finally:
        os.close(fd)


def _hf_env() -> None:
    os.environ.setdefault("HF_HOME", str(ROOT / ".cache" / "hf"))
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    # one growing pool is how a long-running server crept to 10 GB: segments that can grow and shrink instead
    os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")


def _unit(x: np.ndarray) -> np.ndarray:
    x = x.astype(np.float32)
    return x / np.maximum(np.linalg.norm(x, axis=-1, keepdims=True), 1e-8)


class Embedder:
    """image(), image_text(): SigLIP2, one space for photos and short descriptions. text(): bge-m3, for spans."""

    _shared: dict[tuple, "Embedder"] = {}
    _shared_lock = threading.Lock()

    def __init__(self, device: str | None = None, cfg: dict | None = None):
        self.cfg = (cfg or config())["embedder"]
        self.device = device or self.cfg["online_device"]
        # the text model may live on its own GPU (online only); an offline job passes `device` and keeps both on it
        self.text_device = device or self._visible(self.cfg.get("online_text_device") or self.device)
        self._use = threading.RLock()  # Trip looks and retrieval share this object from different threads
        self._online = device is None  # only the online Embedder parks; an offline job keeps its GPU for the whole run
        self._last_used = time.monotonic()
        self._watching = False
        _hf_env()

    @classmethod
    def shared(cls, cfg: dict | None = None) -> "Embedder":
        """The one online Embedder of this process. Trip looks and retrieval each hold an Index; without sharing, each
        loaded its own SigLIP2 and bge-m3 onto the GPU (2 x ~3 GB)."""
        c = cfg or config()
        key = (c["embedder"]["image_model"], c["embedder"]["text_model"], c["embedder"]["online_device"],
               c["embedder"].get("online_text_device"))
        with cls._shared_lock:
            if key not in cls._shared:
                cls._shared[key] = cls(cfg=c)
            return cls._shared[key]

    @property
    def ready(self) -> bool:
        """Both encoders are on their device: a search no longer waits for a cold load (~1 min on a busy GPU)."""
        return "_siglip" in self.__dict__ and "_bge" in self.__dict__

    @classmethod
    def shared_ready(cls) -> bool:
        """This process's shared Embedder exists and is loaded (False before anything asked for it)."""
        return any(e.ready for e in cls._shared.values())

    @classmethod
    def warm(cls, cfg: dict | None = None) -> "Embedder":
        """Load both encoders now (one tiny text each), so the first user search does not pay for it. A server calls this
        in a background thread the moment it starts, before anything else it warms."""
        emb = cls.shared(cfg)
        emb.image_text(["khởi động"])
        emb.text(["khởi động"])
        return emb

    @staticmethod
    def _visible(device: str) -> str:
        """cuda:N this process cannot see (one GPU exposed, two configured) falls back to cuda:0."""
        if not device.startswith("cuda:"):
            return device
        import torch
        n = torch.cuda.device_count()
        return device if int(device.split(":")[1]) < n else "cuda:0"

    def _leased(self) -> bool:
        return self._online and gpu_leased(self.cfg.get("gpu_lease", LEASE))

    def _want(self, device: str) -> str:
        """Where an encoder belongs right now: its device, or the CPU while another job holds the GPU lease."""
        return "cpu" if device.startswith("cuda") and self._leased() else device

    def _move(self, where: str) -> None:
        """Each loaded encoder to `where`: "gpu" (its device, half precision), "ram" (parked as is: a copy back is cheap) or
        "cpu" (float32, the one precision the CPU can run: used while the GPU is leased)."""
        t = self._torch
        for key, device in (("_siglip", self.device), ("_bge", self.text_device)):
            if key not in self.__dict__ or not device.startswith("cuda"):
                continue
            m = self.__dict__[key][0]
            p = next(m.parameters())
            if where == "gpu" and p.device.type != "cuda":
                m.to(device, t.float16)
            elif where == "ram" and p.device.type == "cuda":
                m.to("cpu")
            elif where == "cpu" and (p.device.type == "cuda" or p.dtype != t.float32):
                m.to("cpu", t.float32)
        if where != "gpu":
            self._trim()

    def _settle(self) -> tuple[str, str]:
        """Under `_use`, before a call: the (image, text) devices to run on. An encoder parked in RAM comes back to the
        GPU here (about 3 GB over PCIe, around a second); while the GPU is leased it stays on the CPU."""
        self._last_used = time.monotonic()
        if not self._online:
            return self.device, self.text_device
        leased = self._leased()
        self._move("cpu" if leased else "gpu")
        return (self._want(self.device), self._want(self.text_device))

    def _park_if_due(self) -> None:
        """Give the GPU back: park the encoders in RAM when a job holds the lease, or after `idle_park_s` without a call."""
        idle = float(self.cfg.get("idle_park_s", 0))
        if not self._use.acquire(blocking=False):  # a call is running
            return
        try:
            if self._leased():
                self._move("cpu")
            elif idle and time.monotonic() - self._last_used > idle:
                self._move("ram")
        finally:
            self._use.release()

    def _watch(self) -> None:
        while True:
            time.sleep(WATCH_TICK_S)
            self._park_if_due()

    def _start_watch(self) -> None:
        if self._online and not self._watching:
            self._watching = True
            threading.Thread(target=self._watch, name="embedder-park", daemon=True).start()

    def _trim(self) -> None:
        """Hand the pool's unused blocks back after a call: batch shapes differ, the cache would only grow."""
        if self._torch.cuda.is_available():
            self._torch.cuda.empty_cache()

    @property
    def image_model_id(self) -> str:
        return self.cfg["image_model"]

    @property
    def text_model_id(self) -> str:
        return self.cfg["text_model"]

    @cached_property
    def _torch(self):
        import torch
        return torch

    def _dtype(self, device: str | None = None):
        return self._torch.float16 if (device or self.device).startswith("cuda") else self._torch.float32

    @cached_property
    def _siglip(self):
        from transformers import AutoModel, AutoProcessor
        with self._use:  # a thread that waited here finds the model the first one loaded (no second copy on the GPU)
            if "_siglip" not in self.__dict__:
                dev = self._want(self.device)
                m = AutoModel.from_pretrained(self.image_model_id, dtype=self._dtype(dev)).to(dev).eval()
                self.__dict__["_siglip"] = (m, AutoProcessor.from_pretrained(self.image_model_id))
                self._start_watch()
            return self.__dict__["_siglip"]

    @cached_property
    def _bge(self):
        from transformers import AutoModel, AutoTokenizer
        with self._use:
            if "_bge" not in self.__dict__:
                dev = self._want(self.text_device)
                m = AutoModel.from_pretrained(self.text_model_id, dtype=self._dtype(dev)).to(dev).eval()
                self.__dict__["_bge"] = (m, AutoTokenizer.from_pretrained(self.text_model_id))
                self._start_watch()
            return self.__dict__["_bge"]

    @staticmethod
    def _out(v):
        return v.pooler_output if hasattr(v, "pooler_output") else v

    def image(self, images: list) -> np.ndarray:
        """images: PIL images or encoded bytes -> (n, d) unit float32."""
        from PIL import Image
        pil = [Image.open(io.BytesIO(x)).convert("RGB") if isinstance(x, (bytes, bytearray)) else x.convert("RGB")
               for x in images]
        m, p = self._siglip
        with self._use, self._torch.no_grad():
            dev, _ = self._settle()
            px = p(images=pil, return_tensors="pt")["pixel_values"].to(dev, self._dtype(dev))
            out = _unit(self._out(m.get_image_features(pixel_values=px)).float().cpu().numpy())
        self._trim()
        return out

    def image_text(self, texts: list[str]) -> np.ndarray:
        """Short descriptions in the photo space ("đèn vàng, ghế gỗ") -> (n, d) unit float32."""
        m, p = self._siglip
        with self._use, self._torch.no_grad():
            dev, _ = self._settle()
            t = p(text=[x.lower() for x in texts], padding="max_length", max_length=self.cfg["image_text_len"],
                  truncation=True, return_tensors="pt").to(dev)
            out = _unit(self._out(m.get_text_features(**t)).float().cpu().numpy())
        self._trim()
        return out

    def text(self, texts: list[str]) -> np.ndarray:
        """bge-m3 dense vectors (CLS, normalised) -> (n, d) unit float32."""
        m, tok = self._bge
        with self._use, self._torch.no_grad():
            _, dev = self._settle()
            t = tok(texts, padding=True, truncation=True, max_length=256, return_tensors="pt").to(dev)
            out = _unit(m(**t).last_hidden_state[:, 0].float().cpu().numpy())
        self._trim()
        return out
