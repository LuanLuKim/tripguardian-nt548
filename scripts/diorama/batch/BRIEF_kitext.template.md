AUTONOMOUS RUN: the direction is approved. Do NOT ask questions or wait for approval; do not run brainstorming or
plan-approval workflows. Implement, verify with the render bridge, finish only when this run's scope is done.
Working directory for commands: `{data}/`. Code lives in `{code}/`; write place data and outputs only inside `{data}/`. Do not commit, deploy, or touch/restart the bridge server.

# Extend kit `{kit}` so every {family} in Đà Lạt can be modelled at the approved quality by writing JSON only

The kit `{code}/kits/{kit}.js` exists and works for {regress_names}. Data-only runs on new places failed where the kit lacks
pieces. The owner wants the HIGHEST quality: the bar is the approved Chùa Linh Sơn / Nhà thờ Con Gà look
(`bridge/out/r16f/`, `bridge/out/zcg2/`): recognisable signature features from the overview, true proportions, tight
plinth (subject fills ~80 % of the free width), dense calm planting, no empty patches, muted matte studio palette,
fine linework.

## Read first (only these)
- `{code}/kits/catalog/{kit}.md` (current options), `{code}/kits/{kit}.js`, `{code}/kits/README.md` top section (template helpers)
- For each target place: `places/<slug>/contact.jpg`, `NOTES_coord.md`, current `place.json`, `summary.json` (kit_gaps),
  and the coordinator's review of its last render: {target_sheets}

## Missing pieces (coordinator, from photos + renders)
{gaps}

## Scope
1. Add parametric object types / options to `{code}/kits/{kit}.js` covering the missing pieces, designed for the whole family
   (not one place): defaults sensible, every place-specific number in JSON. Reuse helpers; batch meshes / instancing.
2. Re-author the target places {target_names} with the new options until each reaches the bar above, including an
   interior where the place has ≥ 4 interior photos (`{code}/batch/INTERIOR_RULES.md`).
3. Regression: {regress_names} must look the same. Before changing anything, shoot them once
   (`python3 {code}/build.py places/<slug>/place.json out_<slug>/` + `{repo}/.venv/bin/python {code}/bridge/shot.py {tag}base<slug> --out out_<slug>`),
   and compare after (`python3 compare_renders.py` if it fits, else your eyes on both sheets). Every existing `node {code}/checks/test_<name>.mjs`
   for those places and `for check in {code}/checks/test_*.mjs; do node "$check" || exit; done` must still pass.
4. Update the catalogue: section "## {kit}" in `{code}/kits/README.md` (every new type/option: type, default, meaning, which
   photo pattern it serves, pitfalls), then run `python3 {code}/batch/split_catalog.py`; extend `{code}/kits/examples/{kit}.place.json`
   to use the new options (it must build and boot).

## Tools
- `node {code}/check_place.mjs <slug>` = build + boot in node, prints the exact error. Run it before any shot.
- `{repo}/.venv/bin/python {code}/bridge/shot.py <tag> --out out_<slug> [--stops id1,id2]` = render overview, 2 orbits and the
  stops, prints the path of ONE contact sheet `out_<slug>/sheet_<tag>.jpg`. The bridge is shared and slow: never put a
  timeout on it (up to 10–15 minutes). Look at the sheet, open single PNGs in `bridge/out/<tag>/` only when needed.
- Tags start with `{tag}`. Do at least 4 build → shoot → look → fix rounds per target place.

## Token discipline
Read with targeted `grep -n` / `sed -n` ranges, never whole large files twice; keep command output short; do not print
files you just wrote. Quality first, but no waste.

## Finish
Each target `places/<slug>/summary.json`: `{{"tag", "rounds", "kit_gaps": [], "open_issues": []}}`. Append
"Kit {kit} mở rộng" to `NOTES.md` (Vietnamese, short: new types table, rounds tag → saw → fixed, remaining issues).
Final answer: new types/options, last tag per place, remaining issues (at most 8 lines).
