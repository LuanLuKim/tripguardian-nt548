"""Long-term pattern learning (docs/TRIP_UNDERSTANDING.md §17): which explicit choices a user keeps making.

A vote is one explicit choice made in one session. Silence is no vote (unknown is not "dislike"), a visited place is no
vote (visited is not "liked"), a value the user only confirmed from a stored pattern is no vote (no feedback loop), and
signals about health or the body, hard limits and trip facts are never voted on. Pure functions; storage is profile.py.

The votes are shown to the user as profile entries (like ChatGPT memory): one per (key, value), with a Vietnamese
statement, its evidence and a status. Entries are derived from the stored votes on every read, so deleting an entry's
votes deletes the entry and every effect it had.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from typing import Literal

from pydantic import ValidationError

from ..infrastructure.catalog import Catalog
from ..infrastructure.settings import PatternSettings
from . import values
from .state import Base, Evidence, Frozen, SoftKey, TripState, Update, apply, ontology, with_meta

# What a user keeps choosing the same way becomes a prior, so later trips ask less: the tastes, and how they arrive
# (vehicle, mode, home city), what they spend and the hours they want. origin is voted as JSON of its Base.
VOTE_SCALARS = ("purpose", "pace", "crowd_tolerance", "novelty", "mobility", "arrival_mode", "origin", "budget_vnd",
                "checkin_at", "checkout_at")
QUOTE_MAX = 120  # characters of the user's words kept as evidence
How = Literal["said", "picked", "acted"]  # said: a field with the user's quote (code-checked); picked: a chip, card or
# place; acted: weak evidence from what the user did in Decision / Planning (kept in a plan, rated a stop, dropped it)
KEPT = "kept"  # a place kept in a confirmed plan: neutral, never love
ACTED_WEIGHT = 0.5  # an acted vote counts half a session toward min_sessions / agreement: it never activates alone fast
Kind = Literal["taste", "habit", "need", "avoid", "practical"]  # need: health / body / diet the user said about themselves
EntryStatus = Literal["candidate", "active", "weak", "retired"]
KIND = {"purpose": "taste", "pace": "habit", "crowd_tolerance": "habit", "novelty": "habit", "checkin_at": "habit",
        "checkout_at": "habit", "mobility": "practical", "arrival_mode": "practical", "origin": "practical",
        "budget_vnd": "practical"}
# needs a user may say about themselves (owner 2026-10-28). kids / elderly describe who goes on this trip, pregnant passes.
NEED_KINDS = frozenset({"knee", "wheelchair", "motion_sick", "height", "vegetarian", "vegan"})
NEED_LABEL = {"knee": "Có lưu ý về đầu gối", "wheelchair": "Đi xe lăn", "motion_sick": "Dễ say xe", "height": "Sợ độ cao",
              "vegetarian": "Ăn chay", "vegan": "Ăn chay thuần"}
# The soft prior a stored need puts in a trip (source "profile"; this trip's words replace it). A need with no ontology
# feature (wheelchair, motion_sick, height) has no effect until the user says it in this trip.
NEED_SOFT = {"knee": (("steep_or_stairs=present", "avoid"), ("long_walk=present", "avoid")),
             "vegetarian": (("vegetarian_options=yes", "love"),), "vegan": (("vegan_options=yes", "love"),)}
# words naming someone else: a need said about them is theirs, not the user's, so it is never stored (fail closed)
OTHER_PERSON = re.compile(r"\b(mẹ|bố|ba|bà|má|cha|ông|con|cháu|vợ|chồng|bạn|người yêu|em bé|bé|gia đình|cả nhà|"
                          r"người già|trẻ|anh ấy|chị ấy|cô ấy|em ấy|họ)\b")
CARD_PICKS = ("deck:", "chip:")  # what a card the user answered leaves in Signal.quote (next: / the app's own are no pick)
TOOL = re.compile(r"^[a-z_]+:\S*$")  # what Signal.quote holds when no words of the user came with it (a card, Next)


class Summary(Frozen):
    """What one finished session voted for: key -> choice. Keys: a scalar field name, soft:<feature=value>, place:<id>.
    how / quotes: how each vote was made and the user's words for a said one (files written before them have none)."""
    sid: str
    day: date
    votes: dict[str, str]
    how: dict[str, How] = {}
    quotes: dict[str, str] = {}


