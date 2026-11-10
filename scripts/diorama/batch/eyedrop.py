"""eyedrop.py <image> x,y[,r] ... : median sRGB hex of a (2r+1)^2 patch at each point (default r=3), plus a zoom crop
contact sheet of the patches (<image>.eyedrop.jpg next to the scratch dir given by EYEDROP_OUT, else /tmp) to verify."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from paths import DATA

import colorsys
import os
from statistics import median
from PIL import Image, ImageDraw

def smooth(a, b, x):
    t = min(max((x - a) / (b - a), 0), 1)
    return t * t * (3 - 2 * t)


def precomp(c):
    """Input colour whose render through the viewer's display grade (index.template.html `grade`) keeps the photo's
    saturation: invert s_out = s_in * (1 + (.32 + .55 * (1 - smoothstep(.35, .65, s_in))) * coloured(s_in))."""
    h, s, v = colorsys.rgb_to_hsv(*(x / 255 for x in c))
    lo, hi = 0.0, s
    for _ in range(40):
        mid = (lo + hi) / 2
        out = mid * (1 + (.32 + .55 * (1 - smooth(.35, .65, mid))) * smooth(.05, .15, mid))
        lo, hi = (mid, hi) if out < s else (lo, mid)
    r, g, b = colorsys.hsv_to_rgb(h, lo, v)
    return "#%02x%02x%02x" % tuple(round(x * 255) for x in (r, g, b))


if __name__ == "__main__":
    im = Image.open(DATA / sys.argv[1]).convert("RGB")
    crops = []
    for arg in sys.argv[2:]:
        x, y, *r = [int(v) for v in arg.split(",")]
        r = r[0] if r else 3
        px = [im.getpixel((min(max(x + dx, 0), im.width - 1), min(max(y + dy, 0), im.height - 1)))
              for dx in range(-r, r + 1) for dy in range(-r, r + 1)]
        c = tuple(int(median(p[i] for p in px)) for i in range(3))
        print(f"{arg}: photo #{c[0]:02x}{c[1]:02x}{c[2]:02x}  input {precomp(c)}")
        crop = im.crop((x - 30, y - 30, x + 30, y + 30)).resize((90, 90))
        ImageDraw.Draw(crop).rectangle((40, 40, 50, 50), outline="red")
        ImageDraw.Draw(crop).rectangle((0, 80, 89, 89), fill=c)
        crops.append(crop)
    if crops and os.environ.get("EYEDROP_OUT"):
        sheet = Image.new("RGB", (90 * len(crops), 90), "white")
        for i, c in enumerate(crops):
            sheet.paste(c, (90 * i, 0))
        sheet.save(DATA / os.environ["EYEDROP_OUT"])
