"""Derive the web logo files from the supplied lockup (frontend_images/LOGO-wordmark.png: colour pin with a rabbit + "trip guardian" lettering, on a cream page).

The page colour is cut away from the outside (flood fill from the border, so the cream rabbit inside is kept). The whole lockup is written to
web/public/img/brand/tripguardian-full.webp (`Logo full`: wide places such as the landing nav); the pin alone (the connected blob holding the pin seed) to
web/public/img/brand/tripguardian.webp (the shared `Logo` component: narrow rail, auth, footer). favicon.png, favicon.ico (16-64 px) and icon-192/512.png (manifest) are the mark alone,
apple-touch-icon.png sits on the cream page colour. After changing them bump the `?v=` on the icon links in web/index.html and the manifest: browsers keep favicons for a long time.
Run: python web/scripts/make_logo.py
"""
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent.parent
SRC = ROOT / 'frontend_images/LOGO-wordmark.png'
OUT = ROOT / 'web/public/img'
WORK = 1536  # the cut is made at this size, then the mark is scaled down
HEIGHT = 512
CREAM = (250, 247, 242)  # manifest background_color


def cut_outside(img):
    """RGBA: everything connected to the border and near the page colour becomes transparent; the edge is eroded 1 px so no page-coloured fringe stays."""
    img = img.convert('RGB').resize((WORK, WORK), Image.LANCZOS)
    page = img.getpixel((0, 0))
    near_white = ImageChops.difference(img, Image.new('RGB', img.size, page)).convert('L').point(lambda v: 0 if v > 14 else 255)
    for seed in ((0, 0), (WORK - 1, 0), (0, WORK - 1), (WORK - 1, WORK - 1)):
        ImageDraw.floodfill(near_white, seed, 128)
    outside = near_white.point(lambda v: 255 if v == 128 else 0)
    # enclosed page-coloured pieces go too (the counter of the "p"), but only right of the pin (the left third): the rabbit's cream is within the tolerance of the page
    lettering = Image.new('L', img.size, 0)
    lettering.paste(255, (WORK * 4 // 10, 0, WORK, WORK))
    outside = ImageChops.lighter(outside, ImageChops.multiply(near_white.point(lambda v: 255 if v == 255 else 0), lettering))
    alpha = ImageChops.invert(outside).filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(1.2))
    out = img.convert('RGBA')
    out.putalpha(alpha)
    return out.crop(alpha.point(lambda v: 255 if v > 24 else 0).getbbox())


def pin_only(lockup):
    """The pin from the lockup: the connected piece of the picture that holds its leftmost opaque pixel (the lettering is separate pieces); soft shadows are dropped."""
    import numpy as np
    from scipy import ndimage

    alpha = np.array(lockup.getchannel('A'))
    labels, _ = ndimage.label(alpha > 200)
    ys, xs = np.nonzero(labels)
    keep = labels == labels[ys[xs.argmin()], xs.min()]
    keep = ndimage.binary_dilation(keep, iterations=3)
    out = lockup.copy()
    out.putalpha(Image.fromarray((alpha * keep).astype('uint8')))
    return out.crop(out.getchannel('A').point(lambda v: 255 if v > 24 else 0).getbbox())


def fit(mark, h):
    return mark.resize((round(mark.width * h / mark.height), h), Image.LANCZOS)


def icon(mark, px, pad, bg):
    """The mark centred on a square; `pad` is the margin as a share of the side. `bg` None = transparent."""
    m = fit(mark, round(px * (1 - 2 * pad)))
    tile = Image.new('RGBA', (px, px), bg + (255,) if bg else (0, 0, 0, 0))
    tile.alpha_composite(m, ((px - m.width) // 2, (px - m.height) // 2))
    return tile.convert('RGB') if bg else tile


def main():
    Image.MAX_IMAGE_PIXELS = None
    lockup = cut_outside(Image.open(SRC))
    fit(lockup, HEIGHT).save(OUT / 'brand/tripguardian-full.webp', quality=92, method=6)
    mark = pin_only(lockup)
    logo = fit(mark, HEIGHT)
    logo.save(OUT / 'brand/tripguardian.webp', quality=92, method=6)
    icon(mark, 64, 0.04, None).save(OUT / 'favicon.png')
    icon(mark, 180, 0.14, CREAM).save(OUT / 'apple-touch-icon.png')
    icon(mark, 192, 0.06, None).save(OUT / 'icon-192.png')
    icon(mark, 512, 0.06, None).save(OUT / 'icon-512.png')
    icon(mark, 256, 0.04, None).save(OUT.parent / 'favicon.ico', sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])
    print(f'lockup {lockup.width}x{lockup.height} (aspect {lockup.width / lockup.height:.3f}), logo {logo.width}x{logo.height} (aspect {logo.width / logo.height:.3f}), favicon (png, ico), apple-touch-icon, icon-192/512 -> {OUT}')


if __name__ == '__main__':
    main()
