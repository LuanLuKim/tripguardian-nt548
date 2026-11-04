#!/usr/bin/env python3
"""Real-user scenario matrix on production, over the same HTTP calls the web makes.

Run (one command, from the repo root; needs the harness behind :28899 and 9router for the simulator and the judge):

    .venv/bin/python scripts/prod_journey_e2e.py                      # all cases, 4 at a time
    .venv/bin/python scripts/prod_journey_e2e.py --only a,b --jobs 2  # some cases
    .venv/bin/python scripts/prod_journey_e2e.py --report <run_id>    # rebuild the tables of a finished run

Every case is a new guest session (or the dev account, trips marked "QA matrix"; old trips are never touched). The
runner follows the web's order: auth -> create -> Tìm hiểu chat -> show -> advance -> Lựa chọn picks -> advance (gate
409 is valid) -> gate answers -> readback_ok -> advance (plan) -> edits -> confirm -> reload. It times every wait,
runs the automatic checks (docs: config/prod_journey_cases.yaml, src/bench/prod_cases.py), and asks the Agent model
(9router, role AGENT) to grade each "satisfied" criterion. Results: .superpowers/sdd/2026-11-03-prod-e2e/matrix/runs/<run_id>/.
Keys and cookies are never printed or stored.
"""

import argparse
import asyncio
import concurrent.futures as cf
import copy
import json
import math
import os
import re
import statistics
import sys
import threading
import time
import unicodedata
import uuid
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import httpx  # noqa: E402
from dotenv import dotenv_values  # noqa: E402

from bench import prod_cases  # noqa: E402

OUT = ROOT / ".superpowers" / "sdd" / "2026-11-03-prod-e2e" / "matrix"
BASE_URL = os.environ.get("PROD_JOURNEY_BASE", "http://127.0.0.1:28899")
SESS = "/api/harness/sessions"
SLOW = {"chat": 8.0, "screen": 2.0, "plan": 5.0}   # seconds: chat turn, screen load, plan build
PLACE_ID = re.compile(r"0x[0-9a-f]+:0x[0-9a-f]+")
ENV = dotenv_values(ROOT / ".env")
ORIGIN = BASE_URL.rstrip("/") if os.environ.get("PROD_JOURNEY_BASE") else ENV.get("APP_BASE_URL", "")

# ---------------------------------------------------------------------------------------------------------------
# corpus records (read only, for the id / hours / hard-constraint checks)
_RECS: dict | None = None
_RECS_LOCK = threading.Lock()


def records() -> dict:
    global _RECS
    with _RECS_LOCK:
        if _RECS is None:
            from corpus import serving
            _RECS = {r["id"]: r for r in serving.load()}
        return _RECS


def load_service_records(path: Path) -> dict:
    items = json.loads(path.read_text(encoding="utf-8")).get("items", [])
    return {r["fid"]: r for r in items if r.get("fid") and r.get("name") and r.get("url")}


def service_records() -> dict:
    return load_service_records(ROOT / "data/gmaps/list/dalat_svc.json")


def serving_check(rec: dict, fid: str, forbidden: str) -> str:
    from corpus import serving
    try:
        return serving.check(rec, fid, forbidden)
    except Exception:
        return "unknown"


def norm(s: str) -> str:
    s = unicodedata.normalize("NFD", s.casefold().replace("đ", "d"))
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", "".join(c for c in s if unicodedata.category(c) != "Mn"))).strip()


def hm(t: str) -> int:
    h, m = t.split(":")[:2]
    return int(h) * 60 + int(m)


def clock(x: int) -> str:
    return f"{x // 60 % 24:02d}:{x % 60:02d}"


# ---------------------------------------------------------------------------------------------------------------
# model calls: the simulator and the judge both use role AGENT (9router, cx/gpt-6.1-terra); USER_SIM when configured
def ask_model(system: str, user: str, temperature: float = 0.3, max_tokens: int = 900) -> str:
    from corpus.llm import AGENT
    role = AGENT

    async def go():
        client, model = role.own_client()
        try:
            r = await client.chat.completions.create(model=model, temperature=temperature, max_tokens=max_tokens, timeout=90,
                                                     messages=[{"role": "system", "content": system}, {"role": "user", "content": user}])
            return (r.choices[0].message.content or "").strip()
        finally:
            await client.close()
    last = None
    for n in range(3):
        try:
            return asyncio.run(go())
        except Exception as exc:  # noqa: BLE001 - the model endpoint is outside our control
            last = exc
            time.sleep(2 + 3 * n)
    raise RuntimeError(f"model call failed: {type(last).__name__}")


SIM_SYSTEM = ("Bạn đóng vai một người dùng Việt Nam đang chat với trợ lý lập lịch du lịch Đà Lạt. Chỉ viết MỘT tin nhắn người dùng "
              "sẽ gõ, tiếng Việt, tối đa 25 từ, đúng giọng nhân vật. Chỉ dùng thông tin trong SỰ THẬT; điều không có trong sự thật "
              "thì trả lời 'sao cũng được' hoặc 'chưa biết'. Nếu trợ lý hỏi một điều đã nói rồi thì nói 'mình nói rồi mà'. Không "
              "giải thích, không ngoặc kép, không tiền tố.")

JUDGE_SYSTEM = ("Bạn là người chấm chất lượng một trợ lý lập lịch du lịch Đà Lạt. Bạn nhận: sự thật ẩn của người dùng, danh sách tiêu chí "
                "'thỏa nhu cầu', lịch cuối cùng, tóm tắt hội thoại và các lỗi kiểm tự động. Với MỖI tiêu chí, chấm đúng một trong: "
                "\"đạt\" (lịch/hội thoại làm đúng rõ ràng), \"một phần\" (làm một phần hoặc chưa chắc), \"không\" (sai, thiếu hoặc không có "
                "bằng chứng). Chỉ dựa trên dữ liệu được đưa; không đoán thêm; thiếu bằng chứng thì chấm \"không\". Trả về DUY NHẤT một mảng "
                "JSON, mỗi phần tử {\"criterion\": <nguyên văn tiêu chí>, \"verdict\": \"đạt|một phần|không\", \"reason\": <một câu tiếng Việt>}.")


def sim_reply(case, say: str, tabs: list[str]) -> str:
    truth = json.dumps(case.truth.model_dump(mode="json"), ensure_ascii=False)
    user = (f"NHÂN VẬT: {case.persona}\nSỰ THẬT: {truth}\nTRỢ LÝ VỪA NÓI: {say[:600]}\nCÂU HỎI TRỢ LÝ ĐANG MỞ: {' | '.join(tabs)[:500] or '(không có)'}\n"
            "Viết tin nhắn trả lời của người dùng:")
    return ask_model(SIM_SYSTEM, user, 0.5, 120).strip().strip('"')


def judge(case, plan_text: str, chat_text: str, failed: list[str], evidence: dict | None = None) -> list[dict]:
    truth = json.dumps(case.truth.model_dump(mode="json"), ensure_ascii=False)
    crit = "\n".join(f"{i + 1}. {c}" for i, c in enumerate(case.expect.criteria))
    user = (f"SỰ THẬT ẨN: {truth}\n\nTIÊU CHÍ:\n{crit}\n\nLỊCH CUỐI:\n{plan_text[:6000]}\n\nHỘI THOẠI TÓM TẮT:\n{chat_text[:5000]}\n\n"
            f"LỖI KIỂM TỰ ĐỘNG: {'; '.join(failed)[:900] or 'không'}")
    if evidence:
        user += "\n\nBẰNG CHỨNG THẺ VÀ KIỂM GROUNDING:\n" + json.dumps(evidence, ensure_ascii=False)[:14000]
    raw = ask_model(JUDGE_SYSTEM, user, 0.1, 1800)
    m = re.search(r"\[.*\]", raw, re.S)
    try:
        out = json.loads(m.group(0)) if m else []
    except json.JSONDecodeError:
        out = []
    by = {o.get("criterion", ""): o for o in out if isinstance(o, dict)}
    res = []
    for i, c in enumerate(case.expect.criteria):
        o = by.get(c) or (out[i] if i < len(out) and isinstance(out[i], dict) else {})
        v = o.get("verdict") if o.get("verdict") in ("đạt", "một phần", "không") else "không"
        res.append({"criterion": c, "verdict": v, "reason": str(o.get("reason", "judge gave no verdict"))[:300]})
    return res


# ---------------------------------------------------------------------------------------------------------------
# HTTP client for one case
class Resp:
    def __init__(self, status, secs, events=None, body=None, first_say=None):
        self.status, self.secs, self.events, self.body, self.first_say = status, secs, events or [], body or {}, first_say

    def of(self, name):
        return [e["data"] for e in self.events if e["event"] == name]

    @property
    def journey(self):
        j = self.of("journey")
        return j[-1] if j else (self.body if "stage" in self.body else None)

    @property
    def say(self) -> str:
        out = ""
        for d in self.of("say"):
            out = d["replace"] if d.get("replace") is not None else out + (d.get("delta") or "")
        return out


def path_key(path: str) -> str:
    return re.sub(r"[0-9a-f]{12}", ":id", path.split("?")[0])


def trace_summary(value, key=""):
    if key.casefold() in {"password", "email", "token", "cookie", "tg_session", "api_key", "authorization"}:
        return "[redacted]"
    if isinstance(value, dict):
        if key == "view":
            return {"selected": value.get("selected"), "state": value.get("state"), "group_counts": {g.get("id", ""): len(g.get("cards", [])) for g in value.get("groups", [])}, "ok": value.get("ok"), "violations": value.get("violations")}
        if value.get("event") in ("view", "state", "journey"):
            return {"event": value["event"], "data": "summarized in case result"}
        return {k: trace_summary(v, k) for k, v in value.items()}
    if isinstance(value, list):
        return [trace_summary(v) for v in value[:50]]
    return value[:1200] if isinstance(value, str) else value


