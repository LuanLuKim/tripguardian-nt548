import pytest


@pytest.fixture
def data(tmp_path, monkeypatch):
    """DATA_DIR in a temp dir: the navigator writes data/<city>/navigate/ and compare reads data/serving/."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    return tmp_path
