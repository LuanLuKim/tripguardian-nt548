"""Generate the bunny mascot's extra moods for the sign-in screen through the 9router image endpoint.

The bunny's own poses (idle, happy, wait, wow, sad, sleepy, love, point, curious, map, cry, angry) were drawn by the project owner on
one sheet and cut out of its backdrop by cut_mascot_sheet.py; they live in web/public/img/bunny/ next to the 9router-made ones. Each mood here is the reference (web/public/img/bunny/reference.png,
sent in the `image` field so the character stays the same) in a new pose on a transparent background. Writes
web/public/img/bunny/<mood>.webp (alpha kept, 720 px) and manifest.json (model, prompt, time). The key comes from .env and is
never printed. Skips files that exist unless --force.
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
OUT = WEB / 'public/img/bunny'
REF = OUT / 'reference.png'
MODEL = 'cx/gpt-6.1-sol'
SAME = ('Same exact bunny mascot as the reference image (the cream plush lop-eared bunny with two brown pigtails tied with small yellow bows, '
        'the small brown canvas backpack, same soft 3D plush render, same size and framing, full body centered), '
        'transparent background, no text, no letters, no numbers, no scenery, no ground shadow, new pose: ')
# The poses on the owner's sheet (see the docstring) are cut out, not generated.
MOODS = {
    'shy': 'covering both eyes shyly with its two paws, head turned slightly away, blushing.',
    'peek': 'covering its face with both paws but peeking through a small gap between the fingers with one eye, blushing.',
    'mail': 'holding a small cream envelope with a little pink heart seal in both paws, smiling gently, as if it just sent or received a letter.',
    # states for the product's own moments (weather, cafe, photo, tips, warnings, a finished plan, packing, food)
    'umbrella': 'holding a small open yellow umbrella over its head with one paw, a few raindrops falling beside it, a calm cheerful smile.',
    'cold': 'wearing a cozy cream knitted scarf, hugging itself with both paws and shivering a little, cheeks pink, a small puff of breath, a shy smile.',
    'coffee': 'holding a small white coffee cup with gentle steam in both paws, eyes closed, a relaxed content smile.',
    'camera': 'holding a small retro camera up to one eye with both paws, taking a photo, the other eye open, cheerful.',
    'idea': 'one paw raised with the index finger up, a small glowing yellow lightbulb floating above its head, bright eyes, excited smile.',
    'warn': 'holding up a small yellow triangle warning sign with an exclamation mark in one paw, a concerned but gentle expression, head slightly tilted.',
    'calendar': 'holding a small calendar page with a big green check mark in both paws, proud happy smile.',
    'thumbs_up': 'giving a confident thumbs up with one paw, smiling brightly at the viewer.',
    'suitcase': 'holding the handle of a small cream suitcase with a brown strap in one paw, ready to travel, excited smile.',
    # the chat assistant's own poses: holding a speech bubble, and a small headset for the avatar crop
    'chat': 'holding a large white rounded speech bubble with three small dots inside it in one paw, the other paw waving hello, friendly attentive smile, looking at the viewer.',
    'chat_head': 'wearing a small cream headset with a tiny microphone, one paw touching the headset, a small speech bubble with a heart floating beside its head, helpful cheerful smile, looking at the viewer.',
    'eat': 'holding a small bowl of steaming noodles and a pair of chopsticks, mouth open about to take a bite, happy eyes.',
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


def fit(img):
    """Re-frame a generated picture like the cut-out ones: the alpha bounding box scaled to at most 688 x 660 px, centered, feet at y=695."""
    box = img.getchannel('A').getbbox()
    if not box:
        return img.resize((720, 720), Image.LANCZOS)
    pose = img.crop(box)
    k = min(688 / pose.height, 660 / pose.width)
    pose = pose.resize((round(pose.width * k), round(pose.height * k)), Image.LANCZOS)
    out = Image.new('RGBA', (720, 720), (0, 0, 0, 0))
    out.alpha_composite(pose, ((720 - pose.width) // 2, 695 - pose.height))
    return out


def one(job):
    name, pose, url, key = job
    prompt = SAME + pose
    for attempt in (1, 2):
        try:
            img = fit(Image.open(io.BytesIO(generate(url, key, prompt))).convert('RGBA'))
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
