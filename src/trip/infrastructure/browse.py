"""Tag -> subtag reads (docs/PLACE_DECISION.md §Tag và subtag): the places a broad ask matches, split into a few named
groups by corpus.tags, and one tag's own places for the home page. Reads published data only; every list has passed the
trip's hard filters (fail-closed) and the places the user hid. Nothing here picks a place the corpus does not hold."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Sequence

from corpus import tags
from corpus.ontology import load as load_ontology
from corpus.retrieval import Criteria

from ..domain import tag_policy as policy
from ..domain.state import TripState
from .reads import FIND_KEYS

if TYPE_CHECKING:
    from .knowledge import Knowledge

POOL = 2000          # places asked of corpus.retrieval before the filters (the whole city when the ask names nothing)
EXAMPLES = 3         # places a subtag names in the model's result
FLAT_KEYS = tuple(k for k in FIND_KEYS if k != "exclude")  # find_places keys a split does not take


class Browse:
    def __init__(self, k: "Knowledge"):
        self.k = k
        self._tags: dict[str, tags.PlaceTags] = {}
        self._tag_revisions: dict[str, tuple] = {}
        self._lock = threading.Lock()

    # ---------- what a place carries ----------

    def place_tags(self, pid: str) -> tags.PlaceTags | None:
        """The tags of one place from its serving record (cached once the style index is ready: a style tag that is
        not read yet is unknown, not absent). None for a place without a record."""
        revision = tags.reader_revision(pid)
        got = self._tags.get(pid)
        if got is not None and self._tag_revisions.get(pid) == revision:
            return got
        record = self.k.retrieval.get_place(pid)
        if not record:
            return None
        looks = self.k.looks
        ready = looks is None or looks.ready()
        out = tags.of_record(record, looks.styles_of(pid) if looks is not None and ready else ())
        if ready:
            with self._lock:
                self._tags[pid] = out
                self._tag_revisions[pid] = revision
        return out

    def warm(self, wait_s: float = 120.0) -> int:
        """Tags of every place once, so the first broad ask or home tag does not pay for them (~10 s). Waits for the style
        index so a style is never cached as missing. -> places cached."""
        if self.k.looks is not None:
            self.k.looks.ready(wait_s)
        for p in self.k.catalog.places:
            self.place_tags(p.id)
        return len(self._tags)

    # ---------- a broad ask -> subtags ----------

    @staticmethod
    def fixed(c: Criteria) -> tags.Fixed:
        """What the criteria already state: no subtag repeats it."""
        known = tags.config()["features"]
        keys = {fid if value == "present" else f"{fid}={value}" for fid, value in (*c.must, *c.prefer)}
        return tags.Fixed(groups=frozenset(c.groups), features=frozenset(k for k in keys if k in known), dish=c.dish)

    def subtags(self, criteria: dict, state: TripState, seen: Sequence[str] = (), picked: Sequence[str] = ()) -> dict:
        """find_places criteria -> {mode, why, total, axis, subtags[{id, label, count, examples}], other, _split}. The ask decides
        the mode (domain/tag_policy): "tags" for a vague one, "subtags" for a named interest with a good split, else "places"
        (the plain list, as find_places, no subtags). seen: signatures of the tags blocks shown before, newest first;
        picked: tag refs the user already opened. ValueError on bad criteria."""
        if not isinstance(criteria, dict):
            raise ValueError("criteria must be an object")
        if bad := sorted(set(criteria) & set(FLAT_KEYS)):
            raise ValueError(f"browse_tags takes the find_places criteria without {bad}: use find_places for those")
        core = {k: v for k, v in criteria.items() if k != "exclude"}
        c = Criteria.parse(core, load_ontology())
        exclude = set(criteria.get("exclude") or ())
        found = self.k.retrieval.find(core, limit=POOL)
        hits = [h for h in found.hits if h.place_id not in exclude and self.k._admissible(h.place_id, state)]
        mode, why = policy.first_pick(policy.dimensions(c.groups, c.must, c.dish, c.text), len(hits))
        fixed = self.fixed(c)
        if mode == "tags":
            return self._kinds(hits, fixed, criteria, state, seen, picked)
        if mode == "places":
            return self._flat(hits, criteria, state, why)
        return self._result(hits, fixed, c.dish, criteria, state, seen)

    @staticmethod
    def _fixed_key(fixed: tags.Fixed) -> str:
        return "+".join([*sorted(fixed.groups), *sorted(fixed.features), *sorted(fixed.styles), *([fixed.dish] if fixed.dish else [])])

    def _flat(self, hits: list, criteria: dict, state: TripState, why: str) -> dict:
        """The plain list: find_places' answer with the count of allowed matches and why no tags are shown."""
        flat = self.k.find(criteria, state)
        ranked = flat.pop("ranked", [])
        return {**flat, "mode": "places", "why": why, "total": len(hits), "subtags": [], "_cards": ranked,
                "note": "no tags or subtags for this ask: the places are shown as one list"}

    def _out(self, level: str, split: tags.Split, placed: list, fixed: tags.Fixed, why: str, title: str | None = None,
             criteria: dict | None = None) -> dict:
        name = lambda pid: self.k.catalog.by_id[pid].name  # noqa: E731
        subs = [{"id": s.id, "label": s.label, "count": s.count,
                 "examples": [{"id": pid, "n": name(pid)} for pid in s.place_ids[:EXAMPLES]]} for s in split.subtags]
        sig = policy.signature(level, self._fixed_key(fixed) + (f"@{title}" if title else ""), [s.id for s in split.subtags])
        return {"mode": level, "why": why, "total": split.total, "axis": split.axis, "subtags": subs,
                "other": split.total - split.covered,
                "_split": {"level": level, "axis": split.axis, "criteria": criteria, "total": split.total, "covered": split.covered, "sig": sig,
                           "ranked": [h.place_id for h, _ in placed][:self.k.cards_max],
                           "subtags": [{"id": s.id, "axis": s.axis, "key": s.key, "label": s.label, "count": s.count,
                                        "place_ids": list(s.place_ids)} for s in split.subtags]}}

    def _kinds(self, hits: list, fixed: tags.Fixed, criteria: dict, state: TripState, seen: Sequence[str], picked: Sequence[str]) -> dict:
        placed = [(h, t) for h in hits if (t := self.place_tags(h.place_id)) is not None]
        split = tags.kinds([t for _, t in placed], picked)
        if split is None:
            return self._flat(hits, criteria, state, "weak_kinds")
        out = self._out("tags", split, placed, fixed, "vague", criteria=criteria)
        if policy.repeated(out["_split"]["sig"], seen):
            return self._flat(hits, criteria, state, "repeat")
        return out

    def _result(self, hits: list, fixed: tags.Fixed, dish: str | None, criteria: dict, state: TripState,
                seen: Sequence[str] = (), title: str | None = None) -> dict:
        placed = [(h, t) for h in hits if (t := self.place_tags(h.place_id)) is not None]
        variants = None
        if dish:
            variants = {t.id: tags.dish_variants(self.k.retrieval.get_place(t.id) or {}, dish) for _, t in placed}
        split = tags.split([t for _, t in placed], fixed, variants)
        if split is None:
            return self._flat(hits, criteria, state, "weak_split")
        out = self._out("subtags", split, placed, fixed, "interest", title, criteria)
        if policy.repeated(out["_split"]["sig"], seen):
            return self._flat(hits, criteria, state, "repeat")
        return out

    # ---------- one tag (home page) ----------

    def tag(self, ref: str, state: TripState) -> dict:
        """One tag's places split into subtags: the same result as `subtags`, with the tag's own label as `tag`.
        ValueError when `ref` is not a tag of config/tags.yaml."""
        resolved = tags.resolve_ref(ref)
        if resolved is None:
            return {"mode": "places", "why": "retired_tag", "total": 0, "subtags": [], "_cards": [],
                    "tag": {"ref": ref, "label": "Gu không còn khả dụng", "count": 0}}
        axis, key = resolved
        ref = tags.ref(axis, key)
        found = self.k.retrieval.find({}, limit=POOL)
        hits = [h for h in found.hits if self.k._admissible(h.place_id, state)]
        mine = [h for h in hits if (t := self.place_tags(h.place_id)) is not None and t.carries(axis, key)]
        fixed, dish = self._fixed_of(axis, key)
        out = self._result(mine, fixed, dish, {}, state, title=ref)
        out["tag"] = {"ref": ref, "axis": axis, "key": key, "label": tags.label(axis, key), "count": len(mine)}
        if not out.get("_split"):  # nothing splits it: the tag's own best places, as one list
            out["_cards"] = [h.place_id for h in mine][:self.k.cards_max]
        return out

    @staticmethod
    def _fixed_of(axis: str, key: str) -> tuple[tags.Fixed, str | None]:
        """What opening one tag fixes, so none of its subtags repeats it -> (Fixed, the dish phrase for a dish tag)."""
        if axis == "category":
            return tags.Fixed(groups=frozenset((key,))), None
        if axis == "experience":
            return tags.Fixed(features=frozenset((key,))), None
        if axis == "style":
            return tags.Fixed(styles=frozenset((key,))), None
        dish = next(d["phrases"][0] for d in tags.config()["dishes"] if d["id"] == key)
        return tags.Fixed(dish=dish), dish

    # ---------- the stage: one node of the tag -> subtag -> place tree ----------

    # Levels above the places: a named interest opens kinds, then the vibes inside one kind ("Săn mây" -> "Quán cà phê
    # săn mây" -> "Quán cà phê kiểu Hàn"); a vague ask has its tags on top of that.
    DEPTH = {"subtags": 2, "tags": 3}

    def stage(self, criteria: dict, state: TripState, path: Sequence[str]) -> dict:
        """One node of the tree a tags block opens (docs/TRIP_UNDERSTANDING.md §19): `criteria` = the block's ask, `path` =
        the refs from the root ("category:cafe", then "style:korean"; "*" = every place of the parent). A node splits
        again on an axis its parents left open while it is above DEPTH of the ask's mode. Read only, the trip's hard
        limits and hidden places apply (fail-closed). -> {label, ids, children}: ids = every place of the node, best
        first; children = [{id, kind: "subtag", label, count, ids}] when the node splits, else None (the node's places
        are the leaves). ValueError when the path is not a node of this ask."""
        if not path:
            raise ValueError("path needs a ref")
        if not isinstance(criteria, dict) or set(criteria) & set(FLAT_KEYS):
            raise ValueError("criteria must be an object of find_places keys")
        core = {k: v for k, v in criteria.items() if k != "exclude"}
        c = Criteria.parse(core, load_ontology())
        exclude = set(criteria.get("exclude") or ())
        found = self.k.retrieval.find(core, limit=POOL)
        hits = [h for h in found.hits if h.place_id not in exclude and self.k._admissible(h.place_id, state)]
        mode, _ = policy.first_pick(policy.dimensions(c.groups, c.must, c.dish, c.text), len(hits))
        if mode not in self.DEPTH:
            raise ValueError("this ask shows a plain list: no tags to open")
        if len(path) > self.DEPTH[mode]:
            raise ValueError(f"path is deeper than this ask's {self.DEPTH[mode]} levels")
        canonical = []
        for node in path:
            resolved = tags.resolve_ref(node)
            if resolved is None and not node.startswith("dish:v:"):
                return {"label": "Gu không còn khả dụng", "ids": [], "children": None}
            canonical.append(tags.ref(*resolved) if resolved else node)
        head, rest = canonical[0], canonical[1:]
        placed = [(h, t) for h in hits if (t := self.place_tags(h.place_id)) is not None]
        if mode == "subtags":  # a named interest: its subtags are the first level
            split = self._result(hits, self.fixed(c), c.dish, criteria, state).get("_split")
            sub = next((s for s in (split or {}).get("subtags", ()) if s["id"] == head), None)
            if sub is None:
                raise ValueError(f"{head!r} is not a subtag of this ask")
            keep = set(sub["place_ids"])
            return self._node(sub["label"], [x for x in placed if x[0].place_id in keep],
                              self._with(self.fixed(c), sub["axis"], sub["key"]), c.dish, rest, 1, self.DEPTH[mode])
        resolved = tags.resolve_ref(head)
        if resolved is None:
            return {"label": "Gu không còn khả dụng", "ids": [], "children": None}
        axis, key = resolved
        fixed, dish = self._fixed_of(axis, key)
        return self._node(tags.label(axis, key), [x for x in placed if x[1].carries(axis, key)], fixed, dish, rest, 1,
                          self.DEPTH[mode])

    def _node(self, label: str, placed: list, fixed: tags.Fixed | None, dish: str | None, rest: Sequence[str],
              depth: int, limit: int) -> dict:
        """The node reached after `depth` refs, or the one `rest` leads to below it. fixed None = no further split."""
        ids = [h.place_id for h, _ in placed]
        if not ids:  # nothing of it passes the trip's limits any more: an empty node, not a broken path
            return {"label": label, "ids": [], "children": None}
        split = None
        if fixed is not None and depth < limit:
            variants = {t.id: tags.dish_variants(self.k.retrieval.get_place(t.id) or {}, dish) for _, t in placed} if dish else None
            split = tags.split([t for _, t in placed], fixed, variants)
        if split is None:
            if rest:
                raise ValueError(f"{label!r} does not split")
            return {"label": label, "ids": ids, "children": None}
        subs = [{"id": s.id, "kind": "subtag", "label": s.label, "count": s.count, "ids": list(s.place_ids)} for s in split.subtags]
        if not rest:
            return {"label": label, "ids": ids, "children": subs}
        sub = next((s for s in split.subtags if s.id == rest[0]), None)
        if sub is None:
            raise ValueError(f"{rest[0]!r} is not a subtag of {label!r}")
        keep = set(sub.place_ids)
        return self._node(sub.label, [x for x in placed if x[0].place_id in keep], self._with(fixed, sub.axis, sub.key),
                          dish, rest[1:], depth + 1, limit)

    @staticmethod
    def _with(fixed: tags.Fixed, axis: str, key: str) -> tags.Fixed | None:
        """`fixed` and the subtag just opened, so its children split on another axis. None: a dish or a dish variant,
        whose places are the leaves."""
        if axis == "category":
            return tags.Fixed(groups=fixed.groups | {key}, features=fixed.features, styles=fixed.styles, dish=fixed.dish)
        if axis == "experience":
            return tags.Fixed(groups=fixed.groups, features=fixed.features | {key}, styles=fixed.styles, dish=fixed.dish)
        if axis == "style":
            return tags.Fixed(groups=fixed.groups, features=fixed.features, styles=fixed.styles | {key}, dish=fixed.dish)
        return None