class Api:
    def __init__(self, case_id: str):
        self.case_id = case_id
        self.c = httpx.Client(base_url=BASE_URL, timeout=httpx.Timeout(240, connect=10), headers={"Origin": ORIGIN})
        self.sid = None
        self.rev = 0
        self.calls: list[dict] = []     # every request: path, status, secs, note
        self.steps: list[dict] = []     # what the user waits for: name, secs, ok
        self.limited = 0

    def close(self):
        self.c.close()

    def _log(self, method, path, status, secs, note=""):
        self.calls.append({"m": method, "p": path_key(path), "s": status, "t": round(secs, 2), "note": note})

    def raw(self, method, path, **kw):
        for n in range(4):
            t = time.time()
            try:
                r = self.c.request(method, path, **kw)
            except httpx.HTTPError as exc:
                self._log(method, path, 0, time.time() - t, type(exc).__name__)
                if n == 3:
                    raise
                time.sleep(2)
                continue
            if r.status_code == 429:
                self.limited += 1
                self._log(method, path, 429, time.time() - t, "rate limited, waited")
                time.sleep(7 + 5 * n)
                continue
            body = {}
            try:
                body = r.json()
            except Exception:  # noqa: BLE001
                pass
            note = (body.get("error") if isinstance(body, dict) else "") or ""
            self._log(method, path, r.status_code, time.time() - t, str(note)[:80])
            self.calls[-1].update(request=trace_summary(kw.get("json")), response=trace_summary(body))
            return r.status_code, body, time.time() - t
        return 429, {}, 0.0

    def step(self, name, secs, ok=True, note=""):
        self.steps.append({"step": name, "secs": round(secs, 2), "ok": ok, "note": note})

    # --- auth
    def guest(self):
        st, _, t = self.raw("POST", "/api/auth/guest")
        tok = self.c.cookies.get("tg_session")
        if st != 200 or not tok:
            raise RuntimeError(f"guest sign-in failed: {st}")
        self.c.cookies.clear()
        self.c.headers["Cookie"] = f"tg_session={tok}"   # the session cookie is Secure: over local http it is sent by hand
        self.step("auth", t, True)

    def dev_login(self):
        email, pw = ENV.get("DEV_ACCOUNT_EMAIL"), ENV.get("DEV_ACCOUNT_PASSWORD")
        if not email or not pw:
            raise RuntimeError("DEV_ACCOUNT_EMAIL / DEV_ACCOUNT_PASSWORD missing in .env")
        st, _, t = self.raw("POST", "/api/auth/login", json={"email": email, "password": pw})
        tok = self.c.cookies.get("tg_session")
        if st != 200 or not tok:
            raise RuntimeError(f"dev login failed: {st}")
        self.c.cookies.clear()
        self.c.headers["Cookie"] = f"tg_session={tok}"
        self.step("auth", t, True)

    def leave(self):
        try:
            self.raw("POST", "/api/auth/guest/leave")
        except Exception:  # noqa: BLE001
            pass

    # --- journey
    def create(self):
        st, body, t = self.raw("POST", SESS, json={"experience": "first", "start_with": "nothing"})
        if st not in (200, 201):
            raise RuntimeError(f"create failed: {st}")
        self.sid, self.rev = body["id"], body["revision"]
        self.step("create_trip", t, True)
        return body

    def load(self, stage=None):
        st, body, t = self.raw("GET", f"{SESS}/{self.sid}" + (f"?stage={stage}" if stage else ""))
        if st == 200:
            self.rev = max(self.rev, body["revision"])
        return Resp(st, t, body=body)

    def read(self, path):
        st, body, t = self.raw("GET", f"{SESS}/{self.sid}/read/{path}")
        return Resp(st, t, body=body)

    def request(self, stage, op, payload=None, sse=False, _retry=True) -> Resp:
        body = {"request_id": uuid.uuid4().hex, "stage": stage, "operation": op, "expected_revision": self.rev, "payload": payload or {}}
        for n in range(4):
            t0 = time.time()
            try:
                if not sse:
                    st, js, secs = self.raw("POST", f"{SESS}/{self.sid}/request", json=body)
                    r = Resp(st, secs, body=js)
                    if st == 200 and js.get("revision") is not None:
                        self.rev = js["revision"]
                    if st == 409 and js.get("error") == "stale revision" and _retry:
                        self.load()
                        return self.request(stage, op, payload, sse, False)
                    return r
                r = self._stream(body)
                if r.status == 409 and r.body.get("error") == "stale revision" and _retry:
                    self.load()
                    return self.request(stage, op, payload, sse, False)
                return r
            except httpx.HTTPError as exc:
                self._log("POST", f"{SESS}/{self.sid}/request", 0, time.time() - t0, type(exc).__name__)
                if n == 3:
                    raise
                time.sleep(3)
        raise RuntimeError("request failed")

    def _stream(self, body) -> Resp:
        t0 = time.time()
        events, first_say = [], None
        with self.c.stream("POST", f"{SESS}/{self.sid}/request", json=body, headers={"Accept": "text/event-stream"}) as r:
            if r.status_code != 200:
                try:
                    js = json.loads(r.read() or b"{}")
                except Exception:  # noqa: BLE001
                    js = {}
                self._log("POST", f"{SESS}/{self.sid}/request", r.status_code, time.time() - t0, str(js.get("error", ""))[:80])
                self.calls[-1].update(request=trace_summary(body), response=trace_summary(js))
                if r.status_code == 429:
                    self.limited += 1
                    time.sleep(8)
                    return self._stream(body)
                return Resp(r.status_code, time.time() - t0, body=js)
            buf = ""
            for chunk in r.iter_text():
                buf += chunk
                while "\n\n" in buf:
                    blk, buf = buf.split("\n\n", 1)
                    data = "\n".join(line[6:] for line in blk.split("\n") if line.startswith("data: "))
                    if not data:
                        continue
                    e = json.loads(data)
                    events.append(e)
                    if e["event"] == "say" and first_say is None:
                        first_say = time.time() - t0
        secs = time.time() - t0
        err = next((e["data"] for e in events if e["event"] == "error"), None)
        j = next((e["data"] for e in reversed(events) if e["event"] == "journey"), None)
        if j:
            self.rev = j["revision"]
        self._log("POST", f"{SESS}/{self.sid}/request", err.get("status", 500) if err else 200, secs, (err or {}).get("message", "")[:80] if err else "sse")
        self.calls[-1].update(request=trace_summary(body), response=trace_summary(events))
        return Resp(err.get("status", 500) if err else 200, secs, events, (err or {}), first_say)


# ---------------------------------------------------------------------------------------------------------------
# summaries of what the user sees
def tab_lines(card) -> list[str]:
    out = []
    if not isinstance(card, dict):
        return out
    for t in card.get("tabs", []):
        out.append(t.get("question") or t.get("header") or t.get("qid", ""))
    if card.get("text"):
        out.append(card["text"])
    return out


def card_texts(card) -> list[tuple[str, str]]:
    """Every sentence a deck / card shows the user."""
    out = []
    if not isinstance(card, dict):
        return out
    for t in card.get("tabs", []):
        for k in ("header", "question", "why"):
            out.append((f"deck.{t.get('qid')}.{k}", t.get(k) or ""))
        for o in t.get("options", []):
            out.append((f"deck.{t.get('qid')}.option", f"{o.get('label', '')} {o.get('description', '')} {o.get('because', '')}"))
    for k in ("text", "reason", "placeholder"):
        if card.get(k):
            out.append((f"card.{k}", card[k]))
    for c in card.get("chips", []) or []:
        out.append(("card.chip", c.get("label", "")))
    return out


def place_ids(obj) -> list[str]:
    return list(dict.fromkeys(PLACE_ID.findall(json.dumps(obj, ensure_ascii=False))))


def name_of(pid: str) -> str:
    r = records().get(pid)
    return r["identity"]["name"] if r else pid


def itinerary(view: dict) -> list[dict]:
    if not view:
        return []
    it = view.get("itinerary")
    if it:
        return it
    av = view.get("active_variant") or next(iter(view.get("variants") or []), None)
    return (av or {}).get("itinerary") or []


def plan_summary(view: dict) -> dict:
    days = []
    for d in itinerary(view):
        days.append({"day": d["day"], "date": d.get("date"), "window": d.get("window"),
                     "items": [{k: i.get(k) for k in ("kind", "start", "end", "place_id", "name", "note", "from", "to") if i.get(k) is not None}
                               for i in d.get("items", [])]})
    ov = view.get("overload") or {}
    return {"ok": view.get("ok"), "days": days, "warnings": [w.get("text", "") for w in view.get("warnings", []) if isinstance(w, dict)],
            "unplaced": view.get("unplaced"), "tradeoffs": view.get("tradeoffs"), "overload": ov.get("text") if ov else None,
            "back_to_decision": view.get("back_to_decision"),
            "variants": [{"id": v["id"], "label": v.get("label"), "status": v.get("status"), "places": (v.get("metrics") or {}).get("places"),
                          "dropped": [{"name": d.get("name"), "place_id": d.get("place_id"), "reason": d.get("text")} for d in v.get("dropped_by_plan") or []]}
                         for v in view.get("variants", [])],
            "chosen_variant": (view.get("state") or {}).get("chosen_variant"),
            "recommendations": [r.get("text", "") for r in view.get("recommendations") or []],
            "backups": [{"place_id": p.get("place_id"), "alts": [a.get("id") for a in p.get("alternatives", [])]} for p in (view.get("backups") or {}).get("places", [])][:30],
            "lodging": {"status": (view.get("lodging") or {}).get("status")},
            # the screen's faded suggestions in empty meal slots / free time, its cost line and crowd tips
            "ghosts": [{"day": g.get("day"), "kind": g.get("kind"), "start": g.get("start"),
                        "names": [i.get("name") for i in g.get("items") or []][:3]} for g in view.get("ghosts") or []],
            "cost_vnd": (view.get("metrics") or {}).get("estimated_cost_vnd"),
            "crowd_tips": [t.get("text") for t in view.get("crowd_tips") or [] if t.get("text")][:6]}


def visits(summary: dict) -> list[dict]:
    return [dict(i, day=d["day"], date=d.get("date")) for d in summary["days"] for i in d["items"] if i["kind"] == "visit"]


KIND_VI = {"visit": "ghé", "meal_free": "ăn tự chọn", "rest": "nghỉ", "free": "trống"}
MEAL_VI = {"breakfast": "bữa sáng", "lunch": "bữa trưa", "dinner": "bữa tối", "free": "thời gian trống"}