class Pattern(Frozen):
    key: str
    value: str
    sessions: int
    confidence: Literal["low", "medium", "high"]  # low: only card picks / acts so far
    last: date
    quote: str | None = None  # the user's latest words for it


class Proof(Frozen):
    """One piece of an entry's evidence: the session that voted for it."""
    session_id: str
    how: How
    quote: str | None = None
    date: date


class Edit(Frozen):
    """What the user changed on an entry: their own wording, or a pause. Any edit wins every rule below."""
    statement: str | None = None
    paused: bool = False


class Entry(Frozen):
    """One profile entry. Its signal is (key, value) from the closed set the state takes; statement is for the user."""
    id: str
    kind: Kind
    statement: str
    key: str
    value: str
    evidence: tuple[Proof, ...]
    against: int  # sessions after its last vote that chose another value for the key
    status: EntryStatus
    strength: float
    first_seen: date
    last_seen: date
    user_edited: bool = False
    paused: bool = False
    flag: str | None = None  # the Judge's verdict when it found the entry unfounded

    @property
    def used(self) -> bool:
        """Only an active, unpaused entry becomes a prior."""
        return self.status == "active" and not self.paused


def _fresh(f) -> bool:
    """Said or chosen in this session, not a stored pattern the user only kept."""
    return f.source == "user" and not any((e.tool or "").startswith("chip:prior") for e in f.evidence)


def _how(f) -> tuple[How, str | None]:
    quote = next((e.quote for e in reversed(f.evidence) if e.quote), None)
    return ("said", quote.strip()[:QUOTE_MAX]) if quote else ("picked", None)


def observe(state: TripState) -> dict[str, tuple[str, How, str | None]]:
    """The session's explicit choices: key -> (value, how, quote). Never a guess, an unknown, a visited place, a health
    or body signal, a hard limit or a fact of only this trip (dates, days, people, who goes)."""
    out: dict[str, tuple[str, How, str | None]] = {}
    for name in VOTE_SCALARS:
        f = getattr(state, name)
        if f.known and _fresh(f):
            out[name] = (_ballot(f.value), *_how(f))
    for key, f in state.soft.items():
        if f.value in ("love", "avoid") and _fresh(f):
            out[f"soft:{key}"] = (f.value, *_how(f))
    offered = set(state.meta.prior)
    for a in state.anchors:
        if a.state == "matched" and a.place_id and f"place:{a.place_id}" not in offered:
            out[f"place:{a.place_id}"] = ("love", "picked", None)
    for s in state.signals:  # only the user's own words about themselves; never a card, a guess or someone else
        quote = s.quote.strip()
        if s.source != "user" or s.kind not in NEED_KINDS or s.from_companion is not None or not quote:
            continue
        if not TOOL.match(quote):
            if not OTHER_PERSON.search(quote.lower()):
                out[f"need:{s.kind}"] = ("yes", "said", quote[:QUOTE_MAX])
        elif quote.startswith(CARD_PICKS):  # the user picked it on a card: a low-confidence prior (owner 2026-10-29)
            out[f"need:{s.kind}"] = ("yes", "picked", None)
    for kind, softs in NEED_SOFT.items():  # a correction: the user put the opposite where the stored need had its prior
        f = state.soft.get(softs[0][0])
        if f is not None and f"need:{kind}" in state.meta.prior and _fresh(f) and f.value != softs[0][1]:
            out[f"need:{kind}"] = ("no", *_how(f))
    return out


def votes_from_state(state: TripState) -> dict[str, str]:
    return {k: v for k, (v, _, _) in observe(state).items()}


def summary(state: TripState, sid: str, day: date) -> Summary | None:
    seen = observe(state)
    if not seen:
        return None
    return Summary(sid=sid, day=day, votes={k: v for k, (v, _, _) in seen.items()},
                   how={k: h for k, (_, h, _) in seen.items()}, quotes={k: q for k, (_, _, q) in seen.items() if q})


def acted_statement(key: str, value: str, catalog: Catalog | None = None) -> str:
    """A place entry made only of acts: kept in a plan is not "liked", so it never reads "Thích …"."""
    p = catalog.by_id.get(key[6:]) if catalog is not None else None
    name = p.name if p else "một nơi"
    return {"kept": f"Đã giữ {name} trong lịch", "love": f"Bạn chấm hợp {name}"}.get(value, f"Đã bỏ hoặc chấm không hợp {name}")


