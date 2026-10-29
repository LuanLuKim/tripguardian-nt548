"""python -m notify run [--once]: plan, check the forecast and send due notifications every minute (Asia/Ho_Chi_Minh)."""

import argparse
from pathlib import Path

from dotenv import load_dotenv

from corpus.serving import load as serving_records
from db import pool

from . import Notify


def main():
    parser = argparse.ArgumentParser(prog="python -m notify")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument("--once", action="store_true", help="one tick, then exit")
    args = parser.parse_args()
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    import live
    cfg = live.load_settings()
    records = serving_records()
    Notify(pool(), records, weather=lambda lat, lng, dates: live.weather(lat, lng, dates, cfg),
           eve=_eve(records, cfg), expert=_expert(records, cfg)).run(args.once)


def _eve(records, live_cfg):
    """The D.3 evening check; None while config/planning.yaml eve_replan.enabled is false."""
    import planning
    return planning.eve_runner(records, live_cfg, Path(__file__).resolve().parents[2] / "data" / "planning" / "eve")

def _expert(records, live_cfg):
    """The D.2 Local Expert pass after a confirm; None while config/planning.yaml expert.enabled is false."""
    import planning
    return planning.expert_runner(records, live_cfg, Path(__file__).resolve().parents[2] / "data" / "planning" / "eve")


if __name__ == "__main__":
    main()
