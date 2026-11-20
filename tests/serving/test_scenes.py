import json

import pytest

from corpus.serving import scenes

CFG = scenes.config()


def ph(pid, scene, person=False, conf="high", blur=800.0, light=120.0, keep=True, owner=False):
    return {"photo_id": pid, "file": f"photos/{pid}.jpg", "scene": scene, "blur": blur, "brightness": light, "keep": keep,
            "owner": owner, "person": {"value": person, "confidence": conf}}


def doc(*photos):
    return {"place_fid": "0xa:0xb", "photos": list(photos)}


def test_best_photos_of_the_kind_scenes_first_variety_breaks_near_ties():
    d = doc(ph("f1", "food"), ph("i1", "interior"), ph("e1", "exterior"), ph("i2", "interior", blur=2500))
    got = scenes.pick(d, "restaurant")
    # unscored: the sharpest first, then a new scene beats a second interior, the second interior fills the 4th slot
    assert [(p["scene"], p["photo_id"]) for p in got] == [("interior", "i2"), ("food", "f1"), ("exterior", "e1"), ("interior", "i1")]
    assert got[0]["file"] == "gmaps/places/0xa_0xb/photos/i2.jpg"
    assert [p["scene"] for p in scenes.pick(d, "attraction")] == ["interior", "exterior", "interior"]  # sight: no food
    assert [p["scene"] for p in scenes.pick(doc(ph("r", "room"), ph("e", "exterior")), "stay")] == ["room", "exterior"]


def test_a_restaurant_with_only_dish_photos_shows_its_best_dishes():
    d = doc(*(ph(f"f{i}", "food", blur=500 + 100 * i) for i in range(6)), ph("m", "menu"), ph("o", "other"))
    assert [p["photo_id"] for p in scenes.pick(d, "restaurant")] == ["f5", "f4", "f3", "f2"]


def test_appeal_scores_decide_and_a_much_better_repeat_beats_a_weak_new_scene():
    d = doc(ph("f1", "food"), ph("f2", "food"), ph("f3", "food"), ph("i1", "interior", blur=2900))
    appeal = {"f1": {"beauty": 9, "shows_place": 9}, "f2": {"beauty": 8, "shows_place": 9},
              "f3": {"beauty": 3, "shows_place": 4}, "i1": {"beauty": 4, "shows_place": 5}}
    got = [p["photo_id"] for p in scenes.pick(d, "restaurant", appeal=appeal)]
    assert got == ["f1", "f2", "i1", "f3"]  # f2 (17 - 3 repeat) beats i1 (9 + sharpness); f3 (7 - 6) loses to i1
    near = {**appeal, "f2": {"beauty": 5, "shows_place": 6}, "i1": {"beauty": 5, "shows_place": 5}}
    assert [p["photo_id"] for p in scenes.pick(d, "restaurant", appeal=near)][:2] == ["f1", "i1"]  # near tie: variety


def test_people_blur_dark_duplicates_and_unknown_are_never_shown():
    d = doc(ph("p", "interior", person=True), ph("u", "interior", person=None), ph("l", "interior", conf="low"),
            ph("b", "exterior", blur=20.0), ph("k", "view", light=10.0), ph("w", "view", light=250.0),
            ph("d", "food", keep=False), ph("x", "unknown"), ph("o", "other"), ph("c", "crowd"), ph("m", "menu"))
    assert [p["photo_id"] for p in scenes.pick(d, "restaurant")] == ["p", "u", "l"]  # only people photos stay: they fill a place with none


def test_unlabelled_place_is_empty_not_an_error(tmp_path):
    assert scenes.pick(None, "cafe") == [] and scenes.for_place("0xa:0xb", "cafe", tmp_path) == []