def acts_votes(acts: list[dict]) -> dict[str, str]:
    """Weak votes from Decision / Planning acts, in order (a later act on a place replaces an earlier one):
    kept_in_plan -> "kept" (neutral: kept or visited is not liked; it never counts for or against a place's love and
    never replaces a rating); rated_hop 1 / -1 -> love / avoid (an explicit rating); dropped -> avoid ONLY when the user
    gave the reason "dislike" (a drop for time, distance or no reason says nothing about taste). These votes never
    reach a hard filter."""
    out: dict[str, str] = {}
    for a in acts:
        pid, kind = a.get("place_id"), a.get("kind")
        if not pid:
            continue
        key = f"place:{pid}"
        if kind == "kept_in_plan":
            out.setdefault(key, "kept")
        elif kind == "rated_hop" and a.get("value") in (1, -1) and not isinstance(a.get("value"), bool):
            out[key] = "love" if a["value"] == 1 else "avoid"
        elif kind == "dropped" and a.get("reason") == "dislike":
            out[key] = "avoid"
    return out


def entry_id(key: str, value: str) -> str:
    return hashlib.sha1(f"{key}\n{value}".encode()).hexdigest()[:12]


def _label(feature: str, value: str) -> str:
    """A short Vietnamese label of a feature value, cut from the ontology's hint ("low: vắng, ít khách; ...")."""
    f = ontology().features.get(feature)
    if f is None:
        return f"{feature} = {value}"
    if value == "present":
        text = (f.claims.get("present") or f.hint).split(":")[0]
    else:
        m = re.search(rf"(?:^|;)\s*{re.escape(value)}:\s*([^;]+)", f.hint)
        parts = f.hint.split(" / ")  # "đồ ăn ngon / bình thường / dở": one part per value, the first names the thing
        if m:
            text = m[1]
        elif len(parts) == len(f.values) and value in f.values:
            i = f.values.index(value)
            text = parts[0] if i == 0 else f"{parts[0].rsplit(' ', 1)[0]} {parts[i]}"
        else:
            text = f"{feature} {value}"
    text = re.split(r"[.(\"“]", text)[0]
    return ", ".join(p.strip() for p in text.split(",")[:2]).strip(" ,") or feature


PURPOSE = {"relax": "Thích chuyến đi để thư giãn", "bond": "Hay đi để gắn kết với người đi cùng",
           "photo": "Thích đi để chụp ảnh", "food_culture": "Thích khám phá ẩm thực, văn hoá",
           "nature": "Thích thiên nhiên", "explore": "Thích khám phá nơi mới", "adventure": "Thích trải nghiệm mạo hiểm"}
SAY = {"pace": {"slow": "Thích đi nhịp chậm, thong thả", "normal": "Thích nhịp đi vừa phải",
                "packed": "Thích lịch dày, đi được nhiều nơi"},
       "crowd_tolerance": {"avoid": "Tránh chỗ đông người", "ok_if_worth": "Chịu đông nếu nơi đó đáng đi",
                           "fine": "Không ngại chỗ đông"},
       "novelty": {"familiar": "Thích nơi quen thuộc, nổi tiếng", "new": "Thích nơi mới, ít người biết",
                   "mix": "Thích vừa nơi quen vừa nơi mới"},
       "mobility": {"motorbike": "Thường đi lại bằng xe máy", "car": "Thường đi lại bằng ô tô",
                    "walk": "Thường không tự lái, đi bộ hoặc gọi xe"},
       "arrival_mode": {"self": "Thường tự đi xe tới", "bus": "Thường đi xe khách tới", "plane": "Thường bay tới"},
       "purpose": PURPOSE}


def statement(key: str, value: str, catalog: Catalog | None = None) -> str:
    if key in SAY:
        return SAY[key].get(value, f"{key}: {value}")
    if key == "origin":
        try:
            return f"Thường xuất phát từ {json.loads(value)['text']}"
        except (ValueError, KeyError, TypeError):
            return "Thường xuất phát từ một nơi đã chọn"
    if key == "budget_vnd":
        return f"Mức ngân sách quen khoảng {int(value):,} đ".replace(",", ".") if value.isdigit() else "Mức ngân sách quen"
    if key == "checkin_at":
        return f"Thường bắt đầu ngày đầu lúc {value}"
    if key == "checkout_at":
        return f"Thường xong ngày cuối lúc {value}"
    if key.startswith("need:"):
        return NEED_LABEL.get(key[5:], key[5:])
    if key.startswith("place:"):
        p = catalog.by_id.get(key[6:]) if catalog is not None else None
        return f"Thích {p.name}" if p else "Thích một nơi đã chọn"
    if key.startswith("soft:"):
        try:
            k = SoftKey.parse(key[5:])
        except ValueError:
            return key[5:]
        return f"{'Tránh' if value == 'avoid' else 'Thích'}: {_label(k.feature, k.value)}"
    return f"{key}: {value}"


