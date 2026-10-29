"""python -m trip serve: the Trip Understanding API for the web (http://127.0.0.1:8766).
python -m trip drills: score the photo cards offline (config/trip.yaml drills) so the harness starts with them.
python -m trip profile-replay: replay eval of the long-term profile on synthetic personas (docs/TRIP_UNDERSTANDING.md §17).
python -m trip profile-audit: the Judge reads a sample of active profile entries and flags unfounded ones."""

import argparse
import os

from corpus.releases import resolve
from corpus.snapshot import shared
from dotenv import load_dotenv

from .agent import langchain_chat
from .api.engine import Engine
from .api.server import run
from .api.tools import senses
from .infrastructure.catalog import Catalog
from .infrastructure.clef import Judge
from .infrastructure.profile import ProfileStore
from .infrastructure.sessions import SessionStore
from .infrastructure.settings import ROOT, load


def main() -> None:
    ap = argparse.ArgumentParser(prog="python -m trip")
    sub = ap.add_subparsers(dest="cmd", required=True)
    serve = sub.add_parser("serve", help="run the API the web /app/understand screen talks to")
    serve.add_argument("--port", type=int, default=8766)
    sub.add_parser("drills", help="score every photo-card variant on the active corpus and save it")
    rp = sub.add_parser("profile-replay", help="replay eval of the profile invariants on synthetic personas")
    rp.add_argument("--out", default="data/bench/profile", help="report directory (profiles kept in <out>/profiles)")
    pa = sub.add_parser("profile-audit", help="the Judge checks a random sample of active profile entries")
    pa.add_argument("--dir", default=None, help="profile directory (default: config patterns.dir)")
    pa.add_argument("--sample", type=int, default=None, help="entries read (default: config patterns.audit_sample)")
    pa.add_argument("--log", default="data/trip/profile_audit.jsonl")
    pa.add_argument("--seed", type=int, default=None)
    args = ap.parse_args()

    load_dotenv(ROOT / ".env")
    if args.cmd in ("profile-replay", "profile-audit"):
        return _profile(args)
    if args.cmd == "drills":
        from .api.tools import create_engine, write_drill_scores
        engine = create_engine(ROOT / os.environ.get("DATA_DIR", "data"))
        print(f"saved {write_drill_scores(engine)}")
        return
    cfg = load()
    data = ROOT / os.environ.get("DATA_DIR", "data")
    data_root = resolve(data)
    catalog = Catalog.from_snapshot(shared(data_root / "snapshot").region(), cfg.n_min)
    engine = Engine(catalog, cfg, SessionStore(data / "trip" / "sessions"),
                    chat=langchain_chat(cfg), judge=Judge(cfg),
                    profiles=ProfileStore(ROOT / cfg.patterns.dir, cfg.patterns) if cfg.patterns.enabled else None,
                    **senses(cfg, catalog, data_root=data_root))
    agent = os.environ.get("AGENT_MODEL", "policy fallback")
    print(f"Trip Understanding: http://127.0.0.1:{args.port} ({len(catalog.places)} places, model {agent})")
    run(engine, args.port)


def _profile(args) -> None:
    import json
    import random
    from dataclasses import replace
    from datetime import date, datetime

    cfg = load()
    if args.cmd == "profile-audit":
        from .infrastructure.profile_audit import audit
        store = ProfileStore(ROOT / (args.dir or cfg.patterns.dir), cfg.patterns)
        out = audit(store, date.today(), n=args.sample or cfg.patterns.audit_sample, rng=random.Random(args.seed),
                    log_path=ROOT / args.log)
        print(json.dumps(out))
        return
    from .api.profile_replay import PERSONAS, replay
    data_root = resolve(ROOT / os.environ.get("DATA_DIR", "data"))
    catalog = Catalog.from_snapshot(shared(data_root / "snapshot").region(), cfg.n_min)
    out_dir = ROOT / args.out
    root = out_dir / "profiles"
    if root.exists():
        for f in root.glob("*.json"):
            f.unlink()
    report = replay(PERSONAS, cfg=replace(cfg.patterns, enabled=True), catalog=catalog, today=date.today(), root=root)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{datetime.now():%Y%m%d-%H%M%S}-replay.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(json.dumps({"ok": report["ok"], "metrics": report["metrics"],
                      "invariants": {k: f"{v['checked'] - v['failed']}/{v['checked']}" for k, v in report["invariants"].items()}},
                     ensure_ascii=False))
    print(f"saved {path}")


if __name__ == "__main__":
    main()
