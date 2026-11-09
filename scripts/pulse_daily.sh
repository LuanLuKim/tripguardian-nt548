#!/bin/bash
# usage: scripts/pulse_daily.sh [city] [--once] — Nhịp Đà Lạt job every 24 h (docs/CORPUS.md §Nhịp). Reads data the crawls
# already left; it crawls nothing, so between crawls it only re-dates the same signals. Not left running: start it by hand,
# or use cron:
#   0 3 * * *  <repo>/scripts/pulse_daily.sh dalat --once
cd "$(dirname "$0")/.." || exit 1
mkdir -p logs
city=${1:-dalat}
while true; do
  PYTHONPATH=src .venv/bin/python -m corpus pulse --city "$city" >> logs/pulse_daily.log 2>&1 < /dev/null
  [ "$2" = "--once" ] && break
  sleep 86400
done
