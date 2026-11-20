"""One conversation turn (docs/TRIP_UNDERSTANDING.md §4).

edit / show / theme, a skipped or unsure card and a day picked on a calendar are deterministic. Typing, and choosing an
option the agent wrote, run the agent loop (agent/loop.py): the agent records facts, then asks a card or just replies.
"""

import asyncio
import binascii
import json
import logging
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from datetime import date
from typing import Callable, Literal

from PIL import Image
from pydantic import ValidationError, model_validator

from ..agent import AgentError, Chat, TurnTools, build_messages, lookups, run_loop
from agents.assistant import REGISTRY, Guarded, last_shown, rule_reply
from corpus import tags as corpus_tags

from ..agent.tools import DATE_TOOLS
from ..domain import ask, deck, drill, memo, values
from ..domain.derive import derive
from ..domain.deck import Deck
from ..domain import vibes
from ..domain.card import OPENING, Chip, Question, conversation_card
from ..domain.compile import UnhandledSignal, compile_search_input
from ..domain.frame import FrameDefaults
from ..domain.readback import build as build_readback, party_conflict, plan_digest
from ..domain.guard import asks_settled_care, same_question, prune_say, bad_say, drop_questions, trim_say, trim_words
from ..domain.required import planning
from ..agent.prefetch import candidates, covers, prepare, route, start_weather
from ..infrastructure import clef
from . import blocks
from ..infrastructure.gaps import record as gap
from ..domain.logistics import pick_transit, tradeoffs
from ..domain.patterns import acts_votes, seed, seed_profile, summary
from ..domain.perceive import links_in, photo_context
from ..domain.prepass import Prepass, prepass
from ..domain.questions import (FIELD_LABEL, OFFER_QID, OTHER_CHIP, QUIZ_FIELD, REVIEW_QID, SOFT_LABEL, TO_QUIZ,
                                apply_chip, care_q, c_effort, companions_q, find_quiz, is_quiz, pending_fields, strictest,
                                quiz_queue, review_card)
from ..domain.readiness import gate_missing, missing
from ..domain.resolve import URL, anchor_for, search
from ..domain.coverage import admissible
from ..domain.covers import assign as distinct_covers
from ..domain.state import (MAX_TRIP_DAYS, SCALARS, Anchor, Draft, Evidence, Frozen, KindWish, Meta, SoftKey, TripState, Update, Vibe, apply, apply_drafts,
                            ontology, pending_signals, settle, with_meta)
from ..domain.text import fold, language, says_nothing, squash
from ..domain.traits import compared_places
from ..domain.understanding import chip_effects, fit_summary, view as understanding
from ..infrastructure.catalog import Catalog
from ..infrastructure.images import sanitize_photo
from ..infrastructure.profile import ProfileStore
from ..infrastructure.sessions import Session, SessionStore
from ..infrastructure.settings import ROOT, Settings

Emit = Callable[[str, dict], None]
INVITE = re.compile(r"lên lịch[^.!?…]*\?")  # the assistant's one invitation to plan the trip (agent/prompt.py ASSISTANT)
NO_ANSWER = re.compile(r"\bchua co thong tin\b")  # the assistant's words for "the data has no answer" (folded)
WISH_PLACES = 300  # places a kind wish holds (the best of the node)
SHOWN_KEEP, TOLD_KEEP = 80, 300  # places and numbers of read-tool results a session remembers (Meta.shown_ids / told_numbers)
TURN_LOG = ROOT / "logs" / "run" / "trip_turns.log"  # one JSON line per turn: tools called, retry, reply, card (debugging)


def log_turn(sid: str, turn: int, text: str, log: list[str], say: str, card: str, state: dict | None = None,
             path: Path | None = None) -> None:
    """Append one turn's trace. Logging must never break a turn, so a failed write is ignored. The default file is read
    at call time, so a test that points TURN_LOG elsewhere does not write to the live log."""
    path = path or TURN_LOG
    line = {"at": datetime.now().isoformat(timespec="seconds"), "session": sid, "turn": turn, "user": text,
            "tools": log, "retried": "claim_without_record" in log, "say": say, "card": card, "state": state or {}}
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
    except OSError:
        pass

GREETING = "Chào bạn! Mình hỏi vài câu ngắn để hiểu chuyến Đà Lạt của bạn trước khi chọn chỗ."
RECORDED_SAY = "Mình đã ghi lại ({got})."  # asks nothing: the next question card shows under it
MOVE_ON_SAY = "Mình hỏi tiếp phần này nhé."  # the agent asked the same question again, so only its question is dropped
def _ids_in(o) -> set[str]:
    """Every string in a nested result that looks like a place id."""
    if isinstance(o, dict):
        return set().union(*map(_ids_in, o.values())) if o else set()
    if isinstance(o, (list, tuple)):
        return set().union(*map(_ids_in, o)) if o else set()
    return {o} if isinstance(o, str) and PLACE_ID.fullmatch(o) else set()


PLACE_ID = re.compile(r"0x[0-9a-f]+:0x[0-9a-f]+")
PREPARED_GROUPS = frozenset({"places", "detail", "weather", "distance", "trends", "services"})  # agent/prefetch.covers
INVENTED = ("numbers", "names place")  # bad_say reasons a reply loses only the sentences that hold them
VAGUE = re.compile(r"\b(tuy|chua biet|khong biet|sao cung duoc|gi cung duoc|cung duoc|la duoc|ok|oke|duoc roi|chua chot|"
                   r"chua chac|bo qua|de trong|de sau)\b")
ASKING = re.compile(r"\b(goi y|de xuat|tu van|nen di|nen an|co nen|the nao|sao a|nhu nao)\b")  # the user asks, not tells
PARTIAL_SAY = "Mình đã ghi lại một phần ({got}), phần còn lại chưa xử lý xong. Bạn kể lại giúp mình nhé."
NOT_DONE_SAY = "Mình chưa xử lý xong ý này. Bạn kể lại giúp mình một lần nữa nhé."
FALLBACK_SAY = ("Mình đã ghi lại những gì đọc được, nhưng trợ lý đang bận nên chưa hiểu hết câu này. "
                "Bạn gửi lại giúp mình nhé.")
BUSY_SAY = "Trợ lý đang bận nên chưa ghi được lựa chọn này. Bạn bấm lại giúp mình nhé."  # a button answer the agent missed
LOCAL_NOW_ITEMS = 3  # seasons, events and popular places each, in the agent's local_now
NEXT_CARD_WAIT_S = 0.8  # how long a discovery turn waits, before the agent, for the photo card that opens under its reply
DRILL_WAIT_S = 0.3  # how long a turn waits, after the agent, for its photo card (not ready: it shows on a later turn;
# waiting 3 s added 3 s to every long first message, 2026-10-16)
NOTED_SAY = "Mình đã ghi lựa chọn của bạn."  # a button answer recorded with no agent reply (closed card, or agent failed)
MISSING_SAY = "Mình cần biết thêm {items} trước khi tìm chỗ, bạn kể giúp mình nhé."
NOTED_TEXT_SAY = "Mình ghi lại như dưới đây, bạn xem có đúng không nhé."  # the agent's own words were held back
UNSURE_SAY = "Mình chưa chắc chắn về thông tin này nên chưa trả lời được ở bước này. Bạn cứ kể tiếp về chuyến đi nhé."
DONE_SAY = "Xong rồi, mình đi tìm chỗ hợp với chuyến này."
OTHER_TYPE_SAY = "Bạn gõ ý của bạn vào ô bên dưới giúp mình nhé."
REVIEW_SAY = "Mình đã hỏi đủ những điều cần cho chuyến này. Các nơi đang hợp ở bảng bên cạnh."
BAD_VALUE = "Giá trị này mình chưa đọc được, bạn thử lại nhé."
NEW_CHAT = "new_chat"  # transcript mark of the chat's "Trò chuyện mới" (Engine.new_chat)


def since_new_chat(transcript: list[dict]) -> list[dict]:
    """The conversation on screen: the lines after the user's last "Trò chuyện mới". The earlier lines stay in the trip
    for the record (the history title, the Agent's memo); the screen and the model's chat history start after the mark."""
    for i in range(len(transcript) - 1, -1, -1):
        if transcript[i].get("kind") == NEW_CHAT:
            return transcript[i + 1:]
    return transcript


EXIT_LABEL = {"skip": "Bỏ qua", "unsure": "Chưa chắc"}  # what the user pressed, as it shows in the chat
DECLINE_SAY = "Không sao, mình để trống ý này."
DATE_SAY = "Mình ghi ngày đi {day}."
THEME_SAY = "Mình bắt đầu từ chủ đề “{title}”: {what}."
# after an answer the agent did not see: what the user can do next (no question is forced)
NEXT_READY = " Bạn kể thêm điều mình nên biết, hoặc bấm Xem gợi ý khi sẵn sàng."
THEME_UNKNOWN = "Chủ đề này không còn nữa, bạn chọn chủ đề khác nhé."
PAST_DATE = "Ngày này đã qua, bạn chọn ngày khác giúp mình nhé."
# looks (domain/vibes.py): fixed lines, the agent does not run on these answers
KINDS_SAY = "Mình ghi lựa chọn của bạn: {labels}. Các nơi này lên đầu danh sách."
NO_KIND_SAY = "Không sao, mình không xếp theo kiểu nào. Bạn kể thêm nơi bạn thích trông thế nào nhé."
CUES_ONLY_SAY = "Mình ưu tiên nơi có {cues}."
PHOTO_SAY = "Trong ảnh mình thấy {cues}."
PHOTO_PLACE_SAY = "Mình sẽ tìm nơi cùng phong cách với {name}."
PHOTO_NOT_SAY = "Bạn kể thêm nơi này đẹp ở điểm nào nhé."
PHOTO_BLIND_SAY = "Mình chưa đọc được ảnh này. Bạn kể bằng lời giúp mình nhé."
NOT_PLACE_SAY = ("Ảnh này không giống ảnh một nơi hay khung cảnh nào ở Đà Lạt nên mình không đối chiếu được. "
                 "Bạn gửi ảnh một quán, một góc đồi hay một homestay bạn thích, hoặc kể bằng lời nhé.")
BAD_PHOTO = "Ảnh này mình không mở được, bạn thử ảnh JPG hoặc PNG khác nhé."

# Prepass proposals allowed straight into the Trip State: high-precision slots only (dates, counts,
# money, explicit body signals, effort hard filters, single-meaning soft). Everything else arrives as
# agent-only suggestions and is recorded via record_fact.
log = logging.getLogger(__name__)
PHOTOS_KEPT = 5  # photo records the assistant keeps for one session (memory only)
FOLLOWUP_LIMIT = 3  # the agent's own questions in a row after which the app asks a required topic itself
EXPLORED_MAX = 24   # picks of one photo stage the agent reads
EXPLORED_SHOWN = 4  # picks the chat line names before "và N nữa"
APPLIED_FIELDS = frozenset({"care", "checkout_at", "day_end", "checkin_at", "frame.day_start", "start_date", "month", "month_part", "days", "nights", "people", "budget_vnd",
                            "budget_scope", "signal", "hard", "soft", "arrival_mode", "mobility", "driver", "unmapped"})
# Of those, the ones written as the user's own words (source user): the agent is told not to record or compute them again
EXACT_FIELDS = frozenset({"care", "checkout_at", "day_end", "checkin_at", "frame.day_start", "start_date", "month", "month_part", "days", "nights", "people", "budget_vnd", "budget_scope", "signal", "arrival_mode", "unmapped"})


class TurnInput(Frozen):
    kind: Literal["text", "answer", "edit", "show", "more", "theme", "to_chat", "to_quiz", "image", "deck", "drop", "readback_ok",
                  "like", "tag", "wish", "explored"]
    answers: dict[str, list[str] | str] = {}
    text: str = ""
    qid: str = ""
    chips: tuple[str, ...] = ()
    value: str | None = None
    target: str = ""
    soft_only: bool = False
    at: Literal["understand", "gate", "plan"] = "understand"

    @model_validator(mode="after")
    def _one_answer(self):
        # typing is the card's "other answer" option: an answer is chips / a value, or text, never both
        if self.kind == "answer" and self.text.strip() and (self.chips or self.value):
            raise ValueError("an answer is chips or text, not both")
        return self


def _learned(before: TripState, after: TripState, fields: list[str]) -> bool:
    """Whether the agent wrote something new this turn: a field it recorded now holds another value than before the
    turn. A correction of something already known or an unmapped wish does not answer the open question."""
    def now(st: TripState, f: str):
        if f == "like" or f.startswith("wishes."):
            return st.wishes
        if f.startswith("frame.") or f == "drive_day_min":
            return getattr(st.frame, f.removeprefix("frame.")).value
        if f == "soft":
            return {k: x.value for k, x in st.soft.items()}
        if f in ("anchor", "signal", "hard"):
            return getattr(st, {"anchor": "anchors", "signal": "signals"}.get(f, f))
        if f == "excluded_place":
            return st.excluded_places
        if f == "activity":
            return st.activities
        if f == "time_preference":
            return st.time_preferences
        if f == "intent":
            return st.meta.intent
        return getattr(st, f).value

    return any(now(before, f) != now(after, f) for f in set(fields) - {"unmapped"})


def asks_in_text(say: str) -> bool:
    """The reply ends on a question to the user: the talk stays in plain words, no card opens under it."""
    lines = [x for x in say.strip().splitlines() if x.strip()]
    return bool(lines) and "?" in lines[-1]


def picked_text(d: Deck, answers: dict) -> str:
    """What the user chose on the card, as their line in the talk ("Đi với: Người yêu · 2 người")."""
    tabs = {t.qid: t for t in d.tabs}
    lines: dict[str, list[str]] = {}
    for key, raw in answers.items():
        owner, _, part = key.partition(".")
        tab = tabs.get(key) or tabs.get(owner)
        labels = {o.id: o.label for o in tab.options} if tab else {}
        for v in (raw if isinstance(raw, list) else [raw]):
            v = str(v)
            if v == "skip":
                shown = "Bỏ qua"
            elif key == "trip.dates" and ".." in v:
                a, b = v.split("..")
                shown = f"{a[8:10]}/{a[5:7]} – {b[8:10]}/{b[5:7]}"
            elif key in ("trip.start", "trip.end"):
                shown = f"{'bắt đầu' if part == 'start' else 'xong lúc'} {v}"
            elif key == "companions.people":
                shown = f"{v} người"
            elif key == "budget.amount" and v.isdigit():
                shown = f"{int(v) / 1_000_000:g} triệu".replace(".", ",")
            elif key == "budget.unlimited":
                shown = "không giới hạn"
            elif key == "lodging" and v.startswith("{"):
                try:
                    shown = str(json.loads(v).get("text") or "chỗ ở đã chọn")
                except ValueError:
                    shown = "chỗ ở đã chọn"
            else:
                shown = labels.get(v, v)
            lines.setdefault(tab.header if tab else "Lựa chọn", []).append(shown)
    return "\n".join(f"{h}: {' · '.join(dict.fromkeys(v))}" for h, v in lines.items()) or "Lựa chọn cho chuyến đi"


def photo_choice(tab, vals: list[str], said: str | None, name: Callable[[str], str],
                 known_for: Callable[[str], list[str]] = lambda _: [],
                 looks: Callable[[str], list[str]] = lambda _: []) -> tuple[dict, tuple[str, ...]]:
    """What the user did on a photo card, for the agent: the kinds they kept (what each looks like, the place on its
    photo), the ones they passed over, the card's question and the words of theirs that opened it.
    -> (the context, the kept photos' place ids: the user saw them, so the reply may name them)."""
    shown = [o for o in tab.options if o.id not in ("skip", "other")]
    kept = [o for o in shown if o.id in vals]
    return {"card": tab.header, **({"asked": tab.question} if tab.question else {}),
            **({"opened_by_their_words": said} if said else {}),
            "kept": [{"kind": o.label, "looks_like": list(o.cues), **({"photo_of": name(o.photo[0]),
                                                                        "photo_place_looks": looks(o.photo[0]),
                                                                        "photo_place_known_for": known_for(o.photo[0])}
                                                                       if o.photo else {}),
                      **({"places_of_this_kind": o.count} if o.count else {})} for o in kept],
            "not_chosen_this_time": [o.label for o in shown if o.id not in vals]}, tuple(o.photo[0] for o in kept if o.photo)


def card(q: Question | None, effects: dict[str, int] | None = None) -> dict | None:
    """effects: chip id -> places the "Đang hợp với bạn" count gains or loses if that chip is chosen."""
    if q is None:
        return None
    d = q.model_dump(mode="json", exclude={"exit_drafts"})
    d["chips"] = [{"id": c.id, "label": c.label, "row": c.row, "effect": (effects or {}).get(c.id)} for c in q.chips]
    return d


