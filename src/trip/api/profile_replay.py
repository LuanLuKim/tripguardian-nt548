"""Replay eval of the long-term profile (docs/TRIP_UNDERSTANDING.md §17): python -m trip profile-replay.

Synthetic personas make many trips in different contexts. Before trip n the profile is built from trips 1..n-1 and
seeds a fresh Trip State (patterns.seed, as Engine.create does); the trip's own acts are applied; the session is
remembered (patterns.summary, as Engine._remember does). Every session is checked against the invariants: only explicit
choices are stored, only active unpaused entries seed, the profile never becomes a constraint, the current trip wins,
every stored vote is visible as an entry, deleting an entry removes its effect, pausing stops all use.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from ..domain.patterns import NEED_SOFT, VOTE_SCALARS, _ballot, entry_id, seed, summary
from ..domain.questions import strictest
from ..domain.state import (Anchor, Evidence, TripState, Update, from_stored_need, apply, apply_drafts, pending_signals,
                            settle)
from ..infrastructure.catalog import Catalog
from ..infrastructure.profile import ProfileStore
from ..infrastructure.settings import PatternSettings

UID = "replay-persona"
EXAMPLES = 5


@dataclass(frozen=True)
class Act:
    """One thing the user does in a trip. how: said (with a quote) | picked (a card) | inferred (a guess, never stored).
    value "@place0" / "@place1" is the catalog's first / second place."""
    field: str
    value: object
    how: str = "said"
    op: str = "set"
    quote: str = ""  # the user's words for a said act


@dataclass(frozen=True)
class Persona:
    name: str
    trips: tuple[tuple[Act, ...], ...]
    start_days_ago: int = 200
    gap_days: int = 20
    days_ago: tuple[int, ...] = ()  # when given: how many days before today each trip happens
    delete_after: dict[int, str] = field(default_factory=dict)  # after trip i, the user deletes entry "key=value"
    pause_after: int | None = None  # after this trip the whole profile is paused for one trip, then resumed


def _trip_facts(i: int) -> tuple[Act, ...]:
    """Facts of one trip only: never stored."""
    return (Act("days", 2 + i % 3, quote=f"đi {2 + i % 3} ngày"), Act("people", 2, quote="hai người"),
            Act("companions", "partner", op="add", quote="đi với người yêu"), Act("month", 1 + i % 12, quote="tháng sau"))


SLOW, PACKED = Act("pace", "slow", quote="đi chậm thôi, không muốn vội"), Act("pace", "packed", quote="đi được nhiều chỗ nhất có thể")
QUIET = Act("soft", ("crowd=high", "avoid"), how="picked", op="add")
VIEW = Act("soft", ("scenic_view=present", "love"), how="picked", op="add")
GUESS = Act("soft", ("scenic_view=present", "love"), how="inferred", op="add")
BIKE = Act("mobility", "motorbike", quote="mình chạy xe máy lên")
KNEE = Act("signal", "knee", op="add", quote="mình hơi đau gối")
VEG = Act("signal", "vegetarian", op="add", quote="mình ăn chay trường")
NOT_VEG = Act("soft", ("vegetarian_options=yes", "avoid"), op="add", quote="giờ mình ăn mặn lại rồi")  # a correction
MOM_KNEE = Act("signal", "knee", op="add", quote="mẹ mình đau gối")  # about someone else: never stored
NEED_FEATURES = {"vegetarian": "vegetarian_options", "vegan": "vegan_options"}
VISITED = Act("visited", "@place0", op="add")
LIKE = Act("anchor", "@place1", how="picked", op="add")

PERSONAS: tuple[Persona, ...] = (
    Persona("steady", tuple((SLOW, QUIET, VIEW, BIKE, *_trip_facts(i)) + ((KNEE, VISITED) if i == 4 else ())
                            for i in range(6))),
    Persona("changer", tuple(((PACKED,) if i < 3 else (SLOW,)) + _trip_facts(i) for i in range(9))),
    Persona("one_off", ((Act("soft", ("hiking=present", "love"), quote="lần này muốn thử trekking"), GUESS, *_trip_facts(0)),
                        *((GUESS, VISITED, *_trip_facts(i)) for i in range(1, 5)))),
    Persona("stale", (*((SLOW, LIKE, *_trip_facts(i)) for i in range(3)), _trip_facts(3)),
            days_ago=(800, 790, 780, 0)),
    Persona("deleter", (*((SLOW, BIKE, *_trip_facts(i)) for i in range(3)), (BIKE, *_trip_facts(3)),
                        *(_trip_facts(i) for i in range(4, 6))), delete_after={3: "pace=slow"}),
    Persona("contra_now", (*((SLOW, QUIET, *_trip_facts(i)) for i in range(3)), (PACKED, *_trip_facts(3)),
                           (PACKED, *_trip_facts(4))), pause_after=1),
    Persona("dieter", ((VEG, *_trip_facts(0)), *(_trip_facts(i) for i in range(1, 5))),
            delete_after={3: "need:vegetarian=yes"}),
    Persona("corrector", ((VEG, *_trip_facts(0)), (NOT_VEG, *_trip_facts(1)), *(_trip_facts(i) for i in range(2, 4)))),
    Persona("carer", ((MOM_KNEE, *_trip_facts(0)), *(_trip_facts(i) for i in range(1, 3)))),
)


