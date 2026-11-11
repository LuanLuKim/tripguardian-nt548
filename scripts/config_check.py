"""Load every stage's config/*.yaml with the code on PYTHONPATH and say which one it refuses.

Every settings loader refuses an unknown key, and prod reads config/ from the working tree while its code is the
frozen .prod_src/: a key added for new code breaks prod at its next load (docs/log/AGENT_FAILURES.md F004).

    PYTHONPATH=.prod_src .venv/bin/python scripts/config_check.py     # does the live config load with prod's code?
    ./run.sh prod-check                                              # the same, plus the release prod runs

Exit 0 when all load, 1 otherwise (one line per failing file).
"""

import importlib
import os
import sys

LOADERS = ("journey.settings", "live.settings", "decision.settings", "planning.settings", "booking.settings",
           "trip.infrastructure.settings")


def main() -> int:
    failed = 0
    # The venv installs src/ in editable mode: a PYTHONPATH that does not exist silently checks the dev code instead.
    wanted = os.path.realpath(os.environ["PYTHONPATH"].split(os.pathsep)[0]) if os.environ.get("PYTHONPATH") else None
    for name in LOADERS:
        try:
            module = importlib.import_module(name)
            if wanted and not os.path.realpath(module.__file__).startswith(wanted + os.sep):
                raise ImportError(f"loaded from {module.__file__}, not from PYTHONPATH {wanted}")
            module.load()
        except Exception as error:  # noqa: BLE001 - every refusal is reported, none stops the others
            failed += 1
            print(f"[config] {name}: {type(error).__name__}: {str(error).splitlines()[0][:300]}")
    if not failed:
        print(f"[config] ok: {len(LOADERS)} settings files load with the code at {os.environ.get('PYTHONPATH') or 'src'}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
