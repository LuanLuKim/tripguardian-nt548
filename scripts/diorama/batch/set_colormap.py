"""set_colormap.py <slug> '<json map>' : merge colour swaps into the place file's "colorMap" (null value removes a key).
Keeps the file's own formatting: colorMap lives on one line right after the opening brace."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from paths import DATA

import json
import re

D = DATA
p = D / ("linhson.json" if sys.argv[1] == "linhson" else f"places/{sys.argv[1]}/place.json")
text = p.read_text()


def _pairs(pairs):
    # An older bug inserted a second colorMap line instead of replacing a multi-line one; json keeps the last
    # (stale) map. The inserted map comes first and is the newer one, so it wins over later duplicates.
    out = {}
    for key, value in pairs:
        if key == "colorMap" and key in out:
            out[key] = {**value, **out[key]}
        else:
            out[key] = value
    return out


data = json.loads(text, object_pairs_hook=_pairs)
m = data.get("colorMap", {})
for k, v in json.loads(sys.argv[2]).items():
    if v is None:
        m.pop(k.lower(), None)
    else:
        m[k.lower()] = v.lower()
line = '  "colorMap": ' + json.dumps(m, separators=(",", ":")) + ","
one_line = re.findall(r'^  "colorMap": .*,$', text, re.M)
if len(one_line) == 1 and text.count('"colorMap"') == 1:
    text = re.sub(r'^  "colorMap": .*,$', lambda _: line, text, count=1, flags=re.M)
elif "colorMap" in data:
    # Multi-line or duplicated map: rewrite the file once with a single one-line map first.
    data.pop("colorMap")
    text = "{\n" + line + "\n" + json.dumps(data, ensure_ascii=False, indent=2)[2:] + "\n"
else:
    assert text.startswith("{\n"), "place file must start with '{' on its own line"
    text = "{\n" + line + "\n" + text[2:]
json.loads(text)
p.write_text(text)
print(f"{p.name}: colorMap {len(m)} keys")
