import base64
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path
from paths import CODE


def main():
    if len(sys.argv) != 3:
        raise SystemExit('Usage: python build.py PLACE.json OUTPUT_DIR')
    source = Path(sys.argv[1])
    destination = Path(sys.argv[2])
    place = json.loads(source.read_text(encoding='utf-8'))
    root = CODE
    template = (root / 'index.template.html').read_text(encoding='utf-8')
    kits = []
    for name in place.get('kits', []):
        if not isinstance(name, str) or not re.fullmatch(r'[a-zA-Z0-9_-]+', name):
            raise ValueError(f'Invalid kit name: {name}')
        kit = (root / 'kits' / f'{name}.js').resolve()
        if kit.parent != root / 'kits':
            raise ValueError(f'Invalid kit path: {name}')
        code = kit.read_text(encoding='utf-8')
        if re.search(r'</script', code, re.IGNORECASE):
            raise ValueError(f'Kit must not close the module script: {name}')
        kits.append(code)
    template = template.replace('/*__KITS__*/', '\n'.join(kits))
    payload = json.dumps(place, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c')
    html = template.replace('__PLACE__', payload)
    scripts = re.findall(r'<script(?:\s[^>]*)?>(.*?)</script>', html, re.DOTALL)
    hashes = ' '.join("'sha256-" + base64.b64encode(hashlib.sha256(script.encode()).digest()).decode() + "'" for script in scripts)
    html = html.replace('__SCRIPT_HASHES__', hashes)
    destination.mkdir(parents=True, exist_ok=True)
    photos = destination / 'photos'
    photos.mkdir(exist_ok=True)
    for name in sorted({name for spot in place.get('hotspots', []) for name in spot.get('photos', [])}):
        if Path(name).name != name:
            raise ValueError(f'Invalid photo name: {name}')
        shutil.copy2(source.parent / 'photos' / name, photos / name)
    (destination / 'index.html').write_text(html, encoding='utf-8')
    print(f'Built {destination / "index.html"}')


if __name__ == '__main__':
    main()
