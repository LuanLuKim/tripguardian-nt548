"""Editorial posts about the places with a 3D model (docs/CORPUS.md, Giới thiệu địa điểm §Bài biên tập): the Writer
writes two posts per place from the same evidence as the introduction (INTRO_POSTS), code checks every block like an
introduction sentence and every quote against the review it cites, the Judge (INTRO_CHECK) reads every paragraph, and
what fails is dropped and logged. Signed by TripGuardian; no person, reaction or comment is invented.
-> data/<city>/intro/posts.json (the web reads it through web/scripts/export_snapshot.py)."""

import asyncio
import json
from pathlib import Path

import openai
import yaml

from ..aggregate.naming import display_name
from ..crawl.common.files import ROOT, data_dir, now, write_json
from ..llm import INTRO_CHECK, INTRO_POSTS, JUDGE
from .evidence import Library, fold, pack
from .gate import check, sources
from .run import DROP_VERDICTS, _hash, _read, config, intro_dir, load, render_evidence, render_lines, tidy, writer

ANGLES = {
    "heritage": ["Câu chuyện của nơi này: lịch sử, kiến trúc, những gì đáng nhìn kỹ",
                 "Một buổi ghé thăm cho trọn: đến lúc nào, đi theo thứ tự nào, đừng bỏ lỡ gì"],
    "nature": ["Vẻ đẹp và câu chuyện của nơi này",
               "Đi thế nào cho đẹp: giờ nào, đường nào, nhìn từ đâu, chuẩn bị gì"],
    "cafe_food": ["Một buổi ngồi ở đây: không gian, món, cảm giác",
                  "Gọi gì, ngồi đâu, đến giờ nào"],
    "activity": ["Ở đây có gì hay", "Kinh nghiệm đi cho trọn: giờ, đường, chuẩn bị gì"],
    "other": ["Ở đây có gì hay", "Kinh nghiệm đi cho trọn: giờ, đường, chuẩn bị gì"],
}
CLOSING = "Muốn đi một vòng trước khi đến? Mở trang của nơi này, chọn tab Khám phá 3D để xem mô hình 3D."
MIN_PARAGRAPHS = 3


def quote_ok(block: dict, items: dict[str, dict]) -> bool:
    """A `q` block is the words of the one review it cites."""
    ids = block.get("evidence") or []
    if len(ids) != 1 or items.get(ids[0], {}).get("source") != "review":
        return False
    text = fold(block["text"]).strip(" \"'“”‘’.…")
    return len(text) >= 12 and text in fold(items[ids[0]]["text"])


def assemble(fid: str, slug: str, name: str, items: list[dict], answer: dict, verdicts: dict[int, str],
             cfg: dict) -> tuple[list[dict], list[dict]]:
    """(posts, dropped) from the Writer's answer, the code checks and the Judge's verdicts (index over every `p`)."""
    by_id = {it["id"]: it for it in items}
    posts, dropped, k = [], [], 0
    for n, post in enumerate(answer.get("posts") or []):
        blocks, srcs = [], []
        title = (post.get("title") or "").strip()
        if reason := check({"text": title, "evidence": list(by_id)}, by_id, cfg["gate"], name):
            dropped.append({"post": n, "t": "title", "text": title, "reason": reason})
        for b in post.get("blocks") or []:
            if b["t"] == "p":
                verdict = verdicts.get(k)
                k += 1
                reason = check(b, by_id, cfg["gate"], name) or (
                    f"judge_{verdict}" if verdict in DROP_VERDICTS else None if verdict else "judge_missing")
            elif b["t"] == "q":
                reason = None if quote_ok(b, by_id) else "quote_not_verbatim"
            else:
                reason = "hype" if any(h in fold(b["text"]) for h in cfg["gate"]["hype"]) else None
            if reason:
                dropped.append({"post": n, "t": b["t"], "text": b["text"], "reason": reason})
                continue
            blocks.append({"t": b["t"], "text": b["text"].strip().strip("\"“”")})
            srcs += sources(b, by_id)
        while blocks and blocks[-1]["t"] == "h":  # a heading left without its paragraph
            blocks.pop()
        paragraphs = [i for i, b in enumerate(blocks) if b["t"] == "p"]
        if len(paragraphs) < MIN_PARAGRAPHS or not title or any(d["post"] == n and d["t"] == "title" for d in dropped):
            dropped.append({"post": n, "t": "post", "text": title, "reason": "too_little_left"})
            continue
        for at, cover in ((paragraphs[2] + 1 if len(paragraphs) > 2 else None, 1), (paragraphs[0] + 1, 0)):
            if at is not None:  # photos of the place (photo_allow: no people), after the 1st and 3rd paragraph
                blocks.insert(at, {"t": "img", "src": f"cover:{cover + 2 * n}", "cap": ""})
        blocks.append({"t": "p", "text": CLOSING})
        seen, site_rows, reviews = set(), [], 0
        for s in srcs:
            if s["source"] == "review":
                reviews += s.get("n", 1)
            elif s["domain"] not in seen:
                seen.add(s["domain"])
                site_rows.append({k2: s[k2] for k2 in ("domain", "url", "title") if s.get(k2)})
        posts.append({"id": f"tg-{slug}-{n + 1}", "placeId": fid, "title": title,
                      "tags": [t.strip().lower() for t in post.get("tags") or [] if t.strip()][:4], "blocks": blocks,
                      "angle": post.get("angle"), "sources": site_rows,
                      **({"review_count": reviews} if reviews else {})})
    return posts, dropped


