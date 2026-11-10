import importlib
import sys
from pathlib import Path


CODE = Path(__file__).resolve().parents[2] / "scripts/diorama"
sys.path.insert(0, str(CODE))


def test_data_env_override(monkeypatch):
    monkeypatch.setenv("DIORAMA_DATA", "/x")
    import paths

    assert importlib.reload(paths).DATA == Path("/x")


def test_default_data_outside_repo(monkeypatch):
    monkeypatch.delenv("DIORAMA_DATA", raising=False)
    import paths

    paths = importlib.reload(paths)
    assert not paths.DATA.is_relative_to(paths.REPO)


def test_no_hardcoded_paths():
    for file in CODE.rglob("*"):
        if "node_modules" in file.parts or file.suffix not in {".py", ".mjs", ".sh", ".js"}:
            continue
        source = file.read_text()
        assert "workingspace_aiclub" not in source, file
        assert "logs/splat" not in source, file
