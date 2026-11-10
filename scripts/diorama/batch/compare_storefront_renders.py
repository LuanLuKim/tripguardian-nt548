"""Đối chiếu hai lượt render Gạch; ghi số đo, không tự miễn sai lệch animation."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from paths import DATA

import json
import numpy as np
from PIL import Image

root = DATA
baseline, current = 'ksfbasegach1988', 'ksfgach1988reg'
before = {p.name: p for p in (root / 'bridge' / 'out' / baseline).glob('*.png')}
after = {p.name: p for p in (root / 'bridge' / 'out' / current).glob('*.png')}
assert before and before.keys() == after.keys(), 'Hai bộ ảnh phải có cùng view'
rows = []
for name in sorted(before):
    a = np.asarray(Image.open(before[name]).convert('RGB'), dtype=np.int16)
    b = np.asarray(Image.open(after[name]).convert('RGB'), dtype=np.int16)
    assert a.shape == b.shape, name
    delta = np.abs(a - b)
    row = {'view': name, 'mean_abs': float(delta.mean()), 'max_abs': int(delta.max()),
           'changed_pixel_fraction': float(np.any(delta > 0, axis=2).mean())}
    rows.append(row)
    print(name, 'mean=', round(row['mean_abs'], 6), 'max=', row['max_abs'])
destination = root / 'out_gach1988' / 'storefront-regression.json'
destination.write_text(json.dumps({'baseline': baseline, 'current': current, 'views': rows}, indent=2) + '\n')
print(destination)