def test_for_place_reads_the_observation_file_and_coverage_counts(tmp_path):
    out = tmp_path / "gmaps" / "photo_scenes"
    out.mkdir(parents=True)
    (out / "0xa_0xb.json").write_text(json.dumps(doc(ph("e", "exterior"), ph("i", "interior"), ph("f", "food"))), encoding="utf-8")
    (out / "0xc_0xd.json").write_text(json.dumps({"place_fid": "0xc:0xd", "photos": [ph("e", "exterior")]}), encoding="utf-8")
    for fid, n in (("0xa_0xb", 3), ("0xc_0xd", 2), ("0xe_0xf", 4)):
        d = tmp_path / "gmaps" / "places" / fid
        (d / "photos").mkdir(parents=True)
        for i in range(n):
            (d / "photos" / f"p{i}.jpg").write_bytes(b"x")
        (d / "photos.json").write_text(json.dumps({"photos": [{"file": f"photos/p{i}.jpg"} for i in range(n)]}), encoding="utf-8")
    assert [p["scene"] for p in scenes.for_place("0xa:0xb", "cafe", tmp_path)] == ["interior", "food", "exterior"]
    cov = scenes.coverage(["0xa:0xb", "0xc:0xd", "0xe:0xf"], tmp_path)
    assert cov == {"places": 3, "labelled_places": 2, "photos": 9, "labelled_photos": 4, "with_min_photos": 1,
                   "shown_per_place": {1: 1, 3: 1}}


def test_no_people_rule_doubtful_labels_and_crowds_are_never_allowed():
    rows = [ph("y", "interior", person=True), ph("u", "interior", person=None),
            ph("l", "interior", conf="low"), ph("c", "crowd"), ph("n", "interior", person=None, conf="low"),
            {**ph("nolabel", "interior"), "person": None}, {k: v for k, v in ph("noperson", "view").items() if k != "person"}]
    assert scenes.allowed_files(doc(*rows), CFG) == []
    assert [p["photo_id"] for p in scenes.pick(doc(*rows), "cafe")] == ["y", "noperson", "u", "l"]  # no person-free photo: people ones fill in, never the crowd scene
    ok = doc(ph("a", "interior"), ph("b", "other"), ph("t", "menu"), ph("blur", "view", blur=5.0), ph("dup", "food", keep=False))
    assert scenes.allowed_files(ok, CFG) == [f"gmaps/places/0xa_0xb/photos/{i}.jpg" for i in "abt"]
    assert scenes.allowed_files(None) == []


def test_allowed_for_place_reads_the_file(tmp_path):
    out = tmp_path / "gmaps" / "photo_scenes"
    out.mkdir(parents=True)
    (out / "0xa_0xb.json").write_text(json.dumps(doc(ph("a", "view"), ph("p", "view", person=True))), encoding="utf-8")
    assert scenes.allowed_for_place("0xa:0xb", tmp_path) == ["gmaps/places/0xa_0xb/photos/a.jpg"]
    assert scenes.allowed_for_place("0xz:0xz", tmp_path) == []


def old_ph(pid, scene, month, **kw):
    return {**ph(pid, scene, **kw), "old": True, "month": month}


def test_old_outdoor_photo_of_a_sight_is_a_card_pick_with_its_year_and_nothing_else():
    from datetime import date
    today = date(2026, 10, 30)
    assert scenes.old_shown(old_ph("v", "view", "2021-03"), CFG, "nature", today)
    assert not scenes.old_shown(old_ph("v", "view", "2020-09"), CFG, "nature", today)  # 6 years and 1 month
    assert scenes.old_shown(old_ph("v", "view", "2020-11"), CFG, "nature", today)
    assert not scenes.old_shown(old_ph("i", "interior", "2024-01"), CFG, "nature", today)  # indoor keeps the 3-year cap
    assert not scenes.old_shown(old_ph("f", "food", "2024-01"), CFG, "attraction", today)
    assert not scenes.old_shown(old_ph("v", "view", "2024-01"), CFG, "stay", today)  # stays and eateries keep it too
    assert not scenes.old_shown(old_ph("v", "view", "2024-01"), CFG, "restaurant", today)
    assert not scenes.old_shown(old_ph("v", "view", None), CFG, "nature", today)
    assert not scenes.old_shown(old_ph("v", "view", "2024-01", person=True), CFG, "nature", today)  # the no-people rule holds
    assert not scenes.old_shown(old_ph("v", "view", "2024-01", conf="low"), CFG, "nature", today)
    assert not scenes.old_shown(old_ph("v", "view", "2024-01", blur=5.0), CFG, "nature", today)


