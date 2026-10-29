#!/usr/bin/env bash
# One-time OSRM setup for Planning's travel matrices (docs/PLANNING.md, Live Context).
# Needs docker. Data lands in ./osrm-data, which .gitignore excludes. OSRM_DETACH=1: run osrm-routed as the
# restarting container tripguardian-osrm instead of in the foreground.
set -euo pipefail

# Git Bash on Windows rewrites arguments that start with / (-p /opt/car.lua, /data/...) into Windows paths.
export MSYS_NO_PATHCONV=1

DIR="${1:-osrm-data}"
PBF_URL="https://download.geofabrik.de/asia/vietnam-latest.osm.pbf"
IMAGE="ghcr.io/project-osrm/osrm-backend:latest"

mkdir -p "$DIR"
cd "$DIR"
HOST_DIR="$(pwd -W 2>/dev/null || pwd)"  # Docker Desktop wants a Windows path for -v under Git Bash

if [ ! -f vietnam-latest.osm.pbf ]; then
  echo "downloading $PBF_URL"
  curl -fL -o vietnam-latest.osm.pbf.part "$PBF_URL"  # --fail + .part: an error page or half a file never looks complete
  mv vietnam-latest.osm.pbf.part vietnam-latest.osm.pbf
fi

if [ ! -f vietnam-latest.osrm.mldgr ]; then
  docker run --rm -t -v "$HOST_DIR:/data" "$IMAGE" \
    osrm-extract -p /opt/car.lua /data/vietnam-latest.osm.pbf
  docker run --rm -t -v "$HOST_DIR:/data" "$IMAGE" \
    osrm-partition /data/vietnam-latest.osrm
  docker run --rm -t -v "$HOST_DIR:/data" "$IMAGE" \
    osrm-customize /data/vietnam-latest.osrm
fi

if [ "${OSRM_DETACH:-0}" = "1" ]; then  # server: a named container that comes back after a reboot
  docker rm -f tripguardian-osrm >/dev/null 2>&1 || true
  docker run -d --name tripguardian-osrm --restart unless-stopped -p 127.0.0.1:5000:5000 -v "$HOST_DIR:/data" "$IMAGE" \
    osrm-routed --algorithm mld --max-table-size 300 /data/vietnam-latest.osrm
  echo "osrm-routed started in container tripguardian-osrm on 127.0.0.1:5000"
  exit 0
fi
echo "starting osrm-routed on 127.0.0.1:5000 (ctrl-c to stop)"
docker run --rm -t -p 127.0.0.1:5000:5000 -v "$HOST_DIR:/data" "$IMAGE" \
  osrm-routed --algorithm mld --max-table-size 300 /data/vietnam-latest.osrm
