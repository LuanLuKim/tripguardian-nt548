import os
import stat

import pytest

from harness import Conflict, Store
from test_dispatch import decision, make, run


def test_public_read_cannot_mutate_cached_state_or_receipts():
    h, _ = make()
    view = decision(h)
    session = h.store.get(view["id"])
    session.receipts["old"] = {"response": {"text": "Đà Lạt 🌸"}}
    h.store.save(session)
    leaked = h.store.read(session.id)
    leaked.receipts["old"]["response"]["text"] = "corrupted outside lock"
    leaked.snapshots["decision"]["value"] = 99
    saved = h.store.get(session.id)
    assert saved.receipts["old"]["response"]["text"] == "Đà Lạt 🌸"
    assert saved.snapshots["decision"]["value"] == 0


@pytest.mark.parametrize("reload_first", [False, True])
def test_cas_loser_retry_uses_winning_snapshot(monkeypatch, reload_first):
    h, _ = make()
    view = decision(h)
    # A competing commit arrives after this request has opened its old state.
    save = h.store.save

    def lose(session):
        winner = h.store.get(session.id)
        winner.revision += 1
        winner.snapshots["decision"]["value"] = 1
        winner.receipts["winner"] = {"response": {"value": 1}}
        save(winner)
        raise Conflict("the journey was changed elsewhere; reload it")

    with monkeypatch.context() as m:
        m.setattr(h.store, "save", lose)
        with pytest.raises(Conflict):
            run(h, view, "act", "loser")
    if reload_first:
        assert h.load(view["id"])["result"]["view"]["value"] == 1
    with pytest.raises(Conflict):
        run(h, view, "act", "loser")
    retry = run(h, {**view, "revision": view["revision"] + 1}, "act", "loser")
    saved = h.store.get(view["id"])
    assert retry["result"]["view"]["value"] == 2
    assert saved.snapshots["decision"]["value"] == 2
    assert "winner" in saved.receipts and "loser" in saved.receipts


def test_file_save_syncs_file_before_replace_and_directory_after(tmp_path, monkeypatch):
    from pathlib import Path

    store = Store(tmp_path)
    session = store.new()
    calls = []
    fsync, replace = os.fsync, Path.replace

    def sync(fd):
        calls.append("directory" if stat.S_ISDIR(os.fstat(fd).st_mode) else "file")
        fsync(fd)

    def rename(path, target):
        calls.append("replace")
        return replace(path, target)

    monkeypatch.setattr(os, "fsync", sync)
    monkeypatch.setattr(Path, "replace", rename)
    store.save(session)
    assert calls == ["file", "replace", "directory"]
    assert Store(tmp_path).get(session.id).model_dump() == session.model_dump()


@pytest.mark.parametrize("failure", ["write", "file", "directory"])
def test_file_save_failure_keeps_cache_consistent_with_visible_file(tmp_path, monkeypatch, failure):
    import errno
    from pathlib import Path

    h, _ = make()
    h.store = Store(tmp_path)
    view = decision(h)
    original_open = Path.open
    fsync = os.fsync

    class PartialWrite:
        def __enter__(self):
            self.file = original_open(tmp_path / f"{view['id']}.json.tmp", "w", encoding="utf-8")
            return self

        def write(self, data):
            self.file.write(data[:20])
            raise OSError(errno.EDQUOT, "quota exceeded")

        def __exit__(self, *args):
            self.file.close()

    def open_file(path, *args, **kwargs):
        return PartialWrite() if path.suffix == ".tmp" else original_open(path, *args, **kwargs)

    def sync(fd):
        kind = "directory" if stat.S_ISDIR(os.fstat(fd).st_mode) else "file"
        if kind == failure:
            raise OSError("sync failure")
        fsync(fd)

    with monkeypatch.context() as m:
        m.setattr(os, "fsync", sync)
        if failure == "write":
            m.setattr(Path, "open", open_file)
        with pytest.raises(OSError):
            run(h, view, "act", "retry")
    committed = failure == "directory"
    saved = h.store.get(view["id"])
    assert saved.model_dump() == Store(tmp_path).get(view["id"]).model_dump()
    assert saved.revision == view["revision"] + int(committed)
    assert h.load(view["id"])["result"]["view"]["value"] == int(committed)
    out = run(h, view, "act", "retry")
    assert out["result"]["view"]["value"] == 1
    assert h.store.get(view["id"]).revision == view["revision"] + 1
