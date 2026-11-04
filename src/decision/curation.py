"""⑧ Curation (docs/PLACE_DECISION.md §12): typed actions and explicit session feedback.
Pure: apply() returns a new State; curation never opens unsolicited questions."""

from functools import cache

from pydantic import ValidationError

from corpus.ontology import load
from .guard import filter_ok
from .session import Drop, Lodging, Pending, SoftAdd, State

REASONS = ("far", "crowded", "pricey", "dislike", "visited")
PLACE_ACTIONS = {"select", "drop", "lock", "unlock", "swap", "relax", "wishlist", "move_chunk", "like"}


class ActionError(ValueError):
    """The action is malformed or does not fit the session; nothing changed."""


@cache
def _ontology():
    return load()


def _select(s: State, pid: str) -> None:
    if pid not in s.selected:
        s.selected.append(pid)
    s.dropped = [d for d in s.dropped if d.place_id != pid]
    s.wishlist = [w for w in s.wishlist if w != pid]


def _remove(s: State, pid: str) -> None:
    s.chunk_assignments.pop(pid, None)
    s.selected = [x for x in s.selected if x != pid]
    s.locked = [x for x in s.locked if x != pid]


def _feedback(s: State, reason: str | None, pid: str | None, cfg) -> None:
    p = s.profile
    if reason == "far":
        p.travel_mult = max(cfg.travel_mult_min, round(p.travel_mult * cfg.far_step, 3))
    elif reason == "crowded":
        p.crowd_tolerance = "avoid"
    elif reason == "pricey":
        p.price_sensitivity = round(p.price_sensitivity + cfg.price_step, 3)
    elif reason == "visited" and pid and pid not in p.visited:
        p.visited.append(pid)


def apply(state: State, act: dict, known, alternatives: dict[str, list[str]], pending: Pending | None, cfg) -> State:
    t, pid = act.get("type"), act.get("place_id")
    if t in PLACE_ACTIONS and not (isinstance(pid, str) and known(pid)):
        raise ActionError(f"unknown place {pid!r}")
    s = state.model_copy(deep=True)
    if t != "answer":
        s.suggest_group = None
    if t == "select":
        _select(s, pid)
    elif t == "move_chunk":
        if pid not in s.selected:
            raise ActionError("choose the place before moving it")
        s.chunk_assignments[pid] = act["chunk"]
    elif t == "keep_free_time":
        s.free_time = True
    elif t == "set_lodging":
        try:
            s.lodging = Lodging.model_validate(act.get("lodging"))
        except ValidationError as e:
            raise ActionError(f"bad lodging: {e.errors()[0]['msg']}") from None
    elif t == "clear_lodging":
        s.lodging = None
    elif t == "lock":
        _select(s, pid)
        if pid not in s.locked:
            s.locked.append(pid)
    elif t == "unlock":
        s.locked = [x for x in s.locked if x != pid]
    elif t == "drop":
        reason = act.get("reason")
        if reason not in (None, *REASONS):
            raise ActionError(f"unknown reason {reason!r}")
        _remove(s, pid)
        s.dropped = [d for d in s.dropped if d.place_id != pid] + [Drop(place_id=pid, reason=reason)]
        _feedback(s, reason, pid, cfg)
    elif t == "swap":
        w = act.get("with_id")
        if w not in alternatives.get(pid, []):
            raise ActionError(f"{w!r} is not an alternative of {pid!r}")
        _remove(s, pid)
        s.dropped = [d for d in s.dropped if d.place_id != pid] + [Drop(place_id=pid)]
        _select(s, w)
    elif t == "relax":
        f = act.get("feature")
        if not isinstance(f, str) or f not in _ontology().features:
            raise ActionError(f"unknown feature {f!r}")
        if (pid, f) not in s.relaxed:
            s.relaxed.append((pid, f))
    elif t == "wishlist":
        _remove(s, pid)
        if pid not in s.wishlist:
            s.wishlist.append(pid)
    elif t == "feedback":
        if act.get("reason") not in ("far", "crowded", "pricey"):
            raise ActionError(f"unknown feedback {act.get('reason')!r}")
        _feedback(s, act["reason"], None, cfg)
    elif t == "prefer":
        f, v, w = act.get("feature"), act.get("value"), act.get("weight")
        if not _ontology().valid(f, v) or w not in (1, -1):
            raise ActionError(f"bad preference {f!r}={v!r} weight {w!r}")
        s.profile.soft = [x for x in s.profile.soft if (x.feature, x.value) != (f, v)] + [SoftAdd(feature=f, value=v, weight=w)]
    elif t == "filter":
        k, v = act.get("key"), act.get("value")
        if not filter_ok(k, v):
            raise ActionError(f"bad filter {k!r}={v!r}")
        if (k, v) not in s.filters:
            s.filters.append((k, v))
    elif t == "unfilter":
        s.filters = []
    elif t == "like":
        if pid not in s.likes:
            s.likes.append(pid)
    elif t == "note":
        phrase_ = (act.get("phrase") or "").strip()
        if not phrase_:
            raise ActionError("empty note")
        s.unmapped.append(phrase_[:120])
    elif t == "answer":
        qid, chip = act.get("qid"), act.get("chip")
        if not pending or qid != pending.qid or chip not in [c.id for c in pending.chips]:
            raise ActionError(f"no open question {qid!r} with chip {chip!r}")
        s.answered.append(qid)
        if qid.startswith("meal:"):
            s.activities[pending.data['place_id']] = 'eating' if chip == 'yes' else 'sightseeing'
        elif qid.startswith("pattern:") and chip == "yes":
            f, v = qid[len("pattern:"):].split("=", 1)
            s.profile.soft.append(SoftAdd(feature=f, value=v, weight=-1))
    else:
        raise ActionError(f"unknown action {t!r}")
    s.last = t
    return s


def pending(state: State, by_id: dict, si, feas: dict, first_shortlist: int, group_of: dict[str, str], cfg) -> Pending | None:
    """Curation never opens unsolicited questions; feedback remains user initiated."""
    return None
