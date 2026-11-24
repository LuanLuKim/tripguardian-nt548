"""Gate a corpus data release before any color serves it (T5.3, #10). Exit 0 = pass, 1 = refused, 2 = bad usage.

Checks, in order (thresholds in ops/nt548/data_check.yaml):
  manifest   manifest.json is there, names this release, lists artifacts
  hashes     every listed artifact exists and its sha256 matches
  release    corpus.releases.validate: snapshot and index cover exactly the manifest's eligible places
  schema     the snapshot opens through corpus.snapshot and every served record has the required fields
  coords     lat / lng are numbers inside the release city's area (config/cities.yaml)
  index      corpus.index covers every served place
  drop       against --baseline (the running release): places did not fall by more than max_place_drop

Reading goes through corpus' public API; this script never parses LanceDB itself. A check that cannot run because an
earlier one failed is reported as skipped, so one broken release gives one clear reason.

usage: python ops/nt548/data_check.py <release> [--baseline <release>] [--config data_check.yaml] [--json]
<release> is a release dir (has manifest.json) or a DATA_DIR whose releases/current names one.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
DEFAULT_CONFIG = Path(__file__).resolve().with_name("data_check.yaml")


def release_dir(path: Path) -> Path:
    """A release dir as is, or the release a DATA_DIR's releases/current names."""
    if (path / "manifest.json").is_file():
        return path
    pointer = path / "releases" / "current"
    if pointer.is_file():
        return path / "releases" / pointer.read_text(encoding="utf-8").strip()
    raise FileNotFoundError(f"{path}: no manifest.json and no releases/current")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _field(record: dict, dotted: str):
    value = record
    for key in dotted.split("."):
        value = value.get(key) if isinstance(value, dict) else None
    return value


def served_records(release: Path, city: str) -> list[dict]:
    from corpus.serving import SERVED
    from corpus.snapshot import Snapshot
    return [r for r in Snapshot.open(release / "snapshot").region(city).records() if r.get("status") in SERVED]


class Report:
    def __init__(self, release: Path):
        self.release, self.results, self.failed = release, [], False

    def add(self, check: str, ok: bool | None, reason: str = "") -> bool:
        self.results.append({"check": check, "status": {True: "pass", False: "fail", None: "skip"}[ok], "reason": reason})
        self.failed |= ok is False
        return bool(ok)

    def as_dict(self) -> dict:
        return {"release": str(self.release), "ok": not self.failed, "checks": self.results}


def check(path: Path, baseline: Path | None = None, config: dict | None = None) -> Report:
    """Run every check on the release at path; baseline is the running release (dir or DATA_DIR)."""
    config = config or yaml.safe_load(DEFAULT_CONFIG.read_text(encoding="utf-8"))
    try:
        release = release_dir(path)
    except FileNotFoundError as exc:
        report = Report(path)
        report.add("manifest", False, str(exc))
        return report
    report = Report(release)
    names = ("hashes", "release", "schema", "coords", "index", "drop")

    def skip_rest(after: str) -> Report:
        for name in names[names.index(after) + 1:] if after in names else names:
            report.add(name, None, f"skipped: {after} failed")
        return report

    try:
        manifest = json.loads((release / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        report.add("manifest", False, f"unreadable manifest.json: {exc}")
        return skip_rest("manifest")
    problems = [p for p, bad in ((f"release_id {manifest.get('release_id')!r} is not the dir name {release.name!r}",
                                  manifest.get("release_id") != release.name),
                                 ("no artifacts listed", not manifest.get("artifacts")),
                                 ("no city", not manifest.get("city"))) if bad]
    if not report.add("manifest", not problems, "; ".join(problems)):
        return skip_rest("manifest")

    bad = []
    for item in manifest["artifacts"]:
        artifact = release / item["path"]
        if not artifact.resolve().is_relative_to(release.resolve()):
            bad.append(f"{item['path']}: outside the release")
        elif not artifact.is_file():
            bad.append(f"{item['path']}: missing")
        elif _sha256(artifact) != item["sha256"]:
            bad.append(f"{item['path']}: sha256 mismatch")
    if not report.add("hashes", not bad, "; ".join(bad[:5]) + (f" (+{len(bad) - 5} more)" if len(bad) > 5 else "")):
        return skip_rest("hashes")

    from corpus.releases import validate
    try:
        validate(release)
        report.add("release", True)
    except (OSError, ValueError, KeyError) as exc:
        report.add("release", False, str(exc))
        return skip_rest("release")

    city = manifest["city"]
    try:
        records = served_records(release, city)
    except (OSError, ValueError, KeyError) as exc:
        report.add("schema", False, f"snapshot does not open: {exc}")
        return skip_rest("schema")
    missing = [f"{r.get('id') or '?'}: {f}" for r in records for f in config["required_fields"]
               if _field(r, f) in (None, "")]
    too_few = len(records) < config["min_places"]
    reason = "; ".join(([f"{len(records)} served places < min_places {config['min_places']}"] if too_few else [])
                       + missing[:5]) + (f" (+{len(missing) - 5} more)" if len(missing) > 5 else "")
    report.add("schema", not (missing or too_few), reason)

    area = (yaml.safe_load((ROOT / "config" / "cities.yaml").read_text(encoding="utf-8")).get(city) or {}).get("area")
    outside = []
    for r in records:
        lat, lng = _field(r, "identity.lat"), _field(r, "identity.lng")
        if lat in (None, "") or lng in (None, ""):
            continue  # already reported by schema
        try:
            lat, lng = float(lat), float(lng)
        except (TypeError, ValueError):
            outside.append(f"{r['id']}: not a number")
            continue
        if area and not (area[0] <= lat <= area[2] and area[1] <= lng <= area[3]):
            outside.append(f"{r['id']}: ({lat}, {lng}) outside {city}")
    report.add("coords", not outside, "; ".join(outside[:5]))

    from corpus.index import Index
    try:
        indexed = set(Index.load(data=release).places)
        absent = sorted({r["id"] for r in records} - indexed)
        report.add("index", not absent, f"{len(absent)} served places not in the index: {', '.join(absent[:5])}" if absent else "")
    except (OSError, ValueError, KeyError) as exc:
        report.add("index", False, f"index does not open: {exc}")

    if baseline is None:
        report.add("drop", None, "no --baseline")
        return report
    try:
        base = release_dir(baseline)
        base_manifest = json.loads((base / "manifest.json").read_text(encoding="utf-8"))
        before, after = len(base_manifest["eligible_ids"]), len(manifest["eligible_ids"])
    except (OSError, ValueError, KeyError) as exc:
        report.add("drop", False, f"baseline unreadable: {exc}")
        return report
    drop = max(0.0, (before - after) / before) if before else 0.0
    report.add("drop", drop <= config["max_place_drop"],
               f"{before} -> {after} places ({drop:.0%} drop, limit {config['max_place_drop']:.0%}) vs {base.name}")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("release", type=Path)
    parser.add_argument("--baseline", type=Path, help="the running release (dir or DATA_DIR)")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--json", action="store_true", help="print the report as JSON")
    args = parser.parse_args(argv)
    report = check(args.release, args.baseline, yaml.safe_load(args.config.read_text(encoding="utf-8")))
    if args.json:
        print(json.dumps(report.as_dict(), ensure_ascii=False, indent=1))
    else:
        for r in report.results:
            print(f"{r['status']:4}  {r['check']:8} {r['reason']}")
        print(f"data_check {'PASS' if not report.failed else 'FAIL'}: {report.release}")
    return 1 if report.failed else 0


if __name__ == "__main__":
    sys.exit(main())
