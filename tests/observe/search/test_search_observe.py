import collections
from datetime import date

from corpus.crawl.gsearch import panel as gpanel
from corpus.observe import search


def fact(kind, quote, **kw):
    base = {"kind": kind, "quote": quote, "amount_vnd": 0, "audience": "none", "open": "", "close": "", "days": [],
            "item": "", "unit": "none"}
    return {**base, **kw}


def block(url, text, at="2026-10-29", dated=None):
    return {"url": url, "host": search.host(url), "text": text, "at": at, "dated": dated}


WORDS = "Thác Datanla"
TODAY = date(2026, 10, 30)


def test_panel_title_must_be_this_place():
    assert search.panel_matches("Khu du lịch Thác Datanla", "Thác Datanla")
    assert search.panel_matches("Thung lũng Tình Yêu", "Thung Lũng Tình Yêu Đà Lạt")
    assert not search.panel_matches("Thác Prenn", "Thác Datanla")
    assert not search.panel_matches("", "Thác Datanla")


def test_site_key_tells_a_places_own_social_page_from_other_pages_of_the_network():
    assert search.site_key("https://www.facebook.com/OtomeFarm/posts/12") == "facebook.com/otomefarm"
    assert search.site_key("https://www.facebook.com/groups/x/posts/1") == "facebook.com"
    assert search.site_key("http://www.zoodoodalat.com/vi/ghe-tham") == "zoodoodalat.com"


def test_result_is_about_the_place_only_when_its_name_words_are_there():
    r = {"title": "Thác Datanla giá vé 2026", "snippet": "Giá vé 80.000đ", "url": "u"}
    assert search.relevant(r, {"datanla"})
    assert not search.relevant({**r, "title": "Thác Prenn", "snippet": "Giá vé 50.000đ"}, {"datanla"})
    assert search.relevant({"title": "Đồi chè Cầu Đất Farm", "snippet": "", "url": "u"}, {"cau", "dat", "farm"})
    assert not search.relevant({"title": "Cầu Đất", "snippet": "", "url": "u"}, {"cau", "dat", "farm", "tea"})


def test_snippet_date():
    assert search.snippet_date("15 thg 7, 2026 — Top quán cafe") == "2026-07-15"
    assert search.snippet_date("Top quán cafe") is None


def test_ticket_fact_needs_quote_amount_and_name_near_it():
    b = block("https://blog.vn/a", "Thác Datanla\nVé vào cổng thác Datanla: 80.000đ/người lớn")
    ok = fact("ticket", "Vé vào cổng thác Datanla: 80.000đ/người lớn", amount_vnd=80000, audience="adult")
    kept, why = search.read_facts({"facts": [ok]}, [b], "", WORDS, True, None, TODAY)
    assert [k["basis"] for k in kept] == ["web"] and not why
    wrong = fact("ticket", "Vé vào cổng thác Datanla: 80.000đ/người lớn", amount_vnd=90000, audience="adult")
    kept, why = search.read_facts({"facts": [wrong]}, [b], "", WORDS, True, None, TODAY)
    assert not kept and why["amount_not_in_quote"] == 1
    made_up = fact("ticket", "Vé 80.000đ", amount_vnd=80000, audience="adult")
    kept, why = search.read_facts({"facts": [made_up]}, [b], "", WORDS, True, None, TODAY)
    assert not kept and why["quote_not_in_snippet"] == 1


def test_amount_before_the_name_belongs_to_the_previous_place():
    text = "Thác Prenn giá vé 50.000đ. Thác Datanla là thác đẹp."
    f = fact("ticket", "giá vé 50.000đ", amount_vnd=50000, audience="adult")
    kept, why = search.read_facts({"facts": [f]}, [block("https://blog.vn/l", text)], "", "Thác Datanla", True, None, TODAY)
    assert not kept and why["name_not_before_quote"] == 1
    ok = "Thác Datanla - địa chỉ: QL20 - giá vé 50.000đ."
    kept, _ = search.read_facts({"facts": [f]}, [block("https://blog.vn/l", ok)], "", "Thác Datanla", True, None, TODAY)
    assert len(kept) == 1


def test_from_price_range_and_package_are_not_the_entry_price():
    for quote, amount in (("Giá vé tham quan từ 75.000 VNĐ", 75000), ("Giá vé 50.000 - 120.000 đồng/người", 50000),
                          ("Vé trọn gói 240.000đ/người lớn", 240000)):
        b = block("https://blog.vn/x", f"Thác Datanla: {quote}")
        f = fact("ticket", quote, amount_vnd=amount, audience="adult")
        kept, why = search.read_facts({"facts": [f]}, [b], "", "Thác Datanla", True, None, TODAY)
        assert not kept and why["combo_or_range"] == 1, quote


def test_amount_for_another_place_in_a_list_snippet_is_dropped():
    text = "Top thác\n" + "Thác Prenn 50.000đ. " + "x" * 300 + " Thác Datanla là thác đẹp."
    b = block("https://blog.vn/list", text)
    f = fact("ticket", "Thác Prenn 50.000đ.", amount_vnd=50000, audience="adult")
    kept, why = search.read_facts({"facts": [f]}, [b], "", WORDS, True, None, TODAY)
    assert not kept and why["name_not_before_quote"] == 1


