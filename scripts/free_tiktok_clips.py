"""Delete the video.mp4 of TikTok videos whose evidence is finished, to free disk for the next downloads.

A video is finished when, for every place it was matched to: place_filter kept it, its transcript was checked
(asr_check), place_verify judged it, the place has been observed, and a "yes" verdict has its comments crawled.
With --verified only unrelated clips go: every matched place has a place_verify verdict and all of them are "no"
(the transcript is checked and the frames are already saved). "yes" and "unsure" clips stay on disk for the UI;
comments_crawl and place_crawl both accept clip_removed videos. Keeps video.json (with embed_url, so the clip can still be shown) and marks clip_removed, which place_crawl reads
so it does not download the clip again. Clips a place card plays (corpus tiktok clips) are never deleted.
With --all every downloaded clip goes once its transcript is checked, the clips a place card plays included: the web plays
them through TikTok's embedded player, and the frames (poster, place_verify, observe) are cut first where any is missing.
Run with --dry-run first to see the count and size.
"""

import json
import sys
from pathlib import Path

from corpus.crawl.common.files import data_dir, safe_name
from corpus.crawl.tiktok.clips import picked
from corpus.crawl.tiktok.frames import frames, has_frames
from corpus.crawl.tiktok.place_filter import places_by_video


def every_checked(root: Path) -> list[tuple[str, Path]]:
    """Every mp4 whose transcript is checked (asr_check): nothing left needs the file but its frames."""
    out = []
    for mp4 in sorted((root / "videos").glob("*/video.mp4")):
        try:
            v = json.loads((mp4.parent / "video.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if (v.get("transcript") or {}).get("check"):
            out.append((mp4.parent.name, mp4))
    return out


def drop(root: Path, removable: list[tuple[str, Path]]) -> int:
    """Cut the missing frames, mark the clip removed, delete the mp4. A clip whose frames cannot be cut stays."""
    n = 0
    for vid, mp4 in removable:
        f = root / "videos" / vid / "video.json"
        v = json.loads(f.read_text(encoding="utf-8"))
        if not has_frames(mp4.parent):
            try:
                frames(mp4, float(v["transcript"]["total_s"]), mp4.parent / "frames")
            except Exception as e:  # a broken file: keep it rather than lose its only copy
                print(f"kept {vid}: frames failed ({type(e).__name__})", flush=True)
                continue
        v["embed_url"] = f"https://www.tiktok.com/embed/v2/{vid}"
        v["clip_removed"] = True
        f.write_text(json.dumps(v, ensure_ascii=False, indent=1), encoding="utf-8")  # marked before the file goes
        mp4.unlink()
        n += 1
    return n


def main(city: str, dry_run: bool, verified: bool = False, every: bool = False) -> None:
    root = data_dir() / "tiktok"
    if every:
        removable = every_checked(root)
        size = sum(mp4.stat().st_size for _, mp4 in removable)
        print(f"removable clips {len(removable)} ({size / 1e9:.1f} GB), "
              f"{sum(not has_frames(m.parent) for _, m in removable)} need frames first")
        if not dry_run:
            print(f"deleted {drop(root, removable)} clips")
        return
    matched = places_by_video(city)
    observed = {p.stem for p in (root / "observations").glob("*.json")}
    videos = {d.name: json.loads((d / "video.json").read_text(encoding="utf-8"))
              for d in (root / "videos").iterdir() if (d / "video.json").exists()}

    def pair_done(vid: str, fid: str) -> bool:
        v = videos.get(vid)
        if not v or not v.get("transcript", {}).get("check"):
            return False
        verdicts = [p for p in v.get("places", []) if p["fid"] == fid]
        if not verdicts:
            return False
        return verdicts[0].get("verdict") != "yes" or v.get("comments_complete") is not None

    done_places = set()
    for fid in {f["fid"] for ps in matched.values() for f in ps}:
        vids = [vid for vid, ps in matched.items() if any(f["fid"] == fid for f in ps)]
        if safe_name(fid) in observed and all(pair_done(vid, fid) for vid in vids):
            done_places.add(fid)

    removable, shown = [], picked(city)
    for vid, ps in matched.items():
        mp4 = root / "videos" / vid / "video.mp4"
        if vid not in videos or not mp4.exists() or vid in shown:
            continue
        if verified:
            v = videos[vid]
            verdict = {p["fid"]: p.get("verdict") for p in v.get("places", [])}
            ok = bool(v.get("transcript", {}).get("check")) and all(verdict.get(f["fid"]) == "no" for f in ps)
        else:
            ok = all(f["fid"] in done_places for f in ps)
        if ok:
            removable.append((vid, mp4))
    size = sum(mp4.stat().st_size for _, mp4 in removable)
    print(f"done places {len(done_places)}; removable clips {len(removable)} ({size / 1e6:.0f} MB)")
    if dry_run:
        return
    print(f"deleted {drop(root, removable)} clips")


if __name__ == "__main__":
    city = sys.argv[sys.argv.index("--city") + 1] if "--city" in sys.argv else "dalat"
    main(city, "--dry-run" in sys.argv, "--verified" in sys.argv, "--all" in sys.argv)
