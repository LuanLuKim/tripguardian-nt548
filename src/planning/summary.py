"""Title and short summary of the active itinerary: the heading of the Lịch trình overview.

The facts come from the itinerary itself (stop names, areas, start times). The Agent role words them; the answer is
checked at this boundary and any failure falls back to a plain summary built from the same facts, so the page always
has a heading and the model never adds a place the plan does not hold."""

import asyncio
import hashlib
import json
import logging

from corpus.llm import AGENT, PLANNING_SUMMARY

log = logging.getLogger(__name__)

TIMEOUT_S = 25
TITLE_MAX = 90
TEXT_MAX = 420


def facts(days: list[dict], areas: dict[str, str | None]) -> list[dict]:
    """[{"day", "stops": [{"name", "area", "start"}]}] from the rendered itinerary days; a day with no visit is dropped."""
    out = []
    for d in days:
        stops = [{"name": it["name"], "area": areas.get(it.get("place_id")), "start": it.get("start")}
                 for it in d["items"] if it["kind"] == "visit" and it.get("name")]
        if stops:
            out.append({"day": d["day"], "stops": stops})
    return out


def fingerprint(plan: list[dict]) -> str:
    return hashlib.sha1(json.dumps(plan, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:16]


def plain(plan: list[dict], days: int) -> dict:
    """The summary without a model: each day's areas and stops, as they stand."""
    parts = []
    for d in plan:
        areas = list(dict.fromkeys(s["area"] for s in d["stops"] if s["area"]))
        where = f" quanh {', '.join(areas[:2])}" if areas else ""
        parts.append(f"Ngày {d['day']}{where}: {', '.join(s['name'] for s in d['stops'][:4])}"
                     + (f" và {len(d['stops']) - 4} nơi nữa" if len(d["stops"]) > 4 else ""))
    return {"title": f"Đà Lạt {days} ngày", "text": ". ".join(parts) + "." if parts else "", "source": "plain"}


async def _ask(plan: list[dict]) -> dict:
    client, model = AGENT.client()
    try:
        return await PLANNING_SUMMARY.ask(client, model, attempts=2, plan=json.dumps(plan, ensure_ascii=False))
    finally:
        await client.close()


def checked(answer: dict) -> dict | None:
    """The model's title and text when they are usable: non-empty, one line of title, bounded lengths."""
    title, text = (answer.get("title") or "").strip().strip('"“”'), " ".join((answer.get("text") or "").split())
    if not title or not text or "\n" in title or len(title) > TITLE_MAX or len(text) > TEXT_MAX:
        return None
    return {"title": title, "text": text, "source": "agent"}


def summarize(plan: list[dict], days: int) -> dict:
    """{"title", "text", "source": "agent" | "plain"}; never raises."""
    if not plan:
        return plain(plan, days)
    try:
        used = checked(asyncio.run(asyncio.wait_for(_ask(plan), TIMEOUT_S)))
    except Exception as exc:  # an unset key, a slow or busy model, a malformed answer: the plain summary stands in
        log.warning("planning summary fell back: %s", exc)
        used = None
    return used or plain(plan, days)
