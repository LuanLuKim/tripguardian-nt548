import socket

import pytest


@pytest.fixture(autouse=True)
def offline(monkeypatch, tmp_path):
    """No test reaches the network or the real data root; tests that read pages patch getaddrinfo again."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))

    def _refuse(*args, **kwargs):
        raise OSError("offline")

    monkeypatch.setattr(socket, "getaddrinfo", _refuse)
