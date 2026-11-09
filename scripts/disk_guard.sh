#!/bin/bash
# Warn when the disk that holds the prod Postgres volume (the Docker data root) runs low. Cron: every 10 minutes.
# 2026-11-03 23:52 the root disk hit 100% and Postgres crashed (PANIC on WAL write).
ROOT=$(cd "$(dirname "$0")/.." && pwd)  # repo root, so the script survives a move of the checkout
mkdir -p "$ROOT/logs"
LOG=$ROOT/logs/disk_guard.log
DISK=$(docker info -f '{{.DockerRootDir}}' 2>/dev/null); [ -d "$DISK" ] || DISK=/
free_kb=$(df -Pk "$DISK" | awk 'NR==2 {print $4}')
if [ "$free_kb" -lt 5242880 ]; then
  echo "$(date -Is) LOW disk $DISK: $((free_kb / 1024)) MiB free (< 5 GiB). Postgres tripguardian-pg is at risk." >> "$LOG"
  docker exec tripguardian-pg psql -U postgres -c CHECKPOINT >/dev/null 2>&1  # flush WAL while there is still room
fi
