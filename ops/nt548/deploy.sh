#!/usr/bin/env bash
# Blue/green on one machine (docs/nt548/02-bluegreen-lb.md): two colors of app.yml behind nginx (ops/nt548/lb).
#
#   deploy.sh up <color> <tag> [replicas]   start / update a color (replica i on host port base + 10*(i-1))
#   deploy.sh lb                            start nginx; all traffic to the active color
#   deploy.sh weight <pct>                  pct % of users to the new color (the one that is not active)
#   deploy.sh promote                       the new color takes 100 % and becomes active
#   deploy.sh rollback                      0 % to the new color: everyone back on the active one
#   deploy.sh status                        active color, weight, tag and health of each replica (JSON)
#   deploy.sh down [color]                  stop a color, or everything
#
# Ports: blue 8081, green 8082 (+10 per extra replica); nginx on LB_PORT (8080). State (weight, active color, nginx
# includes, access log) in NT548_STATE (default ops/nt548/state). Extra compose files for app.yml: APP_COMPOSE_EXTRA
# (e.g. "-f ops/nt548/compose/app.build.yml"). Every other variable of app.yml (NT548_FAULT, FAKE_V1_ERROR_RATE, ...)
# is passed through by `up`.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
STATE=${NT548_STATE:-$ROOT/ops/nt548/state}
mkdir -p "$STATE/nginx" "$STATE/log"
STATE=$(cd "$STATE" && pwd)
export NT548_STATE=$STATE
LB="docker compose -f $ROOT/ops/nt548/lb/lb.yml"
APP_FILES="-f $ROOT/ops/nt548/compose/app.yml ${APP_COMPOSE_EXTRA:-}"

die() { echo "deploy.sh: $*" >&2; exit 2; }
base_port() { case $1 in blue) echo 8081 ;; green) echo 8082 ;; *) die "color must be blue or green, got '$1'" ;; esac; }
other() { [ "$1" = blue ] && echo green || echo blue; }
get() { cat "$STATE/$1" 2>/dev/null || echo "$2"; }
active() { get active blue; }
replicas() { get "$1.replicas" 0; }
project() { [ "$2" = 1 ] && echo "tg-$1" || echo "tg-$1-$2"; }

write_upstreams() {
  local out="" c i n port
  for c in blue green; do
    n=$(replicas "$c")
    out+="upstream $c {\n    hash \$split_key consistent;\n"
    if [ "$n" -eq 0 ]; then
      out+="    server 127.0.0.1:9 down;   # not started\n"
    else
      for i in $(seq "$n"); do
        port=$(( $(base_port "$c") + 10 * (i - 1) ))
        out+="    server host.docker.internal:$port max_fails=2 fail_timeout=5s;\n"
      done
    fi
    out+="    keepalive 16;\n}\n"
  done
  printf "%b" "$out" > "$STATE/nginx/upstreams.conf"
}

write_split() {
  local pct=$1 act new
  act=$(active); new=$(other "$act")
  {
    echo "split_clients \"\$split_key\" \$color {"
    if [ "$pct" -ge 100 ]; then echo "    * $new;"
    elif [ "$pct" -le 0 ]; then echo "    * $act;"
    else echo "    $pct% $new;"; echo "    * $act;"; fi
    echo "}"
  } > "$STATE/nginx/split.conf"
  echo "$pct" > "$STATE/weight"
}

reload() {
  if [ -n "$($LB ps -q nginx 2>/dev/null)" ]; then
    $LB exec -T nginx nginx -t -q
    $LB exec -T nginx nginx -s reload
  fi
}

cmd=${1:-status}; shift || true
case $cmd in
  up)
    color=${1:?usage: up <color> <tag> [replicas]}; tag=${2:?usage: up <color> <tag> [replicas]}; n=${3:-1}
    port=$(base_port "$color")
    for i in $(seq "$n"); do
      COLOR=$color IMAGE_TAG=$tag HOST_PORT=$(( port + 10 * (i - 1) )) \
        docker compose -p "$(project "$color" "$i")" $APP_FILES up -d --wait --wait-timeout 180
    done
    old=$(replicas "$color")   # fewer replicas than before: stop the extra ones
    for i in $(seq $(( n + 1 )) "$old"); do docker compose -p "$(project "$color" "$i")" $APP_FILES down -v; done
    echo "$tag" > "$STATE/$color.tag"; echo "$n" > "$STATE/$color.replicas"
    write_upstreams; [ -f "$STATE/nginx/split.conf" ] || write_split 0
    reload
    echo "up $color $tag x$n"
    ;;
  lb)
    write_upstreams; [ -f "$STATE/nginx/split.conf" ] || write_split 0
    touch "$STATE/log/access.log"
    $LB up -d --wait --wait-timeout 60
    echo "lb on :${LB_PORT:-8080}, active $(active)"
    ;;
  weight)
    pct=${1:?usage: weight <pct>}; [[ $pct =~ ^[0-9]+$ ]] && [ "$pct" -le 100 ] || die "weight is 0..100, got '$pct'"
    [ "$pct" -eq 0 ] || [ "$(replicas "$(other "$(active)")")" -gt 0 ] || die "the new color $(other "$(active)") is not up"
    write_split "$pct"; reload
    echo "weight $pct% -> $(other "$(active)")"
    ;;
  promote)
    new=$(other "$(active)")
    [ "$(replicas "$new")" -gt 0 ] || die "the new color $new is not up"
    echo "$new" > "$STATE/active"; write_split 0; reload   # 0 % to the old one: all on $new
    echo "promoted $new"
    ;;
  rollback)
    start=$(date +%s.%N); write_split 0; reload
    echo "rolled back to $(active) in $(awk "BEGIN{printf \"%.2f\", $(date +%s.%N) - $start}") s"
    ;;
  status)
    act=$(active)
    printf '{"active":"%s","weight_to_new":%s,"colors":{' "$act" "$(get weight 0)"
    sep=""
    for c in blue green; do
      n=$(replicas "$c"); codes=()
      for i in $(seq "$n"); do
        codes+=("\"$(curl -s -o /dev/null -m 3 -w '%{http_code}' "http://127.0.0.1:$(( $(base_port "$c") + 10 * (i - 1) ))/" || true)\"")
      done
      health="[$(IFS=,; echo "${codes[*]:-}")]"
      printf '%s"%s":{"tag":"%s","replicas":%s,"http":%s}' "$sep" "$c" "$(get "$c.tag" "")" "$n" "$health"; sep=","
    done
    echo "}}"
    ;;
  down)
    colors=${1:-blue green}
    for c in $colors; do
      for i in $(seq "$(replicas "$c")"); do docker compose -p "$(project "$c" "$i")" $APP_FILES down -v; done
      echo 0 > "$STATE/$c.replicas"
    done
    if [ -z "${1:-}" ]; then $LB down -v; else write_upstreams; reload; fi
    ;;
  *) die "unknown command '$cmd' (up, lb, weight, promote, rollback, status, down)" ;;
esac