def _day(p: Persona, i: int, today: date) -> date:
    if p.days_ago:
        return today - timedelta(days=p.days_ago[i])
    return today - timedelta(days=p.start_days_ago) + timedelta(days=i * p.gap_days)


def _value(v, catalog: Catalog):
    if isinstance(v, str) and v.startswith("@place"):
        return catalog.places[int(v[6:])].id
    return v


def _apply(state: TripState, act: Act, catalog: Catalog, turn: int) -> TripState:
    value = _value(act.value, catalog)
    if act.field == "anchor":
        value = Anchor(text=catalog.by_id[value].name, place_id=value, state="matched", priority="want")
    ev = Evidence(turn=turn, quote=act.quote or f"lời người dùng {turn}") if act.how == "said" else Evidence(turn=turn, tool="chip:x")
    return apply(state, Update(field=act.field, op=act.op, value=value, source="inferred" if act.how == "inferred"
                               else "user", confidence="low" if act.how == "inferred" else "high", evidence=ev))


def _explicit_key(act: Act, catalog: Catalog) -> tuple[str, str] | None:
    """The vote an act may make: only explicit choices of a voted field (or a place picked)."""
    if act.how == "inferred":
        return None
    if act.field in VOTE_SCALARS:
        return act.field, _ballot(act.value)
    if act.field == "soft":
        return f"soft:{act.value[0]}", act.value[1]
    if act.field == "anchor":
        return f"place:{_value(act.value, catalog)}", "love"
    if act.field == "signal" and act.how == "said":
        return f"need:{act.value}", "yes"
    return None


def _seeded(state: TripState) -> list[str]:
    out = [f"{name}={_ballot(f.value)}" for name in VOTE_SCALARS if (f := getattr(state, name)).known
           and f.source == "profile"]
    out += [f"soft:{k}={f.value}" for k, f in state.soft.items() if f.source == "profile" and not from_stored_need(f)]
    out += [f"{k}=yes" for k in state.meta.prior if k.startswith("need:")]  # a need's prior (or only held)
    return sorted(out + [f"{k}=love" for k in state.meta.prior if k.startswith("place:")])  # offered, never put in


class _Check:
    def __init__(self):
        self.checked, self.failed, self.examples = 0, 0, []

    def __call__(self, ok: bool, example: str) -> None:
        self.checked += 1
        if not ok:
            self.failed += 1
            if len(self.examples) < EXAMPLES:
                self.examples.append(example)


def _constraints_from_profile(state: TripState) -> list[str]:
    bad = [f"hard:{h.feature}" for h in state.hard if any((e.tool or "").startswith("profile:") for e in h.evidence)]
    bad += [f"signal:{s.kind}" for s in state.signals if s.source == "profile"]
    bad += [f"anchor:{a.text}" for a in state.anchors if a.place_id and f"place:{a.place_id}" in state.meta.prior]
    bad += [name for name in VOTE_SCALARS if (f := getattr(state, name)).source == "profile" and f.locked]
    return bad


def _delete_and_pause(store: ProfileStore, root: Path, uid: str, today: date, catalog: Catalog, cfg: PatternSettings,
                      deleted: _Check, paused: _Check) -> None:
    """On a copy of the profile: deleting each entry leaves no vote, quote or prior of it; pausing leaves no prior."""
    src = root / f"{uid}.json"
    if not src.exists():
        return
    for e in store.entries(uid, today)[1]:
        work = root / "work"
        work.mkdir(exist_ok=True)
        shutil.copy(src, work / src.name)
        copy = ProfileStore(work, cfg)
        copy.delete(uid, e.id)
        raw = json.loads((work / src.name).read_text(encoding="utf-8"))
        left = [s for s in raw["sessions"] if s["votes"].get(e.key) == e.value]
        state = seed(TripState(), copy.patterns(uid, today), catalog, cfg)
        gone = not left and f"{e.key}={e.value}" not in _seeded(state) and e.id not in raw["edits"] \
            and e.id not in raw["flags"] and all(x.id != e.id for x in copy.entries(uid, today)[1])
        deleted(gone, f"{uid}: {e.key}={e.value} still there after delete")
        copy.pause(uid, True)
        paused(seed(TripState(), copy.patterns(uid, today), catalog, cfg) == seed(TripState(), [], catalog, cfg),
               f"{uid}: a paused profile still seeds")
        shutil.rmtree(work)


