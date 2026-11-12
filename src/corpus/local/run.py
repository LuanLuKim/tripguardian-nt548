"""Phases `local extract` (Extractor reads Documents) and `local group` (code: gate, resolve, group, sol's claims)
-> data/<city>/local/ (docs/CORPUS.md, Tri thức bản địa). Writes nothing outside that folder."""

import collections
import json
from datetime import UTC, datetime
from pathlib import Path

from ..crawl.common.files import append_jsonl, data_dir, load_config, now as stamp, write_json
from ..llm import LOCAL_CLAIM, LOCAL_VERIFY, LOCAL_VERIFY_CLAIM
from ..retrieval import NameRecord, name_score, search_names
from .extract import extract
from .gate import doc_on_topic, gate_claim, rules
from .group import candidate_rows, check_model, fold, group_claims, tokens
from .verify import ckey, claim_todo, load_cache, todo, verify, verify_claims, vkey

CHUNK_CHARS = 3500   # smaller chunks keep an answer well under max_tokens (~4 chars of JSON per char read)
MAX_ROUNDS = 4        # `local verify` re-groups after each round of verdicts until nothing is left to ask
PARALLEL = 4          # the Extractor lane is shared with the nightly chain: a few calls at a time
RESOLVE_SCORE = 0.7   # name_score of a venue to its corpus name, as navigate's `held`
RESOLVE_COVER = 0.5   # share of the venue's own words found in the corpus name


def local_dir(city: str):
    return data_dir() / city / "local"


def _documents(city: str, docs: list[str] | None = None, limit: int | None = None) -> list[dict]:
    root = data_dir() / "web" / city / "documents"
    paths = sorted(root.glob("*.json")) if root.exists() else []
    if docs is not None:
        wanted = set(docs)
        paths = [p for p in paths if p.stem in wanted]
    out = [json.loads(p.read_text(encoding="utf-8")) for p in paths]
    return out[:limit] if limit is not None else out


async def run_extract(city: str, *, limit: int | None = None, docs: list[str] | None = None, ask=None,
                      model: str | None = None, parallel: int = PARALLEL) -> dict:
    name, _ = load_config(city)
    if ask is None:
        client, model = LOCAL_CLAIM.role.client()
        client = client.with_options(timeout=240, max_retries=0)

        async def ask(**fields):
            return await LOCAL_CLAIM.ask(client, model, **fields)
    todo = _documents(city, docs, limit)
    stats = await extract(todo, local_dir(city) / "extracted", city_name=name, ask=ask, model=model or "",
                          chunk_chars=CHUNK_CHARS, parallel=parallel)
    print(f"local extract {city}: {stats}", flush=True)
    return stats


def verified_path(city: str, root=None, claims: bool = False):
    return Path(root or local_dir(city)) / ("verified_claims.jsonl" if claims else "verified.jsonl")


async def run_verify(city: str, *, ask=None, model: str | None = None, parallel: int | None = None,
                     limit: int | None = None, out_dir=None, cask=None) -> dict:
    """Phase `local verify`: gate and group the extracted items (no verdicts), then ask the Extractor whether each quote
    of each would-be-kept claim states it (corpus.local.verify). Answers are appended to verified.jsonl in `out_dir`
    (default data/<city>/local/);
    what was asked before (same claim, quote, prompt) is not asked again."""
    name, _ = load_config(city)
    if ask is None:
        client, model = LOCAL_VERIFY.role.client()
        client = client.with_options(timeout=120, max_retries=0)

        async def ask(**fields):
            return await LOCAL_VERIFY.ask(client, model, **fields)
    rows, *_ = gated_rows(city, name, _resolver(city))
    out = verified_path(city, out_dir)
    stats = {"rounds": 0, "asked": 0, "failed": 0, "ok": 0, "rejected": 0}
    for _ in range(MAX_ROUNDS):   # dropping rejected rows re-groups the rest: a few rows may need a first look
        cache = load_cache(out)
        verdicts = {k: v["problem"] for k, v in cache.items()}
        left = [r for r in rows if verdicts.get(vkey(r), "none") == "none"]
        items = todo(candidate_rows(left, city_name=name), cache)
        items = items[:limit] if limit is not None else items
        if not items:
            break
        got = await verify(items, city_name=name, ask=ask, model=model or "", out=out, parallel=parallel)
        stats["rounds"] += 1
        for k in ("asked", "failed", "ok", "rejected"):
            stats[k] += got[k]
        if got["asked"] == 0 or limit is not None:
            break
    stats["cached"] = len(load_cache(out))
    # third look: each grouped claim that would be kept, against all its quotes
    verdicts = {k: v["problem"] for k, v in load_cache(out).items()}
    left = [r for r in rows if verdicts.get(vkey(r), "none") == "none"]
    claims = group_claims(left, now=datetime.now(UTC), city_name=name, verdicts=verdicts, vkey=vkey)
    cout = verified_path(city, out_dir, claims=True)
    items = claim_todo(claims, load_cache(cout))
    items = items[:limit] if limit is not None else items
    if items:
        if cask is None:
            client, cmodel = LOCAL_VERIFY_CLAIM.role.client()
            client = client.with_options(timeout=120, max_retries=0)

            async def cask(**fields):
                return await LOCAL_VERIFY_CLAIM.ask(client, cmodel, **fields)
        got = await verify_claims(items, city_name=name, chunks={(r["doc_id"], fold(r["quote"])): r["chunk"] for r in rows},
                                  ask=cask, model=model or "", out=cout, parallel=parallel)
        stats["claims"] = got
    print(f"local verify {city}: {stats}", flush=True)
    return stats


