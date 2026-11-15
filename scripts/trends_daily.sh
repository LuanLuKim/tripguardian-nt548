#!/bin/bash
# usage: scripts/trends_daily.sh [city] — the nightly crawl behind Nhịp Đà Lạt (docs/CORPUS.md §Nhịp, crawl định kỳ), then
# the bulletin: this month's and next month's events from the web (corpus events), the TikTok place pages listed again
# (tiktok poi_refresh, tiktok.poi_refresh_per_run places, logged out, no download), the Maps reviews posted since
# (gmaps refresh, in the signed-in login window when it is open), then pulse. A failed step is logged
# and the next one still runs: the bulletin is rebuilt from whatever is there. Log: logs/trends_daily.log. Cron:
#   0 4 * * *  <repo>/scripts/trends_daily.sh dalat   # tripguardian-trends
cd "$(dirname "$0")/.." || exit 1
mkdir -p logs
city=${1:-dalat}
log=logs/trends_daily.log
export PYTHONPATH=src PLAYWRIGHT_BROWSERS_PATH=$PWD/.cache/ms-playwright CORPUS_BROWSER_CHANNEL=chromium
exec 9> logs/trends_daily.lock
flock -n 9 || { echo "$(date -u +%FT%TZ) already running" >> "$log"; exit 0; }
step() {
  echo "$(date -u +%FT%TZ) start $*" >> "$log"
  timeout 2h .venv/bin/python -m corpus "$@" >> "$log" 2>&1 < /dev/null
  echo "$(date -u +%FT%TZ) end $1 $2 exit $?" >> "$log"
}
step events --city "$city"
step tiktok poi_refresh --city "$city"
# Maps reviews since the last night, inside the signed-in login window (`corpus login gmaps --profile gmaps_e` with
# CORPUS_DEBUG_PORT=9530): Google ends a session whose cookies move to another browser, so no window = no refresh
login=http://127.0.0.1:${GMAPS_LOGIN_PORT:-9530}
if curl -s -m 3 "$login/json/version" > /dev/null; then
  CORPUS_ATTACH_URL=$login CORPUS_PROFILE_STATE=1 step gmaps refresh --city "$city"
else
  echo "$(date -u +%FT%TZ) skip gmaps refresh: no login window at $login" >> "$log"
fi
scripts/pulse_daily.sh "$city" --once
echo "$(date -u +%FT%TZ) done" >> "$log"