def test_pick_marks_the_year_only_on_an_old_photo_and_a_fresh_photo_always_comes_first():
    d = doc(old_ph("old", "view", "2022-05", blur=2900), ph("e", "exterior"))
    got = {p["scene"]: p for p in scenes.pick(d, "nature")}
    assert got["view"]["year"] == 2022 and "year" not in got["exterior"]
    assert scenes.pick(d, "restaurant") == [{"scene": "exterior", "photo_id": "e", "file": "gmaps/places/0xa_0xb/photos/e.jpg",
                                             "w": None, "h": None}]  # a restaurant never shows the old view
    d2 = doc(old_ph("old", "view", "2022-05", blur=2900), ph("fresh", "view", blur=300))
    assert [(p["photo_id"], "year" in p) for p in scenes.pick(d2, "nature")] == [("fresh", False), ("old", True)]
    best = {"old": {"beauty": 10, "shows_place": 10}, "fresh": {"beauty": 2, "shows_place": 3}}
    assert [p["photo_id"] for p in scenes.pick(d2, "nature", appeal=best)] == ["fresh", "old"]


def test_an_old_photo_is_never_in_the_gallery_lists():
    d = doc(old_ph("old", "view", "2022-05"), ph("e", "exterior"))
    assert scenes.allowed_files(d, CFG) == ["gmaps/places/0xa_0xb/photos/e.jpg"]


def test_for_place_reads_the_appeal_file(tmp_path):
    out = tmp_path / "gmaps" / "photo_scenes"
    out.mkdir(parents=True)
    (out / "0xa_0xb.json").write_text(json.dumps(doc(ph("a", "food", blur=2900), ph("b", "food"))), encoding="utf-8")
    assert [p["photo_id"] for p in scenes.for_place("0xa:0xb", "cafe", tmp_path)] == ["a", "b"]
    ap = tmp_path / "gmaps" / "photo_appeal"
    ap.mkdir(parents=True)
    (ap / "0xa_0xb.json").write_text(json.dumps({"photos": {"b": {"beauty": 9, "shows_place": 9},
                                                            "a": {"beauty": 3, "shows_place": 3}}}), encoding="utf-8")
    assert [p["photo_id"] for p in scenes.for_place("0xa:0xb", "cafe", tmp_path)] == ["b", "a"]


def test_the_business_may_post_people_a_visitor_may_not():
    d = doc(ph("own", "interior", person=True, owner=True), ph("vis", "interior", person=True),
            ph("ownq", "food", person=None, owner=True), ph("med", "food", conf="medium"),
            ph("crowd", "crowd", person=True, owner=True))
    assert scenes.allowed_files(d, CFG) == [f"gmaps/places/0xa_0xb/photos/{i}.jpg" for i in ("own", "ownq", "med")]
    assert {p["photo_id"] for p in scenes.pick(d, "restaurant")} == {"own", "ownq", "med"}


def test_an_off_kind_scene_is_shown_only_when_the_model_says_it_shows_the_place():
    d = doc(ph("e", "exterior"), ph("sign", "other", blur=2900), ph("menu", "menu"), ph("bfast", "food", blur=2000))
    assert [p["photo_id"] for p in scenes.pick(d, "stay")] == ["e"]  # unscored: only the stay's own scenes
    ap = {"sign": {"beauty": 7, "shows_place": 7}, "menu": {"beauty": 6, "shows_place": 2},
          "bfast": {"beauty": 8, "shows_place": 6}, "e": {"beauty": 6, "shows_place": 8}}
    assert [p["photo_id"] for p in scenes.pick(d, "stay", appeal=ap)] == ["sign", "bfast", "e"]
    assert [e["photo_id"] for e in scenes.off_kind(d, "stay")] == ["sign", "menu", "bfast"]


