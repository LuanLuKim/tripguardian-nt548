"""Season names -> seasons (docs/CORPUS.md §Nhịp). Pages call one season by many names ("vườn hồng", "mùa hồng chín"); the
model groups this month's names and marks those that are no season (a waterfall, the dry weather, "du lịch Đà Lạt"), and
code keeps only what it can check. The result goes in the events snapshot (`season_groups`); corpus.pulse reads it."""

import asyncio
import hashlib
import json
from datetime import date
from pathlib import Path

from ..crawl.common.files import write_json
from ..llm import SEASON_GROUP

MAX_NAMES = 150     # names asked at once (the most pages first): the rest are rare names no page repeats
_LOOSE = {"mua", "hoa", "o", "tai", "doi", "da", "lat", "dalat", "nam", "nay", "va", "vuon", "khu", "canh", "dong", "cay", "trai"}


def _words(name: str) -> set[str]:
    from .gate import fold
    return {w for w in fold(name).split() if w not in _LOOSE}


def check(answer: dict, names: list[dict]) -> dict:
    """{groups[[name]], not_seasons[name]} from the model's numbers: a number that is no name, a name in two groups, a
    group of one, or a member that shares no word with its first name (a group the model made up) is dropped; a name the
    model calls both grouped and no season stays a season of its group."""
    n = len(names)
    valid = lambda i: isinstance(i, int) and 0 <= i < n  # noqa: E731
    used, groups = set(), []
    for g in answer.get("groups") or ():
        members = [i for i in dict.fromkeys(g) if valid(i) and i not in used]
        if len(members) < 2:
            continue
        lead = _words(names[members[0]]["name"])
        members = [members[0]] + [i for i in members[1:] if lead & _words(names[i]["name"])]
        if len(members) >= 2:
            used.update(members)
            groups.append([names[i]["name"] for i in members])
    drop = [names[i]["name"] for i in dict.fromkeys(answer.get("not_seasons") or ()) if valid(i) and i not in used]
    return {"groups": groups, "not_seasons": drop}


def group(names: list[dict], city_name: str, today: date, cache: Path, ask) -> dict | None:
    """The checked groups of `names` ({name, sources, quote} from corpus.pulse.season_names), cached by names and prompt;
    None when the model fails (the night's pulse then keeps config `season.same` alone)."""
    names = names[:MAX_NAMES]
    if len(names) < 2:
        return {"groups": [], "not_seasons": []}
    listing = "\n".join(f'{i}. {x["name"]} ({x["sources"]} trang): {x["quote"]}' for i, x in enumerate(names))
    key = hashlib.sha256(json.dumps([listing, SEASON_GROUP.prompt_hash, today.month, SEASON_GROUP.role.name]).encode()).hexdigest()[:20]
    target = cache / f"{key}.json"
    if target.exists():
        return check(json.loads(target.read_text(encoding="utf-8")), names)
    try:
        answer = asyncio.run(ask(city=city_name, month=today.month, names=listing))
    except Exception as e:  # one failed call must not stop the night: tomorrow asks again
        print(f"events: season grouping failed: {type(e).__name__}", flush=True)
        return None
    write_json(target, answer)
    return check(answer, names)