def _kind(key: str, value: str) -> Kind:
    if key.startswith("need:"):
        return "need"
    if key.startswith("soft:"):
        return "avoid" if value == "avoid" else "taste"
    return "taste" if key.startswith("place:") else KIND.get(key, "taste")


def entries(history: list[Summary], *, cfg: PatternSettings, today: date, edits: dict[str, Edit] | None = None,
            flags: dict[str, str] | None = None, catalog: Catalog | None = None) -> list[Entry]:
    """Every (key, value) a stored session voted for, with its status:
    an edit by the user -> active (paused: kept, not used); a Judge flag -> weak; last vote older than stale_days, two
    later sessions choosing otherwise, or out of the key's latest `window` votes -> retired; one later session choosing
    otherwise -> weak; at least min_sessions of the window and `agreement` of it -> active; else candidate."""
    edits, flags = edits or {}, flags or {}
    by_key: dict[str, list[tuple[date, str, Summary]]] = {}
    for s in sorted(history, key=lambda s: (s.day, s.sid)):
        for key, value in s.votes.items():  # "kept" is neutral: its own series, never for or against a love / avoid
            by_key.setdefault(f"{key}\n{value}" if value == KEPT else key, []).append((s.day, value, s))

    def fade(day: date) -> float:
        return 0.5 ** (max(0, (today - day).days) / cfg.half_life_days)

    out = []
    for series, votes in by_key.items():
        key = series.split("\n")[0]
        window = votes[-cfg.window:]

        def weight(s: Summary) -> float:
            return ACTED_WEIGHT if s.how.get(key) == "acted" else 1.0
        total = sum(weight(s) for _, _, s in window)
        for value in dict.fromkeys(v for _, v, _ in votes):
            support = [(d, s) for d, v, s in votes if v == value]
            last = support[-1][0]
            end = max(i for i, (_, v, _) in enumerate(votes) if v == value)
            after = [d for d, v, _ in votes[end + 1:] if v != value]
            n = sum(weight(s) for _, v, s in window if v == value)
            eid = entry_id(key, value)
            edit, flag = edits.get(eid), flags.get(eid)
            if edit is not None:
                status = "active"
            elif flag:
                status = "weak"
            elif (today - last).days > cfg.stale_days or len(after) >= 2 or n == 0:
                status = "retired"
            elif after:
                status = "weak"
            elif all(sm.how.get(key) == "acted" for _, sm in support):
                status = "candidate"  # only what the user did, never what they said or picked: shown, never used
            elif key.startswith("need:") or (n >= cfg.min_sessions and n / total >= cfg.agreement):
                status = "active"  # a need the user said is active at once; it is only ever asked back
            else:
                status = "candidate"
            said = next((s.quotes[key] for _, s in reversed(support) if s.quotes.get(key)), None)
            if key.startswith("need:") and value == "no":  # a correction of a stored need
                own = f"Không còn: {NEED_LABEL.get(key[5:], key[5:]).lower()}" + (f". Bạn nói: “{said}”" if said else "")
            elif key.startswith("place:") and all(sm.how.get(key) == "acted" for _, sm in support):
                own = acted_statement(key, value, catalog)
            else:
                own = f"Bạn từng nói: “{said}”" if key.startswith("need:") and said else statement(key, value, catalog)
            out.append(Entry(
                id=eid, kind=_kind(key, value),
                statement=(edit.statement if edit and edit.statement else own),
                key=key, value=value,
                evidence=tuple(Proof(session_id=s.sid, how=s.how.get(key, "picked"), quote=s.quotes.get(key), date=d)
                               for d, s in support),
                against=len(after), status=status,
                strength=round(sum(fade(d) for d, _ in support) - sum(fade(d) for d in after), 3),
                first_seen=support[0][0], last_seen=last, user_edited=edit is not None,
                paused=bool(edit and edit.paused), flag=flag))
    return sorted(out, key=lambda e: (e.kind, -len(e.evidence), e.key, e.value))


