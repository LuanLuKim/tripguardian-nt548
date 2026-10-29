"""Phases `local extract` (Extractor reads Documents) and `local group` (code: gate, resolve, group, sol's claims)
-> data/<city>/local/ (docs/CORPUS.md, Tri thức bản địa). Writes nothing outside that folder."""

import collections
import json
from datetime import UTC, datetime

from ..crawl.common.files import append_jsonl, data_dir, load_config, now as stamp, write_json
from ..llm import LOCAL_CLAIM
from ..retrieval import NameRecord, name_score, search_names
from .extract import extract
from .gate import gate_claim
from .group import check_model, group_claims, tokens

CHUNK_CHARS = 3500   # smaller chunks keep an answer well under max_tokens (~4 chars of JSON per char read)
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
            records.append(NameRecord(r["id"], ident["name"]))
    within = {r.place_id for r in records}

    def resolve_name(name: str) -> str | None:
        hits = search_names(name, records, within=within, release_id=None, limit=1)
        if not hits or name_score(name, hits[0].name) < RESOLVE_SCORE:
            return None
        words = tokens(name)
        cover = len(words & tokens(hits[0].name)) / len(words) if words else 0.0
        return hits[0].place_id if cover >= RESOLVE_COVER else None
    return resolve_name


def run_group(city: str, *, general: list[dict] | None = None, now: datetime | None = None,
              map_path=None) -> dict:
    """Gate every extracted item against its chunk, group, give sol's general claims a status, write
    local_claims.json, poi_claims.json (claims about served venues) and poi_unresolved.jsonl (venues to resolve)."""
    name, _ = load_config(city)
    now = now or datetime.now(UTC)
    if general is None:
        from ..navigate import general_claims, load_map
        found = map_path and load_map(city, map_path)
        general = [g.model_dump() for g in (found.general_claims if found else [] if map_path else general_claims(city))]
    meta = {d["doc_id"]: d for d in _documents(city)}
    resolve_name = _resolver(city)
    rows, dropped, items, docs = [], collections.Counter(), 0, 0
    for p in sorted((local_dir(city) / "extracted").glob("*.json")):
        ex = json.loads(p.read_text(encoding="utf-8"))
        doc = meta.get(ex["doc_id"])
        if doc is None:
            continue
        docs += 1
        for chunk in ex["chunks"]:
            for item in chunk["items"]:
                items += 1
                c, why = gate_claim(item, chunk["text"], resolve_name)
                if why:
                    dropped[why] += 1
                    continue
                rows.append({**c, "doc_id": doc["doc_id"], "source_url": doc["source_url"], "domain": doc["domain"],
                             "retrieved_at": doc["retrieved_at"]})
    claims = group_claims(rows, now=now, city_name=name)
    model = check_model(general, claims, city_name=name)
    status = {"document": dict(collections.Counter(c["status"] for c in claims)),
              "model": dict(collections.Counter(c["status"] for c in model))}
    stats = {"documents": docs, "items": items, "gated": len(rows), "dropped": dict(dropped), "status": status}
    out = {"city": city, "built_at": stamp(), "stats": stats, "claims": claims + model}
    root = local_dir(city)
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
