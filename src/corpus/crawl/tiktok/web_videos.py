"""Place phase, web_videos: TikTok videos the web search found (data/web/<city>/tiktok_urls.jsonl, written by
corpus.crawl.web, read here as a file; and data/tiktok/place_web/<city>.jsonl, the videos place_web found by
searching for one place) -> their TikTok place (poi) -> the Maps places place_verify judges them for.

Each video not yet in data/tiktok/videos is opened once in a fresh logged-out session (the same anonymous path as
poi_crawl, at most poi_tabs tabs; a captcha in a headless run stops all, no retry). Its item JSON gives the poi:
- a poi place_poi already mapped -> that Maps place;
- any other poi (never an administrative area) -> the Maps places sharing a distinctive name pair with it
  (poi_crawl.name_keys), at most CANDIDATES; these are candidates only, place_verify decides;
- no poi -> recorded, nothing to judge;
- a video place_web found for a place also gets that place as a candidate (whatever its poi), so a hotel or a shop with
  no TikTok place page of its own can still be judged. A video already on disk is not opened again: the new place is
  only recorded (downloaded true), and place_verify judges the pair.
A video with a place is downloaded in the same session (playAddr is bound to it) into data/tiktok/videos/<id>/ with
the files place_crawl writes (info.json, video.json with comments_complete null, video.mp4). Then asr -> asr_check ->
place_verify judge it for its places (place_filter.places_by_video reads this phase's file), place_poi learns the
pois of the verified ones, poi_crawl lists their place pages and clips picks what users see.
Writes data/tiktok/web_videos/<city>.jsonl, one line per video done: {at, video_id, url, query, poi, mapped,
places: [{fid, name, category, address}], downloaded}. A page without item data (deleted, private or the start of a
block) is logged in errors.jsonl and asked again next run.
"""

import asyncio
import json
import time

from ..common.browser import LoginRequired, open_sessions, pause
from ..common.files import append_jsonl, data_dir, listed, load_config, log_error, now, write_json
from .crawl import ATTEMPTS, MissWatchThrottle, NoItemData, download_video, poi_of, throttled, video_doc
from .page import open_item
from .place_filter import address
from .place_poi import AREAS
from . import place_web
from .poi_crawl import name_keys

CANDIDATES = 3  # Maps places per unmapped poi, most shared name pairs first


def out_path(city: str):
    return data_dir() / "tiktok" / "web_videos" / f"{city}.jsonl"


def load(city: str) -> list[dict]:
    path = out_path(city)
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


def _urls(city: str) -> list[dict]:
    """One row per video: {video_id, url, query, want: [fid, ...]} (want = places place_web searched it for)."""
    rows: dict[str, dict] = {}
    path = data_dir() / "web" / city / "tiktok_urls.jsonl"
    placed = place_web.load(city)
    if not path.exists() and not placed:
        raise SystemExit(f"no {path}; run `python -m corpus web search --city {city}` first")
    for line in path.read_text(encoding="utf-8").splitlines() if path.exists() else []:
        try:
            r = json.loads(line)
            vid = str(r["video_id"])
        except (ValueError, KeyError, TypeError):
            continue
        if vid.isdigit() and vid not in rows:
            rows[vid] = {"video_id": vid, "url": r["url"], "query": r.get("query"), "want": []}
    for r in placed:
        vid = str(r["video_id"])
        row = rows.setdefault(vid, {"video_id": vid, "url": r["url"], "query": r.get("query"), "want": []})
        if r["fid"] not in row["want"]:
            row["want"].append(r["fid"])
    return list(rows.values())


def places_for(poi: dict | None, area: bool, mapped: dict[str, str], places: list[dict]) -> tuple[str | None, list[str]]:
    """-> (fid place_poi mapped this poi to, candidate fids)."""
    if not poi or area:
        return None, []
    if poi["id"] in mapped:
        return mapped[poi["id"]], [mapped[poi["id"]]]
    keys = name_keys(poi.get("name") or "")
    ranked = sorted(((len(keys & name_keys(p["name"])), p["fid"]) for p in places), key=lambda r: (-r[0], r[1]))
    return None, [fid for n, fid in ranked if n > 0][:CANDIDATES]


