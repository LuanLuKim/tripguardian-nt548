"""Shared locations for diorama code and external working data."""
import os
from pathlib import Path

CODE = Path(__file__).resolve().parent
REPO = CODE.parent.parent.resolve()
DATA = Path(os.environ.get("DIORAMA_DATA", REPO.parent / "tripguardian-store/splat/diorama")).resolve()
