#!/usr/bin/env bash
# run_agent.sh <sol|terra|full model slug> <brief.md> <run.log> <effort> [image ...]: Codex CLI subagent through 9router,
# service_tier priority (owner 2026-11-03), workspace-write sandbox. Extra args = images attached (visual review).
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
DATA="${DIORAMA_DATA:-$REPO/../tripguardian-store/splat/diorama}"
get() { grep -E "^$1=" "$REPO/.env" | tail -1 | cut -d= -f2- | sed -e 's/^["'\'']//' -e 's/["'\'']$//'; }
export JUDGE_API_KEY="$(get 9ROUTER_API_KEY)"
BASE="$(get 9ROUTER_API_URL)"
# A bare name (sol, terra) means cx/gpt-6.1-<name>; a full slug (cx/gpt-6-astra) is used as given.
case "$1" in */*) MODEL="$1" ;; *) MODEL="cx/gpt-6.1-$1" ;; esac; BRIEF="$2"; LOG="$3"; EFFORT="$4"; shift 4
IMGS=(); for i in "$@"; do IMGS+=(-i "$i"); done
# Prefer the store itself: other sessions sometimes remove or re-point the repo's .cache symlink.
CACHE="$REPO/../tripguardian-store/cache"; [ -d "$CACHE/codex" ] || CACHE="$REPO/.cache"
PATH=/home/vannk/node/bin:$PATH "$CACHE/codex/node_modules/.bin/codex" exec \
  -c model_provider='"nine"' \
  -c model_providers.nine.name='"9router"' \
  -c "model_providers.nine.base_url=\"$BASE\"" \
  -c model_providers.nine.env_key='"JUDGE_API_KEY"' \
  -c model_providers.nine.wire_api='"responses"' \
  -c 'model_providers.nine.http_headers={"User-Agent"="curl/8.5.0"}' \
  -c service_tier='"fast"' -c "model_catalog_json=\"$HERE/models.json\"" \
  -c 'plugins."superpowers@personal".enabled=false' \
  -m "$MODEL" -c "model_reasoning_effort=\"$EFFORT\"" -c approval_policy='"never"' \
  -s workspace-write --add-dir "$DATA" -C "$REPO" ${IMGS[@]+"${IMGS[@]}"} - < "$BRIEF" > "$LOG" 2>&1
