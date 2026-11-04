#!/bin/bash
# Warn when the local root disk (prod Postgres volume lives there) runs low. Cron: every 10 minutes.
# 2026-11-03 23:52 the root disk hit 100% and Postgres crashed (PANIC on WAL write).
LOG=/workingspace_aiclub/WorkingSpace/Personal/vannk/tripguardian/logs/disk_guard.log
free_kb=$(df -Pk / | awk 'NR==2 {print $4}')
if [ "$free_kb" -lt 5242880 ]; then
  echo "$(date -Is) LOW root disk: $((free_kb / 1024)) MiB free (< 5 GiB). Postgres tripguardian-pg is at risk." >> "$LOG"
  docker exec tripguardian-pg psql -U postgres -c CHECKPOINT >/dev/null 2>&1  # flush WAL while there is still room
fi
