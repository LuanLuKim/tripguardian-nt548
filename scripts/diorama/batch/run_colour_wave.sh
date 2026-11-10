#!/usr/bin/env bash
# run_colour_wave.sh <commands.txt> [parallel=5]: run the colour-pass agent commands (one per line, printed by
# make_colour_brief.py) from the repo root, at most N at once (the render bridge has 3 workers).
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA="$("$HERE/../../../.venv/bin/python" -c 'import sys; sys.path.insert(0, sys.argv[1]); from paths import DATA; print(DATA)' "$HERE/..")"
case "$1" in
  /*) COMMANDS="$1" ;;
  *) COMMANDS="$DATA/$1" ;;
esac
cd "$HERE/../../.."
xargs -P "${2:-5}" -I{} -d '\n' bash -c '{}' < "$COMMANDS"
echo WAVE_DONE
