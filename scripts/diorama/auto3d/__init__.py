"""Public API for the resumable, evidence-gated place pipeline."""

from __future__ import annotations

from paths import REPO


def config() -> dict:
    import yaml

    return yaml.safe_load((REPO / "config/diorama.yaml").read_text())


from .state import Place
from .gate import Gate, check_fid, check_place
from .checklist import verdict, next_action, kit_blocked
from .site import fit_site

__all__ = ["Place", "Gate", "check_fid", "check_place", "verdict", "next_action", "kit_blocked", "config", "fit_site"]
