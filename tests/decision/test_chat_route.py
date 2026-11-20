"""decision.heuristics.route and Engine.route: which agent of the one Lựa chọn chat answers a message."""

from decision.heuristics import route

ON_SCREEN = {"P1": {"id": "a", "name": "Quán Cà Phê Tùng", "group": "Cà phê", "chosen": False, "notes": ""},
             "P2": {"id": "b", "name": "Thiền viện Trúc Lâm", "group": "Tham quan", "chosen": False, "notes": ""}}


def test_messages_about_the_lists_go_to_decision():
    for text in ("Yên tĩnh hơn", "rẻ hơn", "Vì sao không có Langbiang?", "chọn quán đầu", "bỏ Thiền viện Trúc Lâm",
                 "Quán Cà Phê Tùng mở mấy giờ?", "so sánh 2 quán đầu", "lọc quán mở trước 7h", "hoàn tác"):
        assert route(text, ON_SCREEN) == "decision", text


def test_talk_discovery_and_questions_go_to_trip():
    for text in ("Đà Lạt tháng này có sự kiện gì?", "mình đi 3 ngày với gia đình có em bé", "Tìm thêm quán cà phê",
                 "Đi săn mây ở đâu đẹp?", "có quán nào view đồi thông không", "mùa này có hoa gì", ""):
        assert route(text, ON_SCREEN) == "trip", text


def test_a_place_verb_with_no_place_is_left_to_clef():
    assert route("bỏ mấy quán cà phê đi", ON_SCREEN) == "unsure"
    assert route("thêm một chỗ ăn tối", ON_SCREEN) == "unsure"


def test_engine_asks_clef_only_when_unsure_and_fails_open_to_trip():
    from decision.engine import Engine

    class Fake:
        route = Engine.route

        def __init__(self):
            self.store = type("S", (), {"lock": lambda self, sid: __import__("contextlib").nullcontext()})()

        def _get(self, sid):
            return None

        def _result(self, s):
            return type("R", (), {"view": None})()

        def _aliases(self, view):
            return ON_SCREEN

    asked = []

    def yes(state, questions, cfg):
        asked.append(state["user_message"])
        return {"lists": {"choice": "A", "probabilities": {"A": 0.9, "B": 0.1}}}

    e = Fake()
    assert e.route("s", "chọn quán đầu", ask=yes) == "decision" and asked == []
    assert e.route("s", "bỏ mấy quán cà phê đi", ask=yes) == "decision" and asked == ["bỏ mấy quán cà phê đi"]
    assert e.route("s", "bỏ mấy quán cà phê đi", ask=lambda *a: {}) == "trip"