def _resolver(city: str):
    """name -> place id of a served place inside the city's area, None when no corpus name is close enough."""
    from ..releases import resolve
    _, cfg = load_config(city)
    area = cfg.get("area")
    path = resolve(data_dir()) / "serving" / "places.json"
    records = []
    for r in json.loads(path.read_text(encoding="utf-8"))["records"] if path.exists() else []:
        ident = r.get("identity") or {}
        lat, lng = ident.get("lat"), ident.get("lng")
        inside = not area or lat is None or lng is None or (area[0] <= lat <= area[2] and area[1] <= lng <= area[3])
        if inside and ident.get("name"):
            records.append(NameRecord(r["id"], ident["name"], raw=ident.get("name_raw")))
    within = {r.place_id for r in records}

    def resolve_name(name: str) -> str | None:
        hits = search_names(name, records, within=within, release_id=None, limit=1)
        if not hits or name_score(name, hits[0].name) < RESOLVE_SCORE:
            return None
        words = tokens(name)
        cover = len(words & tokens(hits[0].name)) / len(words) if words else 0.0
        return hits[0].place_id if cover >= RESOLVE_COVER else None
    return resolve_name


def gated_rows(city: str, city_name: str, resolve_name=None) -> tuple[list[dict], collections.Counter, int, int]:
    """(rows, dropped reasons, items read, documents read): every extracted item that passes the gate, with its
    document's doc_id, source_url, domain, retrieved_at and (not saved) the chunk text it came from. A Document that is
    not about the city drops all its items (`off_topic_doc`)."""
    meta = {d["doc_id"]: d for d in _documents(city)}
    markers = rules()["topic"]["markers"].get(fold(city_name).replace(" ", ""), [])
    rows, dropped, items, docs = [], collections.Counter(), 0, 0
    for p in sorted((local_dir(city) / "extracted").glob("*.json")):
        ex = json.loads(p.read_text(encoding="utf-8"))
        doc = meta.get(ex["doc_id"])
        if doc is None:
            continue
        docs += 1
        title = doc.get("title") or ""
        on_topic = doc_on_topic(title, [c["text"] for c in ex["chunks"]], city_name, markers)
        for chunk in ex["chunks"]:
            for item in chunk["items"]:
                items += 1
                if not on_topic:
                    dropped["off_topic_doc"] += 1
                    continue
                c, why = gate_claim(item, chunk["text"], resolve_name, city_name=city_name, title=title)
                if why:
                    dropped[why] += 1
                    continue
                rows.append({**c, "doc_id": doc["doc_id"], "source_url": doc["source_url"], "domain": doc["domain"],
                             "retrieved_at": doc["retrieved_at"], "title": title, "chunk": chunk["text"]})
    return rows, dropped, items, docs


def run_group(city: str, *, general: list[dict] | None = None, now: datetime | None = None,
              map_path=None, out_dir=None) -> dict:
    """Gate every extracted item against its chunk, group, give sol's general claims a status, write
    local_claims.json, poi_claims.json (claims about served venues) and poi_unresolved.jsonl (venues to resolve) into
    `out_dir` (default data/<city>/local/; a scratch folder leaves the live files untouched)."""
    name, _ = load_config(city)
    now = now or datetime.now(UTC)
    if general is None:
        from ..navigate import general_claims, load_map
        found = map_path and load_map(city, map_path)
        general = [g.model_dump() for g in (found.general_claims if found else [] if map_path else general_claims(city))]
    rows, dropped, items, docs = gated_rows(city, name, _resolver(city))
    cache = load_cache(verified_path(city, out_dir))   # no cache: no verification (a run before `local verify`)
    verdicts = {k: v["problem"] for k, v in cache.items()} if cache else None
    ccache = load_cache(verified_path(city, out_dir, claims=True))
    cverdicts = {k: v["problem"] for k, v in ccache.items()} if cache else None
    claims = group_claims(rows, now=now, city_name=name, verdicts=verdicts, vkey=vkey, claim_verdicts=cverdicts,
                          ckey=ckey)
    model = check_model(general, claims, city_name=name)
    status = {"document": dict(collections.Counter(c["status"] for c in claims)),
              "model": dict(collections.Counter(c["status"] for c in model))}
    stats = {"documents": docs, "items": items, "gated": len(rows), "dropped": dict(dropped), "status": status,
             "verified": len(cache), "verified_claims": len(ccache)}
    out = {"city": city, "built_at": stamp(), "stats": stats, "claims": claims + model}
    root = Path(out_dir) if out_dir else local_dir(city)
    write_json(root / "local_claims.json", out)
    write_json(root / "poi_claims.json", {"city": city, "built_at": out["built_at"],
                                          "claims": [c for c in claims if c["subject_kind"] == "poi"]})
    queue = root / "poi_unresolved.jsonl"
    seen = {json.loads(x)["name"] for x in queue.read_text(encoding="utf-8").splitlines() if x.strip()} \
        if queue.exists() else set()
    for c in claims:
        if c["subject_kind"] == "poi_unresolved" and c["subject"] not in seen:
            seen.add(c["subject"])
            append_jsonl(queue, {"name": c["subject"], "city": city, "claim_id": c["claim_id"],
                                 "doc_ids": [e["doc_id"] for e in c["evidence"]], "status": "proposed",
                                 "approval": "pending", "at": out["built_at"]})
    print(f"local group {city}: {json.dumps(stats, ensure_ascii=False)}", flush=True)
    return out
