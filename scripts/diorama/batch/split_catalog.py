"""Split kits/README.md into kits/catalog/<kit>.md so a place run reads only the kit it uses, not the whole catalogue."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from paths import CODE

import re

parts = re.split(r"^## ", (CODE / "kits" / "README.md").read_text(), flags=re.M)
out = CODE / "kits" / "catalog"
out.mkdir(exist_ok=True)
for part in parts[1:]:
    name = part.split("\n", 1)[0].strip().split()[0]
    (out / f"{name}.md").write_text("## " + part)
    print(name, len(part))
