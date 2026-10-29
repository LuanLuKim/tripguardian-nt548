import json

from corpus.serving import scenes

CFG = scenes.config()


def ph(pid, scene, person=False, conf="high", blur=800.0, light=120.0, keep=True, owner=False):
    return {"photo_id": pid, "file": f"photos/{pid}.jpg", "scene": scene, "blur": blur, "brightness": light, "keep": keep,
            "owner": owner, "person": {"value": person, "confidence": conf}}


def doc(*photos):
    return {"place_fid": "0xa:0xb", "photos": list(photos)}


def test_one_photo_per_scene_in_the_order_of_the_kind():
    d = doc(ph("f1", "food"), ph("i1", "interior"), ph("e1", "exterior"), ph("i2", "interior", blur=2500))
    got = scenes.pick(d, "restaurant")
    assert [(p["scene"], p["photo_id"]) for p in got] == [("interior", "i2"), ("food", "f1"), ("exterior", "e1")]
    assert got[0]["file"] == "gmaps/places/0xa_0xb/photos/i2.jpg"
    assert [p["scene"] for p in scenes.pick(d, "attraction")] == ["exterior", "interior"]  # sight: no food; view/amenity absent
    assert [p["scene"] for p in scenes.pick(doc(ph("r", "room"), ph("e", "exterior")), "stay")] == ["room", "exterior"]


def test_people_blur_dark_duplicates_and_unknown_are_never_shown():
    d = doc(ph("p", "interior", person=True), ph("u", "interior", person=None), ph("l", "interior", conf="low"),
            ph("b", "exterior", blur=20.0), ph("k", "view", light=10.0), ph("w", "view", light=250.0),
            ph("d", "food", keep=False), ph("x", "unknown"), ph("o", "other"), ph("c", "crowd"), ph("m", "menu"))
    assert scenes.pick(d, "restaurant") == []


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
    assert cov == {"places": 3, "labelled_places": 2, "photos": 9, "labelled_photos": 4, "with_min_scenes": 1,
                   "scenes_per_place": {1: 1, 3: 1}}


def test_strict_no_people_rule_doubtful_labels_and_crowds_are_never_allowed():
    rows = [ph("y", "interior", person=True), ph("u", "interior", person=None), ph("m", "interior", conf="medium"),
            ph("l", "interior", conf="low"), ph("c", "crowd"), ph("n", "interior", person=None, conf="low"),
            {**ph("nolabel", "interior"), "person": None}, {k: v for k, v in ph("noperson", "view").items() if k != "person"}]
    assert scenes.allowed_files(doc(*rows), CFG) == []
    assert scenes.pick(doc(*rows), "cafe") == []
    ok = doc(ph("a", "interior"), ph("b", "other"), ph("t", "menu"), ph("blur", "view", blur=5.0), ph("dup", "food", keep=False))
    assert scenes.allowed_files(ok, CFG) == [f"gmaps/places/0xa_0xb/photos/{i}.jpg" for i in "abt"]
    assert scenes.allowed_files(None) == []


def test_allowed_for_place_reads_the_file(tmp_path):
    out = tmp_path / "gmaps" / "photo_scenes"
    out.mkdir(parents=True)
    (out / "0xa_0xb.json").write_text(json.dumps(doc(ph("a", "view"), ph("p", "view", person=True))), encoding="utf-8")
    assert scenes.allowed_for_place("0xa:0xb", tmp_path) == ["gmaps/places/0xa_0xb/photos/a.jpg"]
    assert scenes.allowed_for_place("0xz:0xz", tmp_path) == []