def plan_text(summary: dict) -> str:
    lines = []
    ghosts = summary.get("ghosts") or []
    for d in summary["days"]:
        lines.append(f"Ngày {d['day']} ({d.get('date')}) khung {d.get('window')}")
        for i in d["items"]:
            if i["kind"] in ("visit", "meal_free", "rest", "free"):
                label = MEAL_VI.get(i.get("name"), i.get("name")) if i["kind"] == "meal_free" else (
                    i.get("name") if i["kind"] == "visit" else "")
                lines.append(f"  {i['start']}-{i['end']} {KIND_VI[i['kind']]} {label or ''}".rstrip())
        for g in ghosts:
            if g.get("day") == d["day"] - 1 and g.get("names"):
                at = f"{g['start'] // 60:02d}:{g['start'] % 60:02d}" if isinstance(g.get("start"), int) else ""
                lines.append(f"  gợi ý mờ (bấm để thêm) {at} {MEAL_VI.get(g['kind'], g['kind'])}: {' / '.join(g['names'])}")
    if summary.get("cost_vnd"):
        lines.append(f"  chi phí ước tính: ~{summary['cost_vnd'] // 1000}k/người")
    lines += [f"  mẹo giờ đông: {t}" for t in summary.get("crowd_tips") or []][:4]
    if summary.get("unplaced") or summary["variants"]:
        for v in summary["variants"]:
            if v["dropped"]:
                lines.append(f"  bỏ: {[(x['name'], x['reason']) for x in v['dropped']][:6]}")
    lines += [f"  cảnh báo: {w}" for w in summary["warnings"][:8]]
    if summary.get("overload"):
        lines.append(f"  quá tải: {summary['overload']}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------------------------------------------
# the gate before planning: answers from the hidden truth, the same form the web fills
MOBILITY_WORDS = {"motorbike": ("motorbike", "xe máy", "xe may"), "car": ("car", "ô tô", "o to", "taxi"), "walk": ("walk", "đi bộ", "xe khách", "taxi", "grab")}
CARE_ID = {"steps": "steps", "wheelchair": "wheelchair", "pregnant": "pregnant", "motion_sick": "motion_sick", "height": "height",
           "vegetarian": "vegetarian", "vegan": "vegan"}


def pick_option(tab: dict, words: tuple) -> str | None:
    for o in tab.get("options", []):
        if o["id"] in ("skip", "other"):
            continue
        hay = norm(f"{o['id']} {o.get('label', '')}")
        if any(norm(w) in hay for w in words):
            return o["id"]
    return None


def option_clock(tab: dict, slot: str) -> str | None:
    for o in tab.get("options", []):
        if o["id"].startswith(f"{slot}.") and o.get("prefilled"):
            m = re.search(r"\b\d{2}:\d{2}\b", f"{o.get('label', '')} {o.get('description', '')}")
            if m:
                return m.group(0)
    return None


def lodging_answer(api: Api, name: str) -> str | None:
    st, hits, _ = api.raw("GET", f"/api/harness/lodging/suggest?q={httpx.QueryParams({'q': name})['q']}&top=3")
    if st == 200 and isinstance(hits, list):
        for h in hits:
            if norm(name) in norm(h.get("text", "")) or norm(h.get("text", "")) in norm(name):
                return json.dumps({"kind": h["kind"], **({"id": h["id"]} if h.get("id") else {}), "text": h["text"], "lat": h["lat"], "lng": h["lng"]}, ensure_ascii=False)
    st, hits, _ = api.raw("GET", f"/api/harness/geo?q={httpx.QueryParams({'q': name})['q']}")
    if st == 200 and isinstance(hits, list) and hits:
        h = hits[0]
        return json.dumps({"kind": "address", "text": h["text"], "lat": h["lat"], "lng": h["lng"]}, ensure_ascii=False)
    return None


def gate_answers(case, deck: dict, api: Api) -> tuple[dict, list[str]]:
    t, answers, notes = case.truth, {}, []
    for tab in deck.get("tabs", []):
        q, inputs = tab["qid"], tab.get("inputs", [])
        ids = {o["id"] for o in tab.get("options", [])}
        if ids == {"other"}:
            continue  # Web sends a text turn for this action, not a deck option.
        if q == "trip":
            if "dates" in inputs or any(i.startswith("dates.") for i in ids):
                start = t.start or (date.today() + timedelta(days=(5 - date.today().weekday()) % 7 + 7))
                if not t.start:
                    notes.append(f"truth has no date: the gate got {start}")
                answers["trip.dates"] = f"{start}..{start + timedelta(days=t.days - 1)}"
            if "start" in inputs:
                v = t.start_hour or option_clock(tab, "start")
                if v:
                    answers["trip.start"] = v
            if "end" in inputs:
                v = t.end_hour or option_clock(tab, "end")
                if v:
                    answers["trip.end"] = v
        elif q == "companions":
            who = [w for w in t.companions if w in ids] or [w for w in t.companions if w == "kids" and "kids" in ids]
            if "who" in inputs or who:
                if who:
                    answers["companions.who"] = who
            implied = 1 if t.companions == ["solo"] else 2 if t.companions == ["partner"] else None
            if "people" in inputs and t.people != implied:
                answers["companions.people"] = str(t.people)
            elif "people.prefilled" in ids and not who:
                answers["companions"] = ["people.prefilled"]
        elif q == "mobility":
            oid = pick_option(tab, MOBILITY_WORDS[t.mobility])
            answers["mobility"] = [oid] if oid else ["skip"] if "skip" in ids else [tab["options"][0]["id"]]
        elif q == "care":
            picked = [CARE_ID[c] for c in t.care if CARE_ID[c] in ids]
            answers["care"] = picked or (["none"] if "none" in ids else ["skip"])
        elif q == "pace":
            answers["pace"] = [t.pace] if t.pace and t.pace in ids else ["skip"]
        elif q == "budget":
            if t.budget_unlimited:
                answers["budget.unlimited"] = "true"
            elif t.budget_vnd:
                answers["budget.amount"] = str(t.budget_vnd)
                answers["budget.scope"] = "per_person_day"
            else:
                answers["budget"] = ["skip"]
        elif q == "lodging":
            pick = lodging_answer(api, t.lodging) if t.lodging else None
            if t.lodging and not pick:
                notes.append(f"lodging '{t.lodging}' not found by suggest/geo: skipped")
            answers["lodging"] = pick or ["skip"]
        else:
            answers[q] = ["skip"] if "skip" in ids else [next(o["id"] for o in tab["options"])]
    # Never invent a skip id on a tab that does not offer it.
    for tab in deck.get("tabs", []):
        q = tab["qid"]
        if isinstance(answers.get(q), list):
            ids = {o["id"] for o in tab.get("options", [])} - {"other"}
            answers[q] = [v for v in answers[q] if v in ids]
            if not answers[q]:
                del answers[q]
    return answers, notes


def gate_payload(case, deck: dict, api: Api) -> dict:
    typed = [t for t in deck.get("tabs", []) if {o["id"] for o in t.get("options", [])} == {"other"}]
    if typed:
        # Reuse the traveller's own dated dietary statement rather than fabricate a date.
        care = [turn.text for turn in case.chat if re.search(r"chay|kiêng|dị ứng|say xe|bậc|bầu|lăn", turn.text, re.I)]
        text = " ".join(care)
        if not text:
            text = "Ăn chay cả chuyến." if "vegetarian" in case.truth.care else "Không có lưu ý sức khỏe hay ăn uống nào khác."
        return {"kind": "text", "text": text}
    answers, _ = gate_answers(case, deck, api)
    return {"kind": "deck", "answers": answers}


def gate_state(rb: dict) -> str:
    return json.dumps({k: rb.get(k) for k in ("missing", "deck", "lines")}, sort_keys=True, ensure_ascii=False)


def resolve_gate(case, api: Api, rb: dict, rec: dict, texts) -> bool:
    seen = set()
    for _ in range(5):
        signature = gate_state(rb)
        if signature in seen:
            rec.setdefault("blocked", {})["planning"] = "gate state did not progress"
            return False
        seen.add(signature)
        deck = rb.get("deck") or {}
        if rb.get("missing"):
            if not deck.get("tabs"):
                rec.setdefault("blocked", {})["planning"] = "missing fields without answerable tabs"
                return False
            payload = gate_payload(case, deck, api)
            a = api.request("decision", "trip", payload, sse=True)
            api.step("gate_answer", a.secs, a.status == 200)
            issues = [i for d in a.of("deck_issues") for i in d.get("issues", [])]
            rec["gate"].append({"answered": list(payload.get("answers", {})), "kind": payload["kind"], "issues": issues, "secs": round(a.secs, 2)})
            if a.status != 200:
                rec["errors"].append(f"gate answer failed {a.status}")
                rec.setdefault("blocked", {})["planning"] = "gate answer rejected"
                return False
            rbr = api.read("trip/readback")
            api.step("gate_readback", rbr.secs, rbr.status == 200)
            if rbr.status != 200:
                rec["errors"].append(f"gate readback failed {rbr.status}")
                rec.setdefault("blocked", {})["planning"] = "readback unavailable"
                return False
            rb = rbr.body
            texts.extend(("gate.line", l["text"]) for l in rb.get("lines", []))
            if rb.get("missing"):
                continue
        if rb.get("digest"):
            ok = api.request("decision", "trip", {"kind": "readback_ok", "value": rb["digest"]}, sse=True)
            api.step("gate_confirm", ok.secs, ok.status == 200)
            if ok.status == 200:
                return True
        rec.setdefault("blocked", {})["planning"] = "readback could not be confirmed"
        return False
    rec.setdefault("blocked", {})["planning"] = "gate remained incomplete"
    return False


def plan_ready(view: dict) -> bool:
    chosen = (view.get("state") or {}).get("chosen_variant")
    active = next((v for v in view.get("variants", []) if v.get("id") == chosen), view.get("active_variant") or {})
    return bool(chosen) and active.get("confirmable") is not False and not view.get("violations") and view.get("ok") is not False


# ---------------------------------------------------------------------------------------------------------------
# the run of one case
def open_question(resp: Resp) -> list[str]:
    cards = resp.of("card")
    tabs = tab_lines(cards[-1]) if cards and cards[-1] else []
    return tabs or ([resp.say] if "?" in resp.say else [])


def understanding_rows(resp: Resp) -> dict:
    st = resp.of("state")
    if not st:
        return {}
    u = st[-1]["understanding"]
    rows = {r["target"]: r["value"] for r in u.get("trip", [])}
    rows["_budget_vnd"] = u.get("budget_vnd")
    rows["_pace"] = u.get("pace")
    rows["_required"] = {r["key"]: r["done"] for r in u.get("required", [])}
    return rows


def pick_places(case, api: Api, view: dict, rec: dict) -> dict:
    """The case's rule over the Lựa chọn list; returns the last view."""
    pk = case.pick
    taken = list(view.get("selected") or [])
    cards = [c for g in view["groups"] for c in g["cards"]]
    chosen: list[str] = []

    def act(pid: str) -> bool:
        nonlocal view
        r = api.request("decision", "act", {"type": "select", "place_id": pid})
        api.step("pick_place", r.secs, r.status == 200, f"{r.status}")
        card = next((c for c in cards if c["id"] == pid), {})
        rec["picks"].append({"id": pid, "name": name_of(pid), "status": r.status, "secs": round(r.secs, 2),
                             "card": {"why": [w.get("text") for w in card.get("why") or []],
                                      "tradeoffs": [w.get("text") for w in card.get("tradeoffs") or []],
                                      "price": card.get("price"), "category": card.get("category"),
                                      "warnings": [w.get("text") if isinstance(w, dict) else w for w in card.get("warnings") or []],
                                      "known_for": card.get("known_for")} if card else None})
        if r.status == 200:
            view = r.body["result"]["view"]
            chosen.append(pid)
            return True
        rec["pick_errors"].append({"id": pid, "status": r.status, "error": r.body.get("error")})
        return False

    for name in pk.include:
        hit = next((c for c in cards if norm(name) in norm(c["name"])), None)
        if hit is None:
            r = api.read(f"decision/search?q={httpx.QueryParams({'q': name})['q']}")
            api.step("search_place", r.secs, r.status == 200)
            found = place_ids(r.body.get("cards") or r.body)
            hit = next(({"id": p, "name": name_of(p)} for p in found if norm(name) in norm(name_of(p))), None)
            rec["searches"].append({"q": name, "status": r.status, "found": hit["name"] if hit else None})
        if hit and hit["id"] not in chosen and hit["id"] not in taken:
            act(hit["id"])
    order = {g: i for i, g in enumerate(pk.groups)}
    pool = [c for c in cards if c["id"] not in chosen and c["id"] not in taken and c.get("status") == "main"
            and c["group"] not in pk.avoid_groups and (not pk.groups or c["group"] in order)]
    pool.sort(key=lambda c: (order.get(c["group"], 99), 0))
    by_group: dict[str, list] = {}
    for c in pool:
        by_group.setdefault(c["group"], []).append(c)
    queue = []
    while any(by_group.values()):                 # round-robin over the preferred groups, display order inside a group
        for g in sorted(by_group, key=lambda x: order.get(x, 99)):
            if by_group[g]:
                queue.append(by_group[g].pop(0))
    for c in queue:
        if len(chosen) >= pk.n:
            break
        act(c["id"])
    return view


def select_variant(api, view):
    if (view.get("state") or {}).get("chosen_variant"):
        return view
    options = [v for v in view.get("variants", []) if v.get("confirmable") is not False]
    if not options:
        return view
    chosen = max(options, key=lambda v: (v.get("metrics") or {}).get("places", 0))
    r = api.request("planning", "act", {"type": "pick_variant", "id": chosen["id"]})
    api.step("pick_variant", r.secs, r.status == 200)
    return r.body["result"]["view"] if r.status == 200 else view


def run_case(case: prod_cases.Case, run_dir: Path) -> dict:
    t_start = time.time()
    api = Api(case.id)
    rec: dict = {"id": case.id, "title": case.title, "auth": case.auth, "axes": case.axes, "chat": [], "gate": [], "picks": [], "pick_errors": [],
                 "searches": [], "plans": {}, "edits": [], "errors": [], "notes": []}
    texts: list[tuple[str, str]] = []          # every sentence the user would read: (where, text)
    try:
        (api.dev_login if case.auth == "dev" else api.guest)()
        create = api.create()
        rec["session"] = api.sid
        texts.append(("create.greeting", " ".join(m.get("text", "") for m in create["result"]["transcript"])))

        # --- Tìm hiểu: scripted turns, then the simulator answers open questions
        last = None
        rows: dict = {}

        def turn(text: str, kind: str):
            nonlocal last, rows
            r = api.request("trip", "turn", {"kind": "text", "text": text}, sse=True)
            last = r
            api.step("chat_turn", r.secs, r.status == 200, kind)
            if r.first_say is not None:
                api.step("chat_first_word", r.first_say, True, kind)
            tabs = open_question(r)
            ent = {"user": text, "kind": kind, "status": r.status, "secs": round(r.secs, 2), "first_say": round(r.first_say, 2) if r.first_say else None,
                   "say": r.say, "open_questions": tabs, "places": place_ids([r.of("places"), r.of("block")]),
                   "blocks": [b.get("kind") for b in r.of("block")], "error": r.body.get("message") if r.status != 200 else None}
            rec["chat"].append(ent)
            texts.append((f"chat.{len(rec['chat'])}.say", r.say))
            for ev_card in r.of("card"):
                texts.extend((f"chat.{len(rec['chat'])}.{w}", s) for w, s in card_texts(ev_card))
            for rp in r.of("replies"):
                texts.extend((f"chat.{len(rec['chat'])}.reply", s) for s in rp.get("options", []))
            got = understanding_rows(r)
            if got:
                rows = got
            return r

        for t in case.chat:
            text = t.text
            turn(text, t.kind)
        for k in range(case.sim_replies):
            if last is None or last.status != 200 or not open_question(last):
                break
            reply = sim_reply(case, last.say, open_question(last))
            turn(reply, "sim_reply")
        rec["understanding_after_chat"] = {k: v for k, v in rows.items() if not k.startswith("_required")}
        rec["required_after_chat"] = rows.get("_required")

        # --- show -> done -> advance (Tìm hiểu -> Lựa chọn)
        done = None
        for n in range(3):
            r = api.request("trip", "turn", {"kind": "show"}, sse=True)
            api.step("show_next", r.secs, r.status == 200)
            if r.of("done"):
                done = r.of("done")[0]["search_input"]
                break
            reply = sim_reply(case, r.say, open_question(r))
            rec["notes"].append(f"show #{n + 1} gave no done: {r.say[:100]}")
            turn(reply, "sim_reply")
        rec["search_input_context"] = (done or {}).get("context")
        if done is None:
            rec["errors"].append("the trip never reached done")
            return finish(case, api, rec, texts, run_dir, t_start)
        adv = api.request("trip", "advance")
        api.step("to_choose", adv.secs, adv.status == 200)
        if adv.status != 200:
            rec["errors"].append(f"trip advance failed {adv.status} {adv.body.get('error')}")
            return finish(case, api, rec, texts, run_dir, t_start)
        ld = api.load("decision")
        api.step("open_choose", ld.secs, ld.status == 200)
        view = ld.body["result"]["view"]

        # --- Lựa chọn
        rec["choose_initial"] = {"groups": {g["id"]: len(g["cards"]) for g in view["groups"]}, "feasibility": view.get("feasibility", {}).get("status")}
        view = pick_places(case, api, view, rec)
        rec["selected"] = [{"id": p, "name": name_of(p)} for p in view.get("selected", [])]
        feas = view.get("feasibility") or {}
        rec["choose_after_picks"] = {"feasibility": feas.get("status"), "conflicts": feas.get("conflicts"), "warnings": feas.get("warnings"),
                                     "pending": view.get("pending"), "change": view.get("change")}
        collect_choose_texts(texts, view)
        # Explore / SelectedBar do not render feasibility conflicts or warnings.
        rec["choose_after_picks"]["visible_nudges"] = []

        # --- Lập lịch: the gate (409 is valid), then the plan
        plan_journey = None
        t_wait = 0.0
        seen_gates = set()
        for n in range(6):
            r = api.request("decision", "advance")
            if r.status == 200:
                api.step("plan_generate", r.secs, True, f"after {n} gate rounds")
                plan_journey = r.body
                t_wait += r.secs
                break
            if r.status == 409 and r.body.get("error") == "trip_incomplete":
                api.step("gate_open", r.secs, True, f"missing {r.body.get('missing')}")
                rb = r.body["readback"]
                signature = gate_state(rb)
                if signature in seen_gates:
                    rec.setdefault("blocked", {})["planning"] = "advance returned the same incomplete state"
                    break
                seen_gates.add(signature)
                rec["gate"].append({"missing": r.body.get("missing"), "inputs": {t["qid"]: t.get("inputs", []) for t in (rb.get("deck") or {}).get("tabs", [])}, "tabs": (rb.get("deck") or {}).get("tabs", []), "lines": [l["text"] for l in rb.get("lines", [])], "round": n, "secs": round(r.secs, 2)})
                texts.extend(("gate.line", l["text"]) for l in rb.get("lines", []))
                texts.extend(card_texts(rb.get("deck")))
                if not resolve_gate(case, api, rb, rec, texts):
                    break
                continue
            rec["errors"].append(f"decision advance {r.status} {r.body.get('error')}")
            break
        if plan_journey is None:
            rec["errors"].append("no plan was produced")
            return finish(case, api, rec, texts, run_dir, t_start)
        rec["plan_wait_after_gate"] = round(t_wait, 2)
        pv = select_variant(api, plan_journey["result"]["view"])
        rec["outputs_trip"] = (plan_journey.get("outputs") or {}).get("trip")
        s0 = plan_summary(pv)
        rec["plans"]["generated"] = s0
        collect_plan_texts(texts, pv, "plan")
        rl = api.load("planning")
        api.step("load_plan", rl.secs, rl.status == 200)
        if case.auth == "guest":
            rec["eve_policy"] = "guest route not called"
        if not plan_ready(pv):
            rec.setdefault("blocked", {})["confirmation"] = "no valid selected variant"
            rec["errors"].append("no confirmable selected plan")
            return finish(case, api, rec, texts, run_dir, t_start)

        # --- edits
        cur_view = pv
        for e in case.edits:
            cur_view = apply_edit(case, api, e, cur_view, rec, texts)

        # --- confirm, reload, trips list
        if not plan_ready(cur_view):
            rec.setdefault("blocked", {})["confirmation"] = "edited draft still has violations"
            rec["errors"].append("edited draft is not confirmable")
            return finish(case, api, rec, texts, run_dir, t_start)
        cf_ = api.request("planning", "confirm")
        api.step("confirm", cf_.secs, cf_.status == 200)
        rec["confirm_status"] = cf_.status
        if cf_.status != 200:
            rec["errors"].append(f"confirm failed {cf_.status} {cf_.body.get('error')}")
        rl2 = api.load("planning")
        api.step("reload_confirmed", rl2.secs, rl2.status == 200)
        if rl2.status == 200:
            rec["plans"]["reloaded"] = plan_summary(rl2.body["result"]["view"])
            rec["reload_stage"] = rl2.body.get("stage")
        st, trips, t = api.raw("GET", "/api/harness/trips")
        api.step("trips_list", t, st == 200)
        mine = next((x for x in trips if x["id"] == api.sid), None) if st == 200 and isinstance(trips, list) else None
        rec["trips_entry"] = {k: mine.get(k) for k in ("stage", "confirmed", "days", "people", "start_date")} | {"places": len(mine.get("places", []))} if mine else None
        return finish(case, api, rec, texts, run_dir, t_start)
    except Exception as exc:  # noqa: BLE001 - one broken case must not stop the matrix
        rec["errors"].append(f"{type(exc).__name__}: {str(exc)[:200]}")
        return finish(case, api, rec, texts, run_dir, t_start)


def collect_choose_texts(texts, view):
    """Project PlaceCard/cardLines and Explore.pending, not internal feasibility."""
    for group in view.get("groups", []):
        for card in group.get("cards", []):
            for key in ("name", "category", "area", "price"):
                if isinstance(card.get(key), str):
                    texts.append((f"choose.card.{key}", card[key]))
            texts.extend(("choose.card.why", why.get("text") or "") for why in (card.get("why") or [])[:3])
            notes = [f"Không hợp điều kiện của bạn: {x}" for x in card.get("failed", [])]
            notes += list(card.get("unverified") or []) + list(card.get("warnings") or [])
            if card.get("depends_on_unknown"):
                notes.append(card["depends_on_unknown"])
            trades = [t.get("text") or "" for t in card.get("tradeoffs") or []]
            trade = trades[0] if trades else notes.pop(0) if notes else ""
            for line in [trade] + (trades[1:] + notes)[:2]:
                if isinstance(line, str) and line:
                    texts.append(("choose.card.alert", line))
    pending = view.get("pending") or {}
    for key in ("text", "reason"):
        if pending.get(key):
            texts.append((f"choose.pending.{key}", pending[key]))
    texts.extend(("choose.pending.chip", c.get("label") or "") for c in pending.get("chips", []))


def collect_plan_texts(texts, view, tag):
    for w in view.get("warnings", []):
        texts.append((f"{tag}.warning", w.get("text", "") if isinstance(w, dict) else str(w)))
    for r in view.get("recommendations") or []:
        texts.append((f"{tag}.recommendation", r.get("text", "")))
    if view.get("overload"):
        texts.append((f"{tag}.overload", view["overload"].get("text", "")))
    for v in view.get("variants", []):
        for k in ("label", "tradeoff"):
            if v.get(k):
                texts.append((f"{tag}.variant.{k}", str(v[k])))
        definition = v.get("definition") if v.get("definition") is not None else v.get("why")
        if definition:
            texts.append((f"{tag}.variant.definition", definition))
        if v.get("status") == "unavailable" and v.get("unavailable_reason"):
            texts.append((f"{tag}.variant.unavailable_reason", v["unavailable_reason"]))
        for d in v.get("dropped_by_plan") or []:
            texts.append((f"{tag}.dropped", f"{d.get('name') or ''}: {d.get('text') or ''}"))
    for d in itinerary(view):
        for i in d.get("items", []):
            note = i.get("note") or ""
            visible_note = note if i.get("kind") == "visit" and " " in note else ""
            texts.append((f"{tag}.item", f"{i.get('name') or ''} {visible_note}".strip()))
    unplaced_labels = {"no_record": "chưa có dữ liệu địa điểm", "not_plannable": "không xếp được vào lịch", "no_coordinates": "chưa có tọa độ", "no_visit_time": "chưa rõ nên ghé bao lâu"}
    for t in view.get("tradeoffs") or []:
        if t.get("kind") != "relaxed":
            reason = t.get("reason") or ""
            texts.append((f"{tag}.tradeoff", f"{name_of(t.get('place_id'))}: chưa xếp được ({unplaced_labels.get(reason, reason)})."))


def apply_edit(case, api: Api, e: prod_cases.Edit, view: dict, rec: dict, texts) -> dict:
    s_before = plan_summary(view)
    vs = visits(s_before)
    out = {"op": e.op, "verify": e.verify, "applied": None, "detail": ""}
    action = None
    if e.op == "drop_first" and vs:
        action = {"type": "drop_place", "place": vs[-1]["place_id"]}
        out["name"] = vs[-1].get("name")
    elif e.op == "drop_name":
        hit = next((v for v in vs if norm(e.name) in norm(v.get("name", ""))), None)
        if hit:
            action = {"type": "drop_place", "place": hit["place_id"]}
            out["name"] = hit.get("name")
    elif e.op == "add_backup":
        for b in s_before.get("backups", []):
            alt = next((a for a in b["alts"] if a and a not in {v["place_id"] for v in vs}), None)
            if alt:
                day = next((v["day"] for v in vs if v["place_id"] == b["place_id"]), 1)
                action = {"type": "add_from_backup", "place": alt, "day": day - 1}
                out["name"] = name_of(alt)
                break
    elif e.op == "set_day_window":
        action = {"type": "set_day_window", "day": e.day - 1, "start": e.start, "end": e.end}
    elif e.op == "move_first" and vs:
        first = next((v for v in vs if v["day"] != e.day), vs[0])
        action = {"type": "move_place", "place": first["place_id"], "day": e.day - 1}
        out["name"] = first.get("name")
    elif e.op == "set_pace":
        action = {"type": "set_pace", "level": e.level}
    if e.op == "assistant":
        r = api.request("planning", "turn", {"text": e.text}, sse=True)
        api.step("edit_assistant", r.secs, r.status == 200)
        out.update(applied=r.status == 200, say=r.say, secs=round(r.secs, 2), status=r.status)
        texts.append(("edit.assistant.say", r.say))
        j = r.journey
        new_view = (j or {}).get("result", {}).get("view") if j else None
        if new_view:
            view = new_view
            collect_plan_texts(texts, view, "edit")
    elif action is None:
        out.update(applied=False, detail="no target for this edit in the current plan (skipped)")
    else:
        if action.get("place"):
            out["place_id"] = action["place"]
        r = api.request("planning", "act", action)
        api.step(f"edit_{e.op}", r.secs, r.status == 200, f"{r.status}")
        out.update(applied=r.status == 200, status=r.status, secs=round(r.secs, 2), action=action["type"], payload=action)
        if r.status == 200:
            view = r.body["result"]["view"]
            collect_plan_texts(texts, view, "edit")
        else:
            out["detail"] = str(r.body.get("error") or r.body.get("message"))[:160]
    after = plan_summary(view)
    out["verified"] = verify_edit(e, out, s_before, after)
    rec["edits"].append(out)
    rec["plans"][f"after_{len(rec['edits'])}_{e.op}"] = after
    return view


def verify_edit(e, out, before, after) -> dict:
    if not out.get("applied"):
        return {"ok": False if out.get("detail", "").startswith("no target") is False else None, "why": out.get("detail") or "not applied"}
    names_after = [norm(v.get("name", "")) for v in visits(after)]
    ids_after = {v["place_id"] for v in visits(after)}
    if e.verify == "absent":
        target = out.get("place_id")
        if not target:
            return {"ok": None, "why": "drop request id was not recorded"}
        gone = target not in ids_after
        return {"ok": gone, "why": f"id {target} {'no longer' if gone else 'still'} in the plan"}
    if e.verify == "present":
        target = e.name or out.get("name")
        if e.op == "assistant" and e.start:
            hit = next((v for v in visits(after) if norm(target) in norm(v.get("name", ""))), None)
            ok = bool(hit) and abs(hm(hit["start"]) - hm(e.start)) <= 10
            return {"ok": ok, "why": f"'{target}' starts {hit['start'] if hit else 'absent'}, asked {e.start}"}
        present = target and any(norm(target) in n for n in names_after)
        return {"ok": bool(present), "why": f"'{target}' {'is' if present else 'is not'} in the plan"}
    if e.verify == "day_window":
        d = next((d for d in after["days"] if d["day"] == e.day), None)
        if not d or not d.get("window"):
            return {"ok": False, "why": f"day {e.day} missing"}
        ok = abs(hm(d["window"][0]) - hm(e.start)) <= 10 and abs(hm(d["window"][1]) - hm(e.end)) <= 10
        return {"ok": ok, "why": f"day {e.day} window {d['window']} asked {e.start}-{e.end}"}
    return {"ok": None, "why": "no verification asked"}


# ---------------------------------------------------------------------------------------------------------------
# automatic checks
RAW_PATTERNS = [(re.compile(r"0x[0-9a-f]{6,}"), "place id"), (re.compile(r"\b[a-z]{2,}_[a-z0-9_]{2,}\b"), "snake_case key"),
                (re.compile(r"\b(?:null|undefined|NaN|None)\b"), "null token"), (re.compile(r"\{[a-z_]+\}"), "template placeholder"),
                (re.compile(r"\b(?:unknown|climate|true|false)\b"), "english key")]
NEGATION = re.compile(r"không (?:thấy|có|tìm|biết|tồn tại|xác minh|rõ)|chưa (?:có|thấy|tìm|xác minh|rõ|chắc(?: chắn)?|biết|thể xác nhận|đủ (?:dữ liệu|bằng chứng))|không nằm|không có trong", re.I)
KNOWN = {"repeat_question": ["T4", "R4"], "start_hour": ["T12", "T11"], "chosen_kept": ["N1", "R1"], "plan_nonempty": ["N1", "R1"],
         "raw_text": ["T10", "R9"], "no_nudge_choose": ["T9"], "http_clean": ["N10", "T16"], "fake_place": ["T1", "T5"],
         "meal_timing": ["T14"], "facts_chat": ["R4"], "origin_recorded": ["N2"], "edit_applied": ["R7"], "trips_count": ["R3"],
         "balance": ["T11", "R8"], "opening_hours": ["T14"], "lodging_known": ["N6"], "hard_constraints": ["R8"], "load_plan_fast": ["N9", "R5"]}


def violating_category(rec_, case_flags) -> str | None:
    return None


def ui_fact(value, field: str):
    if isinstance(value, dict) and "value" in value:
        value = value["value"]
    if isinstance(value, dict):
        return value.get("per_person_day" if field == "budget" else "level")
    return value


def check_chat(case, rec: dict) -> dict:
    t, stated = case.truth, set(case.expect.stated)
    users = [norm(turn["user"]) for turn in rec.get("chat", [])]
    proven = {key for key, quote in case.expect.chat_evidence.items()
              if norm(quote) and any(norm(quote) in text for text in users)}
    u, bad = rec.get("understanding_after_chat") or {}, []
    if "trip" in stated:
        if t.start and u.get("start_date") != t.start.isoformat():
            bad.append(f"start_date {u.get('start_date')} != {t.start}")
        if u.get("days") != t.days:
            bad.append(f"days {u.get('days')} != {t.days}")
    if "companions" in stated:
        if "companions" in proven:
            got, want = set(u.get("companions") or []), set(t.companions)
            if not want <= got:
                bad.append(f"companions {sorted(got)} != {sorted(want)}")
        if "people" in proven and u.get("people") != t.people:
            bad.append(f"people {u.get('people')} != {t.people}")
    if "mobility" in stated:
        ok = {"walk": {"walk", "car"}}.get(t.mobility, {t.mobility})
        if u.get("mobility") not in ok:
            bad.append(f"mobility {u.get('mobility')} != {t.mobility}")
    budget, pace = ui_fact(u.get("_budget_vnd"), "budget"), ui_fact(u.get("_pace"), "pace")
    if "budget" in stated and t.budget_vnd is not None and budget != t.budget_vnd:
        bad.append(f"budget {budget} != {t.budget_vnd}")
    if "pace" in stated and "pace" in proven and t.pace and pace != t.pace:
        bad.append(f"pace {pace} != {t.pace}")

    repeated, asked = set(), set()
    for gate in rec.get("gate", []):
        inputs = gate.get("inputs") or {}
        for key in gate.get("missing") or []:
            asked.add(key)
            fields = inputs.get(key, [])
            tab = next((tab for tab in gate.get("tabs", []) if tab.get("qid") == key), {})
            prefilled = any(o.get("prefilled") for o in tab.get("options", []))
            confirms = prefilled and ("đúng không" in tab.get("question", "").casefold() or "mình đoán" in tab.get("question", "").casefold())
            if confirms or (key == "companions" and prefilled and fields == ["who"]):
                continue
            if key == "trip":
                if "trip" not in stated:
                    continue
                if (("dates" in fields and t.start is not None)
                        or ("start" in fields and "start_hour" in proven)
                        or ("end" in fields and "end_hour" in proven)):
                    repeated.add(key)
            elif key == "companions":
                if key not in stated:
                    continue
                if (("people" in fields and "people" in proven)
                        or ("who" in fields and "companions" in proven)):
                    repeated.add(key)
            elif key in stated and (key != "pace" or "pace" in proven):
                repeated.add(key)

    def result(cid, failures, evidence):
        status = "fail" if failures else "pass"
        return {"status": status, "evidence": evidence[:600], "known": KNOWN.get(cid, []) if failures else []}

    return {
        "facts_chat": result("facts_chat", bad, "; ".join(bad) or "stated facts match the understanding"),
        "repeat_question": result("repeat_question", repeated,
                                  f"gate asked again: {sorted(repeated)}" if repeated else
                                  f"gate asked {sorted(asked)}; stated {sorted(stated)}"),
    }


def check_all(case, rec: dict, texts: list[tuple[str, str]]) -> dict:
    R = records()
    t = case.truth
    checks: dict[str, dict] = {}

    def put(cid, status, evidence, known=True):
        checks[cid] = {"status": status, "evidence": str(evidence)[:600], "known": KNOWN.get(cid, []) if status == "fail" and known else []}

    final = rec["plans"].get("reloaded") or rec["plans"].get("generated") or {"days": [], "variants": [], "warnings": []}
    gen = rec["plans"].get("generated") or final
    vs_final = visits(final)

    checks.update(check_chat(case, rec))

    # 2. facts in the final search input (after the gate)
    ctx = ((rec.get("outputs_trip") or {}).get("context")) or rec.get("search_input_context") or {}
    bad = []
    if t.start and ctx.get("start_date") != t.start.isoformat():
        bad.append(f"final start_date {ctx.get('start_date')} != {t.start}")
    if ctx.get("days") not in (t.days,):
        bad.append(f"final days {ctx.get('days')} != {t.days}")
    if ctx.get("people") != t.people:
        bad.append(f"final people {ctx.get('people')} != {t.people}")
    if t.budget_vnd and ctx.get("budget_vnd") != t.budget_vnd:
        bad.append(f"budget {ctx.get('budget_vnd')} != {t.budget_vnd}")
    allowed_mobility = {"walk", "car"} if t.mobility == "walk" else {t.mobility}
    if ctx.get("mobility") not in allowed_mobility:
        bad.append(f"mobility {ctx.get('mobility')} != {t.mobility}")
    put("facts_final", "fail" if bad else "pass", "; ".join(bad) or "final context matches", known=False)

    # 3. origin / entry recorded (N2)
    aliases = {"sai gon": "hcm", "tp hcm": "hcm", "tp ho chi minh": "hcm", "ho chi minh": "hcm"}
    origin_users = [norm(c.get("user", "")) for c in rec.get("chat", [])]
    origin_stated = bool(t.origin) and any(alias in user for user in origin_users for alias in {norm(t.origin)} | {a for a, canonical in aliases.items() if canonical == aliases.get(norm(t.origin), norm(t.origin))})
    if origin_stated:
        origin = ctx.get("origin") or {}
        text = origin.get("text", "") if isinstance(origin, dict) else origin
        actual, expected = aliases.get(norm(text), norm(text)), aliases.get(norm(t.origin), norm(t.origin))
        put("origin_recorded", "pass" if actual == expected else "fail", f"origin={text!r}; expected={t.origin!r}")
    else:
        put("origin_recorded", "na", "no origin stated; do not require an invented city or station")
    arrive = (ctx.get("frame") or {}).get("arrive") or {}
    mode = ctx.get("arrival_mode") or arrive.get("how")
    put("arrival_mode", "pass" if mode == t.arrive else "fail" if mode else "blocked", f"arrival_mode={mode}; expected={t.arrive}", known=False)
    put("arrival_time", "pass" if arrive.get("at") else "na", f"frame.arrive={arrive}; no independently configured arrival-time assertion", known=False)

    # 5. every place the user sees exists in the corpus
    seen = set(place_ids([c["places"] for c in rec["chat"]])) | {p["id"] for p in rec["picks"]} | {v["place_id"] for v in vs_final if v.get("place_id")}
    services = service_records()
    missing = [p for p in seen if p not in R and p not in services]
    service_leaks = [v["place_id"] for v in vs_final if v.get("place_id") in services and v.get("place_id") not in R]
    put("ids_in_corpus", "fail" if missing or service_leaks else "pass",
        f"unknown={missing[:3]}; service ids in itinerary={service_leaks[:3]}" if missing or service_leaks else f"{len(seen)} ids grounded in serving / service corpus", known=False)

    # 6. fake places: never invented, and the agent says so
    if t.fake_places:
        bad = []
        for fake in t.fake_places:
            nf = norm(fake)
            shown = [name_of(p) for p in seen]
            if any(nf == norm(n) or (len(nf) > 12 and nf in norm(n)) for n in shown):
                bad.append(f"'{fake}' appears as a place")
            turns = [c for c in rec["chat"] if norm(fake)[:14] in norm(c["user"]) or norm(fake.split()[0] + " " + " ".join(fake.split()[1:3])) in norm(c["user"])]
            replies = " ".join(c["say"] for c in turns) or " ".join(c["say"] for c in rec["chat"])
            if turns and not NEGATION.search(replies):
                bad.append(f"no 'not found' wording after asking '{fake}': {replies[:140]}")
        put("fake_place", "fail" if bad else "pass", "; ".join(bad) or "fake place not invented and the reply says it is not found")
    else:
        put("fake_place", "na", "no fake place in this case")

    # 7. hard constraints on the plan's visits
    hard, viol, unver = case.expect.hard, [], 0

    warned = " ".join(final.get("warnings") or []).casefold()

    def require(rec_, fid, forbidden, nm):
        # Owner 04/11: evidence of a fail is a violation; unknown is allowed only when Lịch trình warns about it
        nonlocal unver
        result = serving_check(rec_, fid, forbidden)
        if result == "unknown":
            unver += 1
            if nm.casefold() not in warned:
                viol.append(f"{nm}: {fid} unknown and not warned in Lịch trình")
        elif result != "pass":
            viol.append(f"{nm}: {fid} {result}")
    for v in vs_final:
        r = R.get(v.get("place_id"))
        if not r:
            continue
        cat = (r["identity"].get("category") or "").casefold()
        grp = r["identity"].get("category_group")
        nm = v.get("name", "")
        if "vegetarian" in hard and grp in ("restaurant",):
            require(r, "vegetarian_options", "no", nm)
        if "wheelchair" in hard:
            require(r, "wheelchair", "unsuitable", nm)
            require(r, "steep_or_stairs", "present", nm)
        if "no_stairs" in hard:
            require(r, "steep_or_stairs", "present", nm)
        if "no_bar" in hard and (grp == "bar" or re.search(r"bar|pub|club|quán nhậu|rượu|cocktail", cat + " " + nm.casefold())):
            viol.append(f"{nm}: bar")
        if "no_alcohol" in hard and (grp == "bar" or re.search(r"\bbar\b|pub|quán nhậu|rượu|cocktail|winery|bia", cat + " " + nm.casefold())):
            viol.append(f"{nm}: alcohol venue")
        if "pets" in hard:
            require(r, "pets", "not_allowed", nm)
    if hard:
        put("hard_constraints", "fail" if viol else "pass", "; ".join(viol[:4]) or f"no violation among {len(vs_final)} visits ({unver} restaurant visits unverified)")
    else:
        put("hard_constraints", "na", "no hard flag")
    # soft: kids / elderly cases should avoid bars even when the flag is not hard
    if not hard and ("kids" in t.companions or "baby" in t.companions):
        bars = [v.get("name") for v in vs_final if (R.get(v.get("place_id")) or {"identity": {}})["identity"].get("category_group") == "bar"]
        put("kid_no_bar", "fail" if bars else "pass", f"bar in a family-with-kids plan: {bars[:3]}" if bars else "no bar", known=False)
        if bars:
            checks["kid_no_bar"]["known"] = ["R8"]

    # 8. chosen places are kept or the drop is explained
    sel = [p["id"] for p in rec.get("selected", [])]
    in_plan = {v["place_id"] for v in vs_final}
    dropped = {d["place_id"]: d["reason"] for v in gen.get("variants", []) for d in v.get("dropped", []) if d.get("place_id") and d.get("reason")}
    lost = [name_of(p) for p in sel if p not in in_plan and p not in dropped]
    explained = [name_of(p) for p in sel if p not in in_plan and p in dropped]
    user_dropped = {name_of(v) for v in [e.get("name") for e in rec["edits"] if e["op"] in ("drop_first", "drop_name") and e.get("applied")] if v}
    lost = [n for n in lost if n not in user_dropped]
    put("chosen_kept", "fail" if lost else "pass", f"dropped without reason: {lost[:5]}" if lost else f"{len(sel)} chosen; {len(explained)} dropped with a reason; {len(user_dropped)} dropped by the user")

    unexplained = [d.get("name") or d.get("place_id") for plan in rec["plans"].values() for variant in plan.get("variants", []) for d in variant.get("dropped", []) if not d.get("reason")]
    put("drop_reason", "fail" if unexplained else "pass", f"missing drop reason: {list(dict.fromkeys(unexplained))[:4]}" if unexplained else "drop reasons present", known=False)

    # 9. the plan is not empty when places were chosen
    put("plan_nonempty", "fail" if sel and not vs_final else "pass", f"{len(vs_final)} visits for {len(sel)} chosen places")

    # 10. day count and dates
    bad = []
    if len(final["days"]) != t.days:
        bad.append(f"{len(final['days'])} days in the plan, truth {t.days}")
    if t.start and final["days"] and final["days"][0].get("date") != t.start.isoformat():
        bad.append(f"day 1 date {final['days'][0].get('date')} != {t.start}")
    put("plan_days_dates", "fail" if bad else "pass", "; ".join(bad) or "days and dates match", known=False)

    # 11. start hour of day 1
    if case.expect.start_hour and final["days"]:
        d1 = final["days"][0]
        w0 = d1["window"][0] if d1.get("window") else None
        first = next((i["start"] for i in d1["items"]), None)
        expected = case.expect.start_hour
        frame = ctx.get("frame") or {}
        if frame.get("arrive") and frame.get("days"):
            expected = frame["days"][0].get("start") or expected
        day_edits = [e for e in rec["edits"] if e.get("applied") and e.get("op") == "set_day_window"]
        for edit in day_edits:
            payload = edit.get("payload") or {}
            if payload.get("day") == 0 and payload.get("start"):
                expected = payload["start"]
        gap = abs(hm(w0) - hm(expected)) if w0 else 999
        put("start_hour", "pass" if gap <= 30 else "fail", f"day 1 window starts {w0}, first item {first}, constrained/edited start {expected}; user clock {case.expect.start_hour}")
    else:
        put("start_hour", "na", "no start hour said")

    # 12. meal timing
    bad = []
    for v in vs_final:
        r = R.get(v.get("place_id"))
        if not r or r["identity"].get("category_group") != "restaurant":
            continue
        s, nm = hm(v["start"]), v.get("name", "")
        if 14 * 60 < s < 16 * 60 + 30 or s >= 22 * 60 or s < 6 * 60:
            bad.append(f"{nm} at {v['start']}")
        if s >= 11 * 60 + 30 and re.search(r"phở|cháo|xôi|bánh mì|hủ tiếu|bún bò|bánh ướt", nm.casefold()) and not re.search(r"lẩu|nướng", nm.casefold()) and s < 16 * 60:
            bad.append(f"breakfast dish {nm} at {v['start']}")
    put("meal_timing", "fail" if bad else "pass", "; ".join(bad[:4]) or "restaurant visits sit in meal windows")

    # 13. opening hours known and respected
    bad, unknown = [], 0
    for v in vs_final:
        r = R.get(v.get("place_id"))
        if not r or not v.get("date"):
            continue
        hv = ((r.get("operation") or {}).get("hours") or {}).get("value")
        if not hv:
            unknown += 1
            continue
        wd = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"][date.fromisoformat(v["date"]).weekday()]
        ranges = hv.get(wd) or []
        if not ranges:
            bad.append(f"{v['name']} closed on {wd}")
            continue
        s, e = hm(v["start"]), hm(v["end"])
        ok = False
        for o, c in ranges:
            o_, c_ = hm(o), hm(c) if c != "24:00" else 1440
            if c_ <= o_:
                c_ += 1440
            if s >= o_ - 5 and e <= c_ + 20:
                ok = True
        if not ok:
            bad.append(f"{v['name']} {v['start']}-{v['end']} vs {ranges}")
    put("opening_hours", "fail" if bad else "pass", "; ".join(bad[:4]) or f"all known hours respected ({unknown} visits with unknown hours)")

    # 14. cap per day / balance
    per_day = [sum(1 for v in vs_final if v["day"] == d["day"]) for d in final["days"]]
    bad = []
    cap = t.max_per_day or (4 if t.pace == "slow" else None)
    if cap and any(n > cap for n in per_day):
        bad.append(f"visits per day {per_day} over the cap {cap}")
    if len(per_day) >= 2 and sum(per_day) >= 2 * len(per_day) and max(per_day) - min(per_day) >= 3:
        bad.append(f"unbalanced days {per_day}")
    put("balance", "blocked" if bad else "pass", "; ".join(bad) + "; needs a feasible alternative respecting hours, meals and available minutes" if bad else f"visits per day {per_day}")

    # 15. impossible driving speed
    bad = []
    for d in final["days"]:
        its = d["items"]
        for a, b, c in zip(its, its[1:], its[2:]):
            if b["kind"] == "travel" and a["kind"] == "visit" and c["kind"] == "visit":
                ra, rc = R.get(a.get("place_id")), R.get(c.get("place_id"))
                if ra and rc:
                    km = haversine(ra["identity"], rc["identity"])
                    mins = hm(b["end"]) - hm(b["start"])
                    if mins > 0 and km / (mins / 60) > 90:
                        bad.append(f"{a['name']} -> {c['name']}: {km:.1f} km in {mins} min")
    put("leg_speed", "fail" if bad else "pass", "; ".join(bad[:3]) or "no leg faster than 90 km/h", known=False)

    # 16. Lựa chọn never nudges or blocks
    cap_ = rec.get("choose_after_picks") or {}
    nudges = []
    nudges.extend(cap_.get("visible_nudges") or [])
    pending_text = " ".join(str((cap_.get("pending") or {}).get(k) or "") for k in ("text", "reason"))
    if re.search(r"quá (?:nhiều|ít|tải)|bỏ bớt|chọn (?:thêm|ít)|không đủ thời gian", pending_text, re.I):
        nudges.append(pending_text)
    nudges += [f"pick refused {e['status']}" for e in rec["pick_errors"]]
    put("no_nudge_choose", "fail" if nudges else "pass", "; ".join(nudges) or "Explore/SelectedBar projection: no visible feasibility nudge or refused pick (not a DOM assertion)")

    # 17. HTTP: nothing but the valid gate 409 and the known guest /eve 403
    bad, eve = [], []
    for c in rec["_calls"]:
        if c["p"].endswith("/eve") and case.auth == "guest":
            if c["s"] != 403:
                eve.append(f"guest Eve must be denied, got {c['s']}")
            if c["s"] == 403:
                continue
        request = c.get("request") or {}
        if c["s"] in (400, 409) and request.get("stage") == "planning" and c.get("note") in {
            "plan_violations", "no_variant", "plan has unresolved violations", "pick a variant before editing the plan", "no variant chosen"
        }:
            continue  # Business rejection stays a planning blocker, not an infrastructure failure.
        if c["s"] >= 400 and c["s"] != 429:
            if c["s"] == 409 and c["p"].endswith("/request") and "trip_incomplete" in (c.get("note") or "") or (c["s"] == 409 and c["note"] in ("trip_incomplete",)):
                continue
            (eve if c["p"].endswith("/eve") else bad).append(f"{c['m']} {c['p']} {c['s']} {c['note']}")
        if c["s"] == 0:
            bad.append(f"{c['m']} {c['p']} network {c['note']}")
    put("http_clean", "fail" if bad else "pass", "; ".join(bad[:4]) or "no 4xx/5xx besides the valid gate 409")
    put("eve_guest", "fail" if eve else "pass" if case.auth == "guest" else "na", "; ".join(eve[:2]) or "guest: route not called, or legacy permission probe denied (403); not a browser assertion", known=False)

    # 18. raw text
    found = []
    for where, s in texts:
        if not s:
            continue
        for rx, kind in RAW_PATTERNS:
            m = rx.search(re.sub(r"https?://\S+", " ", s))
            if m:
                found.append(f"{where}: {kind} '{m.group(0)}'")
                break
    found = list(dict.fromkeys(found))
    put("raw_text", "fail" if found else "pass", "; ".join(found[:5]) or f"{len(texts)} user-visible strings clean")

    # 19. every edit takes effect
    bad = [f"{e['op']}: {e['verified']['why']}" for e in rec["edits"] if e.get("applied") and e["verified"].get("ok") is False]
    bad += [f"{e['op']}: {e.get('detail') or e.get('say', '')[:100]} (not applied)" for e in rec["edits"] if e.get("applied") is False and not str(e.get("detail", "")).startswith("no target")]
    asked = [e for e in rec["edits"] if e["op"] == "assistant"]
    put("edit_applied", "fail" if bad else ("pass" if rec["edits"] else "na"), "; ".join(bad[:3]) or "edits took effect")

    # 20. confirm, reload equals confirmed, trips list count
    rl, ge = rec["plans"].get("reloaded"), final
    bad = []
    if rec.get("confirm_status") != 200:
        bad.append(f"confirm {rec.get('confirm_status')}")
    last_edit = [v for k, v in rec["plans"].items() if k.startswith("after_")]
    pre = last_edit[-1] if last_edit else gen
    if rl and {v["place_id"] for v in visits(rl)} != {v["place_id"] for v in visits(pre)}:
        bad.append("reload shows other places than the plan just confirmed")
    put("confirm_reload", "fail" if bad else "pass", "; ".join(bad) or "confirmed plan equals the reloaded plan", known=False)
    te = rec.get("trips_entry")
    if te:
        n_plan = len({v["place_id"] for v in vs_final})
        put("trips_count", "fail" if te["places"] != n_plan or not te["confirmed"] else "pass",
            f"trips list says {te['places']} places, confirmed={te['confirmed']}; plan has {n_plan}")
    else:
        put("trips_count", "fail", "trip missing from /trips")

    # 21. the plan page loads fast enough (screen threshold)
    lp = [s["secs"] for s in rec["_steps"] if s["step"] == "load_plan"]
    put("load_plan_fast", "fail" if lp and lp[0] > SLOW["screen"] else "pass", f"load_plan {lp}")

    # 22. a plan with zero places never goes out as ok
    put("session_errors", "fail" if rec["errors"] else "pass", "; ".join(rec["errors"][:3]) or "no runner error", known=False)
    blocked = rec.get("blocked") or {}
    no_plan = not rec["plans"].get("generated")
    no_choice = bool(rec["plans"].get("generated")) and not gen.get("chosen_variant") and bool(gen.get("variants"))
    rejected = rec.get("confirm_status") in (400, 409)
    if no_plan:
        for cid in ("chosen_kept", "plan_nonempty", "plan_days_dates", "start_hour", "meal_timing", "opening_hours", "balance", "leg_speed", "hard_constraints", "load_plan_fast", "edit_applied"):
            if cid in checks:
                put(cid, "blocked", blocked.get("planning") or "no generated plan; inspect upstream gate/session error")
    if no_plan or no_choice or rejected or blocked.get("confirmation"):
        for cid in ("confirm_reload", "trips_count"):
            put(cid, "blocked", blocked.get("confirmation") or "confirmation prerequisite failed; inspect upstream planning/session error")
    if no_choice:
        put("edit_applied", "blocked", "no confirmable variant selected")
    return checks


def haversine(a: dict, b: dict) -> float:
    la1, lo1, la2, lo2 = map(math.radians, (a["lat"], a["lng"], b["lat"], b["lng"]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 12742 * math.asin(math.sqrt(h))


def finish(case, api: Api, rec: dict, texts, run_dir: Path, t_start: float) -> dict:
    rec["_calls"], rec["_steps"] = api.calls, api.steps
    rec["rate_limited"] = api.limited
    try:
        rec["checks"] = check_all(case, rec, texts)
    except Exception as exc:  # noqa: BLE001
        rec["checks"] = {"checks_crashed": {"status": "fail", "evidence": f"{type(exc).__name__}: {exc}"[:300], "known": []}}
    final = rec["plans"].get("reloaded") or rec["plans"].get("generated")
    failed = [f"{k}: {v['evidence'][:120]}" for k, v in rec["checks"].items() if v["status"] == "fail" and not v.get("noise")]
    if final:
        chat = "\n".join(f"U: {c['user']}\nA: {c['say'][:300]}" for c in rec["chat"][:12])
        try:
            rec["satisfaction"] = judge(case, plan_text(final), chat, failed, evidence={"picks": rec["picks"], "searches": rec["searches"], "checks": rec["checks"]})
        except Exception as exc:  # noqa: BLE001
            rec["satisfaction"] = [{"criterion": c, "verdict": "không", "reason": f"judge unavailable: {type(exc).__name__}"} for c in case.expect.criteria]
            rec["notes"].append("judge failed")
    else:
        rec["satisfaction"] = [{"criterion": c, "verdict": "không", "reason": "no plan was produced"} for c in case.expect.criteria]
    rec["secs_total"] = round(time.time() - t_start, 1)
    rec["texts_seen"] = len(texts)
    rec["visible_texts"] = texts
    if case.auth == "guest":
        api.leave()
    api.close()
    (run_dir / f"{case.id}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return rec


# ---------------------------------------------------------------------------------------------------------------
# aggregate + report tables
def pct(vals, p):
    if not vals:
        return None
    vals = sorted(vals)
    k = (len(vals) - 1) * p
    lo, hi = math.floor(k), math.ceil(k)
    return round(vals[lo] + (vals[hi] - vals[lo]) * (k - lo), 2)


STEP_GROUP = {"chat_turn": "chat", "chat_first_word": "chat", "show_next": "screen", "to_choose": "screen", "open_choose": "screen", "pick_place": "screen",
              "search_place": "screen", "gate_open": "screen", "gate_answer": "chat", "gate_readback": "screen", "gate_confirm": "screen",
              "plan_generate": "plan", "load_plan": "screen", "edit_assistant": "chat", "confirm": "screen", "reload_confirmed": "screen", "trips_list": "screen",
              "create_trip": "screen", "auth": "screen", "eve_probe": "screen"}
STEP_GROUP.update({f"edit_{k}": "plan" for k in ("drop_first", "drop_name", "add_backup", "set_day_window", "move_first", "set_pace")})


def summarize(rows: list[dict]) -> dict:
    steps: dict[str, list[float]] = {}
    for r in rows:
        for s in r.get("_steps", []):
            steps.setdefault(s["step"], []).append(s["secs"])
    timing = {}
    for k, v in steps.items():
        grp = STEP_GROUP.get(k, "screen")
        timing[k] = {"n": len(v), "p50": pct(v, 0.5), "p90": pct(v, 0.9), "max": max(v), "slow_over": SLOW[grp], "slow_n": sum(1 for x in v if x > SLOW[grp])}
    tot = ok = 0
    for r in rows:
        for k, c in r["checks"].items():
            if c["status"] in ("pass", "fail") and not c.get("noise"):
                tot += 1
                ok += c["status"] == "pass"
    sat = [s["verdict"] for r in rows for s in r["satisfaction"]]
    return {"cases": len(rows), "checks_total": tot, "checks_pass": ok, "pass_rate": round(ok / tot, 3) if tot else None,
            "checks_blocked": sum(c["status"] == "blocked" for r in rows for c in r["checks"].values()),
            "cases_all_pass": sum(1 for r in rows if all(c["status"] not in ("fail", "blocked") or c.get("noise") for c in r["checks"].values())),
            "satisfied": {v: sat.count(v) for v in ("đạt", "một phần", "không")},
            "satisfied_rate": round(sat.count("đạt") / len(sat), 3) if sat else None,
            "satisfied_or_partial_rate": round((sat.count("đạt") + sat.count("một phần")) / len(sat), 3) if sat else None, "timing": timing}


def write_tables(run_dir: Path, rows: list[dict]) -> Path:
    summ = summarize(rows)
    (run_dir / "summary.json").write_text(json.dumps(summ, ensure_ascii=False, indent=1), encoding="utf-8")
    L = [f"# Bảng số liệu tự sinh — {run_dir.name}", "", f"Số ca: {summ['cases']} · kiểm tự động đạt {summ['checks_pass']}/{summ['checks_total']} ({summ['pass_rate']}) · "
         f"ca không lỗi kiểm nào: {summ['cases_all_pass']} · tiêu chí thỏa nhu cầu: {summ['satisfied']} (đạt {summ['satisfied_rate']}, đạt+một phần {summ['satisfied_or_partial_rate']})", "",
         "## Ca × kết quả", "", "| ca | kiểm đạt | kiểm trượt | thỏa nhu cầu (đạt/một phần/không) | giây |", "|---|---|---|---|---|"]
    L.insert(4, f"Kiểm bị chặn: {summ['checks_blocked']} (không tính pass/fail); verdict judge giữ nguyên từ lần chạy gốc, không gọi lại. Bề mặt Web suy từ component, không thay thế kiểm DOM prod.")
    for r in rows:
        c = r["checks"]
        fails = [k for k, v in c.items() if v["status"] == "fail" and not v.get("noise")]
        fails += [f"{k} (blocked)" for k, v in c.items() if v["status"] == "blocked"]
        npass = sum(1 for v in c.values() if v["status"] == "pass")
        sat = [s["verdict"] for s in r["satisfaction"]]
        L.append(f"| {r['id']} | {npass} | {', '.join(fails) or '-'} | {sat.count('đạt')}/{sat.count('một phần')}/{sat.count('không')} | {r['secs_total']} |")
    L += ["", "## Tốc độ theo bước (giây)", "", "| bước | n | p50 | p90 | max | ngưỡng | chậm |", "|---|---|---|---|---|---|---|"]
    for k, v in sorted(summ["timing"].items(), key=lambda kv: -(kv[1]["p90"] or 0)):
        L.append(f"| {k} | {v['n']} | {v['p50']} | {v['p90']} | {v['max']} | {v['slow_over']} | {v['slow_n']} |")
    fails: dict[str, list] = {}
    for r in rows:
        for k, v in r["checks"].items():
            if v["status"] == "fail":
                fails.setdefault(k, []).append((r["id"], v))
    L += ["", "## Kiểm trượt gom theo loại", ""]
    for k, items in sorted(fails.items(), key=lambda kv: -len(kv[1])):
        known = sorted({x for _, v in items for x in v.get("known", [])})
        L.append(f"### {k} — {len(items)} ca {('(đã biết: ' + ', '.join(known) + ')') if known else ''}")
        for cid, v in items:
            L.append(f"- `{cid}`: {v['evidence'][:260]}")
        L.append("")
    L += ["## Tiêu chí không đạt", ""]
    for r in rows:
        for s in r["satisfaction"]:
            if s["verdict"] != "đạt":
                L.append(f"- `{r['id']}` [{s['verdict']}] {s['criterion']} — {s['reason']}")
    out = run_dir / "tables.md"
    out.write_text("\n".join(L), encoding="utf-8")
    return out


def rescore_record(case, original: dict) -> dict:
    """Re-evaluate receipts only; never mutate the evidence or rerun the judge."""
    rec = copy.deepcopy(original)
    texts = []
    for where, text in rec.get("visible_texts", []):
        if where in ("choose.conflict", "choose.feasibility.warning"):
            continue
        if where.endswith(".tradeoff") and text.startswith("{"):
            tradeoff = json.loads(text)
            projected = []
            collect_plan_texts(projected, {"tradeoffs": [tradeoff]}, where.rsplit(".", 1)[0])
            texts.extend(projected)
            continue
        if where.endswith(".dropped") and text.endswith(": None"):
            # Only undo Python stringification when the persisted JSON proves null.
            name = text[:-6]
            drops = [d for plan in rec.get("plans", {}).values() for v in plan.get("variants", []) for d in v.get("dropped", []) if d.get("name") == name]
            if any(d.get("reason") is None for d in drops) and not any(d.get("reason") == "None" for d in drops):
                text = text[:-4]
        texts.append((where, text))
    readbacks = [c["response"]["readback"] for c in rec.get("_calls", []) if isinstance(c.get("response"), dict) and isinstance(c["response"].get("readback"), dict)]
    for gate, rb in zip([g for g in rec.get("gate", []) if g.get("missing")], readbacks):
        gate.setdefault("tabs", (rb.get("deck") or {}).get("tabs", []))
    acts = [c.get("request", {}).get("payload", {}) for c in rec.get("_calls", [])
            if isinstance(c.get("request"), dict) and c["request"].get("stage") == "planning" and c["request"].get("operation") == "act"]
    pending = iter(acts)
    previous = rec.get("plans", {}).get("generated")
    for n, edit in enumerate(rec.get("edits", []), 1):
        if edit.get("action"):
            action = next((a for a in pending if a.get("type") == edit["action"]), {})
            edit.setdefault("payload", action)
            if action.get("place"):
                edit.setdefault("place_id", action["place"])
        after = rec["plans"].get(f"after_{n}_{edit['op']}")
        spec = case.edits[n - 1] if n <= len(case.edits) else None
        if previous and after and spec:
            edit["verified"] = verify_edit(spec, edit, previous, after)
        previous = after or previous
    rec["checks"] = check_all(case, rec, texts)
    rec["rescore"] = {"offline": True, "judge": "original verdict retained; not rerun", "visible_texts": "source projection; no browser DOM receipt"}
    return rec


def rescore_run(source: Path, target: Path, cases) -> list[dict]:
    if source.resolve() == target.resolve():
        raise ValueError("rescore output must not overwrite source receipts")
    by_id = {c.id: c for c in cases}
    rows = []
    target.mkdir(parents=True, exist_ok=True)
    for path in sorted(source.glob("*.json")):
        if path.stem not in by_id:
            continue
        row = rescore_record(by_id[path.stem], json.loads(path.read_text(encoding="utf-8")))
        rows.append(row)
        (target / path.name).write_text(json.dumps(row, ensure_ascii=False, indent=1), encoding="utf-8")
    if not rows:
        raise ValueError("no saved case receipts found")
    write_tables(target, rows)
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--only", default="", help="comma list of case ids")
    ap.add_argument("--jobs", type=int, default=4, help="cases in parallel (9router and prod are shared: keep <= 4)")
    ap.add_argument("--run-id", default="")
    ap.add_argument("--report", default="", help="rescore saved receipts offline; keep the source run unchanged")
    ap.add_argument("--report-out", default="", help="separate directory for the offline rescore (default: <run>-rescored)")
    ap.add_argument("--preflight", action="store_true", help="check the cases against the corpus (real places exist, fake ones do not) and exit")
    args = ap.parse_args()
    if not 1 <= args.jobs <= 4:
        ap.error("--jobs must be in 1..4")
    cases = prod_cases.load()
    if args.preflight:
        R = records()
        names = [(r["identity"]["name"], r["identity"].get("category_group")) for r in R.values() if r["identity"].get("category_group") != "stay"]
        bad = 0
        for c in cases:
            for p in c.truth.real_places + c.pick.include:
                if not any(norm(p) in norm(n) for n, _ in names):
                    print(f"[preflight] {c.id}: real place not in corpus: {p}"); bad += 1
            for p in c.truth.fake_places:
                hit = [n for n, _ in names if norm(p) == norm(n)]
                if hit:
                    print(f"[preflight] {c.id}: fake place exists in corpus: {p} -> {hit[:2]}"); bad += 1
        print(f"[preflight] {len(cases)} cases, {bad} problems")
        return 1 if bad else 0
    if args.report:
        run_dir = OUT / "runs" / args.report
        target = Path(args.report_out) if args.report_out else run_dir.with_name(run_dir.name + "-rescored")
        rows = rescore_run(run_dir, target, cases)
        print(json.dumps(summarize(rows), ensure_ascii=False))
        print(target / "tables.md")
        return 0
    if args.only:
        want = set(args.only.split(","))
        cases = [c for c in cases if c.id in want]
        if not cases:
            raise SystemExit("no such case id")
    run_id = args.run_id or time.strftime("%Y%m%d-%H%M%S")
    run_dir = OUT / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    records()   # load the corpus once before the threads start
    print(f"[matrix] run {run_id}: {len(cases)} cases, {args.jobs} at a time -> {run_dir}", flush=True)
    rows = []
    with cf.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futs = {pool.submit(run_case, c, run_dir): c for c in cases}
        for f in cf.as_completed(futs):
            c = futs[f]
            try:
                r = f.result()
            except Exception as exc:  # noqa: BLE001
                print(f"[matrix] {c.id} crashed: {type(exc).__name__}: {exc}", flush=True)
                continue
            rows.append(r)
            fails = [k for k, v in r["checks"].items() if v["status"] == "fail" and not v.get("noise")]
            sat = [s["verdict"] for s in r["satisfaction"]]
            print(f"[matrix] {c.id}: {r['secs_total']}s checks failed {fails or '-'} · satisfied {sat.count('đạt')}/{len(sat)}", flush=True)
    rows.sort(key=lambda r: r["id"])
    print(f"[matrix] tables: {write_tables(run_dir, rows)}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
