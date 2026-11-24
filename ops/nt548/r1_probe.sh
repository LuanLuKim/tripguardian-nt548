#!/usr/bin/env bash
# R1 (T5.1, #8): what does `python -m harness serve` need to start and answer the basic read APIs?
#
# Runs the real harness twice against the same Postgres and prints what each answers:
#   empty   DATA_DIR is an empty dir
#   sample  DATA_DIR is one synthetic release from ops/nt548/sample-data/make.py (r-a)
# For each: seconds until it listens, then GET /api/harness/me, POST /api/auth/guest, GET /api/harness/places?q=...,
# and the first traceback in its log.
#
# Environment: DATABASE_URL (required; migrations are applied), PYTHON (python), PORT (18769), SAMPLE (default
# ops/nt548/sample-data, built when r-a is missing). Run it from a checkout without .env: the harness loads the
# repo's .env and would otherwise pick up real keys.
set -euo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../.." && pwd)
PYTHON=${PYTHON:-python}
PORT=${PORT:-18769}
SAMPLE=${SAMPLE:-$HERE/sample-data}
WORK=$(mktemp -d -t nt548-r1-XXXX)
: "${DATABASE_URL:?DATABASE_URL is required}"
export PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}" LANCEDB_LOG=${LANCEDB_LOG:-error}
[ -e "$ROOT/.env" ] && echo "[r1] warning: $ROOT/.env exists; the harness will load it"

[ -d "$SAMPLE/r-a" ] || "$PYTHON" "$HERE/sample-data/make.py" --out "$SAMPLE"
(cd "$ROOT" && "$PYTHON" -m db migrate)
mkdir -p "$WORK/empty"

probe() {  # probe <name> <data dir>
  local name=$1 data=$2 pid started
  started=$(date +%s.%N)
  DATA_DIR=$data "$PYTHON" -m harness serve --port "$PORT" > "$WORK/$name.log" 2>&1 &
  pid=$!
  for _ in $(seq 1 120); do
    "$PYTHON" -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:$PORT/api/auth/options', timeout=2)" 2>/dev/null && break
    kill -0 $pid 2>/dev/null || break
    sleep 0.5
  done
  echo "== $name (DATA_DIR=$data)"
  if ! kill -0 $pid 2>/dev/null; then
    echo "harness exited:"; tail -20 "$WORK/$name.log"; return 0
  fi
  echo "listening after $("$PYTHON" -c "print(round($(date +%s.%N) - $started, 1))") s"
  "$PYTHON" - "http://127.0.0.1:$PORT" <<'PY'
import json, sys, time, urllib.error, urllib.parse, urllib.request
from http.cookiejar import CookieJar
base = sys.argv[1]
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
def call(method, path):
    req = urllib.request.Request(base + path, method=method, data=b"{}" if method == "POST" else None,
                                 headers={"Origin": base, "Content-Type": "application/json"})
    t = time.monotonic()
    try:
        with opener.open(req, timeout=120) as r:
            status, raw = r.status, r.read()
    except urllib.error.HTTPError as e:
        status, raw = e.code, e.read()
    body = raw.decode("utf-8", "replace")
    print(f"{method} {path} -> {status} ({(time.monotonic() - t) * 1000:.0f} ms) {body[:140]}")
for method, path in (("GET", "/api/harness/me"), ("POST", "/api/auth/guest"),
                     ("GET", "/api/harness/places?q=" + urllib.parse.quote("Cà phê")),
                     ("GET", "/api/harness/places?q=" + urllib.parse.quote("Thác"))):
    call(method, path)
PY
  kill $pid; wait $pid 2>/dev/null || true
  local first
  first=$(grep -n -m1 -A0 "^[A-Za-z]*Error\|^[a-z.]*\.[A-Z][A-Za-z]*Error" "$WORK/$name.log" || true)
  echo "first error in log: ${first:-none}"
}

probe empty "$WORK/empty"
probe sample "$SAMPLE/r-a"
echo "logs: $WORK"
