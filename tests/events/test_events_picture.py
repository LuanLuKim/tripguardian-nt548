"""Pictures for events and seasons from an image search (corpus.events.picture, run.pictures): code rules only."""

from collections import Counter

from corpus.events import pictures
from corpus.events.picture import pick, why_not

SOCIAL = ("facebook.com", "tiktok.com")
NAME = "Festival Âm nhạc quốc tế Lang Biang năm 2026"


def result(title, src="https://cdn.baovanhoa.vn/a.jpg", page="https://baovanhoa.vn/a", resolution="1200×800"):
    return {"title": title, "img_src": src, "url": page, "resolution": resolution}


def test_a_picture_stands_when_its_page_names_the_event_in_its_year():
    good = result("Lâm Đồng: Festival Âm nhạc quốc tế Lang Biang năm 2026 sẽ diễn ra vào tháng 11")
    assert why_not(good, NAME, 2026, SOCIAL, set()) is None
    assert pick([good], NAME, 2026, SOCIAL, set()) == {"image": "https://cdn.baovanhoa.vn/a.jpg",
                                                       "page": "https://baovanhoa.vn/a", "domain": "baovanhoa.vn"}


def test_what_the_picture_rules_refuse():
    title = "Festival Âm nhạc quốc tế Lang Biang 2026"
    cases = {
        "another festival": result("Festival Quốc tế Âm nhạc Mới 2025: gần 100 tác phẩm"),
        "last year": result("Festival Âm nhạc quốc tế Lang Biang 2025"),
        "plain http": result(title, src="http://a.vn/a.jpg"),
        "a social post": result(title, page="https://www.facebook.com/x/videos/1"),
        "a social picture": result(title, src="https://lookaside.fbsbx.com/lookaside/crawler/media/?id=1"),
        "a logo": result(title, src="https://a.vn/uploads/site-logo.png"),
        "too small": result(title, resolution="320x200"),
        "a thin banner": result(title, resolution="1920x300"),
        "no size": result(title, resolution=""),
        "an old upload": result(title, src="https://a.vn/wp-content/uploads/2018/11/a.jpg"),
    }
    for case, r in cases.items():
        assert why_not(r, NAME, 2026, SOCIAL, set()) is not None, case
    assert why_not(result(title, src="https://a.vn/2025/10/a.jpg"), NAME, 2026, SOCIAL, set()) is None  # last year's upload
    used = result(title)
    assert why_not(used, NAME, 2026, SOCIAL, {used["img_src"]}) == "used by another row"


class FakeWeb:
    def __init__(self, answers):
        self.answers, self.asked = answers, []

    def images(self, query, k=30):
        self.asked.append(query)
        if query not in self.answers:
            raise RuntimeError("blocked")
        return self.answers[query]


def test_events_prefer_a_found_picture_keep_the_page_picture_otherwise_and_seasons_get_theirs():
    events = [{"name": NAME, "start": "2026-11-13", "image": "https://site.vn/banner.jpg"},
              {"name": "Đêm nhạc Mây", "start": "2026-11-20", "image": "https://site.vn/may.jpg"}]
    web = FakeWeb({
        f"{NAME} Đà Lạt": [result("Festival Âm nhạc quốc tế Lang Biang năm 2026 khai mạc")],
        "Đêm nhạc Mây Đà Lạt": [],
        "hoa Mimosa Đà Lạt": [result("Ngắm hoa Mimosa Đà Lạt tháng 11", src="https://mia.vn/mimosa.jpg",
                                     page="https://mia.vn/mimosa")],
    })
    seasons, stats = pictures(web, events, ["hoa Mimosa Đà Lạt", "săn mây"], "Đà Lạt", SOCIAL)
    assert events[0]["image"] == "https://cdn.baovanhoa.vn/a.jpg" and events[0]["image_from"]["domain"] == "baovanhoa.vn"
    assert events[1]["image"] == "https://site.vn/may.jpg" and "image_from" not in events[1]
    assert seasons == {"hoa mimosa da lat": {"name": "hoa Mimosa Đà Lạt", "image": "https://mia.vn/mimosa.jpg",
                                             "image_from": {"url": "https://mia.vn/mimosa", "domain": "mia.vn"}}}
    assert "hoa Mimosa Đà Lạt" in web.asked     # the city already in the name is not added twice
    assert stats == Counter(found=2, none=1, failed=1)
