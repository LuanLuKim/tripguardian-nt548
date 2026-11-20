"""Keyframes of a saved video, shared by asr_check (names on screen) and place_verify: videos/<video_id>/frames/f1..fN.jpg."""

import json
import subprocess
from pathlib import Path

FRAMES = 4
FRAME_WIDTH = 512  # enough to read signs and overlays, small enough for four images per call


def frames(mp4: Path, total_s: float, out_dir: Path) -> list[bytes]:
    """FRAMES JPEGs at the middle of equal slices of the video; extracted once, then read from disk."""
    out = []
    for i in range(FRAMES):
        f = out_dir / f"f{i + 1}.jpg"
        if not f.exists():
            out_dir.mkdir(parents=True, exist_ok=True)
            subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-ss", f"{(i + 0.5) * total_s / FRAMES:.2f}",
                            "-i", str(mp4), "-frames:v", "1", "-vf", f"scale={FRAME_WIDTH}:-2", str(f)], check=True)
        out.append(f.read_bytes())
    return out


def has_frames(d: Path) -> bool:
    """Every keyframe of the video directory `d` is saved: frames() reads them without the mp4."""
    return all((d / "frames" / f"f{i + 1}.jpg").exists() for i in range(FRAMES))


def saved(d: Path) -> bool:
    """The clip of video directory `d` was downloaded: its mp4 is on disk, or it was deleted on purpose after its transcript
    and frames were kept (video.json clip_removed, scripts/free_tiktok_clips.py). The web plays it through TikTok's player."""
    if (d / "video.mp4").exists():
        return True
    try:
        return bool(json.loads((d / "video.json").read_text(encoding="utf-8")).get("clip_removed"))
    except (OSError, ValueError):
        return False


def seeable(d: Path) -> bool:
    """Its frames can be read: the mp4 is on disk to cut them from, or they are all saved already."""
    return (d / "video.mp4").exists() or has_frames(d)
