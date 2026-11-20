"""python -m journey.tariffs refresh [--accept] | build [--accept] | boundaries <geoBoundaries ADM1 .geojson>

refresh: fetch every brand page (twice), then build. build: rebuild config/rides_tariffs.json from the pages already in
data/rides/. boundaries: rewrite config/provinces.geojson from a downloaded geoBoundaries file. Run from the repo root;
the table and the boundaries are reviewed with `git diff` and committed (docs/BOOKING.md §Gọi xe)."""

import argparse
import sys

from . import boundaries, build


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m journey.tariffs")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for cmd in ("refresh", "build"):
        p = sub.add_parser(cmd)
        p.add_argument("--accept", action="store_true", help=f"write even if fares moved > {build.CHANGE_PCT}%%")
    b = sub.add_parser("boundaries")
    b.add_argument("source", help="geoBoundaries VNM ADM1 geojson, downloaded from " + boundaries.SOURCE)
    args = ap.parse_args(argv)
    try:
        if args.cmd == "boundaries":
            shapes = boundaries.build(args.source)
            print(f"{len(shapes)} areas, {sum(shapes.values())} polygons -> {boundaries.OUT}")
            return 0
        if args.cmd == "refresh":
            for path in build.refresh():
                print(f"saved {path}")
        rep = build.build(accept=args.accept)
    except (build.BuildError, ValueError, OSError) as e:
        print(f"ERROR {e}", file=sys.stderr)
        return 1
    print(build.summary(rep))
    return 0 if rep["written"] else 1


if __name__ == "__main__":
    sys.exit(main())
