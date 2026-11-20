"""Cut the owner's 12-pose mascot sheet (docs/design/mascot-sheet.png, RGBA, 4 x 3 poses, backdrop already removed) into the
transparent pictures the web uses: web/public/img/bunny/<mood>.webp (720 px, alpha, feet on one baseline, one scale for every
pose so the head stays the same size), plus reference.png (the idle pose, the reference the other moods are generated from) and
web/public/img/gen/bot-avatar.webp (the face of the idle pose, 160 px, the assistant's avatar).

The sheet's alpha carries faint specks around the poses: every pose is the solid blob of alpha > 110 (found as a connected
component), and only the alpha within a few pixels of it survives, so the fur wisps stay and the specks go.
Run: .venv/bin/python web/scripts/cut_mascot_sheet.py [sheet.png]
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

WEB = Path(__file__).resolve().parent.parent
ROOT = WEB.parent
SHEET = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'docs/design/mascot-sheet.png'
OUT = WEB / 'public/img/bunny'
# Cell order of the sheet, row by row. The moods the sheet does not draw are generated from reference.png by
# gen_mascot_moods.py / gen_tour_mascot.py.
POSES = ['idle', 'happy', 'wait', 'wow', 'sad', 'cry', 'angry', 'sleepy', 'love', 'point', 'curious', 'map']
CANVAS, HEIGHT, BASE = 720, 688, 695  # full body, feet near the bottom
KEEP_PX = 7  # how far from the solid body the soft alpha (fur wisps) is kept


def poses(rgba):
    a = rgba[..., 3]
    solid = ndi.binary_opening(a > 110, iterations=1)
    lab, n = ndi.label(solid)
    blobs = [i for i in range(1, n + 1) if (lab == i).sum() > 20000]
    if len(blobs) != len(POSES):
        raise SystemExit(f'expected {len(POSES)} poses, found {len(blobs)}')
    boxes = {i: ndi.find_objects((lab == i).astype(int))[0] for i in blobs}
    row = lambda i: round((boxes[i][0].start + boxes[i][0].stop) / 2 / (a.shape[0] / 3 + 1e-9) - 0.5)
    blobs.sort(key=lambda i: (row(i), boxes[i][1].start))
    out = []
    for i in blobs:
        near = ndi.binary_dilation(lab == i, iterations=KEEP_PX)
        p = rgba.copy()
        p[..., 3] = np.where(near & (a > 6), a, 0)
        out.append(Image.fromarray(p, 'RGBA'))
    return out


def main():
    cut = dict(zip(POSES, poses(np.array(Image.open(SHEET).convert('RGBA')))))
    box = cut['idle'].getchannel('A').getbbox()
    scale = HEIGHT / (box[3] - box[1])
    OUT.mkdir(parents=True, exist_ok=True)
    for name, im in cut.items():
        im = im.crop(im.getchannel('A').getbbox())
        im = im.resize((round(im.width * scale), round(im.height * scale)), Image.LANCZOS)
        canvas = Image.new('RGBA', (CANVAS, CANVAS), (0, 0, 0, 0))
        canvas.alpha_composite(im, ((CANVAS - im.width) // 2, BASE - im.height))
        canvas.save(OUT / f'{name}.webp', 'WEBP', quality=90, method=6)
        if name == 'idle':
            canvas.resize((1024, 1024), Image.LANCZOS).save(OUT / 'reference.png')
            canvas.crop((100, 0, 610, 510)).resize((160, 160), Image.LANCZOS).save(WEB / 'public/img/gen/bot-avatar.webp', 'WEBP', quality=92, method=6)
        print('ok', name)


if __name__ == '__main__':
    main()