async def _video(ctx, row: dict, root, c: dict, throttle, downloads: asyncio.Semaphore, mapped: dict,
                 places: list[dict], by_fid: dict, stats: dict, city: str) -> None:
    item = None
    for attempt in range(1, ATTEMPTS + 1):
        async with throttle:
            try:
                item = await open_item(ctx, row["url"])
                if not item:
                    raise NoItemData()
                throttle.success()
                break
            except LoginRequired:
                raise
            except Exception as e:
                if throttled(e, throttle) and attempt < ATTEMPTS:
                    throttle.blocked()
                    continue
                stats["no_item" if isinstance(e, NoItemData) else "errors"] += 1
                log_error(root, row["video_id"], "web_video", e)
                return
            finally:
                await pause(*c.get("pause_s", (0.0, 0.0)))
    poi = poi_of(item)
    area = bool(poi) and (item.get("poi") or {}).get("ttTypeNameTiny") in AREAS
    fid, fids = places_for(poi, area, mapped, places)
    fids = fids + [f for f in row.get("want") or [] if f in by_fid and f not in fids]
    stats["with_poi"] += bool(poi)
    stats["area"] += area
    stats["mapped"] += fid is not None
    stats["named"] += fid is None and bool(fids)
    stats["wanted"] += bool(row.get("want"))
    play = (item.get("video") or {}).get("playAddr")
    downloaded = False
    if fids and play:
        d = root / "videos" / row["video_id"]
        try:
            async with downloads:
                await download_video(ctx, play, d / "video.mp4")
        except Exception as e:
            stats["errors"] += 1
            log_error(root, row["video_id"], "download", e)
            return  # asked again next run: the play address will be fresh
        write_json(d / "info.json", item)
        write_json(d / "video.json", video_doc({"video_id": row["video_id"], "url": row["url"],
                                                "queries": [row["query"]] if row.get("query") else []},
                                               item, [], f"tiktok/videos/{row['video_id']}/video.mp4", None))
        downloaded = True
        stats["downloaded"] += 1
    append_jsonl(out_path(city), {"at": now(), "video_id": row["video_id"], "url": row["url"], "query": row.get("query"),
                                  "poi": poi, "mapped": fid, "places": [by_fid[f] for f in fids],
                                  "downloaded": downloaded})


async def run(city: str, headed: bool = False, profile_name: str | None = None, sessions=open_sessions,
              limit: int | None = None) -> dict:
    """profile_name is ignored: video pages need no account."""
    started = time.monotonic()
    _, cfg = load_config(city)
    c, root = cfg["tiktok"], data_dir() / "tiktok"
    urls = _urls(city)
    recorded: dict[str, set[str]] = {}  # video_id -> fids web_videos already put on it
    for r in load(city):
        recorded.setdefault(r["video_id"], set()).update(p["fid"] for p in r.get("places") or [])
    poi_file = root / "place_poi" / f"{city}.json"
    mapped = {p["poi"]["id"]: fid for fid, p in json.loads(poi_file.read_text(encoding="utf-8"))["places"].items()
              if p.get("poi")} if poi_file.exists() else {}
    places = [{"fid": r["fid"], "name": r["name"], "category": r.get("category")} for r in listed(city) or []
              if r.get("fid") and r.get("name")]
    by_fid = {p["fid"]: {**p, "address": address(p["fid"])} for p in places}
    todo, extra = [], []
    for r in urls:
        vid = r["video_id"]
        new = [f for f in r["want"] if f in by_fid and f not in recorded.get(vid, set())]
        if (root / "videos" / vid / "video.mp4").exists():
            if new:
                extra.append((r, new))  # on disk already: only record the new candidate place
        elif vid not in recorded or new:
            if not (root / "videos" / vid / "info.json").exists():
                todo.append(r)
    for r, new in extra:
        append_jsonl(out_path(city), {"at": now(), "video_id": r["video_id"], "url": r["url"], "query": r.get("query"),
                                      "poi": None, "mapped": None, "places": [by_fid[f] for f in new],
                                      "downloaded": True})
    stats = {"urls": len(urls), "todo": len(todo), "recorded_only": len(extra), "wanted": 0, "with_poi": 0, "area": 0,
             "mapped": 0, "named": 0, "downloaded": 0, "no_item": 0, "errors": 0}
    print(f"web_videos {city}: {len(todo)} of {len(urls)} web videos left" + (f", running {limit}" if limit else ""),
          flush=True)
    if limit:
        todo = todo[:limit]
    throttle = MissWatchThrottle(root / "web_videos_throttle.json", start=c.get("poi_tabs_start", 2),
                                 hi=c.get("poi_tabs", 3), cooldown_s=c.get("cooldown_s", 60),
                                 max_cooldown_s=c.get("max_cooldown_s", 900))
    downloads = asyncio.Semaphore(c.get("downloads", 4))
    if todo:
        async with sessions(headed) as new_session:
            ctx = await new_session()
            try:
                async with asyncio.TaskGroup() as tg:  # a captcha in a headless run stops all
                    for r in todo:
                        tg.create_task(_video(ctx, r, root, c, throttle, downloads, mapped, places, by_fid, stats,
                                              city))
            except* LoginRequired as eg:
                raise eg.exceptions[0] from None
    stats["seconds"] = round(time.monotonic() - started, 1)
    print(f"web_videos {city}: {json.dumps(stats)}", flush=True)
    return stats
