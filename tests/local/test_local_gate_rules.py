"""Tighter gate rules of 2026-10-30 (docs/CORPUS.md, Tri thức bản địa): each rule is a failure kind found by hand-labelling
95 kept claims (.superpowers/sdd/2026-10-30-local-gate/labels.jsonl)."""

import pytest

from corpus.local import doc_on_topic, gate_claim

CITY = "Đà Lạt"
NONE = {"months": [], "days": [], "hours": "", "weather": ""}


def item(**kw):
    base = {"subject_kind": "poi", "subject_text": "Quán Gỗ", "kind": "specialty", "text": "lẩu bò Ba Toa nổi tiếng",
            "amount_min_vnd": 0, "amount_max_vnd": 0, "who": "", "quote": "Quán nổi tiếng với lẩu bò Ba Toa nổi tiếng",
            **NONE}
    base.update(kw)
    return base


SECTION = ("Hoa ban trắng ở nơi khác.\n\n9. Lẩu bò Quán Gỗ\n\nĐịa chỉ: 19/9 Hoàng Diệu. Quán nổi tiếng với lẩu bò Ba Toa "
           "nổi tiếng. " + "Phần mô tả dài. " * 80 + "Nên đi vào tháng 12.")


def gate(**kw):
    return gate_claim(item(**kw), SECTION, None, city_name=CITY)


def test_the_venue_may_be_named_in_the_text_before_the_quote_not_only_in_the_quote():
    claim, why = gate(subject_text="Quán Gỗ")  # the quote says "Quán", the heading line says "Quán Gỗ"
    assert why is None and claim["subject"] == "Quán Gỗ"


def test_a_subject_the_page_never_names_near_the_quote_is_dropped():
    # the "hoa ban trắng" case: the claim's subject appears in no quote and not near it
    assert gate(subject_kind="phenomenon", subject_text="hoa ban trắng", kind="best_time",
                text="nên đi vào tháng 12", quote="Nên đi vào tháng 12", months=[12])[1] == "subject_not_in_text"


def test_the_window_before_the_quote_is_bounded():
    far = "Quán Bờ Hồ\n\n" + "x " * 700 + "Nên đi vào tháng 12."
    claim, why = gate_claim(item(subject_text="Quán Bờ Hồ", kind="best_time", text="Nên đi vào tháng 12",
                                 quote="Nên đi vào tháng 12.", months=[12]), far, None, city_name=CITY)
    assert (claim, why) == (None, "subject_not_in_text")


def test_a_title_names_the_subject():
    sec = "Nên đi vào tháng 12."
    ok, why = gate_claim(item(subject_kind="phenomenon", subject_text="hồng treo gió", kind="best_time",
                              text="Nên đi vào tháng 12", quote="Nên đi vào tháng 12.", months=[12]), sec, None,
                         city_name=CITY, title="Mùa hồng treo gió Đà Lạt")
    assert why is None and ok["subject"] == "hồng treo gió"


@pytest.mark.parametrize("text, quote", [
    ("Thành phố ngàn hoa", "Đà Lạt được mệnh danh là Thành phố ngàn hoa."),
    ("thành phố sương mù", "Đà Lạt, thành phố sương mù, mát mẻ."),
    ("lá phổi xanh", "Hồ Tuyền Lâm được mệnh danh là lá phổi xanh của Đà Lạt."),
    ("thủ đô cà phê của Việt Nam", "Đây là thủ đô cà phê của Việt Nam."),
])
def test_a_nickname_is_not_a_fact(text, quote):
    sec = f"Tổng quan. {quote} Hết."
    assert gate_claim(item(subject_kind="city", subject_text=CITY, kind="specialty", text=text, quote=quote),
                      sec, None, city_name=CITY)[1] == "epithet"


def test_a_claim_that_repeats_its_subject_says_nothing():
    sec = "Có bán hồng treo gió tại vườn."
    assert gate_claim(item(subject_kind="dish", subject_text="hồng treo gió", text="hồng treo gió",
                           quote="Có bán hồng treo gió tại vườn."), sec, None, city_name=CITY)[1] == "empty_claim"
    sec = "Mùa hoa mai anh đào. Đà Lạt rực rỡ trong mùa hoa mai anh đào."
    assert gate_claim(item(subject_kind="phenomenon", subject_text="mai anh đào", kind="specialty",
                           text="mùa hoa mai anh đào", quote="Đà Lạt rực rỡ trong mùa hoa mai anh đào."),
                      sec, None, city_name=CITY)[1] == "empty_claim"


def test_a_claim_with_a_number_is_not_empty_even_when_short():
    sec = "Đà Lạt Mountain View. Cách trung tâm thành phố: 3,8km."
    claim, why = gate_claim(item(subject_text="Đà Lạt Mountain View", kind="access", text="3,8km",
                                 quote="Cách trung tâm thành phố: 3,8km."), sec, None, city_name=CITY)
    assert why is None


