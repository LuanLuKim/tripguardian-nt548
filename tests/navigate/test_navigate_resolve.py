import json

from corpus.navigate import resolve


def row(fid, name, reviews=100, rating=4.5, inside=True, lodging=False, lat=11.94, lng=108.44):
    return {"fid": fid, "name": name, "reviews": reviews, "rating": rating, "inside": inside, "lodging": lodging,
            "lat": lat, "lng": lng, "category": "Quán cà phê", "url": f"https://maps/{fid}"}


GATES = dict(min_reviews=30, min_reviews_stay=30, same_name_m=1000, held_fids=set())


def decide(rows, name="Married Beans", **over):
    return resolve.decide({"name": name, "area_hint": "Phường 1"}, rows, **{**GATES, **over})


def test_one_clear_place_is_resolved():
    out = decide([row("f1", "Married Beans Coffee"), row("f2", "Quán Gió")])
    assert out["status"] == "resolved" and out["fid"] == "f1" and out["item"]["fid"] == "f1"


def test_no_name_match_is_unresolved_never_a_verdict_of_absence():
    out = decide([row("f2", "Quán Gió"), row("f3", "Cà phê Mây")])
    assert out["status"] == "unresolved" and "item" not in out
    assert {c["fid"] for c in out["candidates"]} <= {"f2", "f3"}
    assert "not_exist" not in json.dumps(out) and "missing" not in out["status"]


def test_empty_result_list_is_unresolved():
    assert decide([])["status"] == "unresolved"


def test_two_different_places_with_the_same_name_are_ambiguous():
    out = decide([row("f1", "Married Beans", lat=11.94), row("f2", "Married Beans", lat=11.99)])
    assert out["status"] == "ambiguous" and "item" not in out


def test_the_same_place_under_two_fids_is_one_place_with_the_most_reviews():
    out = decide([row("f1", "Married Beans", reviews=40), row("f2", "Married Beans", reviews=900, lat=11.9401)])
    assert out["status"] == "resolved" and out["fid"] == "f2"


def test_an_exact_name_next_to_a_longer_name_is_ambiguous_not_guessed():
    # "Married Beans" and "Married Beans Coffee" may be two branches: the margin keeps the guess out
    out = decide([row("f1", "Married Beans"), row("f2", "Married Beans Coffee", lat=11.99)])
    assert out["status"] == "ambiguous" and {c["fid"] for c in out["candidates"]} == {"f1", "f2"}


def test_a_name_that_only_shares_a_word_is_not_a_competing_match():
    out = decide([row("f1", "Married Beans"), row("f2", "Beans Roastery Garden Annex Hill", lat=11.99)])
    assert out["status"] == "resolved" and out["fid"] == "f1"


def test_match_outside_the_area_is_rejected_not_taken():
    out = decide([row("f1", "Married Beans", inside=False)])
    assert out["status"] == "rejected" and out["reason"] == "outside_area" and "item" not in out


def test_outside_match_does_not_hide_an_inside_one():
    out = decide([row("f1", "Married Beans", inside=False), row("f2", "Married Beans")])
    assert out["status"] == "resolved" and out["fid"] == "f2"


def test_few_reviews_and_no_rating_stay_proposals():
    assert decide([row("f1", "Married Beans", reviews=12)])["reason"] == "few_reviews"
    assert decide([row("f1", "Married Beans", reviews=None, rating=None)])["reason"] == "no_rating"


def test_hidden_review_count_waits_for_counts():
    out = decide([row("f1", "Married Beans", reviews=None, rating=4.4)])
    assert out["status"] == "pending_count" and out["item"]["fid"] == "f1"


def test_place_already_in_the_list_is_held_and_not_rewritten():
    out = decide([row("f1", "Married Beans")], held_fids={"f1"})
    assert out["status"] == "already_held" and out["fid"] == "f1" and "item" not in out


def test_lodging_uses_the_stay_review_bar():
    low = row("f1", "Married Beans", reviews=35, lodging=True)
    assert decide([low], min_reviews_stay=50)["reason"] == "few_reviews"
    assert decide([low], min_reviews_stay=30)["status"] == "resolved"


def test_a_short_name_inside_a_long_result_is_not_covered():
    # "Nhà thờ Con Gà" must not resolve to "Ga Đà Lạt": too few of its own words
    out = decide([row("f1", "Ga Đà Lạt")], name="Nhà thờ Con Gà")
    assert out["status"] == "unresolved"


# pending / record -------------------------------------------------------------------------------------------------

def _write(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


def test_pending_joins_queue_and_maybe_matches_and_skips_recorded(data):
    nav = data / "dalat" / "navigate"
    _write(nav / "resolve_queue.jsonl", [{"name": "Married Beans", "area_hint": "P1", "aspect": "a1", "city": "dalat"},
                                         {"name": "Quán Mới", "area_hint": "", "aspect": "a1", "city": "dalat"}])
    report = {"aspects": [{"key": "a2", "nominees": [
        {"name": "Nhà thờ Con Gà", "area_hint": "P3", "status": "maybe", "matches": []},
        {"name": "Đã có rồi", "area_hint": "", "status": "held", "matches": []},
        {"name": "married  beans", "area_hint": "", "status": "maybe", "matches": []}]}]}
    (nav / "compare_20261028T100000Z.json").write_text(json.dumps(report), encoding="utf-8")
    (nav / "compare_20261001T100000Z.json").write_text(json.dumps({"aspects": [{"key": "old", "nominees": [
        {"name": "Cũ", "area_hint": "", "status": "maybe", "matches": []}]}]}), encoding="utf-8")
    names = [p["name"] for p in resolve.pending("dalat")]
    assert names == ["Married Beans", "Quán Mới", "Nhà thờ Con Gà"]  # latest report only; no duplicate; held ignored
    resolve.record("dalat", {"name": "Quán Mới", "status": "unresolved", "reason": "no_name_match"})
    assert [p["name"] for p in resolve.pending("dalat")] == ["Married Beans", "Nhà thờ Con Gà"]
    line = json.loads((nav / "resolved.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert line["name"] == "Quán Mới" and line["city"] == "dalat" and line["at"]


def test_pending_with_no_files_is_empty(data):
    assert resolve.pending("dalat") == []
