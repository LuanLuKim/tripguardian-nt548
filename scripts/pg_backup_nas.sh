#!/bin/bash
# Nightly pg_dump of prod Postgres to the NAS (not the local root disk, not the NFS repo quota). Keeps the newest 14.
DIR=/AIClub_NAS/luanhh/tripguardian/pg-backup
LOG=/workingspace_aiclub/WorkingSpace/Personal/vannk/tripguardian/logs/pg_backup_nas.log
mkdir -p "$DIR"
out="$DIR/$(date +%Y%m%d-%H%M).sql.gz"
if docker exec tripguardian-pg pg_dump -U postgres tripguardian | gzip > "$out" && gzip -t "$out"; then
  echo "$(date -Is) ok $out $(stat -c %s "$out")" >> "$LOG"
  ls -1t "$DIR"/*.sql.gz | tail -n +15 | xargs -r rm -f
else
  echo "$(date -Is) FAILED $out" >> "$LOG"; rm -f "$out"
fi