def test_a_visitor_photo_with_people_fills_a_thin_place_after_the_person_free_ones():
    thin = doc(ph("e", "exterior"), ph("crowd", "view", person=True, blur=2900), ph("selfie", "view", person=True),
               ph("unsure", "food", person=None), ph("c", "crowd", person=True))
    ap = {"crowd": {"beauty": 8, "shows_place": 7}, "selfie": {"beauty": 6, "shows_place": 2},
          "unsure": {"beauty": 5, "shows_place": 6}, "c": {"beauty": 9, "shows_place": 9}}
    assert [p["photo_id"] for p in scenes.pick(thin, "cafe")] == ["e", "crowd", "unsure", "selfie"]  # unscored: they fill in, after the person-free one
    assert [p["photo_id"] for p in scenes.pick(thin, "cafe", appeal=ap)] == ["e", "crowd", "unsure"]  # the model says "selfie" shows nothing of the place
    assert scenes.allowed_files(thin, CFG) == ["gmaps/places/0xa_0xb/photos/e.jpg"]  # the gallery keeps the strict rule
    full = doc(ph("e", "exterior"), ph("i", "interior"), ph("f", "food"), ph("crowd", "view", person=True, blur=2900))
    assert "crowd" not in [p["photo_id"] for p in scenes.pick(full, "cafe", appeal=ap)]
    assert [e["photo_id"] for e in scenes.with_people(thin, CFG)] == ["crowd", "selfie", "unsure"]


def test_photos_with_people_come_least_crowded_first():
    d = doc(ph("big", "view", person=True), ph("small", "view", person=True))
    ap = {"big": {"beauty": 9, "shows_place": 4}, "small": {"beauty": 5, "shows_place": 8}}
    assert [p["photo_id"] for p in scenes.pick(d, "cafe", appeal=ap)] == ["small", "big"]
    d = doc(ph("free", "view"), ph("big", "view", person=True))
    assert [p["photo_id"] for p in scenes.pick(d, "cafe", appeal={"big": {"beauty": 10, "shows_place": 10}})][0] == "free"


def test_a_photo_the_model_says_shows_nothing_of_the_place_is_dropped():
    d = doc(ph("dryer", "room", blur=2900), ph("bed", "room"), ph("ext", "exterior"))
    ap = {"dryer": {"beauty": 6, "shows_place": 2}, "bed": {"beauty": 7, "shows_place": 7}}
    assert [p["photo_id"] for p in scenes.pick(d, "stay", appeal=ap)] == ["bed", "ext"]  # unscored "ext" stays
    assert [p["photo_id"] for p in scenes.pick(d, "stay")] == ["dryer", "ext", "bed"]


def test_pick_never_runs_dry_when_the_only_person_free_photo_is_old_and_a_fresh_one_has_people():
    from corpus.serving import scenes
    cfg = {**scenes.config(), "show": 2}
    a = {"scene": "view", "photo_id": "a", "file": "a.jpg", "w": 800, "h": 600, "blur": 500, "brightness": 120, "with_people": True}
    b = {"scene": "view", "photo_id": "b", "file": "b.jpg", "w": 800, "h": 600, "blur": 500, "brightness": 120, "old": True}
    mp = pytest.MonkeyPatch()
    mp.setattr(scenes, "candidates", lambda *x, **k: [a, b])
    try:
        got = scenes.pick({"place_fid": "x"}, None, cfg)
    finally:
        mp.undo()
    assert [e["photo_id"] for e in got] == ["a", "b"]
