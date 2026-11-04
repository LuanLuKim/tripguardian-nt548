"""Generate the acorn mascot's moods for the sign-in screen through the 9router image endpoint.

Each mood is the reference mascot (web/public/img/auth/acorn_mascot.png, sent in the `image` field so the character stays
the same) in a new pose, on a transparent background. Writes web/public/img/auth/mood/<mood>.webp (alpha kept, 720 px)
and manifest.json (model, prompt, time). The key comes from .env and is never printed. The idle mood is the existing
acorn_greet.webp. Skips files that exist unless --force.
Run: .venv/bin/python web/scripts/gen_mascot_moods.py [--force] [mood ...]
"""
import base64
import io
import json
import os
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

WEB = Path(__file__).resolve().parent.parent
ROOT = WEB.parent
OUT = WEB / 'public/img/auth/mood'
REF = WEB / 'public/img/auth/acorn_mascot.png'
MODEL = 'cx/gpt-6.1-sol'
SAME = ('Same exact acorn mascot as the reference image (same plush character, outfit, colors, same size and framing, '
        'full body centered), transparent background, no text, no letters, no scenery, new pose: ')
MOODS = {
    'shy': 'covering both eyes shyly with its two paws, head turned slightly away, blushing.',
    'peek': 'covering its face with both paws but peeking through a small gap between the fingers with one eye, blushing.',
    'curious': 'tilting its head to one side with one eyebrow raised, curious and puzzled, one paw raised to its chin.',
    'sad': 'sad and apologetic, worried eyebrows, a tiny tear in one eye, one small sweat drop on the forehead, shoulders drooping, slightly slumped.',
    'happy': 'jumping up with joy, both arms raised, eyes closed in a big smile, extra pink cheeks, a few small golden sparkles around it.',
    'mail': 'holding a small cream envelope with a little pink heart seal in both paws, smiling gently, as if it just sent or received a letter.',
    'wait': 'thinking, looking up and to the side, one paw on its chin, calm and patient.',
}


def env(name):
    if os.environ.get(name):
        return os.environ[name]
    for line in (ROOT / '.env').read_text(encoding='utf-8').splitlines():
        if line.startswith(name + '='):
            return line.split('=', 1)[1].strip().strip('"\'')
    raise SystemExit(f'{name} missing in .env')


def generate(url, key, prompt):
    ref = 'data:image/png;base64,' + base64.b64encode(REF.read_bytes()).decode()
    body = json.dumps({'model': MODEL, 'prompt': prompt, 'size': '1024x1024', 'image': ref}).encode()
    req = urllib.request.Request(url.rstrip('/') + '/images/generations', body, {'Authorization': f'Bearer {key}', 'Content-Type': 'application/json', 'User-Agent': 'curl/8.5.0', 'Accept': 'application/json'})
    with urllib.request.urlopen(req, timeout=300) as r:
        return base64.b64decode(json.load(r)['data'][0]['b64_json'])


def one(job):
    name, pose, url, key = job
    prompt = SAME + pose
    for attempt in (1, 2):
        try:
            img = Image.open(io.BytesIO(generate(url, key, prompt))).convert('RGBA')
            img = img.resize((720, 720), Image.LANCZOS)
            img.save(OUT / f'{name}.webp', 'WEBP', quality=88, method=6)
            print('ok  ', name, flush=True)
            return name, {'model': MODEL, 'prompt': prompt, 'size': [720, 720], 'at': datetime.now(timezone.utc).isoformat(timespec='seconds')}
        except Exception as e:
            print('fail', name, attempt, type(e).__name__, str(e)[:120], flush=True)
            time.sleep(3)
    return name, None


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    force = '--force' in sys.argv
    url = os.environ.get('9ROUTER_API_URL') or 'http://127.0.0.1:20128/v1'
    key = env('9ROUTER_API_KEY')
    OUT.mkdir(parents=True, exist_ok=True)
    mf_path = OUT / 'manifest.json'
    manifest = json.loads(mf_path.read_text(encoding='utf-8')) if mf_path.exists() else {}
    jobs = [(n, p, url, key) for n, p in MOODS.items() if (not args or n in args) and (force or args or not (OUT / f'{n}.webp').exists())]
    with ThreadPoolExecutor(max_workers=3) as ex:
        for name, entry in ex.map(one, jobs):
            if entry:
                manifest[name] = entry
    mf_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()
