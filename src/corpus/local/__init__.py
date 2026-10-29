"""Local knowledge (docs/CORPUS.md, Tri thức bản địa): web Documents -> LocalClaim with a quote, grouped by code;
sol's general claims (source = model) get confirmed / contradicted / unverified against them. Offline. Public API:

    gate_claim(item, section, resolve=None) -> (claim | None, reason | None)
    months_in(text) -> set[int]
    chunks(doc, max_chars) -> [{heading, text}]
    extract(docs, out, city_name=, ask=, model=, chunk_chars=, parallel=) -> stats       (async)
    group_claims(rows, now=, city_name=) -> [LocalClaim]      (origin "document": kept | unverified | conflict)
    check_model(general_claims, claims, city_name=) -> [LocalClaim]   (origin "model": confirmed | contradicted | unverified)
    amounts(text) -> (min, max) | None
    run_extract(city, limit=, docs=, ask=, model=, parallel=) -> stats     (async; CLI `local extract`)
    run_group(city, general=, now=, map_path=) -> {city, built_at, stats, claims}   (CLI `local group`)
"""

from .extract import chunks, extract
from .gate import gate_claim, months_in
from .group import amounts, check_model, group_claims
from .run import local_dir, run_extract, run_group

__all__ = ["amounts", "check_model", "chunks", "extract", "gate_claim", "group_claims", "local_dir", "months_in",
           "run_extract", "run_group"]
