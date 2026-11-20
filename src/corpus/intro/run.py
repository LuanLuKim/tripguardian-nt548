"""Build every serving place's introduction (docs/CORPUS.md, Giới thiệu địa điểm): evidence (code) -> Writer
(INTRO_WRITE) -> gate (code) -> Judge (INTRO_CHECK) -> data/<city>/intro/intros.json. Offline.

Both model answers are cached per place by what they read (evidence, sentences, prompt, model), in written/<fid>.json
and checked/<fid>.json, so a re-run asks only for what changed. A call that fails leaves no cache: the next run asks
again.
"""

import asyncio
import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass, fields, replace
from pathlib import Path

import openai
import yaml

from ..aggregate.naming import display_name
from ..crawl.common.files import ROOT, data_dir, now, write_json
from ..llm import INTRO_CHECK, INTRO_WRITE, JUDGE, WRITER, Role
from .evidence import Library, pack
from .gate import check, sources

CONFIG = ROOT / "config" / "intro.yaml"
DROP_VERDICTS = ("partly", "unsupported", "other_place")


def config() -> dict:
    return yaml.safe_load(CONFIG.read_text(encoding="utf-8"))


def intro_dir(city: str, root: Path | None = None) -> Path:
    return (root or data_dir()) / city / "intro"


@dataclass(frozen=True)
class _Writer(Role):
    effort: str = "medium"

    def reasoning(self) -> str:
        return self.effort


def writer(cfg: dict, base=INTRO_WRITE):
    """(task, client, model) of a Writer task (INTRO_WRITE, INTRO_POSTS) as config/intro.yaml sets it: model and
    effort from config, key and endpoint from .env (WRITER_*, else the Agent's)."""
    w = cfg["writer"]
    role = _Writer(**{f.name: getattr(WRITER, f.name) for f in fields(WRITER)}, effort=w["reasoning_effort"])
    client, _ = role.own_client()
    return replace(base, role=role, parallel=w["parallel"]), client, w["model"]


