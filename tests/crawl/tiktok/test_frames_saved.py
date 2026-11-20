"""corpus.crawl.tiktok.frames: a clip deleted on purpose (clip_removed) still counts as downloaded and is read from its frames."""

import json

from corpus.crawl.tiktok.frames import FRAMES, has_frames, saved, seeable


def _dir(tmp_path, mp4=False, removed=False, frames=0):
    d = tmp_path / "123"
    (d / "frames").mkdir(parents=True)
    (d / "video.json").write_text(json.dumps({"video_id": "123", **({"clip_removed": True} if removed else {})}), encoding="utf-8")
    if mp4:
        (d / "video.mp4").write_bytes(b"x")
    for i in range(frames):
        (d / "frames" / f"f{i + 1}.jpg").write_bytes(b"j")
    return d


def test_a_clip_on_disk_is_saved_and_seeable(tmp_path):
    d = _dir(tmp_path, mp4=True)
    assert saved(d) and seeable(d) and not has_frames(d)


def test_a_removed_clip_with_its_frames_is_saved_and_seeable(tmp_path):
    d = _dir(tmp_path, removed=True, frames=FRAMES)
    assert saved(d) and seeable(d) and has_frames(d)


def test_a_clip_never_downloaded_is_not_saved(tmp_path):
    d = _dir(tmp_path, frames=1)
    assert not saved(d) and not seeable(d)