@pytest.mark.parametrize("subject", ["khu vực", "trung tâm", "Những quả màu vàng", "nơi đây", "quán"])
def test_a_subject_that_is_no_name_is_dropped(subject):
    sec = f"{subject}. Quán nổi tiếng với lẩu bò Ba Toa nổi tiếng."
    assert gate_claim(item(subject_kind="area", subject_text=subject), sec, None, city_name=CITY)[1] == "vague_subject"


def test_a_city_claim_must_be_about_the_city():
    sec = "Khách sạn ở khu vực ngoài trung tâm. Có thể di chuyển bằng taxi hoặc xe máy."
    it = item(subject_kind="city", subject_text="khách sạn ở khu vực ngoài trung tâm", kind="access",
              text="Có thể di chuyển bằng taxi hoặc xe máy", quote="Có thể di chuyển bằng taxi hoặc xe máy.")
    assert gate_claim(it, sec, None, city_name=CITY)[1] == "subject_not_city"
    it["subject_text"] = "TP. Đà Lạt"
    assert gate_claim(it, sec, None, city_name=CITY)[1] is None


def test_the_document_must_be_about_the_city():
    med = ["Người bị tăng huyết áp nên ăn nhạt.", "Uống đủ nước, ăn nhiều rau."]
    assert doc_on_topic("Lưu ý trong chế độ ăn của bệnh nhân", med, CITY, ["lâm đồng"]) is False
    one = ["Phiên chợ ở Măng Đen. Du khách từ Đà Lạt lên."]
    assert doc_on_topic("Khám phá chợ phiên độc đáo ở Măng Đen", one, CITY, ["lâm đồng"]) is False
    assert doc_on_topic("Mùa hồng Đà Lạt", ["hồng chín"], CITY, []) is True  # the title names the city
    assert doc_on_topic("Cẩm nang", ["Đà Lạt mát mẻ. Ở Đà Lạt có hồ."], CITY, []) is True
    assert doc_on_topic("Trekking", ["Núi Langbiang cao. Lạc Dương gần đó."], CITY, ["langbiang", "lạc dương"]) is True


def test_a_text_that_does_not_state_its_months_or_amount_becomes_the_whole_quote():
    sec = "Mùa mai anh đào. Tháng 12 đến tháng 2: mai anh đào nở rộ khắp phố. Thuê xe máy khoảng 100.000 – 150.000đ/ngày."
    it = item(subject_kind="phenomenon", subject_text="mai anh đào", kind="season", text="mai anh đào nở rộ khắp phố",
              months=[12, 1, 2], quote="Tháng 12 đến tháng 2: mai anh đào nở rộ khắp phố.")
    claim, why = gate_claim(it, sec, None, city_name=CITY)
    assert why is None and claim["text"] == "Tháng 12 đến tháng 2: mai anh đào nở rộ khắp phố."
    it = item(subject_kind="city", subject_text=CITY, kind="price_norm", text="Thuê xe máy khoảng 100.000 – 150.000đ/ngày",
              amount_min_vnd=100000, amount_max_vnd=150000,
              quote="Thuê xe máy khoảng 100.000 – 150.000đ/ngày.")
    claim, _ = gate_claim(it, sec, None, city_name=CITY)
    assert claim["text"] == "Thuê xe máy khoảng 100.000 – 150.000đ/ngày"   # already states it: unchanged


def test_a_price_claim_needs_to_say_a_price_of_what():
    sec = "Giá dao động từ 400.000 đến 1.000.000đ/người tùy thời gian."
    it = item(subject_kind="city", subject_text=CITY, kind="price_norm", text="dao động từ 400.000 đến 1.000.000đ/người",
              amount_min_vnd=400000, amount_max_vnd=1000000, quote="Giá dao động từ 400.000 đến 1.000.000đ/người tùy thời gian.")
    assert gate_claim(it, sec, None, city_name=CITY)[1] == "empty_claim"
    sec = "Thuê xe máy dao động từ 100.000 đến 150.000đ/ngày."
    it.update(text="Thuê xe máy dao động từ 100.000 đến 150.000đ/ngày", amount_min_vnd=100000, amount_max_vnd=150000,
              quote="Thuê xe máy dao động từ 100.000 đến 150.000đ/ngày.")
    assert gate_claim(it, sec, None, city_name=CITY)[1] is None


@pytest.mark.parametrize("subject", ["Tuyến đường sắt này", "Khi phát hiện cây ngã, đất đá sạt lở hoặc ngập nước trên đường", "mưa",
                                     "trà túi lọc hoà tan, hoàn a-ti-sô, cao ích mẫu"])
def test_a_sentence_a_list_or_a_weather_word_is_no_subject(subject):
    sec = f"{subject}. Quán nổi tiếng với lẩu bò Ba Toa nổi tiếng."
    assert gate_claim(item(subject_kind="area", subject_text=subject), sec, None, city_name=CITY)[1] == "vague_subject"


def test_hype_about_flowers_all_year_is_not_a_season():
    sec = "Đà Lạt với không khí trong lành và hoa nở quanh năm."
    assert gate_claim(item(subject_kind="city", subject_text=CITY, kind="season", text="hoa nở quanh năm",
                           quote="Đà Lạt với không khí trong lành và hoa nở quanh năm."), sec, None,
                      city_name=CITY)[1] == "epithet"
