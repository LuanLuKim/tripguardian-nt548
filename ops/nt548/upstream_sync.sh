#!/usr/bin/env bash
# Merge TripGuardian's main into a sync branch of the fork (#7, docs/nt548/07-sync-report.md).
#
#   ops/nt548/upstream_sync.sh [<upstream url>] [<upstream branch>]
#
# Runs in a clean checkout of the fork's main (nt548-upstream-sync.yml). It only changes the local repository: the
# workflow pushes the branch and opens the PR, or opens an issue on a conflict.
# Prints key=value lines (also appended to $GITHUB_OUTPUT when set):
#   status=up-to-date                      upstream has nothing the fork lacks
#   status=merged branch=<b> commits=<n>   <b> holds a --no-ff merge of <n> new upstream commits
#   status=conflict commits=<n> files=<f>  merge aborted; <f> = conflicting files, space separated
#   upstream=<short sha>
# Environment: SYNC_DATE (default today, UTC) names the branch nt548/sync-<date>.
set -euo pipefail

URL=${1:-https://github.com/hohoangluan/tripguardian.git}
REF=${2:-main}
DATE=${SYNC_DATE:-$(date -u +%F)}
BRANCH=nt548/sync-$DATE

out() { echo "$1"; [ -z "${GITHUB_OUTPUT:-}" ] || echo "$1" >> "$GITHUB_OUTPUT"; }

git fetch --quiet --no-tags "$URL" "$REF"
up=$(git rev-parse FETCH_HEAD)
out "upstream=$(git rev-parse --short "$up")"
if git merge-base --is-ancestor "$up" HEAD; then
  out "status=up-to-date"
  exit 0
fi
n=$(git rev-list --count "HEAD..$up")

git switch --quiet -C "$BRANCH"
if git merge --quiet --no-ff --no-edit -m "chore(nt548): sync TripGuardian $REF at $(git rev-parse --short "$up") ($n commits)" "$up" >/dev/null 2>&1; then
  out "status=merged"
  out "branch=$BRANCH"
  out "commits=$n"
else
  files=$(git diff --name-only --diff-filter=U | tr '\n' ' ' | sed 's/ $//')
  git merge --abort
  out "status=conflict"
  out "commits=$n"
  out "files=$files"
fi