async def build(city: str = "dalat", *, only: list[str] | None = None, root: Path | None = None) -> dict:
    """CLI `intro posts`: two posts for every place with a 3D model (web/space3d/places.json) that is not a lodging and
    has an introduction (its kind picks the angles)."""
    root = root or data_dir()
    cfg = config()
    cities = yaml.safe_load((ROOT / "config" / "cities.yaml").read_text(encoding="utf-8"))
    city_name = (cities.get(city) or {}).get("name") or city
    spaces = json.loads((ROOT / "web" / "space3d" / "places.json").read_text(encoding="utf-8"))
    slug_of = {s["id"]: s["slug"] for s in spaces}
    records = {r["id"]: r for r in json.loads((root / "serving" / "places.json").read_text(encoding="utf-8"))["records"]}
    intros = load(city, root)
    todo = [records[i] for i in slug_of if i in records and records[i]["identity"].get("category_group") != "stay"
            and i in intros and (not only or i in only)]
    out = intro_dir(city, root)
    lib = Library(city, root)
    task, client, model = writer(cfg, INTRO_POSTS)
    jclient, jmodel = JUDGE.client()
    ev_cfg = {**cfg["evidence"], **cfg["posts"]["evidence"]}
    sem_w, sem_j = asyncio.Semaphore(cfg["posts"]["parallel"]), asyncio.Semaphore(cfg["judge"]["parallel"])
    results = []

    async def one(rec):
        fid = rec["id"]
        name = display_name(rec["identity"]["name"])
        items = await asyncio.to_thread(pack, lib, rec, city_name, ev_cfg)
        angles = ANGLES.get(intros[fid]["kind"], ANGLES["other"])
        key = _hash(items, angles, task.prompt_hash, model, task.role.reasoning())
        path = out / "posts" / f"{fid.replace(':', '_')}.json"
        done = _read(path, key)
        if done is None:
            async def write_one(i: int, angle: str):
                others = [a for j, a in enumerate(angles) if j != i]
                async with sem_w:
                    got = await task.ask(client, model, angle=angle, name=name, city=city_name,
                                         others=("Other posts cover, so leave out: " + "; ".join(others)) if others else "",
                                         category=rec["identity"].get("category") or "", evidence=render_evidence(items))
                return {**got, "angle": angle}
            try:
                answer = {"posts": list(await asyncio.gather(*(write_one(i, a) for i, a in enumerate(angles))))}
            except Exception as e:  # noqa: BLE001
                results.append({"id": fid, "error": f"write: {type(e).__name__}: {e}"[:300]})
                return
            done = {"key": key, "at": now(), "model": model, "answer": answer}
            write_json(path, {**done, "items": items})  # kept even if the check below fails
        answer = {"posts": [{**p, "blocks": [{**tidy(b), "t": b["t"]} for b in p.get("blocks") or []]}
                            for p in done["answer"].get("posts") or []]}
        paras = [b for p in answer["posts"] for b in p["blocks"] if b["t"] == "p"]
        by_id = {it["id"]: it for it in items}
        jkey = _hash(paras, INTRO_CHECK.prompt_hash, jmodel)
        if "verdicts" not in done or done.get("judge_key") != jkey:
            async with sem_j:
                for wait in (*cfg["judge"]["busy_wait_s"], None):
                    try:
                        got = await INTRO_CHECK.ask(jclient, jmodel, name=name, city=city_name,
                                                    category=rec["identity"].get("category") or "",
                                                    sentences=render_lines(paras, by_id))
                        break
                    except openai.RateLimitError as e:
                        if wait is None:
                            results.append({"id": fid, "error": f"check: {e}"[:300]})
                            return
                        await asyncio.sleep(wait)
            done = {**done, "judge_key": jkey, "verdicts": got["verdicts"]}
        write_json(path, {**done, "items": items})
        posts, dropped = assemble(fid, slug_of[fid], name, items, answer,
                                  {v["i"]: v["verdict"] for v in done["verdicts"]}, cfg)
        results.append({"id": fid, "posts": posts, "dropped": dropped, "at": done["at"]})

    await asyncio.gather(*(one(r) for r in todo))
    path = out / "posts.json"
    old = {p["id"]: p for p in (json.loads(path.read_text(encoding="utf-8"))["posts"] if path.exists() and only else [])}
    rebuilt = {r["id"] for r in results if "posts" in r}
    posts = [p for p in old.values() if p["placeId"] not in rebuilt]
    for r in results:
        for p in r.get("posts") or []:
            posts.append({**p, "author": "TripGuardian", "kind": "editorial", "at": r["at"]})
    dropped = [{"placeId": r["id"], **d} for r in results for d in r.get("dropped") or []]
    reasons = {}
    for d in dropped:
        reasons[d["reason"]] = reasons.get(d["reason"], 0) + 1
    stats = {"places": len(todo), "posts": len(posts), "errors": sum("error" in r for r in results), "dropped": reasons}
    write_json(path, {"city": city, "built_at": now(), "stats": stats, "posts": sorted(posts, key=lambda p: p["id"]),
                      "dropped": dropped})
    errors = [r for r in results if "error" in r]
    if errors:
        write_json(out / "posts_errors.json", errors)
    print(f"intro posts {city}: {json.dumps(stats, ensure_ascii=False)}")
    return stats
