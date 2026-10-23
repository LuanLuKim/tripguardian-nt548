#!/usr/bin/env python3
"""Probe the public app through Cloudflare; run once per minute from Linux cron."""
import argparse
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import subprocess
import time
from urllib.parse import urlsplit


def check(base_url: str, path: str) -> dict:
    """Require the app shell or the backend's exact anonymous response."""
    command = [
        "curl", "--disable", "--silent", "--show-error", "--compressed",
        "--connect-timeout", "5", "--max-time", "15", "--max-filesize", "1048576",
        "--user-agent", "TripGuardian-Keepalive/1.0",
        "--header", "Cache-Control: no-cache", "--header", "Accept: */*",
        "--write-out", "\n%{http_code}\n%{time_total}",
        f"{base_url.rstrip('/')}{path}?tg_keepalive={time.time_ns()}",
    ]
    result = {"path": path, "ok": False}
    try:
        response = subprocess.run(command, capture_output=True, text=True, timeout=20,
                                  env={**os.environ, "LC_ALL": "C"})
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {**result, "error": type(exc).__name__}
    if response.returncode:
        return {**result, "curl_exit": response.returncode}
    try:
        body, status, elapsed = response.stdout.rsplit("\n", 2)
        result.update(status=int(status), seconds=float(elapsed))
        if path == "/app":
            result["ok"] = result["status"] == 200 and 'id="root"' in body
        else:
            result["ok"] = result["status"] == 401 and json.loads(body) == {"error": "sign in first"}
    except (ValueError, TypeError):
        result["error"] = "unexpected response"
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True, help="Public HTTPS origin, without a path")
    parser.add_argument("--log-file", type=Path,
                        default=Path(__file__).resolve().parents[1] / "logs/run/keepalive.log")
    args = parser.parse_args()
    origin = urlsplit(args.base_url)
    if (origin.scheme != "https" or not origin.hostname or origin.username or origin.password
            or origin.path not in ("", "/") or origin.query or origin.fragment):
        parser.error("--base-url must be an HTTPS origin without credentials, path, query or fragment")

    # Cron is Linux-only; keeping the import here lets response tests run on Windows too.
    import fcntl

    args.log_file.parent.mkdir(parents=True, exist_ok=True)
    with args.log_file.with_suffix(".lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 0
        logger = logging.getLogger("tripguardian.keepalive")
        logger.setLevel(logging.INFO)
        handler = RotatingFileHandler(args.log_file, maxBytes=1048576, backupCount=2, encoding="utf-8")
        formatter = logging.Formatter("%(asctime)sZ %(message)s", "%Y-%m-%dT%H:%M:%S")
        formatter.converter = time.gmtime
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        try:
            checks = [check(args.base_url, path) for path in ("/app", "/api/harness/me")]
            healthy = all(item["ok"] for item in checks)
            report = {"ok": healthy, "origin": args.base_url.rstrip("/"), "checks": checks}
            logger.log(logging.INFO if healthy else logging.ERROR, json.dumps(report))
            print(json.dumps(report))
            return 0 if healthy else 1
        finally:
            logger.removeHandler(handler)
            handler.close()


if __name__ == "__main__":
    raise SystemExit(main())
