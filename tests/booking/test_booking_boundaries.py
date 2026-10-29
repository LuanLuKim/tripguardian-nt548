"""booking and journey reach other modules only through their public __init__ (RULE.md §2), and booking never does I/O of its own."""

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src"
FILES = sorted(p for d in ("booking", "journey") for p in (SRC / d).rglob("*.py"))
PUBLIC_DEPTH = {"live": 1, "booking": 1, "journey": 1, "corpus": 2}  # corpus.serving is the package whose __init__ exports stay_prices
NETWORK = {"requests", "httpx", "urllib3", "aiohttp", "playwright", "socket"}


def imports(path):
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            yield from (a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            yield node.module


@pytest.mark.parametrize("path", FILES, ids=lambda p: f"{p.parent.name}/{p.name}")
def test_imports_are_public_and_there_is_no_network_client(path):
    for mod in imports(path):
        parts = mod.split(".")
        assert parts[0] not in NETWORK, f"{path.name} imports {mod}"
        if parts[0] in PUBLIC_DEPTH:
            assert len(parts) <= PUBLIC_DEPTH[parts[0]], f"{path.name} deep-imports {mod}"
        assert parts[0] not in {"trip", "planning", "decision", "harness"}, f"{path.name} imports {mod}"
