AUTONOMOUS RUN: the direction is approved. Do NOT ask questions or wait for approval; do not run brainstorming or
plan-approval workflows. Finish the place, then stop. Quality comes first; there is no token cap.

# Studio model of {name} (kit `{kit}`): write `places/{slug}/place.json`

We make small architectural scale models (cream plinth, leaf-green trees, roofs and walls in the colours of the photos, ground route arrows) from one
engine. The kit already exists and is approved. **This job is data only**: one JSON file that lays the place out.
Working directory for commands: `{data}/`; code, kits and templates live in `{code}/`.

## Read exactly these, nothing else
- `places/{slug}/contact.jpg` (numbered photos, one look), `places/{slug}/meta.json`, `places/{slug}/osm_footprints.json` if it exists (metres, x east, y north, `main` = the place's building: use it for position, size, orientation)
{catalog}
{example}
{interior_read}
Use the attached full-size evidence photos; the contact sheet is only for orientation.

## Coordinator notes
{photo_notes}

NOTES contract: `signature` is a list of `{{"id": str, "what": str, "photos": ["gNN"], "must": bool}}`.
`kit_gap` is a list of `{{"what": str, "signature_ids": [str]}}`, never plain strings. A gap affecting a
must signature requires a kit change, not an invented approximation. `evidence` holds at most 8 photo ids.

## What a good model has
1. The buildings of the photos at true proportions; the features named above read from the overview. Colours from the photos: set every wall, roof, trim, door, paving and planting colour you can see (glazed tile teal, brick red, mustard plaster, white mosaic…) and note the photo number in a JSON-free comment line of your final message. Write the real colour, not a greyed one: the viewer adds a shared warm grade. No grey-green or khaki stand-ins where the photo shows a clear colour.
2. Layout as the photos show it: paths, gate direction and building positions come from the photos, never invented.
3. Plinth tight around the place, so the subject fills the overview. Dense planting where the photos show it, no big empty patch.
4. {stops} hotspots in real walking order, first outside at the entrance. Short calm Vietnamese titles, captions under 100 characters, stating only what the photos show. `tourTitle` "{tour_title}", plus `tourCaption`, `location`, `subtitle`.
5. `route` is an array of legs, one leg per pair of consecutive outdoor stops, each leg an array of `[x, z]` points: `[[[x,z],[x,z]], [[x,z],[x,z],[x,z]]]`. Every leg lies on paved ground (the viewer throws otherwise). Each stop frames its subject, centred, nothing blocking it.
{interior_scope}

## Loop
`node {code}/check_place.mjs {slug}` (builds and boots the viewer in node, prints the exact error; must say `boot ok` before any shot), then
`python3 {code}/build.py places/{slug}/place.json out_{slug}/` and `{repo}/.venv/bin/python {code}/bridge/shot.py {tag}<a,b,c> --out out_{slug}`
(prints the path of one contact sheet `out_{slug}/sheet_<tag>.jpg` + console errors; `--stops id1,id2` re-shoots only those stops).

## Session limits (hard rules)
- Render budget: the bridge renders in software and a view that takes over 30 s is lost, so the whole place fails. Keep the scene under ~650k triangles: `node {code}/check_place.mjs {slug} --tris` prints the total and the heaviest objects. Large flower fields keep `spacing` >= 0.8 and groves a moderate `density`; fill space with fewer, larger plants rather than thousands of tiny ones.
- At most 3 boot/build/shot/look cycles in this session. The bridge renders slowly: never put a timeout on bridge/shot.py, it can take up to 10 minutes. Stop as soon as the sheet passes the list above. View only that sheet, once per round. A sheet tile that is blank or a console error means the model did not load: fix the JSON first.
- Never read or edit `{code}/kits/*.js`, kit catalogues/examples, `{code}/index.template.html`, `{code}/build.py`, `NOTES.md`, other places, tests. Catalogue and proven example are supplied above; do not open their files. Write no test file. If the kit lacks something, report it in `kit_gaps`; never invent a substitute feature.
- Plan the layout once before writing JSON; do not print files you just wrote; keep command output short.
- Write only inside `places/{slug}/` and `out_{slug}/`. No commit, no deploy, never touch the bridge.

## Finish
`places/{slug}/summary.json`: `{{"tag": last tag, "rounds": n, "kit_gaps": [...], "open_issues": [...]}}`. Final answer: at most 4 lines.
