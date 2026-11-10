AUTONOMOUS RUN: the direction is approved. Do NOT ask questions or wait for approval; do not run brainstorming or
plan-approval workflows. Implement, verify with the render bridge, finish only when this run's scope is done.
Do at least 5 build → shoot → look → fix rounds. Working directory for commands: `{data}/`. Code lives in `{code}/`; write place data and outputs only inside `{data}/`. Do not commit, deploy,
or touch/restart the bridge server.

# Kit `{kit}`: build a REUSABLE kit on {name} (covers ~{count} places of the Đà Lạt batch)

We build architectural studio scale models of Đà Lạt places with one template (cream plinth, sage foam trees, muted
roofs, fine linework, ground route arrows, tour bar, cutaway + eye-level interior stop). Approved references and lessons:
read `NOTES.md` sections "Run 17", "Cam Ly run 1–3", "Cadasa run 1–3", "Ga Đà Lạt run 1–2", "Con Gà", "Dinh III",
`{code}/kits/README.md`, `{code}/batch/INTERIOR_RULES.md`, and look at `bridge/out/zcl/`, `bridge/out/zgd/`, `bridge/out/zcg2/`
(approved look). **The goal of this run is the kit, not only this place**: after it, other {kit_plural} must be
modelled by writing `place.json` only, with no new geometry code.

## Your lane (other agents build other kits in parallel)

- Data: `places/{slug}/place.json` (new). Evidence: `places/{slug}/photos/` (`photos_index.json` has scene labels),
  `places/{slug}/contact.jpg` (look at it first), `places/{slug}/meta.json`, `places/{slug}/osm_footprints.json` if it
  exists (metres, x = east, y = north; `main` = the place's building; use it for position, size, orientation).
  Some Maps photos show a neighbouring place: decide from the contact sheet, list excluded photos in
  `places/{slug}/PHOTOS.md` (Vietnamese, short table), never model them.
- Geometry: new file `{code}/kits/{kit}.js` only. You may call template helpers (see `{code}/kits/README.md`) and copy small helpers
  from other kits, but never edit other kits, other `places/*`, `out_*` dirs, `linhson.json`, `photos/`.
  Shared `{code}/index.template.html` / `{code}/build.py`: only small generic changes, then ALL existing suites must still pass
  (`for check in {code}/checks/test_*.mjs; do node "$check" || exit; done`, every `node {code}/checks/test_<name>.mjs`).
- Build `python3 {code}/build.py places/{slug}/place.json out_{slug}/`; shoot `python3 {code}/bridge/request.py {tag}a --out out_{slug}`
  (a views JSON before `--out` shoots only chosen views: use it between full rounds to save time); tags start with
  `{tag}`. Tests: `{code}/checks/test_{slug}.mjs` (grounded parts, route on paving and clear of buildings, ordered stops, batched meshes).

## Scope

1. **Kit types** in `{code}/kits/{kit}.js`, parametric with sensible defaults, designed for the whole family: {family}.
   One builder with options beats many one-offs; every number specific to this place goes into `place.json`.
2. **This place**: signature features recognisable from the overview, true proportions, tight plinth (subject fills
   ~80 % of the free width), every route leg on visible paving, dense but calm planting, no empty patches, muted
   studio palette. 5–7 stops in real walking order, short calm Vietnamese captions (< 100 chars), `place.tourTitle`
   "Một vòng {name}".
3. **Interior** if the place has ≥ 4 interior photos ({interior_count} here): cutaway stop + eye-level inside stop via
   `registerInteriorKit` in your kit, following `{code}/batch/INTERIOR_RULES.md` exactly. Otherwise no interior.
4. **Kit catalogue** (this is what saves tokens later):
   - add a section "## {kit}" to `{code}/kits/README.md` (English): every object type, every option with type/default/meaning,
     what photos each option corresponds to, pitfalls you hit;
   - add `{code}/kits/examples/{kit}.place.json`: a small but complete example place using every option (it must build and
     boot: add it to your test);
   - `places/{slug}/summary.json`: `{{"runs": [...], "kit_reuse": {{"types": [...], "place_specific": [...]}}}}`.

Append "Kit {kit} — {name}" to `NOTES.md` (Vietnamese): evidence, kit types table, rounds table (tag → saw → fixed),
remaining issues. Final answer: kit types, last tag, remaining issues.
