from fixtures import feat, srec

from decision import evaluate as ev


def test_evaluate_counts_violations_unknowns_and_fill(monkeypatch):
    monkeypatch.setattr(ev, "trips", lambda: (2, [
        {"id": "flat", "role": "experience", "hard": {"steep_or_stairs": "present"}, "soft": {"scenic_view": 1.0}}]))
    safe = srec("S", group="nature", features={"steep_or_stairs": "absent", "scenic_view": "present"})
    disputed = srec("D", group="nature", features={"steep_or_stairs": feat("absent", dist={"absent": 3, "present": 1})})
    steep = srec("X", group="nature", features={"steep_or_stairs": "present"})
    meal = srec("M", group="restaurant", features={"steep_or_stairs": "absent"}, usable=("meal",))
    res = ev.evaluate([safe, disputed, steep, meal])
    row = res["trips"][0]
    assert row["shortlist"] == ["S"] and (row["unverified"], row["excluded"]) == (1, 1)
    assert res["summary"]["violations"] == 0 and res["summary"]["unknown_in_main"] == 0
    assert res["summary"]["unfilled_trips"] == ["flat"] and res["summary"]["ms_max"] >= 0
    assert ev.violates(disputed, "steep_or_stairs", "present")


def test_search_input_from_hidden_trip():
    si = ev.search_input({"id": "x", "role": "meal", "hard": {"kids": "unsuitable"}, "soft": {"noise": 1.0}}, 7)
    assert si.hard_filters[0].feature == "kids" and si.soft_weights[0].value == "quiet"


def test_uncertain_pass_with_warning_is_counted_apart_from_unknown(monkeypatch):
    monkeypatch.setattr(ev, "trips", lambda: (1, [
        {"id": "quiet", "role": "experience", "hard": {"noise": "loud"}, "soft": {}}]))
    shaky = srec("U", group="nature", features={"noise": feat("quiet", status="UNCERTAIN")})
    row = ev.evaluate([shaky])["trips"][0]
    res = ev.evaluate([shaky])
    assert row["shortlist"] == ["U"] and row["unknown_in_main"] == [] and row["uncertain_in_main"] == ["U"]
    assert res["summary"]["unknown_in_main"] == 0 and res["summary"]["uncertain_in_main"] == 1


def test_evaluate_measures_the_top_places_not_the_whole_window(monkeypatch):
    monkeypatch.setattr(ev, "trips", lambda: (2, [
        {"id": "flat", "role": "experience", "hard": {"steep_or_stairs": "present"}, "soft": {"scenic_view": 1.0}}]))
    recs = [srec(f"S{i:02d}", group="nature", features={"steep_or_stairs": "absent", "scenic_view": "present"},
                 lng=108.44 + i / 1000) for i in range(40)]
    row = ev.evaluate(recs)["trips"][0]
    assert 0 < len(row["shortlist"]) < 24


def _c3_records():
    look = {f: feat("present", n=5) for f in ("scenic_view", "photo_spot", "cozy_decor", "live_music")}
    cafes = [srec(f"C{i}", name=f"Quán Cà Phê Số {i}", group="cafe", usable=("experience",), features=look, lng=108.44 + i / 1000)
             for i in range(4)]
    eat = srec("E", name="Quán Bánh Căn Hai", group="restaurant", category="Nhà hàng", usable=("meal",),
               features={"scenic_view": "present"})
    eat["menu"] = {"dishes": [{"name": "bánh căn", "popular": True}]}
    return cafes + [eat]


def test_evaluate_reports_c3_metrics(monkeypatch):
    monkeypatch.setattr(ev, "trips", lambda: (4, [
        {"id": "wishy", "role": "experience", "hard": {}, "soft": {"scenic_view": 1.0, "cozy_decor": 0.5},
         "wishes": [{"dish": "bánh căn"}, {"kind": "quán cà phê"}, {"like": "Quán Cà Phê Số 0"}, {"dish": "xúc xích"}]},
        {"id": "plain", "role": "experience", "hard": {}, "soft": {"scenic_view": 1.0}}]))
    res = ev.evaluate(_c3_records())
    s = res["summary"]
    assert s["wish_penalized"] == 0 and 0 <= s["wish_hit_rate"] <= 1 and s["wishes"] == 3
    assert s["wishes_unresolved"] == ["wishy:xúc xích"] and s["wish_rank_median"] >= 1
    assert 0 <= s["drop_one_changes"] <= 1 and isinstance(s["drop_one_unchanged"], list)
    for key in ("rebase_ms", "text_turn_ms"):
        assert set(s[key]) >= {"p50", "p95"} and s[key]["p95"] >= s[key]["p50"] >= 0
    assert s["text_turn_ms"]["via_model"] == 0 and s["text_turn_ms"]["messages"] >= 7
    row = res["trips"][0]
    assert {w["wish"] for w in row["wishes"]} == {"dish:bánh căn", "kind:quán cà phê", "like:C0"}


def test_dropping_a_wish_changes_the_ranking_it_lifts(monkeypatch):
    monkeypatch.setattr(ev, "trips", lambda: (4, [
        {"id": "w", "role": "experience", "hard": {}, "soft": {}, "wishes": [{"like": "Quán Cà Phê Số 0"}]}]))
    recs = _c3_records()
    recs[1]["identity"]["lng"] = 108.50  # the look-alike would rank last without the wish
    res = ev.evaluate(recs)["summary"]
    assert res["drop_one_changes"] == 1.0 and res["drop_one_unchanged"] == []
