"""corpus tiktok asr: a CUDA out-of-memory caused by another job on the same GPU is waited out and the same video is
tried again; it is never written as a permanent error. Any other failure is still logged and skipped."""

import json

import pytest

from corpus.crawl.tiktok import asr


class FakeOOM(Exception):
    pass


FakeOOM.__name__ = "OutOfMemoryError"  # torch.cuda.OutOfMemoryError by name: the test needs no GPU


def setup_videos(tmp_path, ids):
    for vid in ids:
        d = tmp_path / "tiktok" / "videos" / vid
        d.mkdir(parents=True)
        (d / "video.mp4").write_bytes(b"x")
        (d / "video.json").write_text(json.dumps({"video_id": vid}), encoding="utf-8")


def transcript(vid):
    return {"model": "m", "segments": [{"start_s": 0, "end_s": 1, "text": vid}]}


@pytest.fixture(autouse=True)
def fake_model(monkeypatch):
    monkeypatch.setattr(asr.asr_model, "name", lambda: "m")
    monkeypatch.setattr(asr, "free_gpu_cache", lambda: None)
    waits = []
    monkeypatch.setattr(asr.time, "sleep", waits.append)
    return waits


def errors(tmp_path):
    f = tmp_path / "tiktok" / "errors.jsonl"
    return [json.loads(x) for x in f.read_text(encoding="utf-8").splitlines()] if f.exists() else []


def test_oom_waits_and_retries_the_same_video(tmp_path, monkeypatch, fake_model):
    setup_videos(tmp_path, ["1", "2"])
    calls = []

    def fake(mp4, model=None):
        vid = mp4.parent.name
        calls.append(vid)
        if calls.count("1") <= 2:
            raise FakeOOM("CUDA out of memory. Tried to allocate 20.00 MiB")
        return transcript(vid)

    monkeypatch.setattr(asr, "transcribe_video", fake)
    out = asr.run("dalat")
    assert out == {"videos": 2, "done": 2}
    assert calls == ["1", "1", "1", "2"]
    assert len(fake_model) == 2 and all(w > 0 for w in fake_model)
    assert errors(tmp_path) == []
    assert json.loads((tmp_path / "tiktok" / "videos" / "1" / "video.json").read_text())["transcript"]["model"] == "m"


def test_oom_gives_up_after_the_retry_cap_and_goes_on(tmp_path, monkeypatch):
    setup_videos(tmp_path, ["1", "2"])

    def fake(mp4, model=None):
        if mp4.parent.name == "1":
            raise FakeOOM("CUDA out of memory")
        return transcript("2")

    monkeypatch.setattr(asr, "transcribe_video", fake)
    out = asr.run("dalat")
    assert out == {"videos": 2, "done": 1}
    errs = errors(tmp_path)
    assert [e["id"] for e in errs] == ["1"] and errs[0]["stage"] == "asr"


def test_other_errors_are_logged_without_waiting(tmp_path, monkeypatch, fake_model):
    setup_videos(tmp_path, ["1"])

    def fake(mp4, model=None):
        raise ValueError("bad audio")

    monkeypatch.setattr(asr, "transcribe_video", fake)
    assert asr.run("dalat") == {"videos": 1, "done": 0}
    assert fake_model == [] and errors(tmp_path)[0]["error"].startswith("ValueError")


def test_error_rows_do_not_hide_a_video_from_the_next_run(tmp_path, monkeypatch):
    setup_videos(tmp_path, ["1"])
    (tmp_path / "tiktok" / "errors.jsonl").write_text(
        json.dumps({"at": "x", "id": "1", "stage": "asr", "error": "OutOfMemoryError: CUDA out of memory"}) + "\n",
        encoding="utf-8")
    assert [d.parent.name for d in asr.todo(tmp_path / "tiktok", "m")] == ["1"]
