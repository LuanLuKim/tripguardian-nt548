"""In-process handoffs through public module tools; no hidden LLM supervisor."""

import hashlib
from copy import deepcopy
import json
import logging
import sys
import time
import uuid
import threading
from collections import OrderedDict
from contextlib import contextmanager
from concurrent.futures import Future
from datetime import datetime, timezone

from trip import SearchInput, TurnInput
from planning import TripIncomplete
from companion import plan_hash, stops_of
from corpus import pulse as corpus_pulse
from corpus.releases import Binding, PinnedVersionMissing

from .contracts import Conflict, Emit, Journey, JourneyView, ModuleTools, Request, Stage, StaleDataVersion, TripNotReady
from .router import RouteError, route, route_companion
from .session import Store
from .chat_guard import admit
from .timing import current as current_trace, span


def _said(events: list[dict]) -> str:
    """The reply streamed so far through say events (deltas, or a replace)."""
    out = ""
    for e in events:
        if e["event"] == "say":
            out = e["data"]["replace"] if "replace" in e["data"] else out + e["data"].get("delta", "")
    return out


def _page(query: dict) -> tuple[int, int | None]:
    """(offset, limit) of a paged read (`?offset=&limit=`, both optional); limit is 1-60."""
    offset, limit = str(query.get("offset", "0")), query.get("limit")
    if not offset.isdigit() or len(offset) > 6 or (limit is not None and (not str(limit).isdigit() or not 1 <= int(limit) <= 60)):
        raise ValueError("offset must be a number, limit 1-60")
    return int(offset), int(limit) if limit is not None else None


LIVE = ("say", "preview", "progress", "state", "card", "deck_issues", "readback", "places", "block", "replies")


