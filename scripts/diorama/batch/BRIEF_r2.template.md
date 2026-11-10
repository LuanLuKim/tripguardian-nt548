AUTONOMOUS RUN: the direction is approved. Do NOT ask questions or wait for approval; do not run brainstorming or
plan-approval workflows. Implement, verify with the render bridge, finish only when this run's scope is done.
Do at least 5 build → shoot → look → fix rounds; stopping earlier means the coordinator reruns you.
Working directory for commands: `{data}/`. Code lives in `{code}/`; write place data and outputs only inside `{data}/`. Do not commit, deploy, or touch/restart the bridge server.

# {name}, run {run}: COORDINATOR FIXES + INTERIOR

Continue from your previous run of this place (read its sections in `NOTES.md`; baseline tag `{base}`). Same lane:
`places/{slug}/`, `{code}/kits/{kit_file}`, `{code}/checks/test_{slug}.mjs`, build to `out_{slug}/`, tags start with `{tag}`,
`python3 {code}/bridge/request.py <tag> --out out_{slug}`. Other agents work on other places in parallel: never touch other
`places/*`, `out_*` or kits. Shared `{code}/index.template.html` / `{code}/build.py`: small generic changes only, then all Linh Sơn
tests must pass (`for check in {code}/checks/test_*.mjs; do node "$check" || exit; done`, every `node {code}/checks/test_<name>.mjs`).

## Coordinator review of `{base}` (fix these first)

{fixes}

## Interior (new)

{interior}

Follow `{code}/batch/INTERIOR_RULES.md` exactly (learned the hard way on Linh Sơn). Register an interior kit with
`registerInteriorKit` in your kit file (reusable for other places of this kind; keep place data in `place.json`).
Shoot the default set plus the inside stop at yaw −4°/0°/+4° (see `bridge/r16-views.json` for the view format) and
look at every image.

Update `places/{slug}/summary.json` (append this run; `kit_reuse` as before) and append "{name} run {run}" to
`NOTES.md` (Vietnamese): rounds table, changes, remaining issues. Final answer: changes, last tag, remaining issues.
