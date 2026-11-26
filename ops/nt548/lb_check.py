"""Client-side checks of the blue/green load balancer (docs/nt548/02-bluegreen-lb.md §Kiểm thử). Stdlib only.

    python ops/nt548/lb_check.py split --color green --expect 10 --tol 3      # 1000 new cookies, share on green
    python ops/nt548/lb_check.py sticky --n 100                               # one cookie always gets one color
    python ops/nt548/lb_check.py load --until /tmp/stop --out load.json       # background traffic while switching
    python ops/nt548/lb_check.py verify load.json --max-conn-errors 0 --max-5xx 0
    python ops/nt548/lb_check.py wait-color --color blue --timeout 60         # seconds until 100 % on blue

Every request carries a `tg_session` cookie, the sticky key of nginx; the color comes from the X-LB-Color header.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from collections import Counter
from pathlib import Path

URL = "http://127.0.0.1:8080"
PATHS = ("GET /", "GET /api/harness/nt548-version", "GET /api/harness/me", "POST /api/harness/journeys")


def request(url: str, path: str, cookie: str, method: str = "GET", timeout: float = 10.0) -> tuple[int, str]:
    """(status, color); status 0 means no HTTP answer (connection refused / reset / timeout)."""
    req = urllib.request.Request(url + path, method=method, data=b"{}" if method == "POST" else None,
                                 headers={"Cookie": f"tg_session={cookie}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            r.read()
            return r.status, r.headers.get("X-LB-Color", "")
    except urllib.error.HTTPError as e:
        e.read()
        return e.code, e.headers.get("X-LB-Color", "")
    except OSError:
        return 0, ""


def shares(url: str, n: int) -> Counter:
    return Counter(request(url, "/api/harness/nt548-version", uuid.uuid4().hex)[1] for _ in range(n))


def cmd_split(a) -> int:
    c = shares(a.url, a.n)
    pct = 100 * c[a.color] / a.n
    ok = abs(pct - a.expect) <= a.tol
    print(json.dumps({"n": a.n, "colors": dict(c), "pct_" + a.color: round(pct, 1), "expect": a.expect, "ok": ok}))
    return 0 if ok else 1


def cmd_sticky(a) -> int:
    bad = 0
    for _ in range(a.users):
        cookie = uuid.uuid4().hex
        seen = Counter(request(a.url, "/api/harness/nt548-version", cookie)[1] for _ in range(a.n))
        bad += len(seen) != 1
    print(json.dumps({"users": a.users, "requests_each": a.n, "users_on_two_colors": bad, "ok": bad == 0}))
    return 0 if bad == 0 else 1


def cmd_load(a) -> int:
    """Workers loop over PATHS with cookies from a fixed pool until --until exists or --seconds pass."""
    paths = [p.split(" ", 1) for p in (a.path or PATHS)]
    cookies = [uuid.uuid4().hex for _ in range(a.users)]
    stop_at = time.time() + a.seconds if a.seconds else None
    lock, rows = threading.Lock(), []

    def worker(k: int) -> None:
        rng = random.Random(k)
        while not ((a.until and Path(a.until).exists()) or (stop_at and time.time() >= stop_at)):
            method, path = rng.choice(paths)
            t0 = time.time()
            status, color = request(a.url, path, rng.choice(cookies), method)
            with lock:
                rows.append((t0, time.time() - t0, status, color, path))
            time.sleep(a.pause)

    threads = [threading.Thread(target=worker, args=(k,)) for k in range(a.workers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    out = summary(rows)
    Path(a.out).write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("requests", "conn_errors", "status", "colors")}))
    return 0


def summary(rows: list[tuple]) -> dict:
    lat = sorted(r[1] for r in rows if r[2])
    p = (lambda q: round(1000 * lat[min(len(lat) - 1, int(q * len(lat)))], 1)) if lat else (lambda q: None)
    return {
        "requests": len(rows),
        "conn_errors": sum(1 for r in rows if r[2] == 0),
        "status": dict(Counter(str(r[2]) for r in rows)),
        "colors": dict(Counter(r[3] or "-" for r in rows)),
        "p50_ms": p(0.5), "p95_ms": p(0.95),
        "seconds": round(rows[-1][0] - rows[0][0], 1) if rows else 0,
    }


def cmd_verify(a) -> int:
    s = json.loads(Path(a.file).read_text(encoding="utf-8"))
    n5xx = sum(v for k, v in s["status"].items() if k.startswith("5"))
    ok = s["requests"] > 0 and s["conn_errors"] <= a.max_conn_errors and n5xx <= a.max_5xx
    print(json.dumps({"requests": s["requests"], "conn_errors": s["conn_errors"], "5xx": n5xx, "ok": ok}))
    return 0 if ok else 1


def cmd_wait_color(a) -> int:
    t0 = time.time()
    while time.time() - t0 < a.timeout:
        c = shares(a.url, a.n)
        if c[a.color] == a.n:
            print(json.dumps({"color": a.color, "seconds": round(time.time() - t0, 2), "ok": True}))
            return 0
        time.sleep(0.2)
    print(json.dumps({"color": a.color, "seconds": None, "last": dict(c), "ok": False}))
    return 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default=URL)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("split")
    s.add_argument("--color", default="green")
    s.add_argument("--expect", type=float, required=True, help="expected %% on --color")
    s.add_argument("--tol", type=float, default=3.0)
    s.add_argument("--n", type=int, default=1000)
    s = sub.add_parser("sticky")
    s.add_argument("--users", type=int, default=20)
    s.add_argument("--n", type=int, default=100, help="requests per user")
    s = sub.add_parser("load")
    s.add_argument("--out", required=True)
    s.add_argument("--until", help="stop once this file exists")
    s.add_argument("--seconds", type=float)
    s.add_argument("--workers", type=int, default=8)
    s.add_argument("--users", type=int, default=200)
    s.add_argument("--pause", type=float, default=0.02)
    s.add_argument("--path", action="append", help='"METHOD /path", repeatable (default: a mix of web and API routes)')
    s = sub.add_parser("verify")
    s.add_argument("file")
    s.add_argument("--max-conn-errors", type=int, default=0)
    s.add_argument("--max-5xx", type=int, default=0)
    s = sub.add_parser("wait-color")
    s.add_argument("--color", required=True)
    s.add_argument("--timeout", type=float, default=60)
    s.add_argument("--n", type=int, default=50)
    a = ap.parse_args(argv)
    if a.cmd == "load" and not (a.until or a.seconds):
        ap.error("load needs --until or --seconds")
    a.url = a.url.rstrip("/")
    return {"split": cmd_split, "sticky": cmd_sticky, "load": cmd_load, "verify": cmd_verify,
            "wait-color": cmd_wait_color}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
