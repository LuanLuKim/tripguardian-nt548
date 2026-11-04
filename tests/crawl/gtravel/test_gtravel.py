"""Google Travel: hotel URL for a lodging and a stay, hotel-page parser on saved pages (2026-10-28), the observation."""

import asyncio
import gzip
from datetime import date
from pathlib import Path

import pytest

from corpus.crawl import gtravel
from corpus.crawl.common import lodging

FIX = Path(__file__).parent / "fixtures"
MIST = "0x3171130016e18959:0xc0635c428bdd9b13"


def text(name: str) -> str:
    return (FIX / f"{name}.txt").read_text(encoding="utf-8")


def test_hotel_id_and_stay_param_equal_what_google_emits():
    # both strings were copied from the URL Google Travel itself produced for this lodging on 2026-11-19, 1 night
    assert gtravel.entity_id(MIST) == "CgsIk7b23qiI17HAARAB"
    stay = lodging.Stay(date(2026, 11, 19), 1, 2)
    assert gtravel.stay_param(stay) == "CAEaIAoCGgASGhIUCgcI6g8QCxgTEgcI6g8QCxgUGAEyAhAAKgkKBToDVk5EGgA"
    assert gtravel.hotel_url(MIST, stay).startswith("https://www.google.com/travel/hotels/entity/CgsIk7b23qiI17HAARAB?")


def test_other_party_sizes_are_refused_not_guessed():
    with pytest.raises(ValueError):
        gtravel.stay_param(lodging.Stay(date(2026, 11, 19), 1, 3))


def test_priced_page():
    h = gtravel.parse_hotel(text("entity_priced_2n"))
    assert (h.state, h.name, h.price_night_vnd, h.dates) == ("priced", "The Mist Boutique Hotel DaLat", 2078464, "7 – 9 thg 11")


def test_page_without_offers_is_no_offer_not_sold_out():
    h = gtravel.parse_hotel(text("entity_no_offer"))
    assert (h.state, h.name, h.price_night_vnd) == ("no_offer", "Archy Stayin Nam Hồ Đà Lạt", None)


def test_pages_without_photos_have_the_same_header():
    h = gtravel.parse_hotel(text("entity_priced_1n_no_photos"))
    assert (h.state, h.name, h.price_night_vnd, h.dates) == ("priced", "ORCHID Hotel", 427984, "7 – 8 thg 11")
    h = gtravel.parse_hotel(text("entity_no_offer_no_photos"))
    assert (h.state, h.name) == ("no_offer", "Dalat Horizon Hotel")


def test_page_not_drawn_yet_is_pending():
    assert gtravel.parse_hotel("Quay lại danh sách khách sạn\nTổng quan\n").state == "pending"
    assert gtravel.parse_hotel("").state == "pending"


def test_saved_html_pages_carry_the_same_text_as_the_text_fixtures():
    # the .html.gz fixtures are the pages as loaded; the .txt ones are their innerText
    html = gzip.open(FIX / "entity_priced_2n.html.gz", "rt", encoding="utf-8").read()
    assert "2.078.464" in html and "The Mist Boutique Hotel DaLat" in html


def test_dates_must_be_the_dates_asked():
    two = lodging.Stay(date(2026, 11, 7), 2, 2)
    assert gtravel.dates_match("7 – 9 thg 11", two)
    assert not gtravel.dates_match("7 – 8 thg 11", two)
    assert not gtravel.dates_match(None, two)
    assert gtravel.dates_match("30 thg 11 – 2 thg 12", lodging.Stay(date(2026, 11, 30), 2, 2))


ROW = {"fid": MIST, "name": "The Mist Boutique Hotel DaLat"}


def test_observation_prices_a_night_and_derives_the_total():
    stay = lodging.Stay(date(2026, 11, 7), 2, 2)
    obs = gtravel.observation(ROW, stay, gtravel.parse_hotel(text("entity_priced_2n")), "u", "Đà Lạt")
    assert (obs["price_night_vnd"], obs["price_total_vnd"], obs["available"]) == (2078464, 4156928, True)
    assert obs["stay_date"] == "2026-11-07" and obs["nights"] == 2 and obs["match_score"] == 1.0
    lodging.check(obs)


def test_observation_for_other_dates_is_unknown():
    stay = lodging.Stay(date(2026, 11, 14), 2, 2)  # the page shows 7 - 9 thg 11
    obs = gtravel.observation(ROW, stay, gtravel.parse_hotel(text("entity_priced_2n")), "u", "Đà Lạt")
    assert obs["price_night_vnd"] is None and obs["available"] is None
    lodging.check(obs)


class FakePage:
    def __init__(self, texts):
        self.texts, self.url, self.i = list(texts), "https://www.google.com/travel/hotels/entity/x", 0

    async def goto(self, *a, **k): ...
    async def evaluate(self, js):
        t = self.texts[min(self.i, len(self.texts) - 1)]
        self.i += 1
        return t
    async def wait_for_timeout(self, ms): ...
    async def close(self): ...
    def get_by_text(self, *a, **k):
        class C:
            async def count(self): return 0
        return C()


class FakeCtx:
    def __init__(self, texts): self.page = FakePage(texts)
    async def new_page(self): return self.page


def test_read_waits_until_the_offers_are_drawn():
    ctx = FakeCtx(["", "Tổng quan", text("entity_priced_2n")])
    h = asyncio.run(gtravel.crawl.read(ctx, "u"))
    assert h.state == "priced" and ctx.page.i == 3


def test_the_2026_10_chip_without_a_date_line_reads_dates_from_the_inputs():
    from datetime import date

    from corpus.crawl.common.lodging import Stay
    from corpus.crawl.gtravel.parser import dates_match, parse_hotel
    text = (__import__("pathlib").Path(__file__).parent / "fixtures" / "entity_priced_vs_usual.txt").read_text(encoding="utf-8")
    h = parse_hotel(text)
    assert h.state == "priced" and h.price_night_vnd == 1045729 and h.dates == "inputs"
    assert dates_match("Thứ 7, 21 thg 11|CN, 22 thg 11", Stay(date(2026, 11, 21), 1, 2))
    assert not dates_match("Thứ 7, 21 thg 11|CN, 23 thg 11", Stay(date(2026, 11, 21), 1, 2))


def test_min_stay_page_is_unknown_for_the_nights_asked_not_sold_out():
    h = gtravel.parse_hotel(text("entity_min_stay"))
    assert (h.state, h.name, h.min_nights, h.price_night_vnd) == ("min_stay", "Gia Pham Hotel", 2, None)
    stay = lodging.Stay(date(2026, 11, 7), 1, 2)
    obs = gtravel.observation({"fid": "a:1", "name": "Gia Pham Hotel"}, stay, h, "u", "Đà Lạt")
    assert (obs["price_night_vnd"], obs["available"], obs["min_nights"]) == (None, None, 2)
    lodging.check(obs)


def test_a_page_that_never_drew_is_recorded_as_unknown_with_a_note():
    obs = gtravel.observation({"fid": "a:1", "name": "X"}, lodging.Stay(date(2026, 11, 7), 1, 2),
                              gtravel.Hotel("pending"), "u", "Đà Lạt")
    assert (obs["price_night_vnd"], obs["available"], obs["note"]) == (None, None, "not_drawn")
    lodging.check(obs)
