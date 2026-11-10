AUTONOMOUS RUN: the direction is approved. Do NOT ask questions or wait for approval; do not run brainstorming or
plan-approval workflows. Implement, verify with the render bridge, finish only when this run's scope is done.
Working directory for commands: `{data}/`. Code lives in `{code}/`; write place data and outputs only inside `{data}/`. Do not commit, deploy, or touch/restart the bridge server.

# Colour pass, kit `{kit}`: {names} in the colours of their photos

The owner (2026-11-04): "3D phải có màu sắc rực rỡ, đúng màu của ảnh, thu hút đẹp; giờ hơi đơn sắc và bị lạnh."
The old rule "muted matte studio palette, even where the real place is bright" is CANCELLED (also where a
`NOTES_coord.md` or an old brief still says "muted"). The new bar: someone who has been there recognises the place
from its colours at first glance. Keep the scale-model look (clean matte surfaces, fine linework, cream plinth), but
every surface carries the colour the photos show. Approved reference of this pass: `out_linhphuoc/sheet_kc2lp2.jpg`,
`out_linhan/sheet_kc2la2.jpg` (pagodas recoloured the same way).

The viewer (`{code}/index.template.html`) already has warm lights and a shared display grade that raises chroma on coloured
surfaces and keeps neutral greys clean. So write the REAL colour, never a greyed one, and do not pre-saturate past the
photo: a colour as you would eyedrop it from a sunlit spot is right.

Shapes, layout, route, stops and cameras are approved. **Only colour changes**, plus the kit options needed to set them.

## Read first (only these)
- `{code}/kits/catalog/{kit}.md` if it exists (else the `## {kit}` part of `{code}/kits/README.md`), then `grep -n` into `{kit_file}`
  for hardcoded colours.
- Per place: `contact.jpg` (numbered photos), `NOTES_coord.md` (which photos belong to the place, which to ignore),
  `place.json`, and the current render `checks/colour_before_overview.png`, `colour_before_stop1.png`.
{places}

## Method, per place
1. Compare photos with the current render. Write `places/<slug>/COLOURS.md`: first a short list "render → photo"
   of every surface whose colour is wrong (khaki/grey-green stand-ins, pale roofs, beige where the photo is white,
   brick, glazed tile, painted plaster, timber, gold, flowers, water…), then a table part → hex → photo number.
2. Eyedrop with PIL from single photos in `places/<slug>/photos/` (sunlit patches; never sky, people, deep shadow; only
   photos that belong to the place per `NOTES_coord.md`).
3. Set every visible colour: walls, roofs, trim, doors/windows, paving, lawn, planting and flowers, water, signs,
   statues, vehicles, furniture, interior (if the place has one: interior colours from interior photos, dim/dark
   interiors stay dim/dark, never reuse exterior patterns inside).
4. Each round ask: does each surface match its photo? Anything still grey/khaki where the photo shows colour? Does it
   look attractive, not garish? Large surfaces (roofs, walls, lawns) set the impression: get those right first.

## Kit edits
Where a visible colour is hardcoded in `{kit_file}`, add an optional colour field. **The default must equal today's
hardcoded value**, so places that don't set it render exactly as before. Document each new field in the kit's section
of `{code}/kits/README.md` (type, default, meaning, photo pattern), then `python3 {code}/batch/split_catalog.py`. No new geometry
unless a colour cannot show without it; then keep it light (instanced / merged) and off by default.
{extra}

## Regression
{regress}
`node {code}/check_place.mjs <slug>` must say `boot ok` for every place of this run{regress_boot}.

## Tools
- `node {code}/check_place.mjs <slug>` = build + boot in node, prints the exact error. Run it before any shot.
- `python3 {code}/build.py <place.json> out_<slug>/` then `{repo}/.venv/bin/python {code}/bridge/shot.py <tag> --out out_<slug> [--stops id1,id2]`
  = render overview, 2 orbits and the stops, prints the path of ONE contact sheet `out_<slug>/sheet_<tag>.jpg`. The
  bridge is shared by several runs and slow: never put a timeout on it (up to 15–20 minutes). Look at the sheet; open
  single PNGs in `bridge/out/<tag>/` only when needed.
- Tags start with `{tag}` + a short place code + round number (e.g. `{tag}xx1`). At most 3 full-sheet rounds per place;
  use `--stops` to re-shoot only what you changed.

## Token discipline
If a trivial shell command (`ls`, `true`) hangs twice, the host sandbox is stuck: stop at once, write nothing, final answer "SANDBOX HUNG".
Targeted `grep -n` / `sed -n` reads, never whole large files twice; short command output; do not print files you wrote.

## Finish
Each place's `summary.json`: set `tag`, add `"colour_pass": "<last tag>"`, append to `colour_rounds`
(`tag`, `saw`, `fixed`), `open_issues`. Final answer: new kit colour fields, last tag per place, regression result,
remaining issues (at most 8 lines).
