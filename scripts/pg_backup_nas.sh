#!/bin/bash
# Nightly pg_dump of prod Postgres to the NAS (not the local root disk, not the NFS repo quota). Keeps the newest 14.
ROOT=$(cd "$(dirname "$0")/.." && pwd)  # repo root, so the script survives a move of the checkout
DIR=${PG_BACKUP_DIR:-/data/work/luanhh/nas/tripguardian/pg-backup}  # /AIClub_NAS symlinks are removed 2026-11-12
LOG=$ROOT/logs/pg_backup_nas.log
mkdir -p "$DIR" "$ROOT/logs"
out="$DIR/$(date +%Y%m%d-%H%M).sql.gz"
if docker exec tripguardian-pg pg_dump -U postgres tripguardian | gzip > "$out" && gzip -t "$out"; then
  echo "$(date -Is) ok $out $(stat -c %s "$out")" >> "$LOG"
  ls -1t "$DIR"/*.sql.gz | tail -n +15 | xargs -r rm -f
else
  echo "$(date -Is) FAILED $out" >> "$LOG"; rm -f "$out"
fi
