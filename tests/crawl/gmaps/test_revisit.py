import json
import os

import pytest

from corpus.crawl.gmaps import crawl, revisit

FIXTURES = os.path.join(os.path.dirname(__file__), "..", "..", "fixtures", "gmaps")


def _place(root, fid, group_has=(), **raw):
    d = root / fid
    d.mkdir(parents=True)
    body = {"fid": fid, "url": f"u-{fid}", "hours": [], "popular_times": [[], [], [], [], [], [], []], **raw}
    for key in group_has:
        body[key] = {"hours": ["Thứ Hai 07:00–17:00"], "popular_times": [["Mức độ đông là 100% lúc 09 giờ."]] * 7}[key]
    (d / "place.json").write_text(json.dumps(body), encoding="utf-8")
    return d, body


def test_targets_served_missing_not_lodging_not_visited_in_group_order(tmp_path):
    a, pa = _place(tmp_path, "a")                                   # restaurant, nothing
    b, pb = _place(tmp_path, "b")                                   # attraction, nothing
    c, pc = _place(tmp_path, "c", group_has=("hours", "popular_times"))  # complete
    d, pd = _place(tmp_path, "d", group_has=("hours",))             # nature, hours only: popular times missing
    e, pe = _place(tmp_path, "e")                                   # stay
    f, pf = _place(tmp_path, "f")                                   # visited already
    g, pg = _place(tmp_path, "g")                                   # not served
    (f / revisit.FILE).write_text(json.dumps({"pass": 2, "place": {}}), encoding="utf-8")  # visited twice already
    groups = {"a": "restaurant", "b": "attraction", "c": "attraction", "d": "nature", "e": "stay", "f": "attraction"}
    got = revisit.targets([(x, p) for x, p in ((a, pa), (b, pb), (c, pc), (d, pd), (e, pe), (f, pf), (g, pg))], groups)
    assert [x.name for x, _ in got] == ["b", "d", "a"]
    assert [x.name for x, _ in revisit.targets([(g, pg), (e, pe)], {})] == []


def test_a_place_still_missing_after_the_first_visit_gets_one_more_pass(tmp_path):
    a, pa = _place(tmp_path, "a")   # first pass (no `pass` key): still nothing -> again
    b, pb = _place(tmp_path, "b")   # first pass found popular times, hours missing -> again
    c, pc = _place(tmp_path, "c")   # first pass found both -> done
    (a / revisit.FILE).write_text(json.dumps({"place": {"hours": [], "popular_times": []}}), encoding="utf-8")
    graph = [["Mức độ đông là 50% lúc 09 giờ."]] * 7
    (b / revisit.FILE).write_text(json.dumps({"pass": 1, "place": {"hours": [], "popular_times": graph}}), encoding="utf-8")
    (c / revisit.FILE).write_text(json.dumps({"pass": 1, "place": {"hours": ["Thứ Hai 07:00–17:00"], "popular_times": graph}}),
                                  encoding="utf-8")
    groups = {"a": "cafe", "b": "cafe", "c": "cafe"}
    assert [x.name for x, _ in revisit.targets([(a, pa), (b, pb), (c, pc)], groups)] == ["a", "b"]


def test_served_groups_reads_the_current_release(tmp_path):
    (tmp_path / "releases" / "r1" / "serving").mkdir(parents=True)
    (tmp_path / "releases" / "current").write_text("r1\n", encoding="utf-8")
    (tmp_path / "releases" / "r1" / "serving" / "places.json").write_text(
        json.dumps({"records": [{"id": "x", "identity": {"category_group": "cafe"}}]}), encoding="utf-8")
    assert revisit.served_groups(tmp_path) == {"x": "cafe"}
    assert revisit.served_groups(tmp_path / "none") is None


def _page(name):
    pw = pytest.importorskip("playwright.sync_api")
    return pw, open(os.path.join(FIXTURES, name), encoding="utf-8").read()


def _eval(html, js):
    pw = pytest.importorskip("playwright.sync_api")
    # the browsers live inside the repo (.cache/ms-playwright), not in the user's home cache
    repo = os.path.join(os.path.dirname(__file__), "..", "..", "..")
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", os.path.abspath(os.path.join(repo, ".cache", "ms-playwright")))
    with pw.sync_playwright() as p:
        browser = p.chromium.launch(channel=os.environ.get("CORPUS_BROWSER_CHANNEL", "chromium"))
        try:
            page = browser.new_page()
            page.set_content(f'<html><body>{html}</body></html>')
            return page.evaluate(js)
        finally:
            browser.close()


def test_parse_place_reads_hours_and_the_whole_popular_times_graph_from_a_saved_page():
    _, html = _page("place_graph_hours.html")
    got = _eval(html, crawl.PLACE_JS)
    assert len(got["hours"]) == 7 and got["hours"][0].startswith("Thứ Sáu") and "Mở cửa cả ngày" in got["hours"][0]
    assert len(got["popular_times"]) == 7 and all(len(day) >= 15 for day in got["popular_times"])
    assert got["popular_times"][0][0].startswith("Mức độ đông là")


def test_parse_place_of_a_page_maps_has_no_hours_for_leaves_them_empty():
    _, html = _page("place_no_hours.html")
    got = _eval(html, crawl.PLACE_JS)
    assert got["hours"] == [] and not any(got["popular_times"])


def test_ticket_box_is_found_and_read_as_the_official_row():
    from corpus.observe.gmaps.place_rules import parse_tickets
    _, html = _page("place_ticket_box.html")
    got = _eval(html, crawl.PLACE_JS)
    assert _eval(html, revisit._BOX_JS) is True
    assert parse_tickets(got["tickets"]) == {"usd": 8.21}  # the official row, not Klook's 1,95 US$ above the others
    assert _eval(html, revisit._LINE_JS) is None  # Maps printed no "thường dành" line