def test_own_domain_is_official_basis_old_snippets_and_free_for_some_are_dropped():
    own = block("https://datanla.vn/gia-ve", "Datanla giá vé người lớn 80.000đ")
    f = fact("ticket", "Datanla giá vé người lớn 80.000đ", amount_vnd=80000, audience="adult")
    kept, _ = search.read_facts({"facts": [f]}, [own], "", WORDS, True, "datanla.vn", TODAY)
    assert kept[0]["basis"] == "official_site"
    old = block("https://blog.vn/old", "Datanla giá vé người lớn 80.000đ", dated="2022-01-01")
    kept, why = search.read_facts({"facts": [f]}, [old], "", WORDS, True, None, TODAY)
    assert not kept and why["snippet_too_old"] == 1
    some = block("https://blog.vn/b", "Datanla miễn phí cho trẻ em dưới 1m")
    g = fact("free", "Datanla miễn phí cho trẻ em dưới 1m")
    kept, why = search.read_facts({"facts": [g]}, [some], "", WORDS, True, None, TODAY)
    assert not kept and why["free_for_some"] == 1
    kept, why = search.read_facts({"facts": [f]}, [own], "", WORDS, False, "datanla.vn", TODAY)  # a cafe sells no entry
    assert not kept and why["no_entry_ticket_category"] == 1


def _kept(kind, basis, url, **kw):
    q = kw.pop("quote", "q")
    return {"fact": fact(kind, q, **kw), "basis": basis, "block": block(url, q)}


NOPANEL = gpanel.Panel(present=False)


def test_panel_hours_win_then_pages_that_agree_else_a_conflict():
    pan = gpanel.Panel(present=True, hours={"mon": [["08:00", "17:00"]]}, hours_text="Thứ Hai 08:00–17:00")
    hours, ev, conflict = search.pick_hours(pan, True, [], "2026-10-29")
    assert hours == {"mon": [["08:00", "17:00"]]} and ev["basis"] == "google_panel" and conflict is None
    assert search.pick_hours(pan, False, [], "2026-10-29")[0] is None  # a panel of another place says nothing
    a = _kept("hours", "web", "https://a.vn/x", days=["mon", "tue"], open="07:00", close="17:00")
    b = _kept("hours", "web", "https://b.vn/x", days=["mon", "tue"], open="07:00", close="17:00")
    hours, ev, _ = search.pick_hours(NOPANEL, False, [a, b], "2026-10-29")
    assert hours == {"mon": [["07:00", "17:00"]], "tue": [["07:00", "17:00"]]} and ev["domains"] == 2
    c = _kept("hours", "web", "https://c.vn/x", days=["mon", "tue"], open="08:00", close="16:00")
    hours, ev, conflict = search.pick_hours(NOPANEL, False, [a, c], "2026-10-29")
    assert hours is None and ev is None and conflict == "pages_differ"


def test_ticket_choice_panel_official_line_then_own_site_then_one_amount_per_page():
    pan = gpanel.Panel(present=True, admissions=(
        gpanel.Admission("Klook", "Klook", 50000, False, False),
        gpanel.Admission("Place", "Place", 150000, False, True)))
    t, ev = search.pick_tickets(pan, True, [], "2026-10-29")
    assert t == {"adult": [150000]} and ev["basis"] == "google_panel"
    assert search.pick_tickets(pan, False, [], "2026-10-29") == (None, None)  # reseller prices are never taken
    a = _kept("ticket", "web", "https://a.vn/x", amount_vnd=80000, audience="adult", quote="80k")
    a2 = _kept("ticket", "web", "https://a.vn/y", amount_vnd=100000, audience="adult", quote="100k")
    b = _kept("ticket", "web", "https://b.vn/x", amount_vnd=90000, audience="adult", quote="90k")
    k = _kept("ticket", "web", "https://b.vn/x", amount_vnd=50000, audience="child", quote="50k")
    c = _kept("ticket", "web", "https://c.vn/x", amount_vnd=300000, audience="adult", quote="300k")
    assert search.pick_tickets(NOPANEL, False, [a], "2026-10-29") == (None, None)  # one page alone is not enough
    assert search.pick_tickets(NOPANEL, False, [a, c], "2026-10-29") == (None, None)  # two pages that disagree
    t, ev = search.pick_tickets(NOPANEL, False, [a, a2, b, k, c], "2026-10-29")
    assert t == {"adult": [90000, 100000], "child": [50000]} and ev["domains"] == 2 and ev["basis"] == "web"
    assert a2["used"] and b["used"] and k["used"] and not c.get("used") and not a.get("used")
    own = _kept("ticket", "official_site", "https://own.vn/x", amount_vnd=70000, audience="adult", quote="70k")
    assert search.pick_tickets(NOPANEL, False, [a, own], "2026-10-29")[1]["basis"] == "official_site"  # one own page is enough


