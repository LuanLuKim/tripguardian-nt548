"""python -m harness serve | import-files: one journey API for the online modules, journeys in Postgres."""

import argparse
import hashlib
import logging
import os
import subprocess
import threading
from pathlib import Path

from dotenv import load_dotenv

from accounts import Accounts, GoogleClient, Library
from agents import ChatSafety
from companion import Calendar, Companion
from corpus.serving import load as serving_records
from corpus.releases import Binding, PinnedVersionMissing, bind, resolve_binding
from corpus.retrieval import RetrievalEngine
from db import pool
from notify import Notify
import live
from mailer import from_env as mailer_from_env
from decision import Engine as DecisionEngine, Store as DecisionStore, Tools as DecisionTools, create_engine as decision_engine
from planning import Tools as PlanningTools, create_engine as planning_engine
from social import Social
from trip import Engine as TripEngine, SessionStore, Tools as TripTools, create_engine as trip_engine

from . import Harness, PgStore, import_files, trip_live_tools
from .events import EventLog
from .server import run


def app_version(root: Path) -> str:
    """Short git commit + hash of config/*.yaml, stamped on journeys and events so numbers compare across versions.
    A dirty working tree still gets one stamp per distinct config."""
    try:
        sha = subprocess.run(["git", "-C", str(root), "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                             timeout=5).stdout.strip() or "nogit"
    except OSError:
        sha = "nogit"
    digest = hashlib.sha256()
    for path in sorted((root / "config").glob("*.yaml")):
        digest.update(path.name.encode() + path.read_bytes())
    return f"{sha}-{digest.hexdigest()[:8]}"


class _LazyRecords(dict):
    """Keep record-independent service calls responsive while active engines warm."""
    def __init__(self, factory):
        super().__init__()
        self._factory, self._ready = factory, False
        self._lock = threading.Lock()

    def _load(self):
        with self._lock:
            if not self._ready:
                self.update((r["id"], r) for r in self._factory())
                self._ready = True
        return self

    def get(self, key, default=None):
        return dict.get(self._load(), key, default)

    def __getitem__(self, key):
        return dict.__getitem__(self._load(), key)

    def __iter__(self):
        return dict.__iter__(self._load())

    def __len__(self):
        return dict.__len__(self._load())

    def __contains__(self, key):
        return dict.__contains__(self._load(), key)

    def values(self):
        return dict.values(self._load())

    def items(self):
        return dict.items(self._load())

    def keys(self):
        return dict.keys(self._load())


def recent_bindings(db_pool) -> list[Binding | None]:
    """Read only identities, newest distinct pins of owned journeys saved in the last week."""
    with db_pool.connection() as conn:
        rows = conn.execute(
            "SELECT envelope->'corpus_binding' AS binding FROM journeys "
            "WHERE user_id IS NOT NULL AND updated_at >= now() - interval '7 days' "
            "GROUP BY envelope->'corpus_binding' ORDER BY max(updated_at) DESC LIMIT 3"
        ).fetchall()
    return [Binding.model_validate(row["binding"]) if row["binding"] else None for row in rows]


def recent_journeys(db_pool, hours: int = 48, limit: int = 30) -> list[str]:
    """Owned journeys saved in the last `hours`, newest first: the ones worth warming after a restart."""
    with db_pool.connection() as conn:
        rows = conn.execute("SELECT id FROM journeys WHERE user_id IS NOT NULL AND updated_at >= now() - make_interval(hours => %s) "
                            "ORDER BY updated_at DESC LIMIT %s", (hours, limit)).fetchall()
    return [row["id"] for row in rows]


def create_tools_factory(data, trip_live):
    def tools_for_binding(pinned: Binding | None):
        selected = pinned if pinned is not None else bind(data, legacy=True)
        retrieval = RetrievalEngine.open(data_root=data, binding=selected)
        tools = {"trip": TripTools(trip_engine(data, binding=selected, retrieval=retrieval, live=trip_live)),
                 "decision": DecisionTools(decision_engine(data, binding=selected, retrieval=retrieval)),
                 "planning": PlanningTools(planning_engine(data, binding=selected, retrieval=retrieval))}
        tools["decision"].engine.trip_reader = tools["trip"].read_turn
        tools["planning"].engine.trip_reader = tools["trip"].read_turn
        if pinned is None:
            for tool in tools.values():
                tool.engine.corpus_binding = None
        return tools
    def checked_tools(pinned: Binding | None):
        selected = pinned if pinned is not None else bind(data, legacy=True)
        try:
            resolve_binding(data, selected)
            return tools_for_binding(pinned)
        except (FileNotFoundError, ValueError) as exc:
            if selected.release_id is None:
                raise
            raise PinnedVersionMissing("release", selected.release_id) from exc
    return checked_tools


def create_read_tools_factory(harness):
    """Share immutable corpus/config; each journey reader owns sessions and derived caches."""
    def readers(binding):
        source = harness._tools(binding)
        t, d = (source[name].engine for name in ("trip", "decision"))
        trip = TripEngine(t.catalog, t.cfg, SessionStore(None), t.chat, today=t.today,
                          judge=t.judge, looks=t.looks, web=t.web, see=t.see, knowledge=t.knowledge)
        decision = DecisionEngine(d.data, d.cfg, DecisionStore(None), retrieval=d.retrieval)
        tools = {"trip": TripTools(trip), "decision": DecisionTools(decision)}
        for tool in tools.values():
            tool.engine.corpus_binding = binding
        return tools
    return readers


def main():
    parser = argparse.ArgumentParser(prog="python -m harness")
    sub = parser.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve")
    serve.add_argument("--port", type=int, default=8769)
    serve.add_argument("--host", default="127.0.0.1")
    imp = sub.add_parser("import-files", help="load data/harness/sessions + feedback.jsonl into Postgres (once)")
    imp.add_argument("sessions", type=Path)
    imp.add_argument("feedback", type=Path, nargs="?")
    args = parser.parse_args()
    logging.basicConfig(format="%(asctime)s %(levelname)s %(name)s %(message)s")
    logging.getLogger("harness.dispatch").setLevel(logging.INFO)
    logging.getLogger("harness.server").setLevel(logging.INFO)
    root = Path(__file__).resolve().parents[2]
    load_dotenv(root / ".env")
    if args.command == "import-files":
        journeys, feedback = import_files(pool(), args.sessions, args.feedback)
        print(f"imported {journeys} journeys, {feedback} feedback rows")
        return
    data = Path(os.environ.get("DATA_DIR", "data"))
    if not data.is_absolute():
        data = root / data
    version = app_version(root)
    accounts = Accounts(pool(), GoogleClient.from_env(), data / "accounts" / "avatars", os.environ.get("TOKEN_ENC_KEY"))
    binding = bind(data, verify=False)
    live_cfg = live.load_settings()
    # the Trip assistant's weather and travel time (Trip never imports live)
    trip_live = trip_live_tools(live_cfg)

    harness = Harness(None, None, None, PgStore(pool(), version), EventLog(pool(), version),
        safety=ChatSafety(), corpus_binding=binding, tools_for_binding=create_tools_factory(data, trip_live),
        eve_store=_eve_store())
    harness.read_tools_for_binding = create_read_tools_factory(harness)
    records = _LazyRecords(lambda: harness.tools["planning"].engine.records)
    companion = Companion(pool(), [])
    companion.records = records
    harness.companion = companion
    harness.calendar = Calendar(pool(), accounts, records, os.environ.get("APP_BASE_URL", ""))
    harness.notify = Notify(pool(), records)
    harness.warm_releases(lambda: recent_bindings(pool()), lambda: recent_journeys(pool()), encoders=True)
    # the overload search's standing workers (planning.overload pool), so the first overloaded trip does not start them
    threading.Thread(target=_warm_planning_workers, name="planning-workers-warm", daemon=True).start()
    test_login = os.environ.get("TG_TEST_LOGIN") == "1"  # walk-throughs only; refused when APP_BASE_URL is https
    print(f"Journey harness: http://{args.host}:{args.port} (app {version})")
    run(harness, accounts, args.port, os.environ.get("APP_BASE_URL", ""), test_login,
        Social(pool()), Library(pool()), mailer_from_env(), host=args.host)


def _warm_planning_workers() -> None:
    try:
        from planning import warm_workers
        warm_workers()
    except Exception:
        logging.getLogger(__name__).exception("Planning worker warmup failed")


def _eve_store():
    """The D.3 evening check's pending changes (data/planning/eve), only while eve_replan.enabled is true."""
    import planning
    if not planning.load_settings().eve_replan.get("enabled"):
        return None
    return planning.EveStore(Path(__file__).resolve().parents[2] / "data" / "planning" / "eve")


if __name__ == "__main__":
    main()
