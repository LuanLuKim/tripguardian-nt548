#!/usr/bin/env bash
# Local render dependencies; only PID-file-owned processes are stopped.
set -euo pipefail
STACK_CODE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
PY="$STACK_CODE/../../.venv/bin/python"
eval "$(PYTHONPATH="$STACK_CODE" "$PY" -c 'import shlex; from paths import CODE, DATA, REPO; print("\n".join(f"{k}={shlex.quote(str(v))}" for k,v in dict(CODE=CODE,DATA=DATA,REPO=REPO).items()))')"
# The store itself: other sessions sometimes remove or re-point the repo's .cache symlink.
CACHE="$REPO/../tripguardian-store/cache"; [[ -d "$CACHE/codex" ]] || CACHE="$REPO/.cache"
export DIORAMA_DATA="$DATA" PLAYWRIGHT_BROWSERS_PATH="$CACHE/ms-playwright"
RUN="$DATA/run"

live() {
    local pid start actual
    [[ -f "$1" ]] || return 1
    read -r pid start < "$1" || return 1
    [[ "$pid" =~ ^[0-9]+$ && "$start" =~ ^[0-9]+$ ]] || return 1
    [[ -r "/proc/$pid/stat" ]] || return 1
    actual=$(awk '{print $22}' "/proc/$pid/stat")
    [[ "$actual" == "$start" ]] && kill -0 "$pid" 2>/dev/null &&
        [[ $(ps -o stat= -p "$pid") != *Z* ]]
}

port_open() {
    "$PY" -c 'import socket,sys; s=socket.socket(); s.settimeout(1); sys.exit(s.connect_ex(("127.0.0.1",int(sys.argv[1]))) != 0)' "$1" 2>/dev/null
}

start() {
    local name=$1 pid
    shift
    live "$RUN/$name.pid" && return 0
    setsid nohup "$@" > "$DATA/logs/$name.log" 2>&1 < /dev/null &
    pid=$!
    printf '%s %s\n' "$pid" "$(awk '{print $22}' "/proc/$pid/stat")" > "$RUN/$name.pid"
}

status() {
    local missing=0 count=0 n
    report() {
        if [[ "$1" == 0 ]]; then echo "ok $2"; else echo "MISSING $2"; missing=1; fi
    }
    for n in 1 2 3; do
        if live "$RUN/bridge_$n.pid"; then count=$((count + 1)); fi
    done
    report "$((count != 3))" "bridge workers $count/3"
    for n in 8471 8472; do
        if port_open "$n"; then report 0 "port $n"; else report 1 "port $n"; fi
    done
    if curl -fsS -m 5 http://127.0.0.1:20128/v1/models 2>/dev/null |
        "$PY" -c 'import json,sys; json.load(sys.stdin)' 2>/dev/null; then
        report 0 9router
    else report 1 9router; fi
    if ps -eo stat,args | awk '$1~/D/' | grep -E 'mount|bwrap' >/dev/null; then
        report 1 'sandbox health'
    else report 0 'sandbox health'; fi
    if [[ -e "$CACHE/codex/node_modules/.bin/codex" ]]; then report 0 codex; else report 1 codex; fi
    if compgen -G "$CACHE/ms-playwright/chromium-*/chrome-linux*/chrome" >/dev/null; then
        report 0 'Playwright chromium'
    else report 1 'Playwright chromium'; fi
    return "$missing"
}

case "${1:-}" in
    up)
        mkdir -p "$RUN" "$DATA/logs"
        for n in 1 2 3; do start "bridge_$n" "$PY" "$CODE/bridge/serve.py"; done
        if ! port_open 8471; then start http_8471 "$PY" -m http.server 8471 --bind 127.0.0.1 -d "$DATA"; fi
        if ! port_open 8472; then start http_8472 "$PY" -m http.server 8472 --bind 127.0.0.1 -d "$REPO/web/public"; fi
        for n in {1..20}; do
            if port_open 8471 && port_open 8472; then break; fi
            sleep 0.2
        done
        ;;
    status) status ;;
    down)
        for name in bridge_1 bridge_2 bridge_3 http_8471 http_8472; do
            file="$RUN/$name.pid"
            if live "$file"; then
                read -r pid _ < "$file"
                kill -- "-$pid" 2>/dev/null || kill "$pid" 2>/dev/null || true
                echo "stopped $name ($pid)"
            fi
            if [[ -f "$file" ]]; then rm -- "$file"; fi
        done
        ;;
    *) echo "Usage: $0 up|status|down" >&2; exit 2 ;;
esac
