# Interior stop rules (learned on Chùa Linh Sơn runs 14–16; apply to every place)

- Tour: the outside stop of the building (`insideView: <inside stop id>`) shows it closed, roof on; the next stop
  "Bên trong …" is `interior: true` with `building: <objectId>`. The viewer walks the camera in at eye height through
  the door (`interior.approach` → `interior.entry`), lights coming up as it crosses; leaving walks out the same door
  (owner 2026-11-10: no roof lift, go straight in). `hotspot.cutaway` still lifts the roof, but only at a stop with no
  inside view.
- When the camera is INSIDE the roof is DOWN: a real ceiling (timber beams / planks / vault as the photos show), no
  sky visible anywhere.
- Camera at eye level (~1.6 m) just inside the main door, looking along the main axis to the focal point (altar,
  statue, counter). Enter/leave through the door, never through the roof or a wall; limited orbit inside.
- Soft interior light only for this stop (warm near the focal point + gentle fill); never dark, never blown out.
- Furnishing at true scale (cushions ~0.6 m, pews ~0.45 m seat height, chairs ~0.9 m back); nothing in front of the
  camera; the header fades to ~40 % at the inside stop so it does not cover the view.
- Check the inside view at 3 yaw angles (−4°, 0°, +4°) and the walk through the door (`window.__walk(out, in, q)`): no gaps, no floating pieces,
  no z-fighting, roof never intersecting the camera, no sky through seams.
- Muted studio palette inside too: translate gold / mosaic / stained glass into muted tones + fine linework.
