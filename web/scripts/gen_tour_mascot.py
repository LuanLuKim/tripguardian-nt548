"""Generate the bunny mascot's guided-tour poses (walking, pointing, waving, ...) through the 9router image endpoint.

Same recipe as gen_mascot_moods.py (it is imported for the reference image, the key and the request): the reference mascot in a
new pose on a transparent background, 720 px webp. Writes web/public/img/bunny/<pose>.webp and manifest.json. Skips files that
exist unless --force or the pose is named. `--model terra|sol` picks the image model (default sol).
Run: .venv/bin/python web/scripts/gen_tour_mascot.py [--force] [--model terra] [pose ...]
"""
import io
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

import gen_mascot_moods as base

OUT = base.OUT
POSES = {
    'walk_a': 'walking to the right in a side three-quarter view, facing right, left foot stepping forward, small arms swinging, cheerful.',
    'walk_b': 'walking to the right in a side three-quarter view, facing right, right foot stepping forward, small arms swinging the other way, cheerful.',
    'point_up': 'one paw raised and pointing diagonally up to the upper right, head tilted up, eyes looking up, friendly smile.',
    'wink': 'winking one eye with a cheeky little smile, one paw raised in a small thumbs up.',
    'cheer': 'celebrating, jumping with both paws up, holding a small party popper, a few colorful confetti pieces around it, big open smile.',
    'bow': 'bowing politely forward with both paws together in front, eyes closed in a gentle thankful smile.',
}
MODELS = {'sol': 'cx/gpt-6.1-sol', 'terra': 'cx/gpt-6.1-terra'}


def one(job):
    name, pose, url, key, model = job
    prompt = base.SAME + pose
    base.MODEL = model
    for attempt in (1, 2):
        try:
            img = base.fit(Image.open(io.BytesIO(base.generate(url, key, prompt))).convert('RGBA'))
            img.save(OUT / f'{name}.webp', 'WEBP', quality=88, method=6)
            print('ok  ', name, model, flush=True)
            return name, {'model': model, 'prompt': prompt, 'size': [720, 720], 'at': datetime.now(timezone.utc).isoformat(timespec='seconds')}
        except Exception as e:
            print('fail', name, attempt, type(e).__name__, str(e)[:120], flush=True)
            time.sleep(3)
    return name, None


def main():
    argv = sys.argv[1:]
    model = MODELS['sol']
    if '--model' in argv:
        i = argv.index('--model')
        model = MODELS[argv[i + 1]]
        del argv[i:i + 2]
    force = '--force' in argv
    args = [a for a in argv if not a.startswith('--')]
    url = os.environ.get('9ROUTER_API_URL') or 'http://127.0.0.1:20128/v1'
    key = base.env('9ROUTER_API_KEY')
    OUT.mkdir(parents=True, exist_ok=True)
    mf_path = OUT / 'manifest.json'
    manifest = json.loads(mf_path.read_text(encoding='utf-8')) if mf_path.exists() else {}
    jobs = [(n, p, url, key, model) for n, p in POSES.items() if (not args or n in args) and (force or args or not (OUT / f'{n}.webp').exists())]
    with ThreadPoolExecutor(max_workers=3) as ex:
        for name, entry in ex.map(one, jobs):
            if entry:
                manifest[name] = entry
                mf_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()