class Engine:
    def __init__(self, catalog: Catalog, cfg: Settings, store: SessionStore, chat: Chat,
                 today: Callable[[], date] = date.today, profiles: ProfileStore | None = None,
                 judge=None, looks=None, web=None, see=None, knowledge=None):
        """chat: one model call with tools (agent/loop.py). profiles: stored patterns (config patterns.enabled);
        None = no long-term learning. judge: Clef's yes / no checks on facts, replies and questions (infrastructure.clef.Judge); None = regex guards only.
        looks: corpus.index for looks and photos (infrastructure.looks.Looks); None = no photo cards.
        web: infrastructure.web.Web for the agent's web_search / web_read; None = no web tools.
        see: photo bytes -> {kind, cues} (Extractor PHOTO_CUES); None = a photo is matched by its pixels only.
        knowledge: infrastructure.knowledge.Knowledge, the assistant's read tools (used when cfg.assistant.enabled)."""
        self.catalog, self.cfg, self.store, self.chat, self.today = catalog, cfg, store, chat, today
        self.profiles, self.judge = profiles, judge
        self.looks, self.web, self.see = looks, web, see
        self.knowledge = knowledge
        self.warmed = threading.Event()  # create_engine clears it while the assistant's first search warms (api/tools.py)
        self.warmed.set()

    # ---------- reads ----------

    def create(self, experience: str | None = None, start_with: str | None = None, user_id: str | None = None,
               remember: bool = False, profile: dict | None = None) -> dict:
        """user_id: whose stored patterns seed the session. remember: the user agreed this session may add to them.
        profile: the account's usual mobility / companions, seeded as priors (patterns.seed_profile)."""
        on = self.profiles is not None and user_id is not None
        state = TripState(meta=Meta(experience=experience, start_with=start_with, user_id=user_id if on else None,
                                    remember=remember and on))
        if on:
            state = seed(state, self.profiles.patterns(user_id, self.today()), self.catalog, self.cfg.patterns)
        if profile:
            state = seed_profile(state, profile)
        s = self.store.new(state)
        s.card = OPENING
        s.transcript.append({"role": "agent", "text": GREETING, "turn": 0})
        self.store.save(s)
        return self.view(s)

    def load(self, sid: str) -> dict:
        return self.view(self.store.get(sid))

    def view(self, s: Session) -> dict:
        return {"id": s.id, "discovery": self.cfg.discovery,
                "transcript": [self._entry(t, s.state) for t in since_new_chat(s.transcript) if t["role"] in ("user", "agent")],
                "understanding": understanding(s.state, self.catalog, self.cfg),
                "card": self._card(s.state, s.card),
                "tradeoffs": tradeoffs(s.state, self.cfg),
                "phase": s.state.meta.phase}

    def _entry(self, t: dict, state: TripState) -> dict:
        """One transcript line for the screen; an assistant card line (kind places) gets its cards built again."""
        out = {k: t.get(k) for k in ("role", "text", "turn", "kind")}
        if t.get("kind") == "places":
            out.update(ids=list(t.get("ids") or ()), why=t.get("why") or "", cards=self._cards(t.get("ids") or (), state))
        elif t.get("kind") == "block":
            out["block"] = t.get("block")
        elif t.get("kind") == "replies":
            out["options"] = list(t.get("options") or ())
        return out

    def _named(self, say: str, ids: set[str], most: int = 10) -> list[str]:
        """The ids of `ids` whose place name the reply says, in the reply's order."""
        text = f" {squash(say)} "
        at = {pid: text.find(f" {squash(p.name)} ") for pid in ids if (p := self.catalog.by_id.get(pid)) and squash(p.name)}
        return sorted((pid for pid, i in at.items() if i >= 0), key=at.get)[:most]

    def _cards(self, ids, state: TripState, scenes: dict[str, str] | None = None) -> list[dict]:
        """The chat's place cards (infrastructure.knowledge.Knowledge.view); liked = a want anchor of the trip;
        scenes: place id -> the scene whose photo the card shows first (place_photos)."""
        if self.knowledge is None:
            return []
        liked = {a.place_id for a in state.anchors if a.priority == "want" and a.place_id}
        return [c for pid in ids if (c := self.knowledge.view(pid, self.today(), pid in liked, (scenes or {}).get(pid)))]

    def calendar_days(self, first: date, last: date) -> dict:
        """The home calendar's days: holiday, lunar day and forecast (infrastructure.knowledge.Knowledge.month_days)."""
        if self.knowledge is None:
            return {"from": first.isoformat(), "to": last.isoformat(), "days": {}}
        return self.knowledge.month_days(first, last)

    def tag_view(self, ref: str) -> dict:
        """The home page's tag: {tag, block, cards}. block = the tag's places split into subtags (the chat's `tags` block,
        no trip limits); cards = the tag's best places as one list when nothing splits them. ValueError: unknown tag."""
        if self.knowledge is None:
            raise ValueError("no corpus")
        state = TripState()
        out = self.knowledge.browse.tag(ref, state)
        cards_of = lambda ids: self._cards(ids, state)  # noqa: E731
        block = blocks.tags_block(out, cards_of, cover_fit=self._cover_fit)
        return {"tag": out["tag"], "block": block, "cards": [] if block else cards_of(out.get("_cards") or ())}

    STAGE_PLACES = 60  # place cards one level of the tag stage carries (the node's count says how many there are)

    def _stage_node(self, s: Session, sig: str, path: list[str]) -> dict:
        """The tree node `path` of the tags block `sig` of this chat (infrastructure.browse.stage), through the trip's
        hard limits: {label, ids, children, all}. `*` as the last ref = every place of the parent. ValueError: not a node."""
        if self.knowledge is None:
            raise ValueError("no corpus")
        block = next((t["block"] for t in reversed(s.transcript) if t.get("kind") == "block"
                      and (t.get("block") or {}).get("kind") == "tags" and t["block"].get("sig") == sig), None)
        if block is None:
            raise ValueError("this chat has no such tags block")
        every = bool(path) and path[-1] == "*"
        path = path[:-1] if every else path
        if not path:  # the root's "Xem tất cả": the places the block ranked
            ids = [i for i in block.get("all") or () if self.knowledge._admissible(i, s.state)]
            if not ids:
                raise ValueError("nothing to list")
            return {"label": block.get("title") or "Tất cả", "ids": ids, "children": None}
        node = self.knowledge.browse.stage(block.get("criteria") or {}, s.state, path)
        return {**node, "children": None} if every else node

    def _cover_fit(self, tag: str) -> Callable[[str], str | None] | None:
        """The scenes that show this tag (config/tags.yaml cover_scenes): place id -> its photo of them. None: any photo."""
        shown = corpus_tags.config().get("cover_scenes", {})
        scenes = shown.get(tag) or shown.get(tag.split(":")[0] + ":*")  # "dish:*": every dish tag shows food
        return (lambda pid: self.knowledge.scene_cover(pid, scenes)) if scenes else None

    def tag_stage(self, sid: str, sig: str, path: str) -> dict:
        """One level of the tag stage (docs/TRIP_UNDERSTANDING.md §19), read only, no chat turn: the node `path` ("a/b", refs
        of the tags block `sig`) -> {ref, label, count, nodes}. nodes = its children, either subtags {ref, kind, label,
        count, cover, has_children, wished} (the last may be kind "all": every place of this node) or places
        {ref: "place:<id>", kind: "place", id, card}. Covers are distinct across the level. ValueError: not a node."""
        s = self.store.get(sid)
        refs = [r for r in path.split("/") if r]
        if not refs:
            raise ValueError("path needs a node")
        with s.lock:
            node = self._stage_node(s, sig, refs)
            state = s.state
        wished = {squash(w.kind) for w in state.wishes.kinds}
        base = {"sig": sig, "ref": "/".join(refs), "label": node["label"], "count": len(node["ids"]),
                "wished": squash(node["label"]) in wished}
        today = self.today()
        liked = {a.place_id for a in state.anchors if a.priority == "want" and a.place_id}
        photo_of = lambda pid: next(iter((self.knowledge.view(pid, today) or {}).get("photos") or ()), None)  # noqa: E731
        if node["children"]:
            kids = node["children"]
            groups = [k["ids"] for k in kids] + [node["ids"]]
            cover = distinct_covers(groups, photo_of, fits=[self._cover_fit(k["id"]) for k in kids] + [None])
            nodes = [{"ref": "/".join([*refs, k["id"]]), "kind": k["kind"], "label": k["label"], "count": k["count"], "cover": c,
                      "has_children": True, "wished": squash(k["label"]) in wished} for k, c in zip(kids, cover)]
            nodes.append({"ref": "/".join([*refs, "*"]), "kind": "all", "label": "Xem tất cả", "count": len(node["ids"]),
                          "cover": cover[-1], "has_children": True, "wished": False})
            return {**base, "nodes": nodes}
        cards = [c for pid in node["ids"][:self.STAGE_PLACES] if (c := self.knowledge.view(pid, today, pid in liked))]
        return {**base, "nodes": [{"ref": f"place:{c['id']}", "kind": "place", "id": c["id"], "label": c["name"], "count": 1,
                                   "cover": (c["photos"] or [None])[0], "has_children": False, "card": c} for c in cards]}

    def tag_covers(self, items: list[dict]) -> list[dict]:
        """Trending tags (corpus.pulse.tag_trends) with `cover`: a photo of up to 3 of the places that posted most, one that shows
        the tag when config/tags.yaml `cover_scenes` names scenes for it (else the place's first photo); a place used by an
        earlier tag only when the tag has no other (each tag looks like itself, not like the one before)."""
        state, used, out = TripState(), set(), []
        for it in items:
            fit = self._cover_fit(it.get("ref") or "")  # the scenes that show this tag (a view for "Săn mây", not a plate)
            cards = [(c, (fit(c["id"]) if fit else None) or c["photos"][0]) for c in self._cards(it.get("top") or (), state) if c.get("photos")]
            fitted = [x for x in cards if fit and fit(x[0]["id"]) == x[1]]
            pool = fitted or cards
            pick = [x for x in pool if x[0]["id"] not in used] or pool
            pick = (pick + [x for x in pool if x not in pick])[:3]
            used.update(c["id"] for c, _ in pick)
            out.append({**it, "cover": [photo for _, photo in pick]})
        return out

    def forget(self, user_id: str) -> bool:
        """Delete everything stored about a user. False when nothing was stored (or learning is off)."""
        return self.profiles.forget(user_id) if self.profiles else False

    def profile(self, user_id: str) -> dict:
        """Every stored entry for the user to see (docs/TRIP_UNDERSTANDING.md §17); used = it seeds the next trip."""
        if not self.profiles:
            return {"enabled": False, "paused": False, "entries": []}
        paused, found = self.profiles.entries(user_id, self.today(), self.catalog)
        return {"enabled": True, "paused": paused,
                "entries": [{**e.model_dump(mode="json"), "used": e.used and not paused} for e in found]}

    def note_acts(self, user_id: str, sid: str, acts: list[dict]) -> bool:
        """Weak evidence from Decision / Planning for the trip's trip-session `sid` (patterns.acts_votes): written only
        when that trip's user agreed to remember and is `user_id`. True when something was written."""
        if not self.profiles:
            return False
        try:
            m = self.store.get(sid).state.meta
        except KeyError:
            return False
        votes = acts_votes(acts)
        if not (m.remember and m.user_id == user_id and votes):
            return False
        self.profiles.note(user_id, sid, self.today(), votes)
        return True

    def edit_entry(self, user_id: str, eid: str, patch: dict) -> dict:
        """patch: {statement?, paused?}. KeyError when there is no such entry."""
        if not isinstance(patch, dict) or not patch or set(patch) - {"statement", "paused"}:
            raise ValueError("an entry takes statement and / or paused")
        if not (self.profiles and self.profiles.edit(user_id, eid, patch.get("statement"), patch.get("paused"))):
            raise KeyError(eid)
        return next(e for e in self.profile(user_id)["entries"] if e["id"] == eid)

    def delete_entry(self, user_id: str, eid: str) -> bool:
        return self.profiles.delete(user_id, eid) if self.profiles else False

    def pause_profile(self, user_id: str, paused: bool) -> dict:
        if not self.profiles:
            raise KeyError(user_id)
        self.profiles.pause(user_id, paused)
        return self.profile(user_id)

    def places(self, q: str) -> list[dict]:
        return [{"id": p.id, "name": p.name, "category": p.category} for p in search(q, self.catalog)]

    # ---------- turns ----------

    def turn(self, sid: str, inp: TurnInput, emit: Emit) -> None:
        s = self.store.get(sid)
        gone = False

        def safe(event: str, data: dict) -> None:
            # a closed browser tab must not leave the turn half applied: finish it, stop writing
            nonlocal gone
            if gone:
                return
            try:
                emit(event, data)
            except OSError:
                gone = True

        with s.lock:
            try:
                getattr(self, f"_{inp.kind}")(s, inp, safe)
            finally:
                self.store.save(s)

    def _compile(self, state: TripState):
        return compile_search_input(state, self.cfg.arrival_buffer_min, self.cfg.coach_min_people,
                                    entry_min=self.cfg.entry_min, defaults=FrameDefaults(**self.cfg.frame))

    def _deck(self, s: Session, inp: TurnInput, emit: Emit) -> None:
        legacy = not isinstance(s.card, Deck) and inp.at == "understand"
        current = (deck.build(s.state, self.catalog, self.cfg, at=inp.at) if inp.at != "understand" else
                   deck.build(s.state, self.catalog, self.cfg, agent=s.card.agent, at=s.card.at, ask=s.card.ask,
                              question=s.card.ask_question, agent_only=s.card.agent_only) if not legacy else
                   deck.build(s.state, self.catalog, self.cfg, at="gate" if s.card is None else "understand"))
        available = {t.qid: t for t in current.tabs}
        before = s.state
        turn = self._open_turn(s, picked_text(current, inp.answers), "answer")
        issues, flat, other = [], {}, False
        choices: list[tuple[dict, tuple[str, ...]]] = []  # what the user did on a photo card, for the agent
        for key, raw in inp.answers.items():
            vals = raw if isinstance(raw, list) else [raw]
            tab = available.get(key)
            if tab is None:
                if key in ("trip.dates", "trip.start", "trip.end", "companions.who", "companions.people",
                           "budget.amount", "budget.scope", "budget.unlimited", "lodging") or key in ("mobility", "care", "pace"):
                    owner, _, input_key = key.partition(".")
                    target = available.get(owner)
                    if legacy or (target is not None and (not input_key or input_key in target.inputs or input_key == "unlimited")):
                        flat[key] = raw
                    else:
                        issues.append({"key": key, "code": "invalid"})
                else:
                    issues.append({"key": key, "code": "invalid"})
                continue
            if vals == ["skip"]:
                if key == "budget":
                    s.state = s.state.model_copy(update={name: type(getattr(s.state, name))() for name in
                                                        ("budget_vnd", "budget_scope", "budget_unlimited")})
                if tab.kind == "drill":
                    s.state = drill.skip(s.state, key.removeprefix("drill."))
                at_gate = isinstance(s.card, Deck) and s.card.at == "gate" and tab.kind == "required"
                s.state = with_meta(s.state, declined=tuple(dict.fromkeys((*s.state.meta.declined, key,
                                                                           *((f"gate:{key}",) if at_gate else ())))),
                                    soft_skips=s.state.meta.soft_skips + (tab.kind != "required"))
                continue
            if vals == ["other"]:
                if inp.text.strip():
                    other = True
                else:
                    issues.append({"key": key, "code": "invalid"})
                continue
            if tab.kind == "required" and key in ("mobility", "care", "pace", "lodging") and vals != ["lodging.prefilled"]:
                flat[key] = raw
                continue
            if key == "companions":
                if not vals or not set(vals) <= {o.id for o in tab.options if o.id not in ("other", "skip")}:
                    issues.append({"key": key, "code": "invalid"})
                    continue
                who = [v for v in vals if v != "people.prefilled"]
                if who:
                    flat["companions.who"] = who
                if "people.prefilled" in vals:
                    flat["companions.people"] = str(s.state.people.value)
                continue
            opts = {o.id: o for o in tab.options if o.id not in ("skip", "other")}
            if not vals or not set(vals) <= opts.keys() or (len(vals) > 1 and not tab.multi):
                issues.append({"key": key, "code": "invalid"})
                continue
            try:
                drafts = [d.model_copy(update={"inferred": False}) for v in vals for d in opts[v].writes]
                quote = next((d.quote for d in s.state.drills if key == f"drill.{d.topic}"), None) if tab.kind == "drill" else None
                st = apply_drafts(s.state, drafts, turn, tool=f"deck:{key}", quote=quote)
                if tab.kind == "drill":
                    topic = key.removeprefix("drill.")
                    st = drill.finish(st, topic, "done")
                    selected = [opts[v] for v in vals]
                    choices.append(photo_choice(tab, vals, quote, self._name, self._known_for, self._looks_of))
                    from ..domain.state import Vibe
                    from itertools import zip_longest
                    places = tuple(dict.fromkeys(p for row in zip_longest(*(o.places for o in selected))
                                                  for p in row if p))[:60]
                    if places:
                        st, _ = vibes.put(st, None, Vibe(phrase=topic, turn=turn, status="done", places=places,
                                                        cues=tuple(dict.fromkeys(c for o in selected for c in o.cues))))
                s.state = with_meta(st, asked=tuple(dict.fromkeys((*st.meta.asked, key))))
            except (ValueError, TypeError, ValidationError):
                issues.append({"key": key, "code": "invalid"})
        for key, raw in flat.items():
            vals = raw if isinstance(raw, list) else [raw]
            if not vals or (key not in ("companions.who", "care") and len(vals) != 1):
                issues.append({"key": key, "code": "invalid"})
                continue
            value = vals[0]
            ev = Evidence(turn=turn, tool=f"deck:{key}")

            def put(state, field, parsed):
                return apply(state, Update(field=field, value=parsed, source="user", confidence="high", evidence=ev))

            st = s.state
            try:
                if key == "trip.dates":
                    start_raw, end_raw = value.split("..")
                    start, end = date.fromisoformat(start_raw), date.fromisoformat(end_raw)
                    if start < self.today():
                        issues.append({"key": key, "code": "past_date"})
                        continue
                    if end < start:
                        issues.append({"key": key, "code": "end_before_start"})
                        continue
                    if (end - start).days + 1 > MAX_TRIP_DAYS:
                        issues.append({"key": key, "code": "too_long"})
                        continue
                    st = put(st, "days", (end - start).days + 1)
                    st = put(st, "start_date", start)
                elif key in ("trip.start", "trip.end"):
                    st = put(st, "checkin_at" if key == "trip.start" else "checkout_at", values.clock(value))
                elif key == "companions.who":
                    if not set(vals) <= set(values.ENUM_VALUES["companions"]):
                        raise ValueError("invalid companions")
                    from ..domain.questions import WHO
                    st = put(st, "companions", vals)
                    implied = [d for v in vals for d in WHO[v][1] if d.field != "companions"]
                    st = apply_drafts(st, implied, turn, tool=ev.tool)
                elif key == "companions.people":
                    who = set(vals_who) if (vals_who := flat.get("companions.who")) else set(st.companions.value or ())
                    # alone is one person whatever the count box says (a guest sent "0 người" four times, 2026-10-16)
                    st = put(st, "people", 1 if who - {"pet"} == {"solo"} else int(value))
                elif key == "mobility":
                    if value not in ("motorbike", "car_self", "car_hired", "walk"):
                        raise ValueError("invalid mobility")
                    st = put(st, "mobility", "car" if value.startswith("car_") else value)
                    st = put(st, "driver", value[4:] if value.startswith("car_") else None)
                elif key == "care":
                    if "none" in vals:
                        if len(vals) != 1:
                            raise ValueError("conflicting care choices")
                        inferred = [sig.kind for sig in pending_signals(st)
                                    if sig.from_companion is not None or sig.source == "inferred"]
                        st = put(st, "signal_handled", inferred)
                        if pending_signals(st):
                            issues.append({"key": key, "code": "contradicts_said"})
                        st = put(st, "care", "none")
                    else:
                        chips = {c.id: c.drafts for c in care_q().chips}
                        aliases = {"vegetarian": "veg", "motion_sick": "motion"}
                        for choice in vals:
                            chip = aliases.get(choice, choice)
                            if choice == "other":
                                if not inp.text.strip():
                                    raise ValueError("other care needs the user's words")
                                st = put(st, "unmapped", inp.text.strip())
                                continue
                            if choice not in ("steps", "wheelchair", "pregnant", "motion_sick", "height", "vegetarian", "vegan"):
                                raise ValueError("invalid care")
                            if choice != "steps":
                                st = apply_drafts(st, chips[chip], turn, tool=ev.tool)
                            if choice in ("steps", "wheelchair"):
                                drafts = next(c.drafts for c in c_effort(st).chips if c.id == "both")
                                st = apply_drafts(st, drafts, turn, tool=ev.tool)
                        st = put(st, "care", "listed")
                elif key == "pace":
                    st = put(st, "pace", values.parse("pace", value, self.catalog))
                    st = with_meta(st, conflicts=tuple(k for k in st.meta.conflicts if k != "pace"))
                elif key in ("budget.amount", "budget.scope", "budget.unlimited"):
                    field = {"budget.amount": "budget_vnd", "budget.scope": "budget_scope",
                             "budget.unlimited": "budget_unlimited"}[key]
                    st = put(st, field, values.parse(field, value, self.catalog))
                elif key == "lodging":
                    if value in self.catalog.by_id:
                        place = self.catalog.by_id[value]
                        parsed = {"place_id": value, "text": place.name}
                    else:
                        parsed = values.parse("lodging", value, self.catalog)
                    st = put(st, "lodging", parsed)
                else:
                    raise ValueError("unknown deck key")
                s.state = settle(st)
            except (ValueError, TypeError, ValidationError):
                issues.append({"key": key, "code": "invalid"})
        if current.at != "gate":
            # Gate answers must not silently resolve a pending health hint through unrelated derivations.
            s.state = derive(s.state, self.catalog, turn)  # "Một mình" is one person, "gần trung tâm" a stay point, ...
        st = s.state
        if st.days.value == 1 and st.checkin_at.known and st.checkout_at.known and st.checkout_at.value < st.checkin_at.value:
            clock_keys = {"trip.start", "trip.end"} & flat.keys()
            key = "trip.end" if "trip.end" in clock_keys else "trip.start" if clock_keys else "trip.dates"
            issues.append({"key": key, "code": "end_before_start"})
            restored = st.model_copy(update={"checkin_at": before.checkin_at, "checkout_at": before.checkout_at})
            if not clock_keys or (before.checkin_at.known and before.checkout_at.known
                                  and before.checkout_at.value < before.checkin_at.value):
                restored = restored.model_copy(update={"days": before.days, "nights": before.nights, "start_date": before.start_date})
                if clock_keys and "trip.dates" in flat:
                    issues.append({"key": "trip.dates", "code": "end_before_start"})
            s.state = restored
        if {"companions.who", "companions.people"} & flat.keys() and st.people.known and st.companions.known:
            if st.people.value < 1 + len(set(st.companions.value) - {"solo", "pet"}):
                issues.append({"key": "companions.people", "code": "people_below_groups"})
        if issues:
            emit("deck_issues", {"issues": issues})
        s.card = deck.build(s.state, self.catalog, self.cfg, agent=current.agent, at=current.at, ask=current.ask,
                            question=current.ask_question)
        if other:
            return self._run(s, inp.text.strip(), emit)
        if current.at == "understand" and not issues and inp.answers:
            if not inp.text.strip() and all(raw == ["skip"] or raw == "skip" for raw in inp.answers.values()):
                return self._skip_deck(s, current, turn, emit)
            # whatever the user pressed (an option the agent wrote, a required topic, a photo variant, Bỏ qua) is
            # already written: the agent reads it like a reply in the talk, reacts and chooses the next question in
            # words that fit the talk. The app opens no required topic by itself.
            if self._tap_only(s, available, inp):
                return self._tap_next(s, turn, emit)
            return self._run(s, s.transcript[-1]["text"], emit, answer=True, picked=True,
                             chosen=[c for c, _ in choices], chosen_ids=tuple(p for _, ids in choices for p in ids))
        emit("state", {"understanding": understanding(s.state, self.catalog, self.cfg)})
        emit("card", self._card(s.state, s.card))

    def _skip_deck(self, s: Session, current: Deck, turn: int, emit: Emit) -> None:
        previous = next((t for t in reversed(s.transcript) if t["role"] == "agent" and t.get("kind") == "say"), {})
        repeated = previous.get("skip_only", False)
        say = "Mình bỏ qua nhé." if repeated else "Mình bỏ qua ý này nhé."
        pending = tuple(t for t in current.agent if t.qid not in s.state.meta.declined)
        built = deck.build(s.state, self.catalog, self.cfg, agent=pending, agent_only=True)
        s.card = built if pending and built.tabs and built.tabs[0].kind == "agent" else conversation_card()
        if s.card.qid == "conversation" and not missing(s.state, self.cfg.required):
            say += NEXT_READY
        s.transcript.append({"role": "agent", "text": say, "turn": turn, "kind": "say", "skip_only": True})
        emit("say", {"replace": say})
        emit("state", {"understanding": understanding(s.state, self.catalog, self.cfg)})
        emit("card", self._card(s.state, s.card))
        log_turn(s.id, turn, "(skip)", ["skip_only model_calls=0"], say, s.card.qid)

    def _tap_only(self, s: Session, available: dict, inp: TurnInput) -> bool:
        """True when the user only tapped options on required-topic cards, no words, and a required topic is still
        missing: the app records and opens the next one itself, without a model call."""
        if inp.text.strip() or self._user_asks(s):
            return False
        owners = {key.partition(".")[0] for key in inp.answers}
        if not owners or any((tab := available.get(o)) is None or tab.kind != "required" for o in owners):
            return False
        return self._next_required(s) is not None

    def _next_required(self, s: Session) -> str | None:
        m = s.state.meta
        return next((k for k, _ in missing(s.state, self.cfg.required)
                     if k not in m.declined and m.nudged.count(k) < 2), None)

    def _tap_next(self, s: Session, turn: int, emit: Emit) -> None:
        """A plain card tap: the answer is already written; open the next missing required topic in its default words."""
        started = time.monotonic()
        due = self._next_required(s)
        s.state = with_meta(derive(s.state, self.catalog, turn), unsure_streak=0, idle_streak=0, told=True,
                            nudged=(*s.state.meta.nudged, due), followups=0)
        s.card = deck.build(s.state, self.catalog, self.cfg, ask=due)
        s.transcript.append({"role": "system", "text": f"tap_next {due}", "turn": turn, "tools": {}})
        s.transcript.append({"role": "agent", "text": NOTED_SAY, "turn": turn, "kind": "say"})
        emit("say", {"replace": NOTED_SAY})
        emit("state", {"understanding": understanding(s.state, self.catalog, self.cfg)})
        emit("card", self._card(s.state, s.card))
        log_turn(s.id, turn, "(tap)", [f"tap_next {due}", f"t_turn {time.monotonic() - started:.2f}"], NOTED_SAY, s.card.qid, {})

    def _readback_ok(self, s: Session, inp: TurnInput, emit: Emit) -> None:
        digest = plan_digest(self._compile(s.state)) if not pending_signals(s.state) else None
        if inp.value and inp.value != digest:
            emit("readback", self._readback(s.state))
            return
        if party_conflict(s.state.companions.value, s.state.people.value):
            emit("readback", self._readback(s.state))  # the clash is asked, not planned over
            return
        if not gate_missing(s.state):
            s.state = with_meta(s.state, readback_digest=digest)
        emit("state", {"understanding": understanding(s.state, self.catalog, self.cfg)})

    def _readback(self, state: TripState) -> dict:
        needed = [key for key, _ in gate_missing(state)]
        try:
            rb = build_readback(self._compile(state))
            clash = party_conflict(state.companions.value, state.people.value)
            data = {**rb.model_dump(mode="json"), "conflicts": [clash] if clash else [],
                    "ok": not needed and not clash and state.meta.readback_digest == rb.digest}
        except UnhandledSignal:
            data = {"lines": [], "digest": None, "ok": False}
        gate = deck.build(state, self.catalog, self.cfg, at="gate") if needed else None
        fill = deck.build(state, self.catalog, self.cfg, at="plan")
        return {**data, "missing": needed, "deck": self._card(state, gate), "fill": self._card(state, fill) if fill.tabs else None}

    def _drop(self, s: Session, inp: TurnInput, emit: Emit) -> None:
        target = inp.target
        if target.startswith("soft:"):
            key = target.removeprefix("soft:")
            field = s.state.soft.get(key)
            if field is not None and field.source != "user":
                s.state = s.state.model_copy(update={"soft": {k: v for k, v in s.state.soft.items() if k != key}})
        elif target.startswith("frame.days."):
            _, _, index, key = target.split(".", 3) if target.count(".") == 3 else (None, None, None, None)
            if index is not None and index.isdecimal() and key in {"start", "end", "intensity"}:
                days = tuple(day.model_copy(update={key: None})
                             if day.index == int(index) and day.source != "user" else day for day in s.state.frame.days)
                s.state = s.state.model_copy(update={"frame": s.state.frame.model_copy(update={"days": days})})
        elif target.startswith("frame.busy."):
            label = target.removeprefix("frame.busy.")
            busy = tuple(b for b in s.state.frame.busy if b.label != label or b.source == "user")
            s.state = s.state.model_copy(update={"frame": s.state.frame.model_copy(update={"busy": busy})})
        else:
            owner = s.state.frame if target.startswith("frame.") else s.state
            key = target.removeprefix("frame.")
            field = getattr(owner, key, None) if key in type(owner).model_fields else None
            if target in {"frame.arrive", "frame.leave"} and not field.known:
                key = "inbound" if target == "frame.arrive" else "outbound"
                owner, field = s.state, getattr(s.state, key)
            if hasattr(field, "source") and hasattr(field, "known") and field.source != "user":
                updated = owner.model_copy(update={key: type(field)()})
                s.state = s.state.model_copy(update={"frame": updated}) if owner is s.state.frame else updated
                if target == "budget_scope":
                    s.state = with_meta(s.state, declined=tuple(dict.fromkeys((*s.state.meta.declined, target))))
        s.card = deck.build(s.state, self.catalog, self.cfg,
                            agent=s.card.agent if isinstance(s.card, Deck) else (),
                            at=s.card.at if isinstance(s.card, Deck) else "gate" if s.card is None else "understand",
                            ask=s.card.ask if isinstance(s.card, Deck) else None,
                            question=s.card.ask_question if isinstance(s.card, Deck) else None)
        emit("state", {"understanding": understanding(s.state, self.catalog, self.cfg)})
        emit("card", self._card(s.state, s.card))

    def new_chat(self, sid: str) -> None:
        """The chat's "Trò chuyện mới": a mark in the transcript, so the screen and the model's chat history start
        again after it. The trip stays as it is (what the user told, the places, the schedule). An open card closes,
        except an open health hint: that question still has to be answered before the lists move."""
        s = self.store.get(sid)
        with s.lock:
            if "care" not in self._readback(s.state).get("missing", ()) and s.card is not None and (
                    isinstance(s.card, Deck) or s.card.qid not in ("conversation", "frame")):
                s.card = conversation_card()
            s.transcript.append({"role": "system", "text": NEW_CHAT, "turn": s.state.meta.turn, "kind": NEW_CHAT})
            self.store.save(s)

    def refine(self, sid: str, text: str, emit: Emit) -> None:
        """A wish typed later, at Chọn nơi: read it like any text turn, without questions, then compile again. The
        Understand screen's card is left as it was; only say / state / done leave this method."""
        s = self.store.get(sid)
        with s.lock:
            try:
                card_before = s.card
                self._run(s, text, emit, may_ask=False, quiet=True)
                s.card = card_before
                try:
                    emit("done", {"search_input": self._compile(s.state).model_dump(mode="json")})
                except UnhandledSignal:  # an open health hint: the user answers it on the Understand screen
                    pass
            finally:
                self.store.save(s)

    def _answer(self, s: Session, inp: TurnInput, emit: Emit) -> None:
        if (i := vibes.index_of(inp.qid)) is not None:
            return self._vibe_answer(s, i, inp, emit)
        q = s.card
        if isinstance(q, Deck):
            if inp.text.strip():
                return self._run(s, inp.text.strip(), emit)
            chips = [c.removeprefix("who:") if inp.qid == "companions" else c for c in inp.chips]
            return self._deck(s, TurnInput(kind="deck", answers={inp.qid: chips if chips else inp.value or ""}), emit)
        if (q is None or q.qid != inp.qid) and is_quiz(inp.qid) and not inp.text.strip() \
                and (old := find_quiz(inp.qid, s.state, self.catalog, self.cfg)) is not None:
            return self._answer_quiz(s, old, inp, emit)  # an earlier card in the chat, still unanswered: it still counts
        if q is None or q.qid != inp.qid:
            emit("error", {"message": "Câu này đã qua, bạn trả lời câu mới nhất nhé."})
            emit("card", self._card(s.state, s.card))
            return
        if "show" in inp.chips:
            return self._show(s, inp, emit)
        if q.qid == OFFER_QID:
            return self._answer_offer(s, inp, emit)
        if q.qid == REVIEW_QID:
            return self._answer_review(s, inp, emit)
        if not q.custom and is_quiz(q.qid):
            return self._answer_quiz(s, q, inp, emit)
        typed = inp.text.strip()
        exit_ = next((x for x in ("skip", "unsure") if x in inp.chips), None)
        if exit_ and not typed:
            return self._decline(s, q, exit_, emit)
        if q.input == "date" and inp.value and not typed:
            return self._pick_date(s, inp.value, emit)
        chosen = [c.label for c in q.chips if c.id in inp.chips]
        text = typed or ", ".join(chosen) or (inp.value or "")
        if not text:
            emit("card", self._card(s.state, s.card))
            return
        self._run(s, text, emit, answer=not typed)

    def _text(self, s: Session, inp: TurnInput, emit: Emit) -> None:
        text = inp.text.strip()
        if not text:
            emit("card", self._card(s.state, s.card))
            return
        if inp.soft_only:
            # Extract on a detached draft: only ranking preferences may cross back, never trip facts or limits.
            draft = Session(s.id, with_meta(s.state.model_copy(deep=True), remember=False), s.card, list(s.transcript), list(s.photos))
            self._text(draft, inp.model_copy(update={"soft_only": False}), lambda *_: None)
            prior = Evidence(turn=s.state.meta.turn + 1, quote=text, tool="board:preference")
            soft = {**s.state.soft, **{k: f.model_copy(update={"evidence": (*f.evidence, prior), "requirement": None})
                                     for k, f in draft.state.soft.items() if f != s.state.soft.get(k)}}
            wishes = draft.state.wishes
            if soft == s.state.soft and wishes == s.state.wishes:
                wishes = wishes.model_copy(update={"kinds": (*wishes.kinds, KindWish(kind=text, quote=text))})
            s.state = s.state.model_copy(update={"soft": soft, "wishes": wishes})
            s.state = with_meta(s.state, turn=s.state.meta.turn + 1)
            say = "Mình ghi nhận điều bạn muốn như một ưu tiên mềm, không dùng để loại nơi."
            s.transcript.extend([{"role": "user", "text": text, "turn": s.state.meta.turn},
                                 {"role": "agent", "text": say, "turn": s.state.meta.turn}])
            emit("say", {"replace": say})
            emit("state", {"understanding": understanding(s.state, self.catalog, self.cfg)})
            return
        if isinstance(s.card, Deck):
            return self._run(s, text, emit)
        if s.state.meta.phase == "review":
            return self._review_text(s, text, emit)
        if s.state.meta.phase == "quiz":
            qq = None
            if s.state.meta.other_qid:
                qq = find_quiz(s.state.meta.other_qid, s.state, self.catalog, self.cfg)
            if qq is None and s.card is not None and is_quiz(s.card.qid):
                qq = find_quiz(s.card.qid, s.state, self.catalog, self.cfg) or s.card
            if qq is not None:
                return self._quiz_typed(s, qq, text, emit)
        self._run(s, text, emit)

    def _review_text(self, s: Session, text: str, emit: Emit) -> None:
        """A wish typed in review: a normal chat turn, then back to the review card."""
        self._run(s, text, emit)
        if s.state.meta.phase == "review" and s.card is not None:
            s.card = review_card()
            emit("card", self._card(s.state, s.card))

    # ---------- quiz phase: deterministic answers, no model ----------

    def _answer_offer(self, s: Session, inp: TurnInput, emit: Emit) -> None:
        """The F transition card of a session saved before it was dropped (every later question is a chip card now)."""
        if inp.text.strip():
            return self._text(s, inp, emit)
        picked = [c.id for c in (s.card.chips if s.card else ()) if c.id in inp.chips]
        if TO_QUIZ in picked:
            self._open_turn(s, "Làm trắc nghiệm", "answer")
            s.state = with_meta(s.state, phase="quiz")
            return self._quiz_next(s, emit)
        self._open_turn(s, "Kể thêm bằng chat", "answer")
        s.state = with_meta(s.state, phase="chat")
        s.card = conversation_card()
        emit("state", {"understanding": understanding(s.state, self.catalog, self.cfg)})
        emit("card", self._card(s.state, s.card))

    def _answer_review(self, s: Session, inp: TurnInput, emit: Emit) -> None:
        text = inp.text.strip()
        if not text:
            emit("card", self._card(s.state, s.card))
            return
        self._review_text(s, text, emit)

    def _answer_quiz(self, s: Session, q: Question, inp: TurnInput, emit: Emit) -> None:
        """A chip on a quiz card writes its drafts straight into the state. Typed
        text goes through the other-gate instead."""
        typed = inp.text.strip()
        if q.input == "date" and inp.value and not typed:
            return self._pick_date(s, inp.value, emit)
        if q.input in ("geo", "lodging", "transit") and inp.value and not typed:
            return self._pick_logistics(s, q, inp.value, emit)
        if typed:
            return self._quiz_typed(s, q, typed, emit)
        picked = [c for c in q.chips if c.id in inp.chips and c.id != OTHER_CHIP]
        if OTHER_CHIP in inp.chips and not picked:
            emit("say", {"replace": OTHER_TYPE_SAY})
            emit("card", self._card(s.state, s.card))
            return
        exit_ = next((x for x in ("skip", "unsure") if x in inp.chips), None)
        if exit_ is not None and not picked:
            turn = self._open_turn(s, EXIT_LABEL[exit_], "exit")
            s.state = with_meta(s.state, asked=s.state.meta.asked + (q.qid,),
                                declined=s.state.meta.declined + (q.text,),
                                unsure_streak=s.state.meta.unsure_streak + 1)
            s.transcript.append({"role": "agent", "text": DECLINE_SAY, "turn": turn, "kind": "say"})
            emit("say", {"replace": DECLINE_SAY})
            emit("state", {"understanding": understanding(s.state, self.catalog, self.cfg)})
            return self._quiz_next(s, emit)
        if not picked:
            emit("card", self._card(s.state, s.card))
            return
        turn = self._open_turn(s, ", ".join(c.label for c in picked), "answer")
        try:
            st = apply_chip(s.state, q, tuple(c.id for c in picked), turn)
        except (ValueError, ValidationError, IndexError):
            emit("error", {"message": BAD_VALUE})
            emit("card", self._card(s.state, s.card))
            return
        s.state = with_meta(st, asked=st.meta.asked + (q.qid,))
        emit("state", {"understanding": understanding(s.state, self.catalog, self.cfg)})
        return self._quiz_next(s, emit)

    def _pick_logistics(self, s: Session, q: Question, raw: str, emit: Emit) -> None:
        """A row picked on the origin / lodging card, or a coach / flight on the transit card (or only its time, typed
        when no trip was found). No model call; a chosen trip also sets the city's entry or exit point."""
        try:
            parsed = values.parse(q.qid, raw, self.catalog)
            if isinstance(parsed, str):  # only a time: the day starts (inbound) or ends (outbound) then
                shown, put = parsed, ("checkin_at" if q.qid == "inbound" else "checkout_at", parsed)
            elif q.qid in ("inbound", "outbound"):
                shown, put = f"{parsed.carrier} {parsed.depart_at[11:]}", None
            else:
                shown, put = parsed.text, (q.qid, parsed)
            turn = s.state.meta.turn + 1
            ev = Evidence(turn=turn, tool=f"quiz:{q.qid}")
            if put is None:
                st = pick_transit(s.state, q.qid, parsed, self.cfg, turn)
            else:
                st = settle(apply(s.state, Update(field=put[0], value=put[1], source="user", confidence="high",
                                                  evidence=ev)))
        except (ValueError, ValidationError, KeyError, TypeError):
            emit("error", {"message": BAD_VALUE})
            emit("card", self._card(s.state, s.card))
            return
        self._open_turn(s, shown, "answer")
        s.state = with_meta(st, asked=st.meta.asked + (q.qid,))
        emit("state", {"understanding": understanding(s.state, self.catalog, self.cfg)})
        return self._quiz_next(s, emit)

    def _quiz_typed(self, s: Session, q: Question, text: str, emit: Emit) -> None:
        """Typed text while a quick-reply card is open. Clear for the card's field (prepass, then Clef + parse) fills
        it straight away; anything else is a chat message: the agent reads it, the card stays answerable above."""
        if (filled := self._gate_fill(s, q, text)) is not None:
            turn = self._open_turn(s, text, "text")
            s.state = with_meta(filled, turn=turn, asked=filled.meta.asked + (q.qid,),
                                other_qid=None, other_text=None)
            emit("state", {"understanding": understanding(s.state, self.catalog, self.cfg)})
            return self._quiz_next(s, emit)
        s.state = with_meta(s.state, phase="chat", other_qid=None, other_text=None)
        self._run(s, text, emit)

    def _gate_fill(self, s: Session, q: Question, text: str) -> TripState | None:
        """Other-gate attempt without touching the transcript: deterministic reads
        first (prepass), then Clef + parse. Returns the new state, or None when the
        chat phase must resolve it."""
        field = QUIZ_FIELD.get(q.qid)
        if field is None:
            return None
        turn = s.state.meta.turn + 1
        pre = prepass(text, self.today())
        st = self._deterministic(with_meta(s.state, turn=turn), text, pre, turn)
        fields = {"times": ("checkin_at", "checkout_at"), "dates": ("start_date", "month", "month_part")}.get(q.qid, (field,))
        if any(p.field in fields for p in pre.proposals):
            return st
        if self.judge is not None and (label := FIELD_LABEL.get(field)) \
                and self.judge.clear_for_field(text, label):
            try:
                parsed = values.parse(field, text, self.catalog)
                return settle(apply(st, Update(field=field, op="set", value=parsed, source="user",
                                               confidence="high", evidence=Evidence(turn=turn, quote=text))))
            except (ValueError, ValidationError):
                pass
        return None

    def _quiz_next(self, s: Session, emit: Emit) -> None:
        """The next quiz card, or the review card when the queue is empty."""
        queue = quiz_queue(s.state, self.catalog, self.cfg)
        if not queue:
            turn = s.state.meta.turn
            s.state = with_meta(s.state, phase="review", other_qid=None, other_text=None)
            s.card = review_card()
            s.transcript.append({"role": "agent", "text": REVIEW_SAY, "turn": turn, "kind": "say"})
            emit("say", {"replace": REVIEW_SAY})
            emit("state", {"understanding": understanding(s.state, self.catalog, self.cfg)})
            emit("card", self._card(s.state, s.card))
            return
        s.state = with_meta(s.state, phase="quiz")
        s.card = queue[0]
        emit("state", {"understanding": understanding(s.state, self.catalog, self.cfg)})
        emit("card", self._card(s.state, s.card))

    def _run(self, s: Session, text: str, emit: Emit, may_ask: bool = True, quiet: bool = False,
             answer: bool = False, picked: bool = False, explored: tuple[str, ...] = (),
             chosen: list[dict] | None = None, chosen_ids: tuple[str, ...] = ()) -> None:
        """An agent turn whose reply is sent once, when it is final: every check (Clef, guard, trim, a retry) has
        already run, so the user never sees words that are then replaced. Progress, state and cards pass at once."""
        held: list[str] = []
        sent = False

        def flush() -> None:
            nonlocal sent
            if not sent and held:
                # the checked reply streams word by word (say_stream_s in all), so it reads like typing but is
                # already final: nothing shown is ever taken back
                text = "".join(held)
                words = re.findall(r"\S+\s*", text) if self.cfg.say_stream_s > 0 else []
                words = words or [text]
                pause = self.cfg.say_stream_s / max(1, len(words) - 1)
                emit("say", {"replace": words[0]})
                for w in words[1:]:
                    time.sleep(pause)
                    emit("say", {"delta": w})
            sent = True

        def hold(ev: str, data: dict) -> None:
            if ev == "say" and not sent:
                held[:] = [data["replace"]] if "replace" in data else [*held, data.get("delta") or ""]
                return
            if ev in ("card", "done"):  # the reply goes out just before what ends the turn
                flush()
            emit(ev, data)

        try:
            self._agent_turn(s, text, hold, may_ask, quiet, answer, picked, explored, chosen, chosen_ids)
        finally:
            flush()

    def _agent_turn(self, s: Session, text: str, emit: Emit, may_ask: bool = True, quiet: bool = False,
                    answer: bool = False, picked: bool = False, explored: tuple[str, ...] = (),
                    chosen: list[dict] | None = None, chosen_ids: tuple[str, ...] = ()) -> None:
        """One agent turn: record what the user said, then let the agent loop run until it asks, finishes or replies.
        answer: the text is an option the user pressed on the open card (it answers that card; Clef is not asked).
        picked: the deck already wrote that answer and opened the turn (`text` is its summary): the agent only reacts
        and chooses the next question. explored: with picked, what the user kept on the photo stage they just closed:
        the agent reads their taste from it and opens a new direction. chosen: with picked, what the user kept and
        passed over on each photo card, with what the kinds look like; chosen_ids: the places on the kept photos (the
        user saw them, so the reply may name them)."""
        if not picked and isinstance(s.card, Deck):
            for tab in s.card.tabs:
                if tab.kind == "drill":  # its photos were shown and the user typed instead: answered in words, not shown again
                    s.state = drill.skip(s.state, tab.qid.removeprefix("drill."))
        started_at = time.monotonic()
        before = st = s.state
        prev = s.card
        # Chat mode is plain words, never cards: the agent asks in text and the user types. Quiz and review
        # keep cards; the quiz detour (_quiz_typed) only borrows the chat to resolve a typed answer.
        chat = s.state.meta.phase == "chat"
        clarify = may_ask and (not s.state.meta.told or chat)
        stuck = s.state.meta.unsure_streak >= 2 or s.state.meta.idle_streak >= 2
        turn = st.meta.turn + (0 if picked else 1)
        if not picked:
            self._close_card(s)
            s.transcript.append({"role": "user", "text": text, "turn": turn, "kind": "text"})
        pre = prepass("" if picked else text, self.today())
        emit("preview", {"fields": [{"target": p.field, "value": values.jsonable(p.value), "quote": p.quote}
                                    for p in pre.proposals]})
        st = with_meta(st, turn=turn) if picked else self._deterministic(with_meta(st, turn=turn), text, pre, turn)
        st = derive(st, self.catalog, turn)  # what the words already answer is written before the agent reads the state
        st = self._care_nothing(s, prev, st, text, turn, picked)
        if not quiet:  # what the keyword rules read shows at once, before the agent's slower reply
            emit("state", {"understanding": understanding(st, self.catalog, self.cfg)})
        photos = None  # a drill just heard gets its photo card while the agent runs (no model call)
        if may_ask and not quiet:
            pool = ThreadPoolExecutor(1)
            if self.cfg.discovery and not self._user_asks(s):
                photos = pool.submit(drill.discover, st, self.catalog, self.looks, self.cfg, turn)
            elif not self.cfg.discovery:
                photos = pool.submit(drill.build, st, self.catalog, self.looks, self.cfg, cached_only=True)
            pool.shutdown(wait=False)
        compared = compared_places(text, self.catalog)
        heard = " ".join(t["text"] for t in s.transcript if t["role"] == "user")
        tools = TurnTools(st, text, turn, self.catalog, self.today(), compared, self.judge,
                          web=self.web if may_ask and not quiet else None, cards=may_ask and not quiet,
                          history=tuple((t["turn"], t["text"]) for t in s.transcript if t["role"] == "user"),
                          gaps=Path(self.cfg.gaps_path),
                          knowledge=self.knowledge, assistant=self.cfg.assistant.enabled and not quiet,
                          discovery=self.cfg.discovery and not quiet,
                          on_cards=lambda ids, why: send_cards(ids, why),
                          on_trace=lambda t: emit("progress", t),
                          # each fact reaches the summary as soon as the model has written it, not when the turn ends
                          on_state=None if quiet else lambda st: emit(
                              "state", {"understanding": understanding(st, self.catalog, self.cfg)}))
        if tools.assistant:  # what the user showed or pasted: the perceive tools read these (spec §5.2)
            tools.photos = s.photos
            tools.shown_log = last_shown(since_new_chat(s.transcript), self._name)
            tools.tag_seen, tools.tag_picked = tuple(blocks.recent_signatures(s.transcript)), tuple(blocks.picked_tags(s.transcript))
            tools.slots = {"photos": photo_context(s.photos), "links": links_in(text)}
        tools.told_ids |= set(chosen_ids)  # the places on the photos the user kept: they saw them, the reply may name them
        upcoming = None  # the photo card that opens under this reply: known before the agent writes, so it leads into it
        if photos is not None and self.cfg.discovery:
            try:  # the photo scores are prepared offline, so this is quick; a late card opens after the reply as before
                tools.state = drill.adopt(tools.state, photos.result(timeout=NEXT_CARD_WAIT_S))
                photos = None
                upcoming = next((d for d in tools.state.drills if d.status == "pending" and d.tab is not None), None)
            except Exception as exc:  # noqa: BLE001 - the card is optional
                tools.log.append(f"next_card_late {type(exc).__name__}")
        guard = None
        if tools.assistant and self.cfg.assistant.guard and self.judge is not None and not picked and not answer:
            # Clef reads the message for rules R1-R8 while the model works (spec 2026-10-29 §4); a hit stops the model
            # calls, the cards and the facts of this turn. Clef slow or down = ok.
            def guard_request(st, qs):
                started = time.monotonic()
                try:
                    return clef.ask(st, qs, self.cfg)
                finally:
                    tools.timings.append(f"t_guard phase=request seconds={time.monotonic() - started:.3f}")

            guard = Guarded(guard_request, text, threshold=self.cfg.assistant.guard_threshold,
                            **self._guard_context(s, tools))
            def verdict():
                started = time.monotonic()
                try:
                    return guard.verdict()
                finally:
                    tools.timings.append(f"t_guard phase=verdict seconds={time.monotonic() - started:.3f}")

            def blocked():
                started = time.monotonic()
                try:
                    return guard.blocked_now()
                finally:
                    tools.timings.append(f"t_guard phase=poll seconds={time.monotonic() - started:.3f}")

            tools.verdict = lambda: verdict().hit
            tools.blocked = blocked
        def reply_cards(say: str) -> None:
            # the places a text names, as cards, no model call: the whole ranked list of the search they came from
            if tools.card_lists or not say or any(b.get("kind") == "tags" for b in getattr(tools, "blocks", ())):
                return  # (a browse's subtag cards already show the places)
            if named := self._named(say, tools.told_ids | set(s.state.meta.shown_ids)):
                ranked = next((r for r in tools.rankings if set(named) & set(r)), [])
                tools.emit_cards(ranked + [p for p in named if p not in ranked])

        def send_cards(ids: list[str], why: str) -> None:
            # cards go out the moment a read tool answers the model, before its text is final (spec §2: thẻ trước)
            started = time.monotonic()
            try:
                emit("places", {"ids": ids, "why": why, "cards": self._cards(ids, tools.state, tools.scene_first)})
            finally:
                tools.timings.append(f"t_cards source=places count={len(ids)} seconds={time.monotonic() - started:.3f}")
        blocks.watch(tools, emit, lambda ids: self._cards(ids, tools.state, tools.scene_first))
        hints = [{"field": p.field, "value": values.jsonable(p.value), "quote": p.quote,
                  **({"written": True} if p.field in EXACT_FIELDS and not p.inferred else {})} for p in pre.proposals]
        hints += [{"ambiguous": q, "may_mean": list(k)} for q, k in pre.ambiguous]
        hints += [{"field": p.field, "value": values.jsonable(p.value), "quote": p.quote, "suggested": True}
                  for p in pre.suggestions]
        log = tools.log
        needed = missing(st, self.cfg.required)
        assistant = tools.assistant
        prefetched = None
        # a photo sent now or a link in the message is read by the agent itself (photo_identify, link_resolve): nothing is
        # prepared from its caption (a caption like "quán này ở đâu?" finds nothing) and no tool is hidden
        perceiving = bool(tools.slots.get("links")) or any(p.get("turn") == turn for p in s.photos)
        if assistant and self.cfg.assistant.prefetch and not picked and not perceiving:  # Clef picks the read tools; they run meanwhile
            pool = ThreadPoolExecutor(1)
            prefetched = pool.submit(self._prefetch, text, st, tools)
            pool.shutdown(wait=False)
        found = {} if picked else lookups(text, self.catalog)  # corpus lookups ready before the model reads the message
        tools._reply_lookups = found
        data = None
        if prefetched is not None:
            try:
                data, note = prefetched.result()
                log.append(note)
                if data and "dich_vu" in data and not tools.cards_blocked:  # a prepared answer shows its rows like a called one
                    if block := blocks.services_block(data["dich_vu"]):
                        tools.blocks.append(block)
                        emit("block", block)
            except Exception as exc:  # preparing is optional: the agent calls the read tools itself
                log.append(f"prefetch_failed {type(exc).__name__}")
        if assistant:  # names are matched by prefetch.candidates, and a prepared day needs no date tool
            tools.hidden = {"search_places"} | (set(DATE_TOOLS) if data and "thoi_tiet" in data else set())
            if self.cfg.assistant.hide_prepared_lookup and data and (data.get("tim_noi") or data.get("chi_tiet")):
                tools.hidden.add("find_places")  # the model re-searched what data holds: one 3-8 s call each time
            mode = self.cfg.assistant.covered_tools
            compound = re.search(r"[,;.!?…]\s*\w|\b(và|rồi|còn|từ|cách đi|đi lại|đồng thời|sao|vì sao|tại sao|why)\b", text, re.I)
            if mode in ("write", "none") and tools.route is not None and not compound and covers(tools.route, data):
                # Compound requests keep reads: group-level coverage cannot prove every clause was answered.
                # the prepared data answers every asked group: no lookup (each costs a 3-8 s second call)
                keep = {"record_fact", "browse_tags", "hide_place", "place_clips"} if mode == "write" else set()  # a broad ask still gets its subtags
                # only reads prefetch could have prepared go (and the ungrouped ones, web search): a tool prefetch never
                # prepares stays, so an ask Clef routed elsewhere ("hết bao nhiêu tiền", "homestay dưới 600k") still
                # finds estimate_cost / find_stays
                tools.hidden |= {n for n in tools.tool_names() if mode == "none" or (
                    n not in keep and ((t := REGISTRY.get(n)) is None or t.group is None or t.group in PREPARED_GROUPS))}
                log.append(f"covered tools={mode}")
        fit = fit_summary(st, self.catalog) if assistant else None  # the "Đang hợp" count and what narrows it
        now = self._local_now(st, tools) if assistant and self.cfg.discovery and not quiet else None
        known = self._remembered(s) if not quiet else None  # earlier chats' memos: a prior, never a fact of this trip
        messages = build_messages(st, text, since_new_chat(s.transcript)[:-1], prev.text if prev else None, self.today(), hints, compared,
                                   clarify, dict(needed), stuck, picked=picked, explored=explored, lookups=found, data=data,
                                   assistant=assistant, ask_words=self.cfg.assistant.ask_words,
                                   reply_style=self.cfg.assistant.reply_style, slots=tools.slots, discovery=self.cfg.discovery,
                                   fit=fit, chosen=chosen, local_now=now, remembered=known,
                                   next_card={"about": upcoming.topic, **({"opened_by_their_words": upcoming.quote} if upcoming.quote else {}),
                                              "kinds": [o.label for o in upcoming.tab.options if o.id not in ("skip", "other")]}
                                   if upcoming else None,
                                   name_of=lambda pid: p.name if (p := self.catalog.by_id.get(pid)) else None)
        tools.step("read", "Đọc lựa chọn của bạn" if picked else "Đọc tin nhắn của bạn", "ok")
        if assistant:
            tools.reply_hook = reply_cards
        said: list[str] = []

        def on_retry() -> None:
            # the model is asked again: what it streamed so far is not shown or kept
            said.clear()
            emit("say", {"replace": ""})

        def on_say(delta: str) -> None:
            said.append(delta)
            emit("say", {"delta": delta})

        try:
            asyncio.run(run_loop(self.chat, messages, tools, on_say, self.cfg.tool_steps, on_retry))
            tools.timings.append(f"t_agent {time.monotonic() - started_at:.1f}")
        except AgentError as exc:
            log.append(f"agent_error: {exc}")
            if not said:
                said.append((NOTED_SAY if tools.recorded else BUSY_SAY) if answer else FALLBACK_SAY)
                emit("say", {"replace": said[0]})
        finally:
            tools.close()
        if guard is not None and (hit := verdict()).hit:
            return self._refuse(s, before, prev, turn, text, hit, tools, started_at, emit)
        if photos is not None:
            try:
                tools.state = drill.adopt(tools.state, photos.result(timeout=DRILL_WAIT_S))
            except Exception as exc:  # a photo card is optional: the turn goes on without it (a slow one is built
                log.append(f"drill_build_failed {type(exc).__name__}")  # again on a later turn)
        if getattr(tools, "words", None):  # the model's own words on the photo card of this turn (the config's are the fallback)
            w = tools.words
            tools.state = tools.state.model_copy(update={"drills": tuple(
                d.model_copy(update={"tab": d.tab.model_copy(update={"question": w["question"], "why": w["why"],
                                                                     **({"header": w["header"]} if w["header"] else {})})})
                if (d.turn == turn or (upcoming and d.topic == upcoming.topic)) and d.tab is not None and d.status == "pending"
                else d for d in tools.state.drills)})
        if any(b.get("kind") == "tags" for b in getattr(tools, "blocks", ())):
            # the reply's tags / subtags already ask "which kind?": the photo question on the same taste would open over
            # them and ask it twice, so the taste's photo card is closed for this turn (the subtags win)
            tools.state = tools.state.model_copy(update={"drills": tuple(
                d.model_copy(update={"status": "none"}) if d.status == "pending" and d.turn == turn else d for d in tools.state.drills)})
            tools.told_ids |= {c["id"] for b in tools.blocks if b.get("kind") == "tags" for c in b["cards"]}  # Thích works on them
            log.append("tags_block_wins")
        say = "".join(said).strip()
        if not say and (tools.recorded or "step_cap" in log) and tools.asked is None:  # the agent wrote no reply: never leave the turn silent
            got = ", ".join(sorted({FIELD_LABEL.get(f, "thông tin chuyến đi") for f in tools.recorded}))
            say = (PARTIAL_SAY if "step_cap" in log else RECORDED_SAY).format(got=got) if got else NOT_DONE_SAY
            emit("say", {"replace": say})
        if not may_ask:  # refine (Chọn nơi) asks nothing: a question would go unanswered there
            plain = drop_questions(say)
            if plain != say:
                say = plain
                emit("say", {"replace": say})
        # An unmapped wish is the agent's to handle (see UNMAPPED in the prompt): its own text stays, checked
        # below like any reply. Only a silent turn keeps the recorded-facts fallback above.
        told = " ".join(tools.refusal_notes.values())
        if assistant:  # numbers in this turn's read results may be said, and the places they returned named
            told += " " + " ".join(map(str, sorted(tools.told_numbers)))
            if fit:  # the count on the screen and per wish (places_fitting): "chỉ 6 nơi có máy sưởi" is grounded
                told += f" {fit['now']} {fit['total']} {fit['past_hard_limits']} " + " ".join(
                    str(w["places_with_it"]) for w in fit["wishes"])
            # every place a result block holds (a tag's sample places, a service row that is a corpus place) may be named
            tools.told_ids |= {x for b in tools.blocks for x in _ids_in(b) if x in self.catalog.by_id}
        check = lambda x: bad_say(x, heard, tools.state, self.catalog, {c["id"] for c in compared},  # noqa: E731
                                  reply_language=language(text), told=told, allowed_ids=frozenset(tools.told_ids))
        invented = lambda x: w if (w := check(x)) and w.startswith(INVENTED) else None  # noqa: E731
        if assistant:  # a place the reply names that no tool returned: counted for the corpus (spec §B.5)
            for pid in {w.removeprefix("names place ") for x in re.split(r"(?<=[.!?…])\s+", say)
                        if (w := check(x)) and w.startswith("names place")}:
                gap(Path(self.cfg.gaps_path), text, "unsourced_place", subject=pid)
        if (why := check(say)) and why.startswith(INVENTED) and (kept := prune_say(say, invented)) and check(kept) is None:
            # only the sentences with a figure or a place nobody said go; the rest of the reply stays
            log.append(f"say pruned: {why}")
            say, why = kept, None
            emit("say", {"replace": say})
        if why := (why or tools.rejected_claim(say) or (tools.reply_problem() if say else None)):
            log.append(f"say replaced: {why}")
            # never leave a question without a visible reply; a told trip gets an honest pointer to the summary
            say = (NOTED_TEXT_SAY if "?" not in text and tools.recorded else UNSURE_SAY) if say else ""
            emit("say", {"replace": say})
        if language(text) == "en" and say and language(say) != "en":
            say = "I could not finish understanding that. Please tell me again."
            emit("say", {"replace": say})
        if assistant and NO_ANSWER.search(fold(say)):  # the data had no answer: counted for the corpus (spec §B.5)
            first = max(sorted(tools.route.groups), key=lambda g: tools.route.probs.get(g, 0)) if tools.route and tools.route.groups else None
            gap(Path(self.cfg.gaps_path), text, "no_answer", topic=first)
        short = trim_words(say, self.cfg.assistant.reply_words) if assistant else trim_say(say)
        if short != say:
            say = short
            emit("say", {"replace": say})
        last_ask = next((t["text"] for t in reversed(since_new_chat(s.transcript)[:-1]) if t["role"] == "agent" and t.get("kind") == "say"), "")
        if may_ask and same_question(say, last_ask):
            # the user went on without answering the question: it is not asked again (testers, 2026-10-16)
            log.append("same_question")
            say = drop_questions(say) or MOVE_ON_SAY
            emit("say", {"replace": say})
        invited = False
        if assistant and INVITE.search(say):
            if s.state.meta.invited:  # planning is offered once a session: the talk goes on without asking again
                log.append("invite_again")
                say = drop_questions(say)
                emit("say", {"replace": say})
            else:
                invited = True
        if may_ask and asks_settled_care(say) and "care" not in dict(missing(tools.state, self.cfg.required)):
            # Lưu ý is answered with a safe limit already: how strict it is is not asked again (testers, 2026-10-16)
            log.append("care_asked_again")
            say = drop_questions(say)
            emit("say", {"replace": say})
        card = None
        if self.cfg.discovery and may_ask and not quiet and tools.asked is None and not self._user_asks(s):
            tools.state = drill.discover(tools.state, self.catalog, self.looks, self.cfg, turn)
        if may_ask and tools.asked is not None and asks_in_text(say):
            # a card is this turn's one question: the reply keeps its reaction, never a second question beside it
            log.append("card_is_the_question")
            say = drop_questions(say)
            emit("say", {"replace": say})
        if (may_ask and tools.asked is None and asks_in_text(say) and upcoming is None
                and any(d.turn == turn and d.status == "pending" and d.tab is not None for d in tools.state.drills)):
            # (with next_card the reply may offer the card in a question, "bạn muốn xem thử không?": kept)
            # the taste the user just named has its photo card: the photos are this turn's one question, so the
            # agent's own question in words gives way to them
            log.append("drill_first")
            say = drop_questions(say)
            emit("say", {"replace": say})
        final = tools.finalize_reply(say)
        if final != say:
            say = final
            emit("say", {"replace": say})
        s.transcript.append({"role": "system", "text": "; ".join(log) or "no tools", "turn": turn,
                             "tools": {"recorded": list(tools.recorded), "refused": dict(tools.refusal_notes),
                                       "unmapped": list(tools.unmapped)},
                             "timings": list(tools.timings)})  # model call seconds and cached_tokens (the bench reads them)
        if say:
            s.transcript.append({"role": "agent", "text": say, "turn": turn, "kind": "say"})
        if assistant:
            reply_cards(say)  # a reply that names places no card has shown yet: they go out now
            try:
                if not any(b.get("kind") == "tags" for b in tools.blocks) and (block := blocks.prepared_dish_block(tools, found, lambda ids: self._cards(ids, tools.state, tools.scene_first))):
                    tools.blocks.append(block)
                    emit("block", block)
            except Exception as exc:  # noqa: BLE001 - a block is an extra: the reply must not fail for it
                log.append(f"dish_block_failed {type(exc).__name__}")
            if (data and "xu_huong" in data or any(x.split(" ")[0] == "trends" for x in log)) and self.knowledge is not None and not tools.cards_blocked:
                # a trends question: the short reply, then what is on and in season laid out as rows (no model writes them)
                try:
                    rows = self.knowledge.trend_rows(tools.state, ("event", "season", "trend", "hot", "top"))
                    if block := blocks.trends_block(rows, blocks.trend_kinds(fold(text)),
                                                    lambda ids: self._cards(ids, tools.state, tools.scene_first)):
                        tools.blocks.append(block)
                        emit("block", block)
                except Exception as exc:  # noqa: BLE001
                    log.append(f"trends_block_failed {type(exc).__name__}")
        for shown in tools.card_lists:  # the assistant's cards (already on the screen) are kept with the reply
            s.transcript.append({"role": "agent", "text": "", "turn": turn, "kind": "places", **shown})
        for block in getattr(tools, "blocks", ()):  # dish / services results, kept with the reply like the cards
            s.transcript.append({"role": "agent", "text": "", "turn": turn, "kind": "block", "block": block})
        if tools.quick:
            s.transcript.append({"role": "agent", "text": "", "turn": turn, "kind": "replies", "options": tools.quick})
            emit("replies", {"options": tools.quick})
        kept = tools.settle_refusals(dict(s.state.meta.refusal_turns))
        tools.state = derive(tools.state, self.catalog, turn)
        s.state = with_meta(tools.state, refusal_turns=tuple(sorted(kept.items())))
        if assistant:
            m = s.state.meta
            s.state = with_meta(s.state, invited=m.invited or invited,
                                shown_ids=tuple(dict.fromkeys((*m.shown_ids, *sorted(tools.told_ids))))[-SHOWN_KEEP:],
                                told_numbers=tuple(dict.fromkeys((*m.told_numbers, *sorted(tools.told_numbers))))[-TOLD_KEEP:])
        if may_ask and isinstance(prev, Deck) and VAGUE.search(fold(text)):
            # an open required card answered in words like "chưa chốt" / "bỏ qua" and still not filled: the same as its
            # Bỏ qua (asked again at the read-back before planning), so the talk moves on instead of showing it again
            still = {k for k, _ in missing(s.state, self.cfg.required)}
            put_off = [t.qid for t in prev.tabs if t.kind == "required" and t.qid in still]
            if put_off:
                log.append(f"put_off {put_off}")
                s.state = with_meta(s.state, declined=tuple(dict.fromkeys((*s.state.meta.declined, *put_off))))
        if tools.asked is not None and may_ask:
            card = self._asked(s, tools, turn)
            if tools.asked["kind"] == "agent" and not (isinstance(card, Deck) and any(t.kind in ("agent", "drill") for t in card.tabs)):
                # the post-check kept no question (code drops what it cannot offer): the agent's own words carry it
                # on, because the turn ended at ask_user and wrote no reply
                log.append("ask_dropped")
                if not say and (own := next((str(q.get("question") or "").strip() for q in tools.asked["questions"]), "")):
                    say = own
                    s.transcript.append({"role": "agent", "text": say, "turn": turn, "kind": "say"})
                    emit("say", {"replace": say})
        if _learned(before, tools.state, tools.recorded) or tools.asked is not None:
            s.state = with_meta(s.state, unsure_streak=0, idle_streak=0)
        elif may_ask:
            # an adaptive turn that added nothing: the user may be stuck (surfaced as `stuck` next turn)
            s.state = with_meta(s.state, idle_streak=s.state.meta.idle_streak + 1)
        if clarify and (card is not None or s.state.model_copy(update={"meta": before.meta}) != before):
            # the trip was told (something was read or asked; a greeting or "không đi nữa" is not a telling). An agent
            # that failed still leaves the keyword reads: the quiz asks the rest when the user switches to it.
            s.state = with_meta(s.state, told=True)
        if quiet:
            return
        resumed = False
        if may_ask and s.state.meta.other_qid:
            # the chat just resolved a typed quiz answer: back to the quiz, one card further
            other = s.state.meta.other_qid
            if _learned(before, tools.state, pending_fields(other)):
                s.state = with_meta(tools.state, other_qid=None, other_text=None,
                                    asked=tools.state.meta.asked + (other,))
                resumed = True
            elif (qq := find_quiz(other, tools.state, self.catalog, self.cfg)) is not None:
                card = qq  # not resolved yet: the chat clarifies, the chips stay available
        failed = "step_cap" in log or any(x.startswith("agent_error") for x in log)
        if self.cfg.discovery:
            if card is None and not failed and may_ask and not self._user_asks(s) and not asks_in_text(say):
                s.state = drill.discover(s.state, self.catalog, self.looks, self.cfg, turn)
        elif card is None and not failed and may_ask and (due := self._due_required(s, say)):
            log.append(f"required_fallback {due}")
            if asks_in_text(say):
                say = drop_questions(say)
                emit("say", {"replace": say})
                if s.transcript and s.transcript[-1].get("kind") == "say":
                    s.transcript[-1]["text"] = say
            s.state = with_meta(s.state, nudged=(*s.state.meta.nudged, due))
            card = deck.build(s.state, self.catalog, self.cfg, ask=due)
        # a failed agent leaves the text box: the user says it again before anything else is asked
        s.card = card or (conversation_card() if failed else self._next(s, say, leads=upcoming is not None))
        if may_ask:
            own = (s.card.qid == "conversation" and asks_in_text(say)) or (
                isinstance(s.card, Deck) and any(t.kind in ("agent", "drill") for t in s.card.tabs))
            s.state = with_meta(s.state, followups=s.state.meta.followups + 1 if own else 0)
        st = s.state
        log_turn(s.id, turn, text, log + tools.timings + [f"t_turn {time.monotonic() - started_at:.1f}"], say, s.card.qid, {
            "companions": sorted(map(str, st.companions.value or ())), "start_date": str(st.start_date.value),
            "days": st.days.value, "unmapped": [u.phrase for u in st.unmapped]})
        if not resumed:
            emit("state", {"understanding": understanding(s.state, self.catalog, self.cfg)})
            emit("card", self._card(s.state, s.card))
            return
        self._quiz_next(s, emit)

    def _care_nothing(self, s: Session, prev, st: TripState, text: str, turn: int, picked: bool) -> TripState:
        """"Không có gì" to the open Lưu ý question is the answer (care = none), written whatever the agent does next, so the
        gate does not ask it again. Only while that question is open (a care card, or the last reply asked about it)."""
        if picked or (st.care.known and st.care.source == "user") or not (quote := says_nothing(text)):
            return st
        card_open = isinstance(prev, Deck) and any(t.qid == "care" for t in prev.tabs)
        said = next((t["text"] for t in reversed(s.transcript[:-1]) if t["role"] == "agent" and t.get("kind") == "say"), "")
        care_question = any(x.rstrip().endswith("?") and "luu y" in fold(x)
                            for x in re.split(r"(?<=[.!?…])\s+", said))
        if not (card_open or asks_settled_care(said) or care_question):
            return st
        return apply(st, Update(field="care", value="none", source="user", confidence="high",
                                evidence=Evidence(turn=turn, quote=quote)))

    def _guard_context(self, s: Session, tools: TurnTools) -> dict:
        """What Clef reads next to the message: the user's message before, the start of the last answer, place names just shown."""
        said = [t for t in s.transcript[:-1] if t["role"] == "user" and t.get("kind") == "text"]
        answered = next((t["text"] for t in reversed(s.transcript[:-1]) if t["role"] == "agent" and t.get("kind") == "say"), "")
        shown = next((t["ids"] for t in reversed(s.transcript) if t.get("kind") == "places" and t.get("ids")), [])
        return {"prev_user": said[-1]["text"] if said else "", "prev_reply": answered,
                "shown": [n for pid in shown if (n := self._name(pid))]}

    def _refuse(self, s: Session, before: TripState, prev, turn: int, text: str, hit, tools: TurnTools, started_at: float,
                emit: Emit) -> None:
        """The rule guard stopped the turn: the label's fixed reply, nothing the user said in it is recorded (the state is the
        one before the turn), no card or question goes out."""
        say = rule_reply(hit.label, text)
        emit("say", {"replace": say})
        s.state = with_meta(before, turn=turn)
        s.transcript.append({"role": "system", "text": "; ".join([*tools.log, f"rule_guard {hit.label} {hit.prob:.2f}"]),
                             "turn": turn, "tools": {"recorded": [], "refused": {}, "unmapped": []}})
        s.transcript.append({"role": "agent", "text": say, "turn": turn, "kind": "say"})
        s.card = prev if isinstance(prev, Deck) else conversation_card()
        log_turn(s.id, turn, text, [*tools.log, *tools.timings, f"rule_guard {hit.label} {hit.prob:.2f}", f"t_turn {time.monotonic() - started_at:.1f}"],
                 say, s.card.qid)
        emit("state", {"understanding": understanding(s.state, self.catalog, self.cfg)})
        emit("card", self._card(s.state, s.card))

    def _like(self, s: Session, inp: TurnInput, emit: Emit) -> None:
        """Thích on a chat place card (no model call): on = a want anchor of that place, off = that anchor gone.
        Only a place the assistant showed this session, or one the tag stage listed (a place the trip's limits allow)."""
        pid = inp.target
        offered = pid in s.state.meta.shown_ids or (self.knowledge is not None and inp.qid == "stage" and self.knowledge.fits(pid, s.state))
        if not offered or pid not in self.catalog.by_id or inp.value not in ("on", "off"):
            raise ValueError("like needs a place shown in this chat and value on or off")
        kept = tuple(a for a in s.state.anchors if not (a.place_id == pid and a.priority == "want"))
        if inp.value == "on" and not any(a.place_id == pid for a in kept):  # a must-go stays a must-go
            kept += (Anchor(text=self.catalog.by_id[pid].name, place_id=pid, state="matched", priority="want"),)
        s.state = settle(s.state.model_copy(update={"anchors": kept}))
        if inp.value == "on" and pid not in s.state.meta.shown_ids:
            s.state = with_meta(s.state, shown_ids=(*s.state.meta.shown_ids, pid)[-SHOWN_KEEP:])
        s.transcript.append({"role": "system", "text": f"like {inp.value} {pid}", "turn": s.state.meta.turn})
        emit("state", {"understanding": understanding(s.state, self.catalog, self.cfg)})

    def _wish(self, s: Session, inp: TurnInput, emit: Emit) -> None:
        """Thích cả kiểu này on a tag or subtag card of the stage (no model call): a soft kind wish whose places are the node's
        places the trip allows. qid = the tags block, target = the node path, value on / off. Never a hard filter."""
        if inp.value not in ("on", "off"):
            raise ValueError("wish needs value on or off")
        if inp.target.startswith("wishes:") and inp.value == "off":
            _, kind, index = inp.target.split(":", 2)
            if kind not in {"dishes", "kinds", "like"} or not index.isdecimal():
                raise ValueError("invalid wish target")
            rows = getattr(s.state.wishes, kind)
            if int(index) >= len(rows):
                raise ValueError("invalid wish index")
            s.state = s.state.model_copy(update={"wishes": s.state.wishes.model_copy(
                update={kind: tuple(w for i, w in enumerate(rows) if i != int(index))})})
            s.transcript.append({"role": "system", "text": f"wish off {inp.target}", "turn": s.state.meta.turn})
            emit("state", {"understanding": understanding(s.state, self.catalog, self.cfg)})
            return
        node = self._stage_node(s, inp.qid, [r for r in inp.target.split("/") if r])
        if not node.get("ids"):  # a tag ref this release no longer knows (an old chat): nothing to wish for, keep the wishes
            emit("state", {"understanding": understanding(s.state, self.catalog, self.cfg)})
            return
        label = node["label"]
        kept = tuple(w for w in s.state.wishes.kinds if squash(w.kind) != squash(label))
        if inp.value == "on":
            kept += (KindWish(kind=label, quote=label, place_ids=tuple(node["ids"][:WISH_PLACES])),)
        s.state = s.state.model_copy(update={"wishes": s.state.wishes.model_copy(update={"kinds": kept})})
        s.transcript.append({"role": "system", "text": f"wish {inp.value} {label}", "turn": s.state.meta.turn})
        emit("state", {"understanding": understanding(s.state, self.catalog, self.cfg)})

    def _explored(self, s: Session, inp: TurnInput, emit: Emit) -> None:
        """Xong on a photo stage where the user kept something (chips = "place:<id>" of the places and the labels of the
        kinds they kept; the like and wish turns already wrote them): the agent reads what the picks say of their taste
        and opens a new direction. Only a place this chat holds as a want or a kind it holds as a wish counts: the
        client never writes the prompt."""
        held = {squash(w.kind): w.kind for w in s.state.wishes.kinds}
        held |= {f"place:{a.place_id}": self._name(a.place_id) or a.text for a in s.state.anchors if a.priority == "want" and a.place_id}
        picks = tuple(dict.fromkeys(held[k] for c in inp.chips[:EXPLORED_MAX]
                                    if (k := c if c.startswith("place:") else squash(c)) in held))
        if not picks:
            raise ValueError("explored needs places or kinds this chat recorded")
        shown = " · ".join(picks[:EXPLORED_SHOWN]) + (f" và {len(picks) - EXPLORED_SHOWN} nữa" if len(picks) > EXPLORED_SHOWN else "")
        # what each pick is, for the agent: a place's kind, a kind's first places (the stage showed them)
        wished = {squash(w.kind): w for w in s.state.wishes.kinds}
        kept, ids = [], []
        for c in dict.fromkeys(inp.chips[:EXPLORED_MAX]):
            if c.startswith("place:") and c in held:
                place = self.catalog.by_id.get(pid := c.removeprefix("place:"))
                kept.append({"place": held[c], **({"is_a": place.category} if place and place.category else {}),
                             "looks": self._looks_of(pid), "known_for": self._known_for(pid)})
                ids.append(pid)
            elif (w := wished.get(squash(c))) is not None:
                kept.append({"kind": w.kind, "looks": self._common_look(w.place_ids),
                             "for_example": [self._name(p) for p in w.place_ids[:2]]})
                ids.extend(w.place_ids[:2])
        self._open_turn(s, f"Mình chọn: {shown}", "explored")
        self._run(s, s.transcript[-1]["text"], emit, picked=True, explored=picks,
                  chosen=[{"kept": kept}], chosen_ids=tuple(ids))

    def _tag(self, s: Session, inp: TurnInput, emit: Emit) -> None:
        """A tap on a tag card (no model call): the chat opens that tag, as its subtags when they split its places well
        and as its places otherwise. The trip's hard limits and the places the user hid apply."""
        if self.knowledge is None:
            raise ValueError("no corpus")
        out = self.knowledge.browse.tag(inp.target, s.state)  # ValueError: not a tag the chat offered
        label = out["tag"]["label"]
        turn = self._open_turn(s, label, "tag")
        s.transcript[-1]["ref"] = inp.target
        cards_of = lambda ids: self._cards(ids, s.state)  # noqa: E731
        block = blocks.tags_block(out, cards_of, title=label, cover_fit=self._cover_fit)
        ids = [c["id"] for c in block["cards"]] if block else list(out.get("_cards") or ())[:self.knowledge.cards_max]
        say = (f"{label} có {len(block['subtags'])} kiểu, bạn bấm một kiểu để xem nơi." if block else
               f"Đây là các nơi {label.lower()} hợp với chuyến của bạn." if ids else f"Mình chưa có nơi {label.lower()} nào phù hợp với chuyến này.")
        s.transcript.append({"role": "agent", "text": say, "turn": turn, "kind": "say"})
        emit("say", {"replace": say})
        if block:
            s.transcript.append({"role": "agent", "text": "", "turn": turn, "kind": "block", "block": block})
            emit("block", block)
        elif ids:
            s.transcript.append({"role": "agent", "text": "", "turn": turn, "kind": "places", "ids": ids, "why": label})
            emit("places", {"ids": ids, "why": label, "cards": cards_of(ids)})
        m = s.state.meta
        s.state = with_meta(s.state, shown_ids=tuple(dict.fromkeys((*m.shown_ids, *ids)))[-SHOWN_KEEP:])
        s.card = self._next(s, say)
        emit("state", {"understanding": understanding(s.state, self.catalog, self.cfg)})
        emit("card", self._card(s.state, s.card))

    def _prefetch(self, text: str, st: TripState, tools: TurnTools) -> tuple[dict, str]:
        """The assistant's prepared data (agent/prefetch.py): candidates -> one Clef request -> the read tools at once,
        waiting at most cfg.assistant.prefetch_wait_s in all. -> (data, the turn-log line)."""
        from ..agent.prefetch import Route

        started = time.monotonic()
        deadline = started + max(0.0, self.cfg.assistant.prefetch_wait_s)
        early = start_weather(st, tools)  # runs while Clef is asked

        def routing():
            cands = candidates(text, self.catalog, self.cfg.assistant.max_candidates)
            clef_started = time.monotonic()
            try:
                return route(text, cands, self.cfg, ask=clef.ask if self.judge is not None else (lambda *_: {}), today=self.today())
            finally:
                tools.timings.append(f"t_prefetch_clef seconds={time.monotonic() - clef_started:.3f}")

        pool = ThreadPoolExecutor(1, thread_name_prefix="prefetch-route")
        future = pool.submit(routing)
        expired = False
        try:
            r = future.result(timeout=max(0.0, deadline - time.monotonic()))
        except TimeoutError:
            expired = True
            r = Route(set(), [])  # only completed early reads, no guessed routing decision
            tools.timings.append(f"t_prefetch_clef_pending seconds={time.monotonic() - started:.3f}")
        finally:
            pool.shutdown(wait=False, cancel_futures=True)
        tools.route = r  # a late routing worker never changes the turn's route or starts more tools
        left = max(0.0, deadline - time.monotonic())
        data = prepare(r, text, st, tools, self.today(), left, early)
        expired = expired or time.monotonic() >= deadline
        return data, (f"prefetch groups={','.join(sorted(r.groups)) or '-'} places={len(r.places)} "
                      f"clef={r.clef_s:.2f}s wait={time.monotonic() - started:.2f}s deadline={int(expired)}")

    # ---------- answers the agent does not need to read ----------

    def _decline(self, s: Session, q: Question, exit_: str, emit: Emit) -> None:
        """"Bỏ qua" / "Chưa chắc": the field stays unknown and the question is never asked again. No model call."""
        turn = self._open_turn(s, EXIT_LABEL[exit_], "exit")
        s.state = with_meta(s.state, declined=s.state.meta.declined + (q.text,),
                            unsure_streak=s.state.meta.unsure_streak + 1)
        self._close_turn(s, DECLINE_SAY, turn, emit)

    def _pick_date(self, s: Session, raw: str, emit: Emit) -> None:
        """A day picked on the calendar card is the start date the user chose. No model call."""
        try:
            day = date.fromisoformat(raw.strip()[:10])
        except ValueError:
            emit("error", {"message": BAD_VALUE})
            return
        if day < self.today():
            emit("error", {"message": PAST_DATE})
            return
        shown = f"{day.day}/{day.month}/{day.year}"
        turn = self._open_turn(s, shown, "answer")
        s.state = settle(apply(s.state, Update(field="start_date", value=day, source="user", confidence="high",
                                               evidence=Evidence(turn=turn, tool="date_picker"))))
        if s.state.meta.phase == "quiz" and s.card is not None and s.card.qid == "dates":
            s.state = with_meta(s.state, asked=s.state.meta.asked + ("dates",))
            emit("say", {"replace": DATE_SAY.format(day=shown)})
            emit("state", {"understanding": understanding(s.state, self.catalog, self.cfg)})
            return self._quiz_next(s, emit)
        self._close_turn(s, DATE_SAY.format(day=shown), turn, emit)

    def _theme(self, s: Session, inp: TurnInput, emit: Emit) -> None:
        """A theme card of Khám phá: its fixed tastes (config/trip.yaml `themes`) are written as they are; no sentence
        is read. They are the user's choice but not confirmed, so anything said later overrides them."""
        th = self.cfg.themes.get(inp.value or "")
        if th is None:
            emit("error", {"message": THEME_UNKNOWN})
            return
        turn = self._open_turn(s, th["title"], "theme")
        ev = Evidence(turn=turn, tool=f"theme:{inp.value}")
        st = s.state
        for raw in th.get("soft", ()):
            key, weight = values.split_weight(raw)
            st = apply(st, Update(field="soft", op="add", value=(str(SoftKey.parse(key)), weight), source="user",
                                  confidence="medium", evidence=ev))
        for g in th.get("groups", ()):
            st = apply(st, Update(field="liked_groups", op="add", value=g, source="user", confidence="medium",
                                  evidence=ev))
        s.state = with_meta(settle(st), told=True)  # the theme is the telling; the user picks chat or quiz next
        self._close_turn(s, THEME_SAY.format(title=th["title"], what=th["say"]), turn, emit)

    def _open_turn(self, s: Session, shown: str, kind: str) -> int:
        turn = s.state.meta.turn + 1
        self._close_card(s)
        s.transcript.append({"role": "user", "text": shown, "turn": turn, "kind": kind})
        s.state = with_meta(s.state, turn=turn)
        return turn

    def _close_turn(self, s: Session, say: str, turn: int, emit: Emit) -> None:
        """Ends a turn the agent did not run. The session stays in its phase: the quiz moves to its next
        card, chat keeps the text box open."""
        if s.state.meta.phase == "quiz":
            s.transcript.append({"role": "agent", "text": say, "turn": turn, "kind": "say"})
            emit("say", {"replace": say})
            return self._quiz_next(s, emit)
        s.card = self._next(s, say)
        if s.card.qid == "conversation" and not missing(s.state, self.cfg.required):
            say += NEXT_READY
        s.transcript.append({"role": "agent", "text": say, "turn": turn, "kind": "say"})
        emit("say", {"replace": say})
        emit("state", {"understanding": understanding(s.state, self.catalog, self.cfg)})
        emit("card", self._card(s.state, s.card))

    def _edit(self, s: Session, inp: TurnInput, emit: Emit) -> None:
        ev = Evidence(turn=s.state.meta.turn, tool="edit")

        def user(field, value=None, op="set"):
            return Update(field=field, op=op, value=value, source="user", confidence="high", evidence=ev)

        kind, _, arg = inp.target.partition(":")
        v = inp.value
        if kind == "vibe":  # the ticket's ✕ on a look: it ranks nothing any more
            if not arg.isdigit() or int(arg) >= len(s.state.vibes) or v is not None:
                emit("error", {"message": BAD_VALUE})
                return
            gone = list(s.state.vibes)
            del gone[int(arg)]
            s.state = s.state.model_copy(update={"vibes": tuple(gone)})
            emit("state", {"understanding": understanding(s.state, self.catalog, self.cfg)})
            return
        try:
            if kind in SCALARS:
                if v is None:
                    u = user(kind, op="remove")
                else:
                    parsed = values.parse(kind, v, self.catalog)
                    if isinstance(parsed, str) and kind in ("inbound", "outbound"):  # only a time was typed: no trip to store
                        u = user("checkin_at" if kind == "inbound" else "checkout_at", parsed)
                    else:
                        u = user(kind, parsed)
            elif kind in ("companions", "liked_groups"):
                u = user(kind, [x for x in (v or "").split(",") if x])
            elif kind == "soft":
                u = user("soft", arg, "remove") if v is None else user("soft", (arg, v))
            elif kind == "hard":
                u = user("hard", arg, "remove") if v is None else user("hard_policy", (arg, v))
            elif kind in ("anchor", "unmapped"):
                u = user(kind, int(arg), "remove")
            elif kind == "signal":
                u = user("signal", arg, "remove")
            else:
                raise ValueError(f"unknown target {inp.target!r}")
            removed = s.state.soft.get(arg) if self.cfg.discovery and kind == "soft" and v is None else None
            s.state = settle(apply(s.state, u))
            if removed is not None:
                origins = {(e.tool.removeprefix("deck:drill."), e.turn) for e in removed.evidence
                           if e.tool and e.tool.startswith("deck:drill.")}
                s.state = s.state.model_copy(update={"vibes": tuple(
                    look for look in s.state.vibes if (look.phrase, look.turn) not in origins)})
        except (ValueError, ValidationError, IndexError):
            emit("error", {"message": BAD_VALUE})
            return
        emit("state", {"understanding": understanding(s.state, self.catalog, self.cfg)})

    def _more(self, s: Session, inp: TurnInput, emit: Emit) -> None:
        """"Hỏi tiếp": kept as an alias of the mode bar's to_quiz (an unanswered open card counts as declined)."""
        return self._to_quiz(s, inp, emit)

    def _to_chat(self, s: Session, inp: TurnInput, emit: Emit) -> None:
        """The mode bar: free chat from here on (plain words, no cards). An open card left unanswered counts
        as declined: it is never asked again in either mode."""
        if s.state.meta.phase == "chat":
            emit("card", self._card(s.state, s.card))
            return
        self._close_card(s)
        self._decline_open_card(s)
        turn = s.state.meta.turn + 1
        s.transcript.append({"role": "user", "text": "Trò chuyện tự do", "turn": turn, "kind": "answer"})
        s.state = with_meta(s.state, turn=turn, phase="chat")
        s.card = conversation_card()
        emit("state", {"understanding": understanding(s.state, self.catalog, self.cfg)})
        emit("card", self._card(s.state, s.card))

    def _to_quiz(self, s: Session, inp: TurnInput, emit: Emit) -> None:
        """The mode bar: quick chip cards from here on. An open card left unanswered counts as declined:
        it is never asked again in either mode."""
        if s.state.meta.phase == "quiz":
            emit("card", self._card(s.state, s.card))
            return
        was_review = s.card is not None and s.card.qid == REVIEW_QID
        self._close_card(s)
        self._decline_open_card(s)
        turn = s.state.meta.turn + 1
        s.transcript.append({"role": "user", "text": "Làm trắc nghiệm nhanh", "turn": turn, "kind": "answer"})
        s.state = with_meta(s.state, turn=turn, phase="quiz")
        if was_review and not quiz_queue(s.state, self.catalog, self.cfg):
            s.card = review_card()
            emit("state", {"understanding": understanding(s.state, self.catalog, self.cfg)})
            emit("card", self._card(s.state, s.card))
            return
        self._quiz_next(s, emit)

    def _decline_open_card(self, s: Session) -> None:
        """An open question left unanswered on a mode switch: never asked again in either mode."""
        q = s.card
        if q is None or q.qid in ("conversation", "frame"):
            return
        s.state = with_meta(s.state, asked=s.state.meta.asked + (q.qid,),
                            declined=s.state.meta.declined + (q.text,))

    def _show(self, s: Session, inp: TurnInput | None, emit: Emit) -> None:
        # Next is always open: unknown fields ride along as unknowns. An open health / body / diet hint gets the
        # strictest answer of its card (fail-closed); if one still stays open, Next waits for it.
        if pending_signals(s.state):
            s.state = apply_drafts(s.state, strictest(s.state), s.state.meta.turn, tool="next:strictest")
        if pending_signals(s.state):
            say = MISSING_SAY.format(items="điều cần lưu ý về sức khỏe")
            s.transcript.append({"role": "agent", "text": say, "turn": s.state.meta.turn, "kind": "say"})
            emit("say", {"replace": say})
            emit("card", self._card(s.state, s.card))
            return
        si = self._compile(s.state)
        self._remember(s)
        self._close_card(s)
        s.card = None
        s.transcript.append({"role": "agent", "text": DONE_SAY, "turn": s.state.meta.turn, "kind": "done"})
        emit("done", {"search_input": si.model_dump(mode="json")})

    # ---------- helpers ----------

    def _deterministic(self, st: TripState, text: str, pre: Prepass, turn: int) -> TripState:
        """Links, pasted place lists, keyword matches: written before the agent so nothing depends on it.

        Only high-precision prepass proposals reach the state (dates, counts, money, explicit body
        signals, effort hard filters). Suggestions (who goes, transport, pace, novelty, kinds of place)
        are agent-only hints: the agent reads the user's words and records them via record_fact.
        """
        from ..domain import diet
        diet_before = diet.progress(st)
        diet_pending = diet.question(st)
        st, scoped_diet = diet.record(st, text, turn)
        lines = [x.strip() for x in text.splitlines() if x.strip()]
        names = [x for x in lines if not URL.match(x)] if len(lines) >= 2 else []
        for raw in URL.findall(text) + names:
            a = anchor_for(raw, self.catalog)
            if a.state == "missing" and not URL.match(raw):
                continue
            st = apply(st, Update(field="anchor", op="add", value=a, source="user", confidence="high",
                                  evidence=Evidence(turn=turn, quote=raw)))
        for p in pre.proposals:
            if scoped_diet and (p.field in {"start_date", "days", "month", "month_part"} and not diet.DIET.search(fold(text))
                                or p.field == "signal" and p.value in {"vegetarian", "vegan"}):
                continue
            if p.field not in APPLIED_FIELDS:
                continue
            try:
                if p.field == "start_date" and st.start_date.known and st.start_date.value != p.value:
                    from ..domain.dates import FULL_DATE, RANGE, relative_date_changes_trip, relative_dates
                    low = fold(p.quote)
                    if (relative_dates(low, p.quote.lower(), self.today()) and not FULL_DATE.search(low)
                            and not RANGE.search(low) and not relative_date_changes_trip(text, p.quote)):
                        continue
                exact = p.field in EXACT_FIELDS and not p.inferred
                st = apply(st, Update(field=p.field, op=p.op, value=p.value,
                                      source="user" if exact else "inferred",
                                      confidence="high" if exact else "low" if p.inferred else "medium",
                                      evidence=Evidence(turn=turn, quote=p.quote)))
            except (ValueError, ValidationError):
                pass
        if allergy := next((p for p in pre.proposals if p.field == "unmapped"
                            and re.search(r"\b(?:di ung|ung)\b", fold(p.quote))), None):
            if not (st.care.known and st.care.source == "user"):  # the care question is answered by what they told
                st = apply(st, Update(field="care", value="listed", source="user", confidence="high",
                                      evidence=Evidence(turn=turn, quote=allergy.quote, tool="derived:allergy")))
        hints = tuple((p.value, p.quote) for p in pre.suggestions if p.field == "companions")
        rushed = bool(re.search(r"\b(goi y luon|tim luon|khoi hoi|nhanh len)\b", fold(text)))
        st = with_meta(st, companion_hints=tuple(dict.fromkeys((*st.meta.companion_hints, *hints))),
                       rushed=st.meta.rushed or rushed)
        if st.diet_requests:
            st = diet.refresh(st)
            feed = self.knowledge.more.feeds.calendar if self.knowledge is not None else None
            try:
                calendar = feed() if feed and any(r.lunar_day for r in st.diet_requests) else None
            except (OSError, ValueError, TypeError):
                calendar = None
            st = st.model_copy(update={"diet_days": diet.resolved(st, calendar)})
            unchanged = diet_before == diet.progress(st)
            st = with_meta(st, diet_stalled=bool(diet_pending and unchanged))
        return drill.note(settle(st), text, turn, discovery=self.cfg.discovery)

    def _remember(self, s: Session) -> None:
        """The user is done with this session: add its explicit choices to their stored history, if they agreed."""
        m = s.state.meta
        if not (self.profiles and m.remember and m.user_id):
            return
        done = summary(s.state, s.id, self.today())
        if done is None:
            return
        try:
            self.profiles.record(m.user_id, done)
        except OSError as e:
            s.transcript.append({"role": "system", "text": f"profile not saved: {e}", "turn": m.turn})

    def _next(self, s: Session, say: str, leads: bool = False) -> Question | Deck:
        """The open question after a turn in which the agent showed no card. A reply that ends on a question keeps the
        talk in plain text: the user answers in words, unless it `leads` into the photo card it was told of (next_card):
        then the question offers that card and the card waits under the reply for a tap. Otherwise the deck shows one question: a pending follow-up or a
        confirmation. A required topic is never opened here: only the agent asks it (ask_required), in its own words;
        with nothing to show the text box stays open."""
        s.state = drill.refresh(s.state, self.catalog, self.cfg)
        if asks_in_text(say) and not leads:
            return conversation_card()
        built = deck.build(s.state, self.catalog, self.cfg,
                           agent=s.card.agent if isinstance(s.card, Deck) else ())
        if self.cfg.discovery:
            built = built.model_copy(update={"tabs": tuple(t for t in built.tabs if t.kind != "confirm")})
        return self._open(s, built)

    def _due_required(self, s: Session, say: str) -> str | None:
        """The required topic the app opens itself after a turn, or None. Only when the agent opened none and either
        its reply asks nothing (no deck tab waits either) or it has asked its own questions FOLLOWUP_LIMIT times in a
        row. Never while the user is asking, for a topic they skipped, nor more than twice for one topic."""
        m = s.state.meta
        if self.cfg.assistant.enabled and self.knowledge is not None and not planning(s.state):
            return None  # the user explores Đà Lạt: the assistant invites planning once, the app opens no required topic
        asking = asks_in_text(say)
        last = fold(next((t["text"] for t in reversed(s.transcript) if t["role"] == "user"), ""))
        if self._user_asks(s) or (asking and m.followups < FOLLOWUP_LIMIT) or re.search(
                r"\b(khong muon (?:di|tiep)|khong di nua|thoi khong|huy)\b", last):
            return None
        if not asking and (built := deck.build(s.state, self.catalog, self.cfg, agent=s.card.agent if isinstance(s.card, Deck) else ())).tabs:
            return None
        return next((k for k, _ in missing(s.state, self.cfg.required)
                     if k not in m.declined and m.nudged.count(k) < 2), None)

    def _open(self, s: Session, built: Deck) -> Question | Deck:
        """The deck the app built, or the text box: no tab, or only the app's own confirmation while the user asks."""
        if built.tabs and built.tabs[0].kind == "confirm" and self._user_asks(s):
            return conversation_card()  # the user is asking: the app's confirmation waits for a calmer turn
        return built if built.tabs else conversation_card()

    @staticmethod
    def _user_asks(s: Session) -> bool:
        last = next((t["text"] for t in reversed(s.transcript) if t["role"] == "user"), "")
        return "?" in last or bool(ASKING.search(fold(last))) or fold(last).rstrip(" .!").endswith(" khong")

    def _pool(self, st: TripState, scope: str = "any") -> set[str]:
        """Places past the hard limits now, of the kind a look is about: looks rank inside these, never outside."""
        groups = vibes.SCOPES.get(scope)
        return {c.id for c in self.catalog.places if admissible(c, st.hard, st.activities.get(c.id))
                and (groups is None or c.category_group in groups)}

    def _local_now(self, st: TripState, tools: TurnTools) -> dict | None:
        """What is in season, on and popular in Đà Lạt now (the daily Nhịp snapshot, a few ms), short, so the agent can
        weave one item into the talk like a local friend. Places in it pass the trip's hard limits and may be named."""
        if self.knowledge is None:
            return None
        out: dict = {}
        try:
            for kind, key in (("season", "seasons"), ("event", "events"), ("trend", "popular_places")):
                got = self.knowledge.trends(st, kind=kind, limit=LOCAL_NOW_ITEMS)
                rows = []
                for it in got.get("items", ())[:LOCAL_NOW_ITEMS]:
                    see = it.get("see_at") or it.get("held_at") or []
                    tools.told_ids |= {x["id"] for x in see} | ({it["id"]} if it.get("id") else set())
                    rows.append({"name": it["name"], **({"hot": True} if it.get("hot") else {}),
                                 **({"days": it["days"]} if it.get("days") else {}),
                                 **({"where": [x["name"] for x in see]} if see else {})})
                if rows:
                    out[key] = rows
                    out.setdefault("as_of", got.get("as_of"))
        except Exception as exc:  # noqa: BLE001 - local colour is optional; the turn goes on without it
            tools.log.append(f"local_now_failed {type(exc).__name__}")
        return out or None

    def _looks_of(self, pid: str) -> list[str]:
        """The photo styles of a place's own photos (corpus.index style tags): what it looks like, beside what reviews say."""
        try:
            return self.looks.style_labels(pid) if self.looks is not None else []
        except Exception:  # noqa: BLE001 - looks are optional context
            return []

    def _common_look(self, pids) -> list[str]:
        try:
            return self.looks.common_style(pids) if self.looks is not None else []
        except Exception:  # noqa: BLE001
            return []

    def _remembered(self, s: Session) -> dict | None:
        """What earlier chats' memos say of this user (memo.remembered), for CURRENT CONTEXT; None without consent."""
        m = s.state.meta
        if not (self.profiles and m.remember and m.user_id):
            return None
        try:
            return memo.remembered(self.profiles.memos(m.user_id, but=s.id))
        except (OSError, ValueError):
            return None

    def remember(self, sid: str, state: TripState, transcript: list[dict]) -> bool:
        """The Agent's memo of chat `sid` for the user's next trips (domain/memo.py), when its user agreed to remember
        and the chat has turns the last memo did not read: one model call, merged with that memo. True when written.
        Called when the itinerary is confirmed and when the chat has been quiet a while (harness), never on a turn."""
        m = state.meta
        if not (self.profiles and m.remember and m.user_id) or m.turn <= self.profiles.memo_upto(m.user_id, sid):
            return False
        data = memo.chat_input(state, transcript, self._name, self._known_for, self._looks_of, self._common_look)
        if not data.get("said"):
            return False
        before = self.profiles.memo(m.user_id, sid)
        messages = [{"role": "system", "content": memo.PROMPT},
                    {"role": "user", "content": json.dumps({"CHAT": data, **({"PREVIOUS": before.model_dump(mode="json")} if before else {})},
                                                           ensure_ascii=False)}]
        try:
            reply = asyncio.run(self.chat(messages, [], lambda _: None))
        except AgentError as exc:
            log.warning("memo not written for %s: %s", sid, exc)
            return False
        written = memo.parse(getattr(reply, "text", None) or str(getattr(reply, "content", "") or ""))
        if written is None:
            log.warning("memo not written for %s: the reply was not a memo", sid)
            return False
        self.profiles.put_memo(m.user_id, sid, self.today(), m.turn, written)
        return True

    def _known_for(self, pid: str, most: int = 5) -> list[str]:
        """What reviews confirm of a place the user chose ("outdoor_seating=present"), the best attested first: the
        agent reads a taste across picks from these, never a fact it did not get."""
        p = self.catalog.by_id.get(pid)
        if p is None:
            return []
        said = [(k.n, f"{f}={k.value}") for f, k in p.known.items() if k.value not in ("absent", "unknown", "none", None)]
        return [x for _, x in sorted(said, reverse=True)[:most]]

    def _name(self, pid: str) -> str:
        c = self.catalog.by_id.get(pid)
        return c.name if c else (self.looks.name(pid) if self.looks else pid)

    def _match(self, st: TripState, cues: tuple[str, ...], step, scope: str = "any") -> tuple[list[str], list]:
        """The look's signs against the corpus photos: (places best first, their kinds)."""
        total = self.looks.total if self.looks else 0
        step("match", f"Đối chiếu {total:,} nơi".replace(",", "."), "run")
        places, vec = self.looks.by_cues(list(cues), self._pool(st, scope)) if self.looks else ([], None)
        kinds = self.looks.kinds(places[:80], vec) if places else []
        step("match", f"Đối chiếu {total:,} nơi · {len(places)} nơi gần".replace(",", "."), "ok" if self.looks and self.looks.ready() else "fail")
        return places, kinds

    def _asked(self, s: Session, tools: TurnTools, turn: int) -> Question | Deck:
        """The card the agent asked for with `ask`, built from real data (it only named the look or the readings)."""
        a = tools.asked
        if a["kind"] == "required":
            return deck.build(s.state, self.catalog, self.cfg, ask=a["topic"], question=a.get("question"))
        if a["kind"] == "agent":
            heard = " ".join(re.findall(r"\d+", " ".join(t["text"] for t in s.transcript if t["role"] == "user")))
            # a figure the user never said (an hour, a count) is the agent's invention: that question is dropped
            fresh = [q for q in a["questions"] if all(n in heard.split() for n in re.findall(
                r"\d+", " ".join([str(q.get("question") or "")] + [str(o.get("label") or "") for o in q.get("options") or ()])))]
            tabs = ask.check(fresh, s.state, self.catalog, self.cfg, self.looks)
            built = {t.qid.removeprefix("drill."): t for t in tabs if t.kind == "drill"}
            attempted = {ask.visual_topic(q, s.state) for q in a["questions"] if q.get("visual")}
            s.state = s.state.model_copy(update={"drills": tuple(
                d.model_copy(update={"tab": built[d.topic]}) if d.topic in built else
                d.model_copy(update={"status": "none"}) if d.topic in attempted and d.tab is None and d.status == "pending" else d
                for d in s.state.drills)})
            return self._open(s, deck.build(s.state, self.catalog, self.cfg, agent=tuple(t for t in tabs if t.kind != "drill")))
        tools.step("cues", "Tách thành dấu hiệu nhìn thấy được", "ok")
        vibe = Vibe(phrase=a["about"], turn=turn, cues=tuple(a["cues"]), scope=a.get("where", "any"),
                    sources=vibes.sources_of(tools.sources))
        places, kinds = self._match(s.state, vibe.cues, tools.step, vibe.scope)
        vibe = vibe.model_copy(update={"offered": tuple(kinds), "places": tuple(places[:vibes.VIBE_PLACES])})
        s.state, i = vibes.put(s.state, None, vibe)
        return vibes.cues_card(i, vibe, kinds, len(places), self.looks.total if self.looks else 0, self._name)

    def _vibe_answer(self, s: Session, i: int, inp: TurnInput, emit: Emit) -> None:
        """An answer on a look's card (signs, kinds, "is it this place?"), from any point of the chat. No model call."""
        if not 0 <= i < len(s.state.vibes):
            emit("error", {"message": "Câu này đã qua, bạn trả lời câu mới nhất nhé."})
            return
        v = s.state.vibes[i]
        exit_ = next((x for x in ("skip", "unsure") if x in inp.chips), None)
        steps: list[dict] = []

        def step(sid, label, status):
            steps[:] = [x for x in steps if x["id"] != sid] + [{"id": sid, "label": label, "status": status}]
            emit("progress", {"steps": list(steps), "sources": []})

        say, card = "", None
        if exit_:
            turn = self._open_turn(s, EXIT_LABEL[exit_], "exit")
            v = v.model_copy(update={"status": "none", "places": ()})
            say = DECLINE_SAY
        elif inp.value is not None:  # the signs card: kept / removed signs
            try:
                kept, removed = vibes.read_cues(inp.value)
            except ValueError:
                emit("error", {"message": BAD_VALUE})
                return
            turn = self._open_turn(s, "Đúng rồi, xem ảnh các kiểu", "answer")
            places, kinds = self._match(s.state, kept, step, v.scope)
            v = v.model_copy(update={"cues": kept, "removed": removed, "offered": tuple(kinds),
                                     "places": tuple(places[:vibes.VIBE_PLACES]), "chosen": ()})
            if len(kinds) >= 2:
                v = v.model_copy(update={"status": "kinds"})
                card = vibes.kinds_card(i, v, self._name)
            else:
                v = v.model_copy(update={"status": "done" if places else "none"})
                say = CUES_ONLY_SAY.format(cues=", ".join(kept))
        elif v.status == "cues" and v.picked is None and inp.chips and set(inp.chips) <= {"yes", "no"}:
            turn = self._open_turn(s, "Đúng nơi này" if "yes" in inp.chips else "Không phải", "answer")
            pid = (v.places or (None,))[0]
            if "yes" in inp.chips and pid:
                v = v.model_copy(update={"picked": pid, "status": "done",
                                         "places": (pid, *self.looks.similar(pid, self._pool(s.state)))[:vibes.VIBE_PLACES]
                                         if self.looks else (pid,)})
                say = PHOTO_PLACE_SAY.format(name=self._name(pid))
            elif len(v.offered) >= 2:
                v = v.model_copy(update={"status": "kinds", "places": ()})
                card = vibes.kinds_card(i, v, self._name)
            else:
                v = v.model_copy(update={"status": "none", "places": ()})
                say = PHOTO_NOT_SAY
        else:  # the kinds card
            ids = [c for c in inp.chips if c != "none"]
            v = vibes.choose(v, ids)
            labels = [k.label for k in v.offered if k.id in v.chosen]
            turn = self._open_turn(s, ", ".join(labels) or "Không kiểu nào giống", "answer")
            say = KINDS_SAY.format(labels=", ".join(labels)) if labels else NO_KIND_SAY
        s.state, _ = vibes.put(s.state, i, v)
        s.state = with_meta(s.state, told=True)
        if card is not None:
            s.card = card
            emit("state", {"understanding": understanding(s.state, self.catalog, self.cfg)})
            emit("card", self._card(s.state, s.card))
            return
        self._close_turn(s, say, turn, emit)

    def _image(self, s: Session, inp: TurnInput, emit: Emit) -> None:
        """A photo the user sent: matched against the corpus photos (looks) and read for visible signs (see), in
        parallel. One clear match -> "is it X?"; else the kinds of the nearest places, or the signs to confirm. The
        photo is never stored: only the corpus places and the signs stay."""
        try:
            data = sanitize_photo(inp.value or "")
        except (ValueError, binascii.Error, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning):
            emit("error", {"message": BAD_PHOTO})
            return
        if self._sees_photos(s):
            return self._image_assistant(s, data, inp, emit)
        caption = inp.text.strip()[:200]
        turn = self._open_turn(s, caption or "Ảnh bạn gửi", "image")
        steps: list[dict] = []

        def step(sid, label, status):
            steps[:] = [x for x in steps if x["id"] != sid] + [{"id": sid, "label": label, "status": status}]
            emit("progress", {"steps": list(steps), "sources": []})

        step("read", "Đọc ảnh", "run")
        pool = self._pool(s.state)
        with ThreadPoolExecutor(2) as ex:
            seen = ex.submit(self.see, data) if self.see else None
            matched = ex.submit(self.looks.by_photo, data, pool) if self.looks else None
            read_ok = False
            try:
                read = seen.result() if seen else {}
                read_ok = "kind" in read and "cues" in read  # a real reading, even an empty one
            except Exception:  # the reader is down: the pixels still match
                read = {}
            vec, places, shows = matched.result() if matched else (None, [], None)
        try:
            cues = vibes.clean_cues(read.get("cues"), {fold(c.name) for c in self.catalog.places})
        except ValueError:
            cues = ()
        if read_ok and not cues and not read.get("kind") and not shows:
            # the reader saw no place or scene and no corpus photo is a clear match (a chart, a screenshot, a document):
            # the pixels still land near some corpus photos, but nothing here is a taste the user showed
            step("read", "Đọc ảnh · không phải ảnh nơi chốn", "fail")
            return self._close_turn(s, NOT_PLACE_SAY, turn, emit)
        step("read", "Đọc ảnh" + (f" · {read['kind']}" if read.get("kind") else ""), "ok" if cues or places else "fail")
        total = self.looks.total if self.looks else 0
        step("match", f"Đối chiếu {total:,} nơi · {len(places)} nơi gần".replace(",", "."), "ok" if places else "fail")
        ids = [p.place_id for p in places]
        kinds = self.looks.kinds(ids[:80], vec) if self.looks and ids else []
        v = Vibe(phrase=caption or "ảnh bạn gửi", turn=turn, cues=cues, image=True, offered=tuple(kinds),
                 places=tuple(ids[:vibes.VIBE_PLACES]))
        if shows:
            step("name", "Kiểm tra tên và địa chỉ", "ok")
            v = v.model_copy(update={"places": (shows, *[p for p in ids if p != shows])[:vibes.VIBE_PLACES]})
            s.state, i = vibes.put(s.state, None, v)
            s.card = vibes.pick_card(i, v, shows, self.looks.best_photo(shows), self._name)
            say = ""
        elif len(kinds) >= 2:
            v = v.model_copy(update={"status": "kinds"})
            s.state, i = vibes.put(s.state, None, v)
            s.card = vibes.kinds_card(i, v, self._name)
            say = PHOTO_SAY.format(cues=", ".join(cues)) if cues else ""
        elif cues:
            s.state, i = vibes.put(s.state, None, v)
            s.card = vibes.cues_card(i, v, kinds, len(ids), total, self._name)
            say = PHOTO_SAY.format(cues=", ".join(cues))
        else:
            return self._close_turn(s, PHOTO_BLIND_SAY, turn, emit)
        s.state = with_meta(s.state, told=True)
        if say:
            s.transcript.append({"role": "agent", "text": say, "turn": turn, "kind": "say"})
            emit("say", {"replace": say})
        emit("state", {"understanding": understanding(s.state, self.catalog, self.cfg)})
        emit("card", self._card(s.state, s.card))

    def _sees_photos(self, s: Session) -> bool:
        """The assistant reads a photo itself (the agent chooses photo_identify / photo_similar) in chat; every other
        phase, or an engine without the reader, keeps the card flow."""
        k = self.knowledge
        return bool(self.cfg.assistant.enabled and self.looks and k is not None and getattr(k, "perceiver", None)
                    and hasattr(self.looks, "read_photo") and s.state.meta.phase == "chat")

    def _image_assistant(self, s: Session, data: bytes, inp: TurnInput, emit: Emit) -> None:
        """A photo in the assistant's chat: read once into a session record (what it shows, the words written in it, the
        places it matches), then the agent turn runs on the caption with that record in its context. The picture itself
        is dropped here: only the record stays, in memory, for this session."""
        caption = inp.text.strip()[:200]
        turn = s.state.meta.turn + 1
        photo_id = f"p{turn}"
        emit("progress", {"steps": [{"id": "read", "label": "Đọc ảnh", "status": "run"}], "sources": []})
        try:
            record = self.looks.read_photo(data, None, set(s.state.meta.shown_ids), photo_id, turn)
        except Exception as exc:  # the reader is down: the agent still hears the caption and asks for the name
            log.warning("photo read failed: %s", type(exc).__name__)
            record = {"photo_id": photo_id, "turn": turn, "kind": "", "cues": [], "screenshot": False, "text_in_image": "",
                      "names_in_image": [], "match": None, "candidates": [], "similar": []}
        s.photos = [*s.photos, record][-PHOTOS_KEPT:]
        self._run(s, caption or "Ảnh bạn gửi", emit)

    def _card(self, state: TripState, q: Question | Deck | None) -> dict | None:
        if isinstance(q, Deck):
            q = deck.build(state, self.catalog, self.cfg, agent=q.agent, at=q.at, ask=q.ask, question=q.ask_question,
                           agent_only=q.agent_only)
            q = q.model_copy(update={"tabs": tuple(ask.with_photos(t, state, self.catalog, self.looks) for t in q.tabs)})
            out = q.model_dump(mode="json", exclude={"agent": True, "agent_only": True, "at": True, "ask": True, "tabs": {"__all__": {"options": {"__all__": {"writes"}}}}})
            for tab in out["tabs"]:
                for option in tab["options"]:
                    if option["photo"]:
                        pid, file = option["photo"]
                        option["photo"] = {"place_id": pid, "name": self._name(pid), "url": vibes.media_url(file)}
            return out
        return card(q, chip_effects(state, q, self.catalog))

    def _close_card(self, s: Session) -> None:
        if s.card and s.card.text.strip():  # an empty text box closing leaves no trace
            s.transcript.append({"role": "agent", "text": s.card.text, "turn": s.state.meta.turn, "kind": "card"})
