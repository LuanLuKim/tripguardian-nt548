"""Generate the sign-in screen's scenery through the 9router image endpoint: the Da Lat highland backdrop behind the bunny
(web/public/img/auth/scene.webp, portrait) and a leafy branch for the page corner (web/public/img/auth/leaves.webp, transparent).
Illustration only, never presented as a real photo of a place. The key comes from .env and is never printed.
Run: .venv/bin/python web/scripts/gen_auth_scene.py [--force] [scene|leaves ...]
"""
import io
import sys
from pathlib import Path

from PIL import Image

import gen_mascot_moods as base

OUT = base.WEB / 'public/img/auth'
STYLE = ('Soft pastel 3D-illustration look, gentle watercolor haze, calm and welcoming, mint green and cream palette with a warm peach sky. '
         'No text, no letters, no logos, no characters, no animals, no people, no watermark. ')
JOBS = {
    'scene': ('1024x1536', (720, 1080), False, STYLE + 'Portrait scenery of the Da Lat highlands at dawn: layered misty green hills and pine forests fading into fog, '
              'a small white church with a red roof on a far hillside, a few glass greenhouses on the right, a soft peach and pale blue sky. '
              'In the foreground a clean flat green meadow with a few tiny white daisies at the very bottom edges. The center and the lower middle '
              'are open and calm (a character will stand there later). The top fifth is empty soft sky (a logo will sit there later).'),
    'leaves': ('1024x1024', (640, 640), True, STYLE + 'A leafy green branch with broad soft leaves entering from the top-left corner and hanging diagonally, '
               'a few leaves in blurred depth of field, transparent background.'),
}


def main():
    argv = sys.argv[1:]
    force = '--force' in argv
    names = [a for a in argv if not a.startswith('--')] or list(JOBS)
    url = base.os.environ.get('9ROUTER_API_URL') or 'http://127.0.0.1:20128/v1'
    key = base.env('9ROUTER_API_KEY')
    for name in names:
        size, final, alpha, prompt = JOBS[name]
        path = OUT / f'{name}.webp'
        if path.exists() and not force:
            continue
        data = _post(url, key, size, prompt)
        img = Image.open(io.BytesIO(data)).convert('RGBA' if alpha else 'RGB').resize(final, Image.LANCZOS)
        img.save(path, 'WEBP', quality=86, method=6)
        print('ok  ', name, flush=True)


def _post(url, key, size, prompt):
    import base64
    import json
    import urllib.request
    body = json.dumps({'model': base.MODEL, 'prompt': prompt, 'size': size}).encode()
    req = urllib.request.Request(url.rstrip('/') + '/images/generations', body, {'Authorization': f'Bearer {key}', 'Content-Type': 'application/json', 'User-Agent': 'curl/8.5.0', 'Accept': 'application/json'})
    with urllib.request.urlopen(req, timeout=300) as r:
        return base64.b64decode(json.load(r)['data'][0]['b64_json'])


if __name__ == '__main__':
    main()
