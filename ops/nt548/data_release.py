"""Switch and roll back a corpus data release per color, and check what a running harness serves (T5.4, #11).

  stage <data dir> --release <sample dir>... --current <sample dir>
      Build one color's DATA_DIR: copy the release of every --release (a make.py output dir such as
      ops/nt548/sample-data/r-a), then point releases/current at --current through corpus.releases.publish (which
      validates hashes first). Running it again with another --current is the data switch; with the old one, the
      rollback. Keeping the old release next to the new one lets journeys pinned to it still open.

  smoke <harness url> --expect <sample dir> [--not <sample dir>] [--cookies FILE]
        [--create-journey FILE | --open-journey FILE --want 200|409]
      Sign in as a guest (the cookie is kept in FILE, so later calls are the same guest), search each served place
      of --expect by name and require it to come back; search the places only --not has and require them absent.
      --create-journey saves a new journey id (pinned to the release the harness serves); --open-journey opens a saved
      one and requires the HTTP status --want (409 = stale_data_version: its release is not mounted).

Exit 0 = as expected, 1 = not. Stdlib + corpus' public API only.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import urllib.error
import urllib.parse
import urllib.request
from http.cookiejar import MozillaCookieJar
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))


def release_of(sample: Path) -> Path:
    """The release a make.py output dir (or any DATA_DIR) points at."""
    pointer = sample / "releases" / "current"
    return sample / "releases" / pointer.read_text(encoding="utf-8").strip()


def served(sample: Path) -> dict[str, str]:
    """id -> name of every served place of the release sample points at (read through corpus.snapshot)."""
    from corpus.serving import SERVED
    from corpus.snapshot import Snapshot
    release = release_of(sample)
    city = json.loads((release / "manifest.json").read_text(encoding="utf-8"))["city"]
    return {r["id"]: r["identity"]["name"] for r in Snapshot.open(release / "snapshot").region(city).records()
            if r.get("status") in SERVED}


def stage(data: Path, releases: list[Path], current: Path) -> str:
    from corpus.releases import publish
    (data / "releases").mkdir(parents=True, exist_ok=True)
    for sample in {*releases, current}:
        source = release_of(sample)
        target = data / "releases" / source.name
        if not target.exists():
            shutil.copytree(source, target)
    release_id = release_of(current).name
    publish(release_id, data)  # validates every artifact hash, then swaps the pointer atomically
    print(f"{data}: releases {sorted(p.name for p in (data / 'releases').iterdir() if p.is_dir())}, current {release_id}")
    return release_id


class Client:
    def __init__(self, base: str, cookies: Path | None):
        self.base = base.rstrip("/")
        self.jar = MozillaCookieJar(str(cookies)) if cookies else MozillaCookieJar()
        if cookies and cookies.exists():
            self.jar.load(ignore_discard=True)
        self.cookies = cookies
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))

    def call(self, method: str, path: str, body: dict | None = None) -> tuple[int, object]:
        data = json.dumps(body).encode() if body is not None else (b"{}" if method == "POST" else None)
        req = urllib.request.Request(self.base + path, data=data, method=method, headers={
            "Origin": self.base, "Content-Type": "application/json", "X-TG-Synthetic": "smoke"})
        try:
            with self.opener.open(req, timeout=60) as r:
                status, raw = r.status, r.read()
        except urllib.error.HTTPError as exc:
            status, raw = exc.code, exc.read()
        if self.cookies:
            self.jar.save(ignore_discard=True)
        try:
            return status, json.loads(raw)
        except ValueError:
            return status, raw[:200]

    def signed_in(self) -> None:
        if self.call("GET", "/api/harness/me")[0] != 200:
            status, body = self.call("POST", "/api/auth/guest")
            if status != 200:
                raise SystemExit(f"guest sign-in failed: {status} {body}")


def smoke(args) -> int:
    client = Client(args.url, args.cookies)
    client.signed_in()
    failures = []
    expect = served(args.expect)
    only_other = {pid: name for pid, name in served(args.other).items() if pid not in expect} if args.other else {}
    for pid, name in expect.items():
        status, hits = client.call("GET", "/api/harness/places?q=" + urllib.parse.quote(name))
        if status != 200 or pid not in {h.get("id") for h in hits}:
            failures.append(f"{pid} {name!r}: expected, got {status} {str(hits)[:120]}")
    for pid, name in only_other.items():
        status, hits = client.call("GET", "/api/harness/places?q=" + urllib.parse.quote(name))
        if status != 200 or pid in {h.get("id") for h in hits}:
            failures.append(f"{pid} {name!r}: belongs to {release_of(args.other).name} only, but served ({status})")
    print(f"places: {len(expect)} expected from {release_of(args.expect).name}, {len(only_other)} must be absent")
    if args.create_journey:
        status, view = client.call("POST", "/api/harness/sessions", {})
        if status != 200 or "id" not in view:
            failures.append(f"create journey: {status} {str(view)[:200]}")
        else:
            args.create_journey.write_text(view["id"], encoding="utf-8")
            print(f"journey {view['id']} created")
    if args.open_journey:
        jid = args.open_journey.read_text(encoding="utf-8").strip()
        status, body = client.call("GET", f"/api/harness/sessions/{jid}")
        error = body.get("error") if isinstance(body, dict) else None
        print(f"journey {jid}: {status} {error or ''}")
        if status != args.want or (args.want == 409 and error != "stale_data_version"):
            failures.append(f"open journey {jid}: wanted {args.want}, got {status} {str(body)[:200]}")
    for line in failures:
        print("FAIL " + line)
    print("smoke " + ("FAIL" if failures else "PASS") + f": {args.url}")
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    st = sub.add_parser("stage")
    st.add_argument("data", type=Path)
    st.add_argument("--release", type=Path, action="append", default=[])
    st.add_argument("--current", type=Path, required=True)
    sm = sub.add_parser("smoke")
    sm.add_argument("url")
    sm.add_argument("--expect", type=Path, required=True)
    sm.add_argument("--not", dest="other", type=Path)
    sm.add_argument("--cookies", type=Path)
    sm.add_argument("--create-journey", type=Path)
    sm.add_argument("--open-journey", type=Path)
    sm.add_argument("--want", type=int, default=200)
    args = parser.parse_args(argv)
    if args.command == "stage":
        stage(args.data, args.release, args.current)
        return 0
    return smoke(args)


if __name__ == "__main__":
    sys.exit(main())
