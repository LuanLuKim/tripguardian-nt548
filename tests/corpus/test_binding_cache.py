import hashlib
import json

import pytest

from corpus.releases import Binding, bind, resolve_binding
import corpus.releases.binding as implementation


def release(root, content=b"artifact"):
    path = root / "releases" / "r-test"
    path.mkdir(parents=True)
    (path / "artifact").write_bytes(content)
    raw = json.dumps({"release_id": "r-test", "city": "dalat", "artifacts": [
        {"path": "artifact", "sha256": hashlib.sha256(b"artifact").hexdigest()}]}).encode()
    (path / "manifest.json").write_bytes(raw)
    return path, Binding(release_id="r-test", region="dalat", manifest_sha256=hashlib.sha256(raw).hexdigest())


def test_resolving_same_pin_hashes_artifacts_only_once(tmp_path, monkeypatch):
    path, binding = release(tmp_path)
    calls = []
    original = implementation._hash

    def counted(artifact):
        calls.append(artifact)
        return original(artifact)

    monkeypatch.setattr(implementation, "_hash", counted)
    for _ in range(4):
        assert resolve_binding(tmp_path, binding.model_copy()) == path
    assert calls == [path / "artifact"]


def test_first_open_rejects_corruption_and_does_not_cache_failure(tmp_path):
    path, binding = release(tmp_path, b"corrupt")
    for _ in range(2):
        with pytest.raises(ValueError, match="artifact hash"):
            resolve_binding(tmp_path, binding)
    (path / "artifact").write_bytes(b"artifact")
    assert resolve_binding(tmp_path, binding) == path


def test_verified_pin_does_not_authorize_other_root_or_binding(tmp_path):
    good, binding = release(tmp_path / "good")
    bad, _ = release(tmp_path / "bad", b"corrupt")
    assert resolve_binding(tmp_path / "good", binding) == good
    with pytest.raises(ValueError, match="artifact hash"):
        resolve_binding(tmp_path / "bad", binding)
    with pytest.raises(ValueError, match="region"):
        resolve_binding(tmp_path / "good", binding.model_copy(update={"region": "hanoi"}))
    with pytest.raises(ValueError, match="manifest hash"):
        resolve_binding(tmp_path / "good", binding.model_copy(update={"manifest_sha256": "0" * 64}))


def test_capturing_active_identity_defers_artifact_verification(tmp_path, monkeypatch):
    path, expected = release(tmp_path, b"corrupt")
    (tmp_path / "releases" / "current").write_text("r-test")
    binding = bind(tmp_path, verify=False)
    assert binding == expected
    with pytest.raises(ValueError, match="artifact hash"):
        resolve_binding(tmp_path, binding)


@pytest.mark.parametrize("corrupt", [False, True])
def test_engine_factory_maps_missing_or_corrupt_release_to_409(tmp_path, corrupt):
    from harness.__main__ import create_tools_factory
    from corpus.releases import PinnedVersionMissing
    if corrupt:
        _, binding = release(tmp_path, b"corrupt")
    else:
        binding = Binding(release_id="r-missing", region="dalat")
    with pytest.raises(PinnedVersionMissing):
        create_tools_factory(tmp_path, None)(binding)


def test_manifest_replacement_invalidates_verification(tmp_path):
    path, binding = release(tmp_path)
    assert resolve_binding(tmp_path, binding) == path
    (path / "manifest.json").write_text("{}")
    with pytest.raises(ValueError, match="identity"):
        resolve_binding(tmp_path, binding)
