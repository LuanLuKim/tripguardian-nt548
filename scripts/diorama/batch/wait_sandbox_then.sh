#!/usr/bin/env bash
# wait_sandbox_then.sh <max_minutes> <command...>: wait until a stuck NFS mount no longer blocks bwrap (Codex sandbox),
# then run the command detached. A hung mount (e.g. /run/nas-test, 2026-11-04) makes every `bwrap --ro-bind / /` hang in D state.
end=$(( $(date +%s) + $1 * 60 )); shift
test_pid=""
while [ "$(date +%s)" -lt "$end" ]; do
  if ! pgrep -f "mount.nfs4" >/dev/null; then
    if [ -z "$test_pid" ] || ! kill -0 "$test_pid" 2>/dev/null; then
      bwrap --unshare-user --ro-bind / / /bin/true & test_pid=$!
      sleep 20
      if ! kill -0 "$test_pid" 2>/dev/null && wait "$test_pid"; then
        setsid nohup "$@" > /dev/null 2>&1 &
        echo "SANDBOX OK $(date +%H:%M), launched"; exit 0
      fi
    fi
  fi
  sleep 120
done
echo "TIMEOUT $(date +%H:%M): sandbox still blocked"; exit 1
