import asyncio
import json
from contextlib import asynccontextmanager

import pytest

from corpus.crawl.gmaps import resolve

AREA = [11.8, 108.3, 12.1, 108.6]  # dalat area as in config/cities.yaml (shape only)


def card(fid, name, reviews=120, rating=4.5, lat=11.94, lng=108.44, category="Quán cà phê"):
    return {"fid": fid, "name": name, "url": f"https://maps/{fid}", "category": category, "rating": rating,
            "reviews": reviews, "lat": lat, "lng": lng, "price_vnd": None, "amenities": []}


def write(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


@pytest.fixture
def data(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture
def world(data, monkeypatch):
    nav = data / "dalat" / "navigate"
    write(nav / "resolve_queue.jsonl", [
        {"name": "Married Beans", "area_hint": "P1", "aspect": "cafe", "city": "dalat"},
        {"name": "Quán Không Thấy", "area_hint": "", "aspect": "cafe", "city": "dalat"},
        {"name": "Hai Chi Nhánh", "area_hint": "", "aspect": "cafe", "city": "dalat"},
        {"name": "Quán Ít Review", "area_hint": "", "aspect": "cafe", "city": "dalat"},
        {"name": "Quán Đã Có", "area_hint": "", "aspect": "cafe", "city": "dalat"}])
    write(data / "gmaps" / "list" / "dalat.json", [])  # replaced below with the real shape
    (data / "gmaps" / "list" / "dalat.json").write_text(json.dumps({"items": [{"fid": "held1", "name": "Quán Đã Có"}]}))
    monkeypatch.setattr(resolve, "load_config", lambda city: ("Đà Lạt", {"area": AREA, "gmaps": {
        "min_reviews": 30, "same_name_m": 1000, "pause_s": [0, 0], "cooldown_s": 0, "max_cooldown_s": 0, "grid": {"start_zoom": 13}}, "stay": {"min_reviews": 30}}))
    return data


ANSWERS = {
    "Married Beans Đà Lạt": [card("f1", "Married Beans Coffee"), card("x", "Quán Gió")],
    "Quán Không Thấy Đà Lạt": [card("x", "Quán Gió")],
    "Hai Chi Nhánh Đà Lạt": [card("b1", "Hai Chi Nhánh"), card("b2", "Hai Chi Nhánh", lat=11.99)],
    "Quán Ít Review Đà Lạt": [card("l1", "Quán Ít Review", reviews=7)],
    "Quán Đã Có Đà Lạt": [card("held1", "Quán Đã Có")],
}


def fake_sessions(headed=False):
    @asynccontextmanager
    async def cm(headed=False):
        async def new_session():
            class Ctx:
                async def close(self): ...
            return Ctx()
        yield new_session
    return cm(headed)


def run(city="dalat", limit=None, answers=ANSWERS, calls=None):
    async def searcher(ctx, query, n, at):
        if calls is not None:
            calls.append((query, n, at))
        return answers[query], True, False
    return asyncio.run(resolve.run(city, False, limit=limit, sessions=fake_sessions, searcher=searcher))


def ledger(data):
    return {r["name"]: r for r in map(json.loads, (data / "dalat" / "navigate" / "resolved.jsonl").read_text(encoding="utf-8").splitlines())}


def test_only_one_clear_place_reaches_the_search_file(world):
    stats = run()
    led = ledger(world)
    assert {n: r["status"] for n, r in led.items()} == {
        "Married Beans": "resolved", "Quán Không Thấy": "unresolved", "Hai Chi Nhánh": "ambiguous",
        "Quán Ít Review": "rejected", "Quán Đã Có": "already_held"}
    recs = [json.loads(line) for line in (world / "gmaps" / "search" / "dalat" / "resolve.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [r["items"][0]["fid"] for r in recs] == ["f1"]
    rec = recs[0]
    assert rec["end"] is True and rec["lodging"] is False and rec["tile"] == [] and rec["query"] == "resolve: Married Beans"
    assert rec["nominee"]["name"] == "Married Beans" and "inside" not in rec["items"][0]
    assert stats["resolved"] == 1 and stats["total"] == 5


def test_search_text_is_name_plus_city_at_the_area_centre(world):
    calls = []
    run(calls=calls)
    query, n, at = calls[0]
    assert query == "Married Beans Đà Lạt" and n == 15
    assert at == (round((AREA[0] + AREA[2]) / 2, 6), round((AREA[1] + AREA[3]) / 2, 6), 13)


def test_a_second_run_does_not_search_recorded_nominees_again(world):
    run()
    calls = []
    run(calls=calls)
    assert calls == []


def test_limit_caps_the_nominees_looked_up(world):
    calls = []
    run(limit=2, calls=calls)
    assert len(calls) == 2 and len(ledger(world)) == 2


def test_result_outside_the_area_is_rejected(world):
    answers = {**ANSWERS, "Married Beans Đà Lạt": [card("f1", "Married Beans", lat=10.7, lng=106.7)]}
    run(answers=answers)
    assert ledger(world)["Married Beans"]["reason"] == "outside_area"
    assert not (world / "gmaps" / "search" / "dalat" / "resolve.jsonl").exists()


def test_empty_result_list_is_a_failed_page_not_a_verdict(world):
    answers = {**ANSWERS, "Quán Không Thấy Đà Lạt": []}
    run(answers=answers)
    assert "Quán Không Thấy" not in ledger(world)  # looked up again next run
    errors = (world / "gmaps" / "errors.jsonl").read_text(encoding="utf-8")
    assert "Quán Không Thấy" in errors


def test_a_page_error_leaves_no_ledger_row(world):
    calls = []

    async def searcher(ctx, query, n, at):
        calls.append(query)
        raise RuntimeError("boom")
    asyncio.run(resolve.run("dalat", False, sessions=fake_sessions, searcher=searcher))
    assert not (world / "dalat" / "navigate" / "resolved.jsonl").exists()
    assert len(calls) == 5  # one try each: a RuntimeError is not a timeout


def test_lodging_result_is_written_for_the_stay_list(world):
    answers = {**ANSWERS, "Married Beans Đà Lạt": [card("h1", "Married Beans", category="Khách sạn")]}
    run(answers=answers)
    assert ledger(world)["Married Beans"]["status"] == "resolved"


def test_cli_runs_the_resolve_phase_with_limit(monkeypatch):
    import sys

    from corpus import __main__ as cli
    seen = []

    async def fake(city, headed, limit=None):
        seen.append((city, headed, limit))
    monkeypatch.setitem(cli.PHASES["gmaps"], "resolve", (fake, True))
    monkeypatch.setattr(sys, "argv", ["corpus", "gmaps", "resolve", "--city", "dalat", "--limit", "7"])
    cli.main()
    assert seen == [("dalat", False, 7)]


def test_resolved_place_enters_list_only_through_the_existing_gates(world):
    from corpus.crawl.gmaps import listing
    answers = {**ANSWERS, "Quán Ít Review Đà Lạt": [card("l1", "Quán Ít Review", reviews=None, rating=4.4)]}
    run(answers=answers)
    search_dir = world / "gmaps" / "search" / "dalat"
    build = lambda kept, counts=None: listing.build(search_dir, AREA, 100, kept, "Đà Lạt", 30, 1000, counts)  # noqa: E731
    assert [i["fid"] for i in build(kept={"f1"})["items"]] == ["f1"]
    assert build(kept=set())["items"] == []  # the Extractor relevance filter still decides
    # pending_count: no count on the card, so list.py drops it until `gmaps counts` reads it
    assert build(kept={"l1"})["items"] == []
    assert [i["fid"] for i in build({"l1"}, {"l1": {"rating": 4.4, "reviews": 90}})["items"]] == ["l1"]
    assert build({"l1"}, {"l1": {"rating": 4.4, "reviews": 9}})["items"] == []