def _hash(*parts) -> str:
    return hashlib.sha256(json.dumps(parts, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:16]


def render_evidence(items: list[dict]) -> str:
    rows = []
    for it in items:
        tag = {"web": f"web · {it['domain']}", "search": f"search · {it['domain']}", "official": "the place's own site",
               "maps": "Google Maps description", "review": "one review", "detail": f"visitors n={it['n']}"}[it["source"]]
        mark = " [chính thống]" if it["authority"] else ""
        rows.append(f"[{it['id']}] ({tag}){mark} {it['text']}")
    return "\n".join(rows)


def render_lines(lines: list[dict], items: dict[str, dict]) -> str:
    out = []
    for i, line in enumerate(lines):
        cited = "\n".join(f"  - [{e}] {items[e]['text']}" for e in dict.fromkeys(line["evidence"]) if e in items)
        out.append(f"{i}. {line['text']}\n{cited}")
    return "\n".join(out)


def _read(path: Path, key: str) -> dict | None:
    if path.exists():
        d = json.loads(path.read_text(encoding="utf-8"))
        if d.get("key") == key:
            return d
    return None


CITE = re.compile(r"\s*\[\s*(e\d+(?:\s*[,;]\s*e\d+)*)\s*\]")


def tidy(line: dict) -> dict:
    """The Writer's line with ids it wrote into the text ("… 7 km.[e2]") moved to `evidence`, and letters of other
    scripts (a stray Tamil "ி") removed."""
    text = line.get("text") or ""
    ids = list(line.get("evidence") or []) + [i for m in CITE.findall(text) for i in re.findall(r"e\d+", m)]
    text = CITE.sub("", text)
    text = "".join(ch for ch in text if not (unicodedata.category(ch).startswith(("L", "M"))
                                             and "LATIN" not in unicodedata.name(ch, "")
                                             and unicodedata.category(ch) != "Mn"))
    return {"text": re.sub(r"\s+", " ", text).strip(), "evidence": list(dict.fromkeys(ids))}


def assemble(record: dict, items: list[dict], answer: dict, verdicts: dict[int, str], cfg: dict) -> dict:
    """The served introduction from the Writer's answer, the gate and the Judge's verdicts (index over summary + story)."""
    by_id = {it["id"]: it for it in items}
    out = {"kind": answer["kind"], "summary": [], "story": [], "dropped": []}
    i = 0
    for part in ("summary", "story"):
        for line in answer[part]:
            reason = check(line, by_id, cfg["gate"], record["identity"]["name"]) or (f"judge_{verdicts.get(i)}" if verdicts.get(i) in DROP_VERDICTS
                                                         else None if i in verdicts else "judge_missing")
            if reason:
                out["dropped"].append({"part": part, "text": line["text"], "reason": reason})
            else:
                out[part].append({"text": line["text"].strip(), "sources": sources(line, by_id)})
            i += 1
    total = 0
    for n, line in enumerate(out["summary"]):
        total += len(line["text"]) + 1
        if total > cfg["gate"]["summary_max_chars"] and n:
            out["dropped"] += [{"part": "summary", "text": x["text"], "reason": "summary_too_long"} for x in out["summary"][n:]]
            out["summary"] = out["summary"][:n]
            break
    return out


async def one(record: dict, lib: Library, out: Path, cfg: dict, city_name: str, write, check_, sem_w, sem_j) -> dict:
    """{id, status, intro?}: status ok | thin (too little evidence) | empty (nothing survived) | error."""
    fid = record["id"]
    items = await asyncio.to_thread(pack, lib, record, city_name, cfg["evidence"])  # CPU: keep the calls moving
    if len(items) < cfg["evidence"]["min_items"]:
        return {"id": fid, "status": "thin"}
    task, client, model = write
    name = fid.replace(":", "_")
    wkey = _hash(items, task.prompt_hash, model, task.role.reasoning())
    wpath = out / "written" / f"{name}.json"
    done = _read(wpath, wkey)
    if done is None:
        async with sem_w:
            try:
                answer = await task.ask(client, model, name=display_name(record["identity"]["name"]),
                                        category=record["identity"].get("category") or "",
                                        city=city_name, evidence=render_evidence(items))
            except Exception as e:  # noqa: BLE001 - one place's failure must not stop the build
                return {"id": fid, "status": "error", "error": f"write: {type(e).__name__}: {e}"[:300]}
        done = {"key": wkey, "at": now(), "model": model, "items": items, "answer": answer}
        write_json(wpath, done)
    answer = {**done["answer"], **{p: [tidy(ln) for ln in done["answer"][p]] for p in ("summary", "story")}}
    by_id = {it["id"]: it for it in items}
    lines = [ln for part in ("summary", "story") for ln in answer[part]]
    if not lines:
        return {"id": fid, "status": "empty"}
    jtask, jclient, jmodel = check_
    jkey = _hash(lines, [by_id.get(e, {}).get("text") for ln in lines for e in ln["evidence"]], jtask.prompt_hash, jmodel)
    jpath = out / "checked" / f"{name}.json"
    judged = _read(jpath, jkey)
    if judged is None:
        async with sem_j:
            for wait in (*cfg["judge"]["busy_wait_s"], None):
                try:
                    got = await jtask.ask(jclient, jmodel, name=display_name(record["identity"]["name"]),
                                          category=record["identity"].get("category") or "", city=city_name,
                                          sentences=render_lines(lines, by_id))
                    break
                except openai.RateLimitError as e:  # the shared UIT key is full: wait for other runs, not fail
                    if wait is None:
                        return {"id": fid, "status": "error", "error": f"check: {type(e).__name__}: {e}"[:300]}
                    await asyncio.sleep(wait)
                except Exception as e:  # noqa: BLE001
                    return {"id": fid, "status": "error", "error": f"check: {type(e).__name__}: {e}"[:300]}
        judged = {"key": jkey, "at": now(), "model": jmodel, "verdicts": got["verdicts"]}
        write_json(jpath, judged)
    verdicts = {v["i"]: v["verdict"] for v in judged["verdicts"]}
    intro = assemble(record, items, answer, verdicts, cfg)
    intro["name"] = display_name(record["identity"]["name"])
    intro["model"] = done["model"]
    intro["built_at"] = done["at"]
    return {"id": fid, "status": "ok" if intro["summary"] else "empty", "intro": intro}


async def build(city: str = "dalat", *, only: list[str] | None = None, limit: int | None = None,
                root: Path | None = None) -> dict:
    """CLI `intro build`: every serving record (or `only` ids), written into data/<city>/intro/intros.json. A partial
    run (`only` / `limit`) keeps the introductions of the other places from the last full file."""
    root = root or data_dir()
    cfg = config()
    cities = yaml.safe_load((ROOT / "config" / "cities.yaml").read_text(encoding="utf-8"))
    city_name = (cities.get(city) or {}).get("name") or city
    records = json.loads((root / "serving" / "places.json").read_text(encoding="utf-8"))["records"]
    if only:
        want = set(only)
        records = [r for r in records if r["id"] in want]
    records = records[:limit] if limit else records
    out = intro_dir(city, root)
    lib = Library(city, root)
    write = writer(cfg)
    jclient, jmodel = JUDGE.client()
    check_ = (INTRO_CHECK, jclient, jmodel)
    sem_w, sem_j = asyncio.Semaphore(write[0].parallel), asyncio.Semaphore(cfg["judge"]["parallel"])
    results, counts = [], {}

    queue = asyncio.Queue()
    for rec in records:
        queue.put_nowait(rec)

    async def worker():  # a few places at a time: the evidence of the next is read while the models answer
        while not queue.empty():
            rec = queue.get_nowait()
            r = await one(rec, lib, out, cfg, city_name, write, check_, sem_w, sem_j)
            results.append(r)
            counts[r["status"]] = counts.get(r["status"], 0) + 1
            if len(results) % 50 == 0:
                print(f"intro {city}: {len(results)}/{len(records)} {counts}", flush=True)

    await asyncio.gather(*(worker() for _ in range(write[0].parallel * 2)))
    path = out / "intros.json"
    old = json.loads(path.read_text(encoding="utf-8"))["intros"] if path.exists() and (only or limit) else {}
    intros = {**old, **{r["id"]: r["intro"] for r in results if r["status"] == "ok"}}
    for r in results:
        if r["status"] in ("thin", "empty"):  # an error keeps the last introduction: the next run asks again
            intros.pop(r["id"], None)
    dropped = {}
    for r in results:
        for d in (r.get("intro") or {}).get("dropped") or []:
            dropped[d["reason"]] = dropped.get(d["reason"], 0) + 1
    stats = {"places": len(records), "status": counts, "dropped": dropped, "served": len(intros)}
    write_json(path, {"city": city, "built_at": now(), "stats": stats, "intros": dict(sorted(intros.items()))})
    errors = [r for r in results if r["status"] == "error"]
    if errors:
        write_json(out / "errors.json", errors)
    print(f"intro {city}: {json.dumps(stats, ensure_ascii=False)}")
    return stats


def load(city: str = "dalat", root: Path | None = None) -> dict[str, dict]:
    """{fid: introduction} of the last build; {} when there is none (unknown, not "no introduction")."""
    path = intro_dir(city, root) / "intros.json"
    return json.loads(path.read_text(encoding="utf-8"))["intros"] if path.exists() else {}