def replay(personas, *, cfg: PatternSettings, catalog: Catalog, today: date, root: Path) -> dict:
    checks = {name: _Check() for name in ("explicit_only", "only_used_entries_seed", "no_constraint_from_profile",
                                          "current_trip_wins", "every_vote_visible", "delete_removes_effect",
                                          "pause_stops_use", "need_is_silent_prior")}
    out: dict = {"personas": {}}
    priors = hits = overridden = sessions = 0
    for p in personas:
        uid = f"{UID}-{p.name.replace('_', '-')}"
        store = ProfileStore(root, cfg)
        store.forget(uid) if (root / f"{uid}.json").exists() else None
        seeded_log, need_filter = [], []
        for i, acts in enumerate(p.trips):
            day = _day(p, i, today)
            found = store.patterns(uid, day)
            used = {f"{e.key}={e.value}" for e in store.entries(uid, day)[1] if e.used}
            state = seed(TripState(), found, catalog, cfg)
            seeded = _seeded(state)
            seeded_log.append(seeded)
            checks["only_used_entries_seed"](set(seeded) <= used, f"{p.name} trip {i}: seeded {set(seeded) - used}")
            for turn, act in enumerate(acts, 1):
                state = _apply(state, act, catalog, turn)
            state = settle(state)
            if pending_signals(state):  # Next: an open health / diet hint gets its strictest answer (Engine._show)
                state = settle(apply_drafts(state, strictest(state), len(acts) + 1, tool="next:strictest"))
            feats = {h.feature for h in state.hard}
            for key in (k for k in state.meta.prior if k.startswith("need:")):
                kind, said = key[5:], any(a.field == "signal" and a.value == key[5:] and a.how == "said" for a in acts)
                has = any(x.kind == kind for x in state.signals) or NEED_FEATURES.get(kind) in feats
                prior = all(f"{k}" in state.soft and (state.soft[k].source == "profile" or any(
                    a.field == "soft" and a.value[0] == k for a in acts)) for k, _ in NEED_SOFT.get(kind, ()))
                checks["need_is_silent_prior"](has == said and prior, f"{p.name} trip {i}: need {kind} signal/filter={has}, said={said}")
            need_filter.append(bool(feats & set(NEED_FEATURES.values())))
            checks["no_constraint_from_profile"](not _constraints_from_profile(state),
                                                 f"{p.name} trip {i}: {_constraints_from_profile(state)}")
            explicit = {k for a in acts if (k := _explicit_key(a, catalog))}
            for kind, softs in NEED_SOFT.items():  # a correction of a stored need: the opposite where its prior sits
                if f"need:{kind}" in state.meta.prior and any(a.field == "soft" and a.how != "inferred" and a.value[0] == softs[0][0]
                                                              and a.value[1] != softs[0][1] for a in acts):
                    explicit.add((f"need:{kind}", "no"))
            for k, v in explicit:
                if k.startswith(("place:", "need:")):
                    continue
                now = state.soft.get(k[5:]) if k.startswith("soft:") else getattr(state, k)
                ok = now is not None and now.source == "user" and (now.value == v if k.startswith("soft:")
                                                                  else _ballot(now.value) == v)
                checks["current_trip_wins"](ok, f"{p.name} trip {i}: {k}={v} not kept")
            for s in seeded:
                priors += 1
                said = next((v for k, v in explicit if s.startswith(f"{k}=")), None)
                hits += said is not None and s.endswith(f"={said}")
                overridden += said is not None and not s.endswith(f"={said}")
            done = summary(state, f"{p.name}-{i}", day)
            stored = {(k, v) for k, v in (done.votes.items() if done else ())}
            checks["explicit_only"](stored <= explicit, f"{p.name} trip {i}: stored {stored - explicit}")
            if done:
                store.record(uid, done)
            sessions += 1
            listed = {(e.key, e.value) for e in store.entries(uid, day)[1]}
            votes = {(k, v) for s in store.history(uid) for k, v in s.votes.items()}
            checks["every_vote_visible"](votes <= listed, f"{p.name} trip {i}: hidden {votes - listed}")
            if i in p.delete_after:
                key, _, value = p.delete_after[i].partition("=")
                store.delete(uid, entry_id(key, value))
            if p.pause_after is not None and i in (p.pause_after, p.pause_after + 1):
                store.pause(uid, i == p.pause_after)
        end = _day(p, len(p.trips) - 1, today)
        _delete_and_pause(store, root, uid, end, catalog, cfg, checks["delete_removes_effect"], checks["pause_stops_use"])
        out["personas"][p.name] = {"seeded": seeded_log, "need_filter": need_filter,
                                   "final": {f"{e.key}={e.value}": e.status for e in store.entries(uid, end)[1]}}
    out["invariants"] = {k: {"checked": c.checked, "failed": c.failed, "examples": c.examples} for k, c in checks.items()}
    out["ok"] = all(c.failed == 0 and c.checked > 0 for c in checks.values())
    out["metrics"] = {"sessions": sessions, "priors": priors,
                      "prior_hit": round(hits / priors, 3) if priors else 0.0,
                      "prior_overridden": round(overridden / priors, 3) if priors else 0.0}
    return out