def _ballot(value) -> str:
    if isinstance(value, Base):
        return json.dumps({k: v for k, v in value.model_dump().items() if k in ("text", "lat", "lng", "province") and v is not None},
                          ensure_ascii=False, sort_keys=True)
    return str(value)


def _prior(key: str, raw: str, catalog: Catalog):
    """The value of a stored vote, as the state field takes it."""
    return Base(**json.loads(raw)) if key == "origin" else values.parse(key, raw, catalog)


def detect(history: list[Summary], cfg: PatternSettings, today: date, edits: dict[str, Edit] | None = None,
           flags: dict[str, str] | None = None) -> list[Pattern]:
    """The used entries as patterns: the same choice in at least min_sessions distinct sessions, at least `agreement`
    of the key's window, the most recent vote still that choice (or an entry the user edited), not paused, not flagged."""
    return patterns_of(entries(history, cfg=cfg, today=today, edits=edits, flags=flags), cfg)


def _confidence(e: Entry, cfg: PatternSettings) -> str:
    if all(p.how != "said" for p in e.evidence) and e.key.startswith("need:") and not e.user_edited:
        return "low"  # a need only picked on a card: a guess-grade prior
    return "high" if len(e.evidence) >= 2 * cfg.min_sessions else "medium"


def patterns_of(found: list[Entry], cfg: PatternSettings) -> list[Pattern]:
    out = [Pattern(key=e.key, value=e.value, sessions=len(e.evidence), last=e.last_seen,
                   confidence=_confidence(e, cfg),
                   quote=next((p.quote for p in reversed(e.evidence) if p.quote), None))
           for e in found if e.used]
    return sorted(out, key=lambda p: (-p.sessions, p.key))


def seed(state: TripState, found: list[Pattern], catalog: Catalog, cfg: PatternSettings) -> TripState:
    """Patterns become priors: source "profile", shown with ✎, and replaced by anything the current trip says.
    meta.prior lists the stored keys that were put in the state or only held (a place, a need with no feature)."""
    keys: list[str] = []
    places = 0
    for p in found:
        ev = Evidence(turn=0, tool=f"profile:{p.key}")
        try:
            if p.key in VOTE_SCALARS:
                state = apply(state, Update(field=p.key, value=_prior(p.key, p.value, catalog), source="profile",
                                            confidence=p.confidence, evidence=ev))
            elif p.key.startswith("soft:"):
                state = apply(state, Update(field="soft", op="add", value=(p.key[5:], p.value), source="profile",
                                            confidence=p.confidence, evidence=ev))
            elif p.key.startswith("place:") and p.value == "love" and p.key[6:] in catalog.by_id \
                    and places < cfg.max_places:
                places += 1  # offered on the card only: a stored place is never put in the trip unasked
            elif p.key.startswith("need:") and p.value == "yes" and p.key[5:] in NEED_KINDS:
                # a prior, never a signal or a hard filter: only what this trip says can limit the plan
                for soft_key, soft_value in NEED_SOFT.get(p.key[5:], ()):
                    state = apply(state, Update(field="soft", op="add", value=(soft_key, soft_value), source="profile",
                                                confidence=p.confidence, evidence=ev))
            else:
                continue
        except (ValueError, TypeError, ValidationError):  # a value the ontology (or a field) no longer knows
            continue
        keys.append(p.key)
    return with_meta(state, prior=tuple(keys))


def seed_profile(state: TripState, profile: dict) -> TripState:
    """Account profile fields (docs/ACCOUNTS.md) as priors: source "profile", replaced by anything this trip says.
    Only values Trip knows are used; anything else in the profile is ignored."""
    ev = Evidence(turn=0, tool="profile:account")
    for field, value, op in (("mobility", profile.get("usual_mobility"), "set"),
                             ("companions", profile.get("usual_companions"), "add")):
        if not value:
            continue
        try:
            state = apply(state, Update(field=field, op=op, value=value, source="profile", confidence="medium",
                                        evidence=ev))
        except (ValueError, ValidationError):
            continue
    home = profile.get("home")  # {"text", "lat", "lng", "province"?}: home_city resolved by the caller (Trip never imports live)
    if isinstance(home, dict) and home.get("text") and state.origin.value is None:
        try:
            state = apply(state, Update(field="origin", value=Base(text=home["text"], lat=home.get("lat"), lng=home.get("lng"),
                                                                   province=home.get("province"), kind="address"),
                                        source="profile", confidence="medium", evidence=ev))
        except (ValueError, ValidationError):
            pass
    return state
