AUTONOMOUS RUN: the direction is approved. Do NOT ask questions or wait for approval; do not run brainstorming or
plan-approval workflows. Implement, verify with the render bridge, finish only when this run's scope is done.
Do at least 5 build → shoot → look → fix rounds; stopping earlier means the coordinator reruns you.
Working directory for commands: `{data}/`. Code lives in `{code}/`; write place data and outputs only inside `{data}/`. Do not commit, deploy, or touch/restart the bridge server.

# {name}, run 1: SITE LAYOUT + MASSING + SIGNATURE (kit `{kit}`)

We build architectural studio scale models of Đà Lạt places with one template (look: cream plinth, sage foam trees,
muted roofs, fine linework, ground route arrows, tour bar). Approved reference: Chùa Linh Sơn (`linhson.json`, shots
`bridge/out/r16f/`). Read first: `NOTES.md` sections "Run 17", "Cam Ly run 1/2", "Cadasa run 1/2" (what worked, what
the coordinator rejected), and `{code}/kits/README.md`.

## Your lane (other agents build other places in parallel)

- Data: `places/{slug}/place.json` (new). Evidence: `places/{slug}/photos/` (index `photos_index.json` with scene labels,
  contact sheet `contact.jpg`), `places/{slug}/meta.json`, OSM footprint `places/{slug}/osm_footprints.json` if present
  (metres, x = east, y = north; the place's main building is `main`; use it for position, size, orientation).
- Geometry: `{code}/kits/{kit_file}` ({kit_note}). Never edit another place's `places/*`, `out_*`, or a kit you were not given.
  Shared `{code}/index.template.html` / `{code}/build.py`: only small generic changes, then every Linh Sơn test must still pass
  (`for check in {code}/checks/test_*.mjs; do node "$check" || exit; done`, every `node {code}/checks/test_<name>.mjs`).
- Build `python3 {code}/build.py places/{slug}/place.json out_{slug}/`; shoot `python3 {code}/bridge/request.py {tag}a --out out_{slug}`
  (optional views JSON before `--out`); tags start with `{tag}`. Test file `{code}/checks/test_{slug}.mjs` (grounded parts, route
  avoids buildings, ordered stops, meshes batched).

## Coordinator notes on the photos

{photo_notes}

## Scope

1. Massing of every building in the photos at true proportions; the signature features named above must read from the
   overview. Studio-model colour discipline (muted, matte; no saturated colours even where the real place is colourful:
   translate colour into a muted palette + fine linework/relief).
2. Site: plinth tight around the place (subject fills the overview like Linh Sơn), every route leg on a visible paved
   path, dense planting where the photos show it, no large empty patch in any default orbit. Instancing.
3. Hotspots in real walking order, short calm Vietnamese titles/captions (< 100 chars), each with `photos`;
   `place.tourTitle` "{tour_title}". Frame every stop: subject centred, nothing blocking, tour bar not covering it.
   No interior this run, but register the roof of the building whose interior photos exist (for a later cutaway).
4. Write `places/{slug}/summary.json` `{{"runs": [...], "kit_reuse": {{...}}}}`: kit types/options used, and what still
   needed place-specific code or magic numbers. Prefer reusable kit options.

Append "{name} run 1" to `NOTES.md` (Vietnamese): evidence used, rounds table (tag → saw → fixed), remaining issues.
Final answer: changes, last tag, remaining issues.