def _fingerprint(request: Request) -> str:
    raw = json.dumps(request.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()



CHAT_TITLE_MAX = 60


def chat_title(transcript: list) -> str | None:
    """The chat's one-line title for the history list: what the user said first (its first line, cut at
    CHAT_TITLE_MAX). A list file attached to that message is part of its text, so only the first line is read.
    None while the user has said nothing yet."""
    for turn in transcript:
        if not isinstance(turn, dict) or turn.get("role") != "user":
            continue
        lines = [ln.strip() for ln in str(turn.get("text") or "").splitlines() if ln.strip()]
        if not lines:
            continue
        line = " ".join(lines[0].split())
        return line if len(line) <= CHAT_TITLE_MAX else line[:CHAT_TITLE_MAX - 1].rstrip() + "…"
    return None


@contextmanager
def _advance_span(spans: dict | None, name: str):
    with span(name, spans):
        yield


class Harness:
    def __init__(self, trip_tools: ModuleTools, decision_tools: ModuleTools, planning_tools: ModuleTools, store: Store,
                 events=None, companion=None, calendar=None, notify=None, safety=None,
                 corpus_binding: Binding | None = None, tools_for_binding=None, eve_store=None,
                 read_tools_for_binding=None):
        """events: harness.events.EventLog (usage events in Postgres); companion: companion.Companion (Đang đi).
        None turns either off (CLI, most tests)."""
        initial = {"trip": trip_tools, "decision": decision_tools, "planning": planning_tools}
        self.store = store
        self.events = events
        self.companion = companion
        self.calendar = calendar
        self.notify = notify
        self.eve_store = eve_store      # planning.EveStore of the D.3 evening check; None = off
        self.safety = safety
        self.corpus_binding = corpus_binding
        self.tools_for_binding = tools_for_binding
        self.read_tools_for_binding = read_tools_for_binding
        self._corpus_tools = OrderedDict({self._binding_key(corpus_binding): initial} if all(initial.values()) else {})
        self._opened_journeys: dict[str, set[str]] = {}
        self._corpus_lock = threading.RLock()
        self._builds: dict[str, Future] = {}
        self._loaded: set[str] = set()
        self._runtime_tokens: dict[str, object] = {}
        self._readers: dict[str, tuple] = {}
        self._readers_guard = threading.Lock()

    @property
    def tools(self) -> dict[str, ModuleTools]:
        return self._tools(self.corpus_binding)

    def warm_releases(self, recent_bindings, recent_journeys=None) -> threading.Thread:
        """Warm active plus two distinct recent pins off the startup/request thread, then the journeys people used
        lately (recent_journeys: newest first), so the first open after a restart does not pay a cold Planning base
        or Decision reader (6-9 s each, measured 04/11)."""
        def warm():
            logger = logging.getLogger(__name__)
            def open_one(binding):
                started = time.monotonic()
                try:
                    self._tools(binding)
                    logger.info("Corpus warmup ready %s in %.3fs", self._binding_key(binding), time.monotonic() - started)
                except Exception:
                    logger.exception("Corpus warmup failed %s", self._binding_key(binding))
            open_one(self.corpus_binding)
            try:
                seen = {self._binding_key(self.corpus_binding)}
                for binding in recent_bindings():
                    key = self._binding_key(binding)
                    if key in seen:
                        continue
                    if len(seen) >= 3:
                        break
                    seen.add(key)
                    open_one(binding)
            except Exception:
                logger.exception("Corpus warmup recent bindings failed")
            if recent_journeys is None:
                return
            started, n = time.monotonic(), 0
            try:
                for jid in recent_journeys():
                    try:
                        view = self.load(jid)
                        if view["stage"] == "planning" and "decision" in view["sessions"]:
                            self.load(jid, "decision")        # Lịch trình's way back to Lựa chọn
                        n += 1
                    except Exception:
                        logger.exception("Journey warmup failed %s", jid)
            except Exception:
                logger.exception("Journey warmup list failed")
            logger.info("Journey warmup: %d journeys in %.1fs", n, time.monotonic() - started)
        worker = threading.Thread(target=warm, name="corpus-warm", daemon=True)
        worker.start()
        return worker

    @staticmethod
    def _binding_key(binding: Binding | None) -> str:
        return binding.model_dump_json() if binding is not None else "legacy"

    def _tools(self, binding: Binding | None) -> dict[str, ModuleTools]:
        key = self._binding_key(binding)
        with self._corpus_lock:
            tools = self._corpus_tools.get(key)
            if tools is not None:
                self._corpus_tools.move_to_end(key)
                return tools
            build = self._builds.get(key)
            builder = build is None
            if builder:
                build = self._builds[key] = Future()
        if not builder:
            return build.result()
        try:
            if self.tools_for_binding is None:
                raise Conflict("corpus binding unavailable; restore the pinned release before continuing")
            try:
                tools = self.tools_for_binding(binding)
            except PinnedVersionMissing as exc:
                raise StaleDataVersion(exc.name, exc.version) from exc
            with self._corpus_lock:
                self._corpus_tools[key] = tools
                while len(self._corpus_tools) > 3:
                    oldest = next(k for k in self._corpus_tools if k != self._binding_key(self.corpus_binding))
                    del self._corpus_tools[oldest]
                    evicted = self._opened_journeys.pop(oldest, set())
                    self._loaded.difference_update(evicted)
                    for jid in evicted:
                        self._runtime_tokens[jid] = object()
                build.set_result(tools)
            return tools
        except Exception as exc:
            build.set_exception(exc)
            raise
        finally:
            with self._corpus_lock:
                self._builds.pop(key, None)

    def _module(self, session: Journey, stage: Stage) -> ModuleTools:
        tools = self._tools(session.corpus_binding)
        with self._corpus_lock:
            self._opened_journeys.setdefault(self._binding_key(session.corpus_binding), set()).add(session.id)
        return tools[stage]

    @staticmethod
    def _bound_output(session: Journey, output: dict) -> dict:
        if session.corpus_binding is None:
            return output
        existing = output.get("corpus_binding")
        binding = session.corpus_binding.model_dump(mode="json")
        if existing is not None and existing != binding:
            raise Conflict("module output uses a different corpus binding")
        return {**output, "corpus_binding": binding}

    def _event(self, name: str, owner: str | None, jid: str | None, **props) -> None:
        if self.events is not None:
            self.events.server(name, owner, jid, **props)

    def _get(self, jid: str, owner: str | None = None, *, readonly: bool = False, spans: dict | None = None,
             borrow: bool = False) -> Journey:
        """owner None is the in-process caller (CLI, tests); the HTTP server always names the signed-in account,
        and another account's journey is reported as missing. borrow: a pure reader of a journey whose modules are
        already restored gets Store.peek (no deepcopy of a multi-MB envelope); it must not mutate nested values."""
        with _advance_span(spans, "db_state_ms"):
            if borrow and jid in self._loaded:
                session = self.store.peek(jid)
            else:
                session = self.store.state(jid) if readonly else self.store.get(jid)
        if owner is not None and session.user_id != owner:
            raise KeyError(jid)
        if jid not in self._loaded:
            self._runtime_tokens[jid] = object()
            for stage, snapshot in session.snapshots.items():
                with _advance_span(spans, "tools_ms"):
                    module = self._module(session, stage)
                with _advance_span(spans, f"{stage}_restore_ms"):
                    module.restore(snapshot)
            self._loaded.add(jid)
        return session

    def _save(self, session: Journey) -> None:
        try:
            self.store.save(session)
        except Exception:
            # Rollback may restore an obsolete snapshot after a competing commit.
            # The next read/request must restore modules from the store again.
            self._loaded.discard(session.id)
            raise

    def _view(self, session: Journey, result: dict | None = None, stage: Stage | None = None) -> dict:
        shown = stage or session.stage
        if shown not in session.sessions:
            raise Conflict(f"no {shown} session")
        return JourneyView(id=session.id, stage=session.stage, revision=session.revision,
                sessions=session.sessions, outputs=session.outputs,
                result=result if result is not None else self._module(session, shown).load(session.sessions[shown])).model_dump(mode="json")

    def create(self, experience=None, start_with=None, user_id=None, remember=False, owner=None, profile=None) -> dict:
        """profile: the account's usual mobility / companions, a prior for Trip (never a fact of this trip)."""
        session = self.store.new()
        session.user_id = owner
        session.corpus_binding = self.corpus_binding
        payload = {"experience": experience, "start_with": start_with, "user_id": user_id, "remember": remember}
        if profile:
            payload["profile"] = profile
        result = self._module(session, "trip").create(payload)
        session.sessions["trip"] = result["id"]
        session.snapshots["trip"] = self._module(session, "trip").snapshot(result["id"])
        self._save(session)
        self._loaded.add(session.id)
        self._event("journey.create", owner, session.id, start_with=start_with, experience=experience,
                    profile_prior=bool(profile))
        return self._view(session, result)

    def state(self, jid: str, owner: str | None = None) -> dict:
        """Committed journey metadata without restoring or rendering a module."""
        with self.store.lock(jid):
            with _advance_span(None, 'db_state_ms'):
                session = self.store.peek(jid)
            if owner is not None and session.user_id != owner:
                raise KeyError(jid)
            return JourneyView(id=session.id, stage=session.stage, revision=session.revision,
                sessions=session.sessions, outputs=session.outputs, result={}).model_dump(mode="json")

    def _planning_read(self, jid: str, stage: Stage | None, owner: str | None, operation: str | None = None,
                       payload: dict | None = None, spans: dict | None = None) -> dict | None:
        """A Planning read rendered on the writer module outside the journey lock (Planning's engine takes its own
        session lock), then published only when no write landed meanwhile: same revision and the same runtime token
        (every rollback, restore and eviction mints a new one, so an intermediate write state is never shown). A fork
        deep-copies the session and its schedules, seconds on a multi-MB journey; this costs the render alone.
        None when the journey is not at Planning: the caller takes its usual path."""
        while True:
            waiting = time.monotonic()
            with self.store.lock(jid):
                if spans is not None:
                    spans["lock_wait_ms"] = spans.get("lock_wait_ms", 0) + (time.monotonic() - waiting) * 1000
                session = self._get(jid, owner, readonly=True, spans=spans, borrow=True)
                shown = stage or session.stage
                if shown != "planning":
                    return None
                if shown not in session.sessions:
                    raise Conflict(f"no {shown} session")
                module = self._module(session, shown)
                token = self._runtime_tokens.get(jid)
            with _advance_span(spans, "view_ms"):
                if operation is None:
                    result = self._view(session, result=module.load(session.sessions[shown]), stage=shown)
                else:
                    result = module.read(session.sessions[shown], operation, payload or {})
                    if operation == "suggestions":
                        result = {**result, "revision": session.revision}
                    result = deepcopy(result)
            with self.store.lock(jid):
                current = self.store.peek(jid)
                if (current.revision == session.revision and current.user_id == session.user_id
                        and jid in self._loaded and self._runtime_tokens.get(jid) is token):
                    return result

    def _snapshot_read(self, jid: str, stage: Stage | None, owner: str | None,
                       operation: str | None = None, payload: dict | None = None, spans: dict | None = None) -> dict:
        if spans is None and (trace := current_trace()) is not None:
            spans = trace.spans
        # Readers own their sessions/caches; expensive rendering never locks a writer's module.
        with self._readers_guard:
            reader_lock, tools, snapshots = self._readers.setdefault(jid, (threading.Lock(), {}, {}))
        with reader_lock:
            while True:
                waiting = time.monotonic()
                with self.store.lock(jid):
                    if spans is not None:
                        spans["lock_wait_ms"] = spans.get("lock_wait_ms", 0) + (time.monotonic() - waiting) * 1000
                    with _advance_span(spans, "db_state_ms"):
                        session = self.store.peek(jid)
                    if owner is not None and session.user_id != owner:
                        raise KeyError(jid)
                    shown = stage or session.stage
                    if shown not in session.sessions:
                        raise Conflict(f"no {shown} session")
                    if shown not in {"trip", "decision"} or self.read_tools_for_binding is None:
                        return self._view(self._get(jid, owner), stage=shown)
                    if jid in self._loaded:
                        session.snapshots[shown] = self._module(session, shown).snapshot(session.sessions[shown])
                    runtime_token = self._runtime_tokens.get(jid)
                binding_key = self._binding_key(session.corpus_binding)
                with _advance_span(spans, "reader_tools_ms"):
                    if tools.get("binding") != binding_key:
                        tools.clear()
                        tools.update(binding=binding_key, modules=self.read_tools_for_binding(session.corpus_binding))
                        snapshots.clear()
                modules = tools["modules"]
                with _advance_span(spans, "reader_restore_ms"):
                    snapshot = session.snapshots[shown]
                    if snapshots.get(shown) != snapshot:
                        modules[shown].restore(deepcopy(snapshot))
                        snapshots[shown] = snapshot
                module = modules[shown]
                with _advance_span(spans, "view_ms"):
                    result = (self._view(session, result=module.load(session.sessions[shown]), stage=shown)
                              if operation is None else module.read(session.sessions[shown], operation, payload or {}))
                    if operation is not None:
                        result = deepcopy(result)
                # A mutation may have committed during rendering. Never publish that obsolete view.
                with self.store.lock(jid):
                    current = self.store.peek(jid)
                    if current.revision == session.revision and current.user_id == session.user_id:
                        if jid in self._loaded:
                            latest_snapshot = self._module(current, shown).snapshot(current.sessions[shown])
                            if latest_snapshot != session.snapshots[shown]:
                                snapshots.pop(shown, None)
                                continue
                        # Restore/rollback can invalidate capabilities without changing persisted state.
                        if self._runtime_tokens.get(jid) is not runtime_token:
                            continue
                        return result

    def load(self, jid: str, stage: Stage | None = None, owner: str | None = None) -> dict:
        started = time.monotonic()
        trace = current_trace()
        spans = trace.spans if trace else {}
        shown = stage
        if shown is None:
            with self.store.lock(jid):
                shown = self.store.peek(jid).stage
        # None: the journey left Planning meanwhile (a back), rendered by its current stage below.
        result = self._planning_read(jid, stage, owner, spans=spans) if shown == "planning" else None
        if result is None and self.read_tools_for_binding is not None and shown in {"trip", "decision", "planning"}:
            result = self._snapshot_read(jid, stage, owner, spans=spans)
        elif result is None:
            waiting = time.monotonic()
            with self.store.lock(jid):
                spans['lock_wait_ms'] = (time.monotonic() - waiting) * 1000
                session = self._get(jid, owner, readonly=True, spans=spans)
                with _advance_span(spans, "view_ms"):
                    result = self._view(session, stage=stage)
        logging.getLogger(__name__).info("Journey load %s stage=%s total_ms=%.2f spans=%s",
            jid, stage or result["stage"], (time.monotonic() - started) * 1000, json.dumps(spans, sort_keys=True))
        return result

    def read(self, jid: str, stage: Stage, operation: str, payload: dict | None = None, owner: str | None = None) -> dict:
        if stage == "decision" and operation == "lodging":
            return self.lodging(jid, owner, *_page(payload or {}))
        # Planning reads that mint nothing render outside the journey lock; preview-act mints tokens on the writer.
        planning_read = stage == 'planning' and operation in {'variants', 'routes', 'lodging', 'suggestions'}
        out = self._planning_read(jid, stage, owner, operation=operation, payload=payload) if planning_read else None
        if out is None and self.read_tools_for_binding is not None and stage in {"trip", "decision"} and operation != "page":
            out = self._snapshot_read(jid, stage, owner, operation, payload)
        elif out is None:
            # Paging and preview tokens update module state consumed by the next action.
            with self.store.lock(jid):
                session = self._get(jid, owner)
                if stage not in session.sessions:
                    raise Conflict(f"no {stage} session")
                out = self._module(session, stage).read(session.sessions[stage], operation, payload or {})
                if operation in {"suggestions", "preview-act"} and stage == "planning":
                    out = {**out, "revision": session.revision}
        if operation == "why-not":
            self._event("why_not", owner, jid, place_id=(payload or {}).get("place"))
        elif operation == "page":
            self._event("page_more", owner, jid, group=(payload or {}).get("group"), page=(payload or {}).get("n"))
        return out

    def preview(self, jid: str, owner: str | None = None) -> dict:
        """The schedule the current Decision selection would get, built in the background without confirming it.
        Reads Decision under the journey lock, then builds outside it; nothing in the journey changes."""
        with self.store.lock(jid):
            session = self._get(jid, owner)
            if session.stage != "decision":
                raise Conflict("preview needs the decision stage")
            draft = self._module(session, "decision").read(session.sessions["decision"], "draft", {})["output"]
            revision = session.revision
        if draft is None:
            out = {"revision": revision, "status": "blocked", "plan": None}
        elif not draft["confirmed"]:
            out = {"revision": revision, "status": "empty", "plan": None}
        else:
            plan = self._module(session, "planning").preview({"decision_output": self._bound_output(session, draft)})
            out = {"revision": revision, "status": "ready" if plan["ok"] else "failed", "plan": plan}
        self._event(f"preview.{out['status']}", owner, jid, revision=revision)
        return out

    def lodging(self, jid: str, owner: str | None = None, offset: int = 0, limit: int | None = None) -> dict:
        """Lựa chọn's lodging list, one page: every served stay, those around the places chosen so far first
        (Planning ranks them), read under the journey lock and built outside it; nothing in the journey changes. A
        selection that cannot be confirmed yet, or no place chosen at all, still gets its list: where to sleep does not
        wait for the plan to fit."""
        with self.store.lock(jid):
            session = self._get(jid, owner)
            if session.stage not in ("decision", "planning"):  # read only: Lựa chọn reopened from Lịch trình lists it too
                raise Conflict("lodging list needs the decision stage")
            draft = self._module(session, "decision").read(session.sessions["decision"], "draft", {"any": True})["output"]
        if draft is None:
            return {"status": "empty", "candidates": [], "total": 0}
        return self._module(session, "planning").lodging_options({"decision_output": self._bound_output(session, draft)}, offset, limit)

    def trips(self, owner: str) -> list[dict]:
        """One line per journey of the signed-in account, newest first. All of them: the profile counts these."""
        return self.summaries(self.store.list_for(owner, limit=1000), limit=None)

    def summaries(self, ids: list[str], limit: int | None = 20) -> list[dict]:
        """One line per asked journey (the first `limit`, all when None); unknown IDs are skipped. Reads only the
        fields a line shows (Store.summary_parts): no module restored, no whole journey loaded."""
        wanted = ids[:limit]
        parts = self.store.summary_parts(wanted)
        out = []
        for jid in wanted:
            p = parts.get(jid)
            if p is None:
                continue
            context = p["context"]
            if p["itinerary"] is not None:
                places = list(dict.fromkeys(item["place_id"] for day in p["itinerary"] for item in day.get("items", [])
                                            if item.get("kind") == "visit" and item.get("place_id")))
            elif p["decision_confirmed"] is not None:
                places = p["decision_confirmed"]
            else:                       # not confirmed yet: the choices the Decision snapshot holds
                places = p["selected"]
            out.append({"id": p["id"], "stage": p["stage"], "revision": p["revision"],
                        "start_date": context.get("start_date"), "days": context.get("days"),
                        "people": context.get("people"), "places": places,
                        "confirmed": p["confirmed"], "updated_at": p["updated_at"],
                        "title": chat_title(p["transcript"])})
        return out

    def discard(self, jid: str, owner: str) -> None:
        """The account removes one of its journeys: it leaves the account (and the list) at once and cannot be opened
        again; like a deleted account's trips, the usage numbers stay without a user. A schedule already on
        Đang đi goes with it."""
        with self.store.lock(jid):
            session = self._get(jid, owner)
            session.user_id = None
            self._save(session)
        if self.companion is not None:
            self.companion.forget(jid)
        self._event("journey.discard", owner, jid, stage=session.stage)

    def owns(self, jid: str, owner: str) -> bool:
        try:
            with self.store.lock(jid):
                self._get(jid, owner)
        except KeyError:
            return False
        return True

    def copy(self, jid: str, source_owner: str, owner: str) -> dict:
        """A new journey of `owner` with the trip, choices and schedule of another account's journey (a trip a friend
        sent). Module sessions get fresh IDs so the two never share state; the chat transcript and the source
        account's pattern link stay behind."""
        with self.store.lock(jid):
            source = self._get(jid, source_owner)
            raw = json.dumps({"sessions": source.sessions, "outputs": source.outputs, "snapshots": source.snapshots})
        for old in set(source.sessions.values()):
            raw = raw.replace(old, uuid.uuid4().hex[:12])
        data = json.loads(raw)
        trip = data["snapshots"].get("trip") or {}
        if "transcript" in trip:
            trip["transcript"] = []
        if meta := (trip.get("state") or {}).get("meta"):
            meta |= {"user_id": None, "remember": False}
        session = self.store.new()
        session.user_id, session.stage, session.revision = owner, source.stage, source.revision
        session.corpus_binding = source.corpus_binding
        session.sessions, session.outputs, session.snapshots = data["sessions"], data["outputs"], data["snapshots"]
        for stage, snapshot in session.snapshots.items():
            self._module(session, stage).restore(snapshot)
        self._save(session)
        self._loaded.add(session.id)
        self._event("journey.copy", owner, session.id, source=jid)
        return {"id": session.id, "stage": session.stage, "revision": session.revision}

    def feedback(self, jid: str, payload: dict, owner: str | None = None) -> dict:
        """After-trip answers (1-5 scales, yes/no, a short note), one JSON line per submission next to the sessions."""
        if set(payload) - {"scores", "more_search", "note"}:
            raise ValueError("unknown feedback field")
        scores, more, note = payload.get("scores") or {}, payload.get("more_search"), payload.get("note") or ""
        if not isinstance(scores, dict) or len(scores) > 10 or any(
                not isinstance(k, str) or len(k) > 40 or not isinstance(v, int) or isinstance(v, bool) or not 1 <= v <= 5
                for k, v in scores.items()):
            raise ValueError("scores must map up to 10 names to 1-5")
        if more is not None and not isinstance(more, bool):
            raise ValueError("more_search must be true, false or null")
        if not isinstance(note, str) or len(note) > 1000:
            raise ValueError("note must be at most 1000 characters")
        with self.store.lock(jid):
            with _advance_span(None, 'db_state_ms'):
                session = self.store.peek(jid)
            if owner is not None and session.user_id != owner:
                raise KeyError(jid)
        record = {"journey": jid, "user_id": owner, "at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "scores": scores,
                  "more_search": more, "note": note.strip()}
        with _advance_span(None, 'feedback_write_ms'):
            self.store.append_feedback(record)
        self._event("feedback.submit", owner, jid, scores=",".join(f"{k}:{v}" for k, v in sorted(scores.items())),
                    more_search=more, has_note=bool(record["note"]))
        return {"stored": True}

    def report(self, payload: dict) -> dict:
        return self.tools["decision"].report(payload)

    def places(self, query: str, owner: str | None = None) -> list[dict]:
        hits = self.tools["trip"].places(query)
        if query.strip():
            self._event("places.search", owner, None, q=query.strip()[:80], hits=len(hits))
        return hits

    def geo(self, q: str) -> list[dict]:
        """Search-as-you-type for a starting point; Planning owns Live Context (docs/PLANNING.md §Live Context)."""
        return self.tools["planning"].geo(q)

    def pulse(self) -> dict:
        """Nhịp Đà Lạt (docs/CORPUS.md §Nhịp): the bulletin of the newest daily snapshot; no sections when the job never ran."""
        return corpus_pulse.bulletin("dalat") or {"city": "dalat", "generated_at": None, "day": None, "stale": True, "sections": []}

    def tags_trending(self) -> dict:
        """Home topics: tags ranked by the TikTok clips of the last 30 days (corpus.pulse.tag_trends), each with the cover
        photos of its most posted places. `tags` is empty when the daily job never wrote them (the page shows its own)."""
        out = corpus_pulse.tag_trends("dalat")
        if out is None:
            return {"as_of": None, "window_days": None, "stale": True, "tags": []}
        return {**out, "tags": self.tools["trip"].tag_covers(out["tags"])}

    def tag(self, ref: str) -> dict:
        """One tag split into subtags with place cards: ref = "experience:cloud_hunting", "dish:lau", ... ValueError: unknown."""
        return self.tools["trip"].tag(ref)

    def lodging_suggest(self, q: str, top: int = 0) -> list[dict]:
        return self.tools["planning"].lodging_suggest(q, top)

    def forget_profile(self, user_id: str) -> bool:
        return self.tools["trip"].forget(user_id)

    def profile(self, user_id: str) -> dict:
        """The account's profile entries (docs/TRIP_UNDERSTANDING.md §17): Trip owns them."""
        return self.tools["trip"].profile(user_id)

    def edit_profile_entry(self, user_id: str, eid: str, patch: dict) -> dict:
        out = self.tools["trip"].edit_entry(user_id, eid, patch)
        self._event("profile.edit", user_id, None, fields=",".join(sorted(patch)))
        return out

    def delete_profile_entry(self, user_id: str, eid: str) -> bool:
        if not self.tools["trip"].delete_entry(user_id, eid):
            raise KeyError(eid)
        self._event("profile.delete", user_id, None)
        return True

    def pause_profile(self, user_id: str, paused: bool) -> dict:
        out = self.tools["trip"].pause_profile(user_id, paused)
        self._event("profile.pause", user_id, None, paused=paused)
        return out

    def adopt(self, from_id: str, to_id: str) -> int:
        """A guest signed in with Google: their journeys now belong to the account. Returns how many moved."""
        moved = 0
        for jid in self.store.list_for(from_id):
            with self.store.lock(jid):
                session = self.store.get(jid)
                session.user_id = to_id
                self._save(session)
            moved += 1
        return moved

    def request(self, jid: str, request: Request, emit: Emit | None = None, owner: str | None = None) -> dict:
        started = time.monotonic()
        trace: dict = {"t0": started}
        if request.stage == "decision" and request.operation == "advance":
            trace["advance_spans"] = {"tools_ms": 0}
        status = "ok"
        name = f"{request.stage}.{request.operation}"
        if request.operation == "act" and isinstance(request.payload.get("type"), str):
            name += "." + request.payload["type"][:40]
        try:
            response = self._request(jid, request, emit, owner, trace)
        except Exception as exc:
            status = type(exc).__name__
            if not isinstance(exc, KeyError):
                self._event(name, trace.get("user_id"), jid, revision=request.expected_revision, error=type(exc).__name__,
                            latency_ms=round((time.monotonic() - started) * 1000), path=trace.get("path"))
            raise
        finally:
            if "advance_spans" in trace and not trace.get("replayed"):
                spans = {key: round(value, 3) for key, value in trace["advance_spans"].items()}
                logging.getLogger(__name__).info("Harness advance %s", json.dumps({
                    "journey": jid, "request": request.request_id, "pin": trace.get("advance_pin"),
                    "status": status, "total_ms": round((time.monotonic() - started) * 1000, 3), **spans,
                }, separators=(",", ":")))
        if not trace.get("replayed") and name == "planning.confirm" and self.companion is not None:
            self._sync_trip(jid)
        if not trace.get("replayed") and name == "planning.confirm":
            self._learn_from_plan(jid)
        if not trace.get("replayed"):
            props = self.events.act_props(request.payload) if self.events and request.operation == "act" else {}
            if request.stage == "trip" and request.operation == "turn":
                chips = request.payload.get("chips") or []
                props |= {"kind": request.payload.get("kind"), "qid": request.payload.get("qid") or None,
                          "exit": next((c for c in ("skip", "unsure") if c in chips), None)}
            if name == "planning.confirm" and self.companion is not None:
                props |= self._quality(jid)
            if name == 'planning.turn' and trace.get('turn_trace'):
                props |= {'trace_id': trace['turn_trace']['id'], 'turn_trace': trace['turn_trace']}
            self._event(name, trace.get("user_id"), jid, revision=response["revision"], path=trace.get("path"),
                        latency_ms=round((time.monotonic() - started) * 1000), first_ms=trace.get("first_ms"),
                        refined=trace.get("refined"),
                        compiled=True if trace.get("compiled") else None, **props)
        return response

    # --- Đang đi (companion) ------------------------------------------------------------------------------------

    def _sync_trip(self, jid: str) -> None:
        """The confirmed plan becomes (or updates) the trip; a failure is logged and leaves the confirm committed."""
        try:
            session = self.store.peek(jid)
            self.companion.sync(jid, session.user_id, deepcopy(session.outputs["planning"]))
        except Exception as exc:
            print(f"trip not synced for {jid}: {type(exc).__name__}: {exc}", file=sys.stderr)

    def _learn_acts(self, jid: str, acts: list[dict]) -> None:
        """Weak profile evidence (trip.note_acts decides by consent); a failure only loses the learning."""
        try:
            session = self.store.peek(jid)
            if session.user_id and session.sessions.get("trip") and acts:
                self.tools["trip"].note_acts(session.user_id, session.sessions["trip"], acts)
        except Exception as exc:
            print(f"profile not updated for {jid}: {type(exc).__name__}: {exc}", file=sys.stderr)

    def _learn_from_plan(self, jid: str) -> None:
        """A confirmed plan: its places were kept in it; places the user dropped saying "dislike" are against."""
        try:
            session = self.store.peek(jid)
            dropped = ((session.snapshots.get("decision") or {}).get("state") or {}).get("dropped") or []
            acts = [{"kind": "dropped", "place_id": d.get("place_id"), "reason": d.get("reason")} for d in dropped]
            acts += [{"kind": "kept_in_plan", "place_id": s["place_id"]} for s in stops_of(session.outputs["planning"])]
        except Exception as exc:
            print(f"profile not updated for {jid}: {type(exc).__name__}: {exc}", file=sys.stderr)
            return
        self._learn_acts(jid, acts)

    def _confirmed(self, jid: str, owner: str | None, operation: str = "checkin") -> Journey:
        if self.companion is None:
            raise Conflict("companion is off")
        with self.store.lock(jid):
            session = self._get(jid, owner)
        route_companion(session.outputs, operation)
        return session

    def _quality(self, jid: str) -> dict:
        """Event props for a confirmed plan (Admin tab Chất lượng): hard filters failed / unknown on its places, and
        the plan's robustness. A failure here only loses the props."""
        try:
            session = self.store.peek(jid)
            plan, si = session.outputs["planning"], session.outputs.get("trip") or {}
            return {**self.companion.quality(plan, si), "robustness": (plan.get("robustness") or {}).get("level")}
        except Exception as exc:
            print(f"plan quality not measured for {jid}: {exc}", file=sys.stderr)
            return {}

    def today(self, jid: str, owner: str | None = None, day: int | None = None) -> dict:
        session = self._confirmed(jid, owner)
        plan = session.outputs["planning"]
        try:
            return self.companion.today(jid, plan, day)
        except KeyError:  # confirmed before trips existed
            self.companion.sync(jid, session.user_id, plan)
            return self.companion.today(jid, plan, day)

    def suggest(self, jid: str, place_id: str, owner: str | None = None, similar: bool = False) -> dict:
        session = self._confirmed(jid, owner)
        dropped = ((session.snapshots.get("decision") or {}).get("state") or {}).get("dropped") or []
        disliked = {d.get("place_id") for d in dropped if d.get("reason") == "dislike"}
        out = self.companion.suggestions(jid, session.outputs.get("trip") or {}, session.outputs["planning"], place_id,
                                         disliked, similar)
        backups = {b.get("id") for b in (session.outputs.get("decision") or {}).get("backup_pool") or []}
        for item in out.get("nearby", []) + out.get("similar", []):
            item["addable"] = item["place_id"] in backups  # Planning only adds from the backup pool
        return out

    def companion_act(self, jid: str, operation: str, payload: dict, owner: str | None = None) -> dict:
        """checkin / skip / rate write the trip; add / adjust change the plan through Planning (act, then confirm)
        and only with confirmed: true, i.e. after the user saw what changes."""
        session = self._confirmed(jid, owner, operation)
        uid = session.user_id
        if operation == "checkin":
            out = self.companion.checkin(jid, payload.get("stop_id"), payload.get("place_id"))
        elif operation == "skip":
            out = self.companion.skip(jid, payload.get("stop_id"), payload.get("reason"))
        elif operation == "rate":
            out = self.companion.rate(jid, payload.get("stop_id"), payload.get("value"))
            self._learn_acts(jid, [{"kind": "rated_hop", "place_id": out.get("place_id"), "value": out.get("rating")}])
        else:
            if payload.get("confirmed") is not True:
                raise ValueError(f"{operation} changes the plan: show the change, then send confirmed: true")
            if operation == "adjust":
                action = self.companion.option(jid, session.outputs["planning"], payload.get("option_id"))
            else:
                day = payload.get("day")
                if not isinstance(day, int) or isinstance(day, bool):
                    raise ValueError("day must be the trip day (1, 2, …)")
                action = {"type": "add_from_backup", "place": payload.get("place_id"), "day": day - 1}
            self._replan(jid, action, owner)
            out = {"changed": True, "today": self.today(jid, owner)}
        self._event(f"companion.{operation}", uid, jid, **{k: payload[k] for k in ("reason", "value", "option_id", "place_id")
                                                           if k in payload and not isinstance(payload[k], (dict, list))})
        return out

    def calendar_preview(self, jid: str, owner: str) -> dict:
        self.today(jid, owner)  # makes sure the trip rows exist
        session = self._confirmed(jid, owner)
        return self.calendar.preview(jid, owner, session.outputs["planning"])

    def calendar_apply(self, jid: str, preview_hash: str, owner: str) -> dict:
        session = self._confirmed(jid, owner)
        if not isinstance(preview_hash, str):
            raise ValueError("preview_hash is required")
        out = self.calendar.apply(jid, owner, session.outputs["planning"], preview_hash)
        if not out["stale"]:
            self._event("calendar.apply", owner, jid, applied=out["applied"], failed=out["failed"] is not None)
        return out

    def calendar_disconnect(self, owner: str, delete_calendar: bool) -> dict:
        if not isinstance(delete_calendar, bool):
            raise ValueError("delete_calendar must be true or false")
        out = self.calendar.disconnect(owner, delete_calendar)
        self._event("calendar.disconnect", owner, None, deleted=delete_calendar)
        return out

    def _replan(self, jid: str, action: dict, owner: str | None) -> None:
        """Planning act + confirm as two journey requests; when the confirm fails the act is undone and confirmed
        again, so the journey keeps a confirmed plan."""
        self._replan_many(jid, [action], owner)

    def _replan_many(self, jid: str, actions: list[dict], owner: str | None, back: dict | None = None) -> None:
        """Several Planning acts, then one confirm. On any failure the acts already sent are reversed (`back`,
        default undo) and the plan confirmed again before the error is raised."""
        def send(operation, payload=None):
            view = self.load(jid, None, owner)
            if view["stage"] != "planning":
                raise Conflict("the plan is being edited elsewhere")
            return self.request(jid, Request(request_id=f"companion-{uuid.uuid4().hex}", stage="planning",
                                             operation=operation, expected_revision=view["revision"],
                                             payload=payload or {}), None, owner)
        done = 0
        try:
            for action in actions:
                send("act", action)
                done += 1
            send("confirm")
        except Exception:
            for _ in range(done):
                send("act", back or {"type": "undo"})
            if done:
                send("confirm")
            raise

    # --- D.3 evening check: pending changes for tomorrow on the confirmed plan --------------------------------------

    def _eve_session(self, jid: str, owner: str | None) -> tuple[Journey, str]:
        if self.eve_store is None:
            raise Conflict("the evening check is off")
        with self.store.lock(jid):
            session = self._get(jid, owner)
        if "planning" not in session.outputs:
            raise RouteError("the evening check needs a confirmed plan")
        return session, plan_hash(stops_of(session.outputs["planning"]))

    def eve(self, jid: str, owner: str | None = None) -> dict:
        """What the evening check left for this confirmed plan:
        {"enabled": bool, "pending": [...], "notes": [...], "undo": bool}. Notes are what it saw but does not ask about
        (level 1, later days): shown on the plan, nothing to choose. A read, so "off" (no store) and "no confirmed plan
        yet" are normal empty answers, not errors (QA 2026-10-30 B12); the acts below still refuse."""
        empty = {"enabled": self.eve_store is not None, "pending": [], "notes": [], "undo": False}
        if self.eve_store is None:
            self._get(jid, owner)  # an unknown journey is still a 404
            return empty
        try:
            _, digest = self._eve_session(jid, owner)
        except RouteError:
            return empty
        kept = self.eve_store.get(jid, digest)
        return {**empty, "pending": kept["pending"], "notes": kept.get("notes", []),
                "undo": self.eve_store.last_accept(jid, digest) is not None}

    def eve_act(self, jid: str, operation: str, payload: dict, owner: str | None = None) -> dict:
        """accept {date, place_id, option_id, confirmed: true}: the option's acts, then confirm (a new plan);
        decline {date, place_id}: keep the plan, never ask again for that cause (level 2 only); undo: back to the
        plan before the last accepted option."""
        session, digest = self._eve_session(jid, owner)
        if operation == "times":
            return self.trip_times(jid, payload, owner)
        if operation == "undo":
            rec = self.eve_store.last_accept(jid, digest)
            if rec is None:
                raise Conflict("nothing to undo")
            self._replan_many(jid, [{"type": "undo"}] * rec["n"], owner, back={"type": "redo"})
            self.eve_store.accepted(jid, None)
            self._event("eve.undo", session.user_id, jid)
            return self.eve(jid, owner)
        if operation not in ("accept", "decline"):
            raise ValueError(f"the evening check does not accept {operation}")
        item = next((p for p in self.eve_store.get(jid, digest)["pending"]
                     if p.get("date") == payload.get("date") and p.get("place_id") == payload.get("place_id")), None)
        if item is None:
            raise ValueError("no such pending change for this plan")
        option = next((o for o in item["options"] if o["id"] == payload.get("option_id")), None) \
            if operation == "accept" else None
        if operation == "accept" and option is None:
            raise ValueError("that option is not offered")
        if operation == "decline" or option["kind"] == "keep":
            if item["level"] >= 3:
                raise ValueError("this stop cannot go as planned: choose one of the options")
            self.eve_store.decline(jid, item["cause"]["key"])
            self._event("eve.decline", session.user_id, jid, place_id=item["place_id"])
            return self.eve(jid, owner)
        if payload.get("confirmed") is not True:
            raise ValueError("accept changes the plan: show the change, then send confirmed: true")
        self._replan_many(jid, option["actions"], owner)
        new = plan_hash(stops_of(self.store.get(jid).outputs["planning"]))
        self.eve_store.accepted(jid, {"plan_hash": new, "n": len(option["actions"]), "option_id": option["id"],
                                      "date": item["date"], "place_id": item["place_id"]})
        self._event("eve.accept", session.user_id, jid, place_id=item["place_id"], kind=option["kind"])
        return self.eve(jid, owner)

    def trip_times(self, jid: str, payload: dict, owner: str | None = None) -> dict:
        """Trip -> Planning event: the trip's arrival (first day starts) and / or departure (last day ends) changed
        after the confirm. Each becomes a Planning set_day_window on that day; the confirmed plan stays confirmed (no
        replan, no confirm), the Planning session now holds the new window, and the next evening check (D.3, `window`
        factor) offers the user the options. {"arrive": "HH:MM"?, "leave": "HH:MM"?}"""
        from planning.settings import to_min
        times = {k: payload.get(k) for k in ("arrive", "leave") if payload.get(k) is not None}
        if not times:
            raise ValueError("send arrive and / or leave as HH:MM")
        for value in times.values():
            try:
                ok = 0 <= to_min(value) < 24 * 60
            except (ValueError, AttributeError, TypeError):
                ok = False
            if not ok:
                raise ValueError(f"bad time {value!r}")
        with self.store.lock(jid):
            session = self._get(jid, owner)
            plan = session.outputs.get("planning")
            if plan is None or "planning" not in session.sessions:
                raise RouteError("the arrival / departure of a confirmed plan can only change on a confirmed plan")
            per_day = (plan.get("time_budget") or {}).get("per_day") or []
            if not per_day:
                raise Conflict("the confirmed plan has no day windows")
            last = len(per_day) - 1
            acts = []
            if "arrive" in times:
                acts.append({"type": "set_day_window", "day": 0, "start": times["arrive"], "end": per_day[0]["to"]})
            if "leave" in times:
                start = times["arrive"] if last == 0 and "arrive" in times else per_day[last]["from"]
                acts.append({"type": "set_day_window", "day": last, "start": start, "end": times["leave"]})
            before = session.model_copy(deep=True)
            planning = self._module(session, "planning")
            try:
                for act in acts:
                    planning.apply(session.sessions["planning"], "act", act, lambda *a: None)
                session.revision += 1
                session.snapshots["planning"] = planning.snapshot(session.sessions["planning"])
                self._save(session)
            except Exception:
                self._runtime_tokens[jid] = object()
                planning.restore(before.snapshots["planning"])
                raise
        self._event("trip.times", session.user_id, jid, arrive=times.get("arrive"), leave=times.get("leave"))
        return self.eve(jid, owner)

    def _request(self, jid: str, request: Request, emit: Emit | None, owner: str | None, trace: dict) -> dict:
        with self.store.lock(jid):
            spans = trace.get("advance_spans")
            with _advance_span(spans, "load_ms"):
                # before is read only (compare, roll back from a copy): borrowing it saves one multi-MB deepcopy
                before = self._get(jid, owner, readonly=True, spans=spans, borrow=True)
                session = self.store._working(jid)
            if spans is not None:
                trace["advance_pin"] = session.corpus_binding.model_dump(mode="json") if session.corpus_binding else None
            trace["user_id"] = session.user_id
            fingerprint = _fingerprint(request)
            receipt = session.receipts.get(request.request_id)
            if receipt:
                if receipt["fingerprint"] != fingerprint:
                    raise Conflict("request_id was already used for another request")
                if emit:
                    for event in receipt["events"]:
                        emit(event["event"], deepcopy(event["data"]))
                trace["replayed"] = True
                return deepcopy(receipt["response"])
            if request.expected_revision != session.revision:
                raise Conflict(f"expected revision {session.revision}, got {request.expected_revision}")
            stage = route(session.stage, request)
            events: list[dict] = []

            had_trip = "trip" in session.outputs

            def capture(event: str, data: dict) -> None:
                if event == "trace":  # internal: how the module answered (agent, fallback, heuristic), for events
                    trace.update(data)
                    return
                if "first_ms" not in trace and event in ("say", "preview", "view"):  # time to the first SSE event
                    trace["first_ms"] = round((time.monotonic() - trace["t0"]) * 1000)
                events.append({"event": event, "data": data})
                if emit and event in LIVE:
                    emit(event, data)
                if stage == "trip" and event == "done" and "search_input" in data:
                    session.outputs["trip"] = SearchInput.model_validate(self._bound_output(session, data["search_input"])).model_dump(mode="json")

            try:
                refusal = None
                if self.safety is not None and request.operation in {"turn", "act"}:
                    current = self._module(session, stage).load(session.sessions[stage])
                    refusal = admit(self.safety, request.payload, current, stage, review_text=request.operation == "turn")
                if refusal:
                    trace["path"] = "chat_refused"
                    capture("say", {"replace": refusal})
                    capture("done", {})
                    result = self._module(session, stage).load(session.sessions[stage])
                elif request.operation == "advance":
                    result = self._advance(session, spans)
                elif request.operation == "trip":
                    inp = TurnInput.model_validate(request.payload)
                    if inp.kind not in {"deck", "drop", "readback_ok"}:
                        raise ValueError("decision.trip accepts only deck, drop or readback_ok")
                    trip = self._module(session, "trip")
                    payload = {**request.payload, "at": "plan" if request.payload.get("at") == "plan" else "gate"} if inp.kind == "deck" else request.payload
                    trip.apply(session.sessions["trip"], "turn", payload, capture)
                    readback = trip.read(session.sessions["trip"], "readback", {})
                    if "care" in readback.get("missing", ()):
                        # Save partial gate answers without compiling over an unresolved safety question.
                        capture("readback", readback)
                        rebased = self._module(session, "decision").load(session.sessions["decision"])
                    else:
                        output = trip.read(session.sessions["trip"], "search_input", {})
                        session.outputs["trip"] = SearchInput.model_validate(self._bound_output(session, output)).model_dump(mode="json")
                        rebased = self._module(session, "decision").rebase(session.sessions["decision"],
                            self._decision_input(session))
                    result = {"id": rebased["id"], "view": rebased["view"]}
                    for key in ("decision", "planning"):
                        session.outputs.pop(key, None)
                    session.sessions.pop("planning", None)
                    session.snapshots.pop("planning", None)
                elif request.operation == "back":
                    # Navigation changes the displayed stage, never the persisted trip or schedule.
                    session.stage = "decision" if stage == "planning" else "trip"
                    result = self._module(session, session.stage).load(session.sessions[session.stage])
                else:
                    payload = request.payload
                    if stage == "planning" and request.operation == "turn":
                        if set(payload) != {"text"}:
                            raise ValueError("planning.turn accepts only text")
                        # the Lịch trình assistant reads place data through this journey's Trip session
                        payload = {**payload, **({"trip_session": session.sessions["trip"]} if "trip" in session.sessions else {})}
                    result = self._module(session, stage).apply(session.sessions[stage], request.operation, payload, capture)
                    if stage == "decision" and request.operation == "turn":
                        texts = [t for e in events if e["event"] == "trip" for t in e["data"]["texts"]]
                        events[:] = [e for e in events if e["event"] != "trip"]  # internal: the web never sees it
                        if texts and "trip" in session.sessions:
                            trace["refined"] = True
                            result = self._refine(session, " ".join(texts), events, capture) or result
                    if stage == "trip" and request.operation == "turn":
                        if not any(e["event"] == "done" for e in events) and request.payload.get("kind") != "show":
                            session.outputs.pop("trip", None)
                        if session.outputs.get("trip") != before.outputs.get("trip"):
                            session.outputs.pop("decision", None)
                            session.outputs.pop("planning", None)
                    if request.operation in ("act", "turn", "recommend") and stage != "trip":
                        session.outputs.pop("planning", None)
                        if stage == "decision":
                            session.outputs.pop("decision", None)
                            session.sessions.pop("planning", None)
                            session.snapshots.pop("planning", None)
                    if request.operation == "confirm":
                        result = self._bound_output(session, result)
                        session.outputs["planning"] = result
                trace["compiled"] = stage == "trip" and not had_trip and "trip" in session.outputs
                session.revision += 1
                with _advance_span(spans, "snapshot_ms"):
                    # Back only loads its destination; untouched stages retain their committed snapshots.
                    names = [session.stage] if request.operation == 'back' else session.sessions
                    for name in names:
                        sid = session.sessions[name]
                        session.snapshots[name] = self._module(session, name).snapshot(sid)
                if stage == 'planning' and request.operation == 'turn' and not refusal:
                    current_traces = session.snapshots.get('planning', {}).get('turn_traces') or []
                    old_traces = before.snapshots.get('planning', {}).get('turn_traces') or []
                    if current_traces and (not old_traces or current_traces[-1]['id'] != old_traces[-1]['id']):
                        latest = current_traces[-1]
                        trace['turn_trace'] = {'id': latest['id'], 'total_ms': latest['total_ms'],
                                               'spans': [line for line in latest.get('log', []) if line.startswith('t_')]}
                response = self._view(session, result)
                session.receipts[request.request_id] = {"fingerprint": fingerprint, "response": response, "events": events,
                                                        "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
                with _advance_span(spans, "store_ms"):
                    self._save(session)
            except Exception:
                self._runtime_tokens[jid] = object()
                for name, snapshot in before.snapshots.items():
                    self._module(session, name).restore(deepcopy(snapshot))
                raise
            if emit:
                for event in events:
                    if event["event"] not in LIVE:
                        emit(event["event"], event["data"])
            return response

    def _refine(self, session: Journey, text: str, events: list[dict], capture) -> dict | None:
        """A wish typed at Chọn nơi: Trip Understanding reads it, then Decision is rebuilt on the new Search Input.
        The rebuilt view replaces the turn's own; Trip's reply and the list change follow Decision's in the same bubble."""
        said = _said(events)
        compiled: list[dict] = []
        reply = ""

        def on_trip(event: str, data: dict) -> None:
            nonlocal reply
            if event == "say":
                reply = data["replace"] if "replace" in data else reply + data.get("delta", "")
                capture("say", {"replace": f"{said} {reply}".strip()})
            elif event == "done":
                compiled.append(data["search_input"])

        self._module(session, "trip").apply(session.sessions["trip"], "refine", {"text": text}, on_trip)
        if not compiled:
            return None
        session.outputs["trip"] = SearchInput.model_validate(self._bound_output(session, compiled[-1])).model_dump(mode="json")
        out = self._module(session, "decision").rebase(session.sessions["decision"], self._decision_input(session))
        rebuilt = {"view": out["view"], "diff": out["diff"]}
        if note := out["diff"].get("text"):  # the reply ends with what happened to the list: "Giữ 22 nơi, thay 2 …"
            capture("say", {"replace": f"{said} {reply} {note}.".replace("  ", " ").strip()})
        views = [e for e in events if e["event"] == "view"]
        for e in views:
            e["data"] = rebuilt
        if not views:
            capture("view", rebuilt)
        return {"id": out["id"], "view": out["view"]}

    def _decision_input(self, session: Journey) -> dict:
        trip_sid = session.sessions["trip"]
        snapshot = self._module(session, "trip").snapshot(trip_sid)
        hidden_ids = snapshot.get("state", {}).get("meta", {}).get("hidden_ids", [])
        return {"search_input": session.outputs["trip"], "trip_session": trip_sid, "hidden_ids": hidden_ids}

    def _advance(self, session: Journey, spans: dict | None = None) -> dict:
        if session.stage == "trip":
            if "trip" not in session.outputs:
                raise Conflict("Trip Understanding has not compiled Search Input")
            payload = self._decision_input(session)
            existing = session.sessions.get("decision")
            decision = self._module(session, "decision")
            snapshot = session.snapshots.get("decision") or {}
            unchanged = (snapshot.get("search_input") == session.outputs["trip"]
                         and snapshot.get("hidden_ids", []) == payload["hidden_ids"])
            result = decision.load(existing) if existing and unchanged else decision.rebase(existing, payload) if existing else decision.create(payload)
            session.stage = "decision"
        elif "planning" in session.sessions and "decision" in session.outputs:
            session.stage = "planning"
            result = self._module(session, "planning").load(session.sessions["planning"])
        else:
            # Read the current gate, including health hints that cannot be compiled into a SearchInput yet.
            readback = self._module(session, "trip").read(session.sessions["trip"], "readback", {})
            if needed := readback.get("missing"):
                raise TripNotReady(needed, readback)
            with _advance_span(spans, "tools_ms"):
                decision = self._module(session, "decision")
            with _advance_span(spans, "decision_handoff_ms"):
                output = decision.apply(session.sessions["decision"], "confirm", {"for_planning": True}, lambda *args: None)
                output = self._bound_output(session, output)
            try:
                with _advance_span(spans, "tools_ms"):
                    planning = self._module(session, "planning")
                with _advance_span(spans, "planning_create_ms"):
                    result = planning.create({"decision_output": output})
            except TripIncomplete as exc:
                readback = self._module(session, "trip").read(session.sessions["trip"], "readback", {})
                raise TripNotReady(exc.missing, readback) from exc
            session.outputs["decision"] = output
            session.stage = "planning"
        session.sessions[session.stage] = result["id"]
        return result