def test_part_of_the_day_is_not_opening_hours():
    b = block("https://blog.vn/x", "Thác Datanla: khung tối tham khảo: khoảng 16:00–23:00.")
    f = fact("hours", "khung tối tham khảo: khoảng 16:00–23:00.", open="16:00", close="23:00", days=[])
    kept, why = search.read_facts({"facts": [f]}, [b], "", "Thác Datanla", True, None, TODAY)
    assert not kept and why["partial_hours"] == 1
    g = fact("hours", "Thác Datanla: 07:00–17:00", open="07:00", close="17:00", days=[])
    kept, _ = search.read_facts({"facts": [g]}, [block("https://blog.vn/x", "Thác Datanla: 07:00–17:00")], "", "Thác Datanla", True, None, TODAY)
    assert len(kept) == 1 and len(kept[0]["fact"]["days"]) == 7  # no day named: every day


def test_free_needs_every_panel_line_free_and_loses_to_a_price():
    pan = gpanel.Panel(present=True, admissions=(gpanel.Admission("P", "P", None, True, False),))
    assert search.pick_free(pan, True, [], "2026-10-29")["basis"] == "google_panel"
    mixed = gpanel.Panel(present=True, admissions=(gpanel.Admission("P", "P", None, True, False),
                                                   gpanel.Admission("Klook", "Klook", 50000, False, False)))
    assert search.pick_free(mixed, True, [], "2026-10-29") is None
    place = {"fid": "f", "name": "P"}
    recs = {"panel": {"at": "2026-10-29T00:00:00+00:00", "results": []}, "fee": None, "hours": None}
    paid = [_kept("ticket", "web", "https://a.vn/x", amount_vnd=80000, audience="adult", quote="80k"),
            _kept("ticket", "web", "https://b.vn/x", amount_vnd=85000, audience="adult", quote="85k")]
    out = search.build(place, recs, pan, True, paid, collections.Counter(), [], True)
    assert "entry_free" not in out["place_facts"] and out["place_facts"]["tickets_vnd"] == {"adult": [80000, 85000]}


def test_gate_v6_generic_name_closed_place_and_bundle_price_are_dropped():
    def read(name, text, f):
        return search.read_facts({"facts": [f]}, [block("https://blog.vn/x", text)], "", name, True, None, TODAY)
    hours = fact("hours", "mở cửa 8h00-17h00 mỗi ngày", open="08:00", close="17:00")
    kept, why = read("Khu Vui Chơi", "Khu vui chơi Wonderland mở cửa 8h00-17h00 mỗi ngày.", hours)
    assert not kept and why["generic_name"] == 1
    kept, _ = read("Núi VOI", "Khu du lịch Núi Voi mở cửa 8h00-17h00 mỗi ngày.", hours)
    assert len(kept) == 1  # a rare word keeps the name specific
    free = fact("free", "miễn phí")
    kept, why = read("Tua Bin Số 7", "Tua Bin Số 7 miễn phí, nhưng đã bị rào chắn và cấm tham quan từ 2024.", free)
    assert not kept and why["closed_nearby"] == 1
    bundle = fact("ticket", "nếu bạn chọn 120.000/người sẽ bao gồm 1 phần nước", amount_vnd=120000, audience="adult")
    kept, why = read("Mongo Land", "Mongo Land: nếu bạn chọn 120.000/người sẽ bao gồm 1 phần nước", bundle)
    assert not kept and why["combo_or_range"] == 1


def test_searxng_snippets_give_tickets_and_free_but_not_hours_and_google_wins_a_shared_url():
    hours = fact("hours", "mở cửa 8h00-17h00 mỗi ngày", open="08:00", close="17:00")
    b = {**block("https://blog.vn/x", "Thác Datanla mở cửa 8h00-17h00 mỗi ngày."), "via": "searxng"}
    kept, why = search.read_facts({"facts": [hours]}, [b], "", "Thác Datanla", True, None, TODAY)
    assert not kept and why["searxng_hours"] == 1
    kept, _ = search.read_facts({"facts": [hours]}, [{**b, "via": "google"}], "", "Thác Datanla", True, None, TODAY)
    assert len(kept) == 1
    result = {"url": "https://blog.vn/x", "title": "Thác Datanla", "snippet": "giá vé 50.000đ"}
    recs = {"fee": {"at": "2026-10-30T00:00:00+00:00", "source": "searxng", "results": [result]},
            "hours": {"at": "2026-10-01T00:00:00+00:00", "results": [result]}}
    assert [x["via"] for x in search.blocks_of(recs, {"datanla"})] == ["google"]


def test_searxng_facts_get_their_own_basis_so_aggregate_ignores_them_until_enabled():
    f = fact("ticket", "giá vé 50.000đ", amount_vnd=50000, audience="adult")
    for via, basis in (("searxng", "web_searxng"), ("google", "web")):
        b = {**block("https://blog.vn/l", "Thác Datanla - giá vé 50.000đ."), "via": via}
        kept, _ = search.read_facts({"facts": [f]}, [b], "", "Thác Datanla", True, None, TODAY)
        assert kept[0]["basis"] == basis
