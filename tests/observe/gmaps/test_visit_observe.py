import asyncio
import json

import pytest

from corpus.observe.gmaps import visit_observe as vo


@pytest.mark.parametrize("text,quote,minutes", [
    ("Tụi mình tới quán là 8h, thời gian tụi mình ăn cũng lâu, khoảng tầm 10h rưỡi và lúc đó vẫn còn khách trong quán", "khoảng tầm 10h rưỡi", 630),
    ("7h30 nhà mình tới quán mà 10h mới ăn xong, khu này xa trung tâm", "10h mới ăn xong", 600),
    ("đến 8h", "đến 8h", 480),
    ("7h30 tới", "7h30", 450),
    ("đến 8h rưỡi", "8h rưỡi", 510),
    ("khoảng 10h rưỡi", "khoảng 10h rưỡi", 630),
])
def test_clock_times_are_not_visit_durations(text, quote, minutes):
    obs = {"span": {"quote": quote}, "detail": {"minutes": [minutes, minutes]}}
    assert vo.rule_drop(text, obs) is not None


@pytest.mark.parametrize("text,minutes", [
    ("1h rưỡi", 90), ("ăn hết 2h", 120), ("ngồi 2 tiếng", 120), ("mất khoảng 45 phút", 45),
])
def test_actual_durations_are_kept(text, minutes):
    obs = {"span": {"quote": text}, "detail": {"minutes": [minutes, minutes]}}
    assert vo.rule_drop(text, obs) is None


class Stub:
    def __init__(self, fn):
        self.fn, self.prompt_hash, self.parallel = fn, "h", 4

    async def ask(self, client, model, **fields):
        return self.fn(fields)


TEXTS = {
    "R1": "Mình đi dạo một vòng quanh vườn hết khoảng 2 tiếng, nhiều chỗ chụp ảnh",
    "R2": "Từ trung tâm chạy xe tầm 40 phút là tới",
    "R3": "Có thể chơi cả ngày không chán, nên đi sớm",
    "R4": "Nên dành nửa ngày để tham quan hết các khu",
    "R5": "Quán mở cửa lúc 7h sáng",
    "R6": "Staff searched for my phone for 3 tiếng",  # the model says own_stay, the second read refuses
    "R7": "Chùa đẹp, 30 phút không đủ để tham quan",
}


def _place(tmp_path):
    d = tmp_path / "gmaps" / "places" / "F1"
    d.mkdir(parents=True)
    (d / "place.json").write_text(json.dumps({"fid": "F1", "name": "Vườn A", "category": "Vườn",
                                              "fetched_at": "2026-10-02T00:00:00"}), encoding="utf-8")
    reviews = [{"review_id": k, "text": t, "author_hash": f"a{k}", "published_text": "2 tháng trước", "rating": "5 sao",
                "details": []} for k, t in TEXTS.items()]
    (d / "reviews.json").write_text(json.dumps(reviews), encoding="utf-8")
    return d


def test_visit_observe_keeps_stays_the_code_can_read_and_the_second_read_supports(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    _place(tmp_path)
    asked = []

    def observe(fields):
        asked.append(fields["snippets"])
        lines = [ln for ln in fields["snippets"].splitlines() if ln.startswith("[")]
        items = []
        for ln in lines:
            n = int(ln[1:ln.index("]")])
            if "hết khoảng 2 tiếng" in ln:
                items.append({"ref": n, "quote": "hết khoảng 2 tiếng", "kind": "own_stay"})
            elif "tầm 40 phút" in ln:
                items.append({"ref": n, "quote": "tầm 40 phút", "kind": "travel"})
            elif "cả ngày" in ln:
                items.append({"ref": n, "quote": "chơi cả ngày", "kind": "own_stay"})  # capacity: code drops it
            elif "nửa ngày" in ln:
                items.append({"ref": n, "quote": "dành nửa ngày", "kind": "advised_stay"})
            elif "7h" in ln:
                items.append({"ref": n, "quote": "7h sáng", "kind": "own_stay"})  # clock time: no duration
            elif "30 phút không đủ" in ln:
                items.append({"ref": n, "quote": "30 phút không đủ", "kind": "advised_stay"})  # a floor: the rules drop it
            elif "3 tiếng" in ln:
                items.append({"ref": n, "quote": "3 tiếng", "kind": "own_stay"})
        return {"items": items}

    monkeypatch.setattr(vo, "VISIT_OBSERVE", Stub(observe))
    monkeypatch.setattr(vo, "VISIT_VERIFY", Stub(lambda f: {"verdict": "insufficient" if f["quote"] == "3 tiếng" else "supports",
                                                          "reason": "r"}))

    async def providers():
        return [(None, "m", 4)]

    monkeypatch.setattr(vo, "_providers", providers)

    async def call(slots, fn):
        return await fn(None, "m")

    monkeypatch.setattr(vo, "call", call)
    assert asyncio.run(vo.run("dalat"))["status"] == {"done": 1}
    doc = json.loads((tmp_path / "gmaps" / "visit_observations" / "F1.json").read_text(encoding="utf-8"))
    got = [(o["source_id"], o["value"], o["detail"]["minutes"], o["source_type"]) for o in doc["observations"]]
    assert got == [("R1", "1_to_2h", [120, 120], "gmaps_review"), ("R4", "half_day", [180, 300], "gmaps_review")]
    assert doc["stats"]["dropped"] == {"kind_travel": 1, "verify_insufficient": 1}
    assert doc["stats"]["rules"] == {"capacity": 1, "not_enough": 1} and len(doc["verified"]) == 4
    assert doc["observations"][0]["observed_at"] == "2026-08-03"
    assert asyncio.run(vo.run("dalat"))["status"] == {"cached": 1}
    monkeypatch.setattr(vo, "RULES_VERSION", "visit_rules@next")  # a changed rule re-applies offline: the model is not asked
    monkeypatch.setattr(vo, "VISIT_OBSERVE", Stub(lambda f: 1 / 0))
    assert asyncio.run(vo.run("dalat"))["status"] == {"rules": 1}
