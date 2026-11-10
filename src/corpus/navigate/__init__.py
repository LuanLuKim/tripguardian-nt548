"""Navigator: sol decides what to mine for a city, code checks it against what we hold (docs/CORPUS.md, sol dẫn đường).

sol proposes blind (`plan`), code gates the shape (`schema`) and `compare` diffs the proposal against the ontology, the
query config and the places in the corpus. Everything new is a proposal waiting for the owner; nothing here writes the
ontology, a config file or the corpus. Public API:

    plan(city, client=None, model=None, now=None, latest=True) -> MiningMap        (async, one sol call)
    compare_map(city, mining_map=None, now=None) -> dict    (report; also written, new things are proposals)
    enqueue_nominees(city: str, rows: list[dict]) -> int    (append lookup requests, deduplicated by folded name)
    seed(city: str, path: pathlib.Path | None = None) -> int    (owner-approved config names -> resolve queue)
    table(report) -> str                                                             (the report for the owner, Vietnamese)
    load_map(city, path=None) -> MiningMap | None
    general_claims(city) -> list[GeneralClaim]        (P4: sol's general knowledge, source = "model")
    pending_nominees(city) -> list[dict]      (nominees waiting for a Maps lookup: queue + 'maybe', minus the ledger)
    decide_resolution(nominee, rows, ...) -> dict   (verdict from the Maps results; never "does not exist")
    record_resolution(city, row)                    (append to resolved.jsonl)
    run(phase, city, path=None, latest=True)                                         (CLI entry)
"""

from .common import NavigateError
from .compare import compare_map, enqueue_nominees, seed, table
from .plan import general_claims, load_map, plan
from .resolve import STATUSES as RESOLVE_STATUSES, decide as decide_resolution, pending as pending_nominees, record as record_resolution, search_limit as resolve_search_limit
from .schema import Aspect, GeneralClaim, MiningMap, Nominee, Rejected, When, fold

__all__ = ["Aspect", "GeneralClaim", "MiningMap", "NavigateError", "Nominee", "Rejected", "When", "general_claims",
           "RESOLVE_STATUSES", "compare_map", "decide_resolution", "enqueue_nominees", "fold", "load_map", "pending_nominees", "plan", "record_resolution", "resolve_search_limit", "seed", "table"]
