import json
from datetime import UTC, datetime

from corpus.navigate import compare  # the module (the package exports compare_map)
from corpus.navigate.compare import Known, Place
from corpus.navigate.schema import parse_answer

NF_NONE = {"key": "", "type": "none", "values": [], "hint": ""}
NOW = datetime(2026, 10, 28, 11, 0, 0, tzinfo=UTC)


def aspect(key, name_vi, kind="feature", ref=None, queries=None, nominees=(), new_feature=None):
    return {"key": key, "name_vi": name_vi, "why": "vì thành phố này cần", "months": [],
            "target": {"kind": kind, "ref": ref or key, "new_feature": new_feature or NF_NONE},
            "queries": queries or [f"{name_vi} Đà Lạt"], "sources": ["web"],
            "nominees": [{"name": n, "area_hint": "p1"} for n in nominees]}


def the_map(*aspects):
    return parse_answer("dalat", {"aspects": list(aspects), "general_claims": []}, "sol", "2026-10-28T10:00:00+00:00")


KNOWN = Known(
    feature_ids={"cloud_hunting", "scenic_view"},
    concepts=[("ontology", "cloud_hunting", "cloud hunting"), ("ontology", "cloud_hunting", "săn mây"),
              ("ontology", "scenic_view", "view đẹp"), ("season", "dã quỳ", "mùa dã quỳ"),
              ("dish", "lẩu gà lá é", "lẩu gà lá é")],
    queries=["săn mây {city}", "quán cà phê {city}"], city_name="Đà Lạt")

PLACES = [Place("p1", "Married Beans Coffee"), Place("p2", "Hội Ngộ Quán"), Place("p3", "Cafe Tùng")]


def run(m, tmp, places=PLACES, known=KNOWN):
    return compare.compare_map("dalat", m, known=known, places=places, now=NOW)


def test_aspect_statuses(data):
    m = the_map(
        aspect("cloud_hunting", "Săn mây"),                                   # exact feature id
        aspect("cloud_view", "săn mây", ref="cloud_view"),                    # same words as an ontology hint
        aspect("wild_sunflower_season", "mùa dã quỳ", kind="local_claim", ref="season"),   # known season phrase
        aspect("tide_walk", "đi bộ lúc nước rút", kind="new_feature", ref="tide_walk", new_feature={
            "key": "tide_walk", "type": "presence", "values": ["present"], "hint": "đi bộ trên bãi khi nước rút"}),
        aspect("night_cycling", "đạp xe đêm"))
    r = run(m, data)
    by = {a["key"]: a for a in r["aspects"]}
    assert by["cloud_hunting"]["status"] == "covered_feature" and by["cloud_hunting"]["match"]["score"] == 1.0
    assert by["cloud_view"]["status"] == "covered_feature"
    assert by["wild_sunflower_season"]["status"] == "covered_query" and by["wild_sunflower_season"]["match"]["source"] == "season"
    assert by["tide_walk"]["status"] == "new" and by["night_cycling"]["status"] == "new"
    assert r["summary"]["aspects"] == {"covered_feature": 2, "covered_query": 1, "new": 2}


def test_new_things_are_proposals_waiting_for_approval(data):
    m = the_map(aspect("tide_walk", "đi bộ lúc nước rút", kind="new_feature", new_feature={
        "key": "tide_walk", "type": "presence", "values": ["present"], "hint": "đi bộ trên bãi khi nước rút"}),
        aspect("night_cycling", "đạp xe đêm"))
    r = run(m, data)
    assert r["new_features"] == [{"key": "tide_walk", "type": "presence", "values": ["present"],
                                  "hint": "đi bộ trên bãi khi nước rút", "aspect": "tide_walk", "approval": "pending"}]
    assert all(a["approval"] == "pending" for a in r["aspects"] if a["status"] == "new")
    assert all("approval" not in a for a in r["aspects"] if a["status"] != "new")


def test_a_new_feature_the_ontology_already_has_is_not_proposed_again(data):
    m = the_map(aspect("cloud_hunting", "Săn mây", kind="new_feature", new_feature={
        "key": "cloud_hunting", "type": "presence", "values": ["present"], "hint": "săn mây"}))
    r = run(m, data)
    assert r["new_features"] == [] and r["aspects"][0]["status"] == "covered_feature"


def test_query_overlap_counts_new_queries(data):
    m = the_map(aspect("cafe_hills", "cà phê đồi", queries=["quán cà phê Đà Lạt", "cà phê view đồi thông"]))
    q = run(m, data)["aspects"][0]["queries"]
    assert q["total"] == 2 and q["held"] == ["quán cà phê Đà Lạt"] and q["new"] == ["cà phê view đồi thông"]


def test_nominees_held_maybe_missing_and_queue(data):
    m = the_map(aspect("cafe_hills", "cà phê đồi", nominees=["Married Beans", "Woodstock Cafe", "Hội Ngộ"]))
    r = run(m, data)
    st = {n["name"]: n["status"] for n in r["aspects"][0]["nominees"]}
    assert st == {"Married Beans": "held", "Woodstock Cafe": "missing", "Hội Ngộ": "held"}
    assert r["aspects"][0]["nominees"][0]["matches"][0]["place_id"] == "p1"
    assert r["summary"]["nominees"] == {"held": 2, "maybe": 0, "missing": 1}
    queue = [json.loads(x) for x in (data / "dalat" / "navigate" / "resolve_queue.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [(q["name"], q["status"], q["approval"], q["aspect"]) for q in queue] == [("Woodstock Cafe", "proposed", "pending", "cafe_hills")]
    run(m, data)  # a second run adds nothing
    assert len((data / "dalat" / "navigate" / "resolve_queue.jsonl").read_text(encoding="utf-8").splitlines()) == 1


def test_maybe_is_listed_not_queued(data):
    m = the_map(aspect("cafe_hills", "cà phê đồi", nominees=["Làng Cù Lần"]))
    r = run(m, data, places=[Place("p9", "Cù Lần Garden")])
    n = r["aspects"][0]["nominees"][0]
    assert n["status"] == "maybe" and n["matches"][0]["name"] == "Cù Lần Garden"
    assert r["summary"]["nominees"] == {"held": 0, "maybe": 1, "missing": 0}
    assert r["summary"]["resolve_queue_added"] == 0 and not (data / "dalat" / "navigate" / "resolve_queue.jsonl").exists()
    assert "Cù Lần Garden" in compare.table(r)


def test_report_is_written_and_nothing_else_is(data):
    m = the_map(aspect("night_cycling", "đạp xe đêm", nominees=["Xe Đạp Đêm"]))
    r = run(m, data)
    out = data / "dalat" / "navigate"
    assert (out / "compare_20261028T110000Z.json").exists()
    assert json.loads((out / "compare_20261028T110000Z.json").read_text(encoding="utf-8"))["city"] == "dalat"
    written = {p.relative_to(data).as_posix() for p in data.rglob("*") if p.is_file()}
    assert written == {"dalat/navigate/compare_20261028T110000Z.json", "dalat/navigate/resolve_queue.jsonl"}


def test_table_is_vietnamese_and_lists_the_new_part(data):
    m = the_map(aspect("night_cycling", "đạp xe đêm", nominees=["Xe Đạp Đêm"]))
    text = compare.table(run(m, data))
    assert "Cần duyệt" in text and "night_cycling" in text and "Xe Đạp Đêm" in text


def test_real_ontology_knows_cloud_hunting(data):
    known = compare.load_known("dalat")
    m = the_map(aspect("cloud_hunting", "Săn mây"))
    r = compare.compare_map("dalat", m, known=known, places=[], now=NOW)
    assert r["aspects"][0]["status"] == "covered_feature"
    assert r["ontology_version"] == known.ontology_version


def test_one_shared_word_is_not_a_match(data):
    known = Known(feature_ids=set(), concepts=[("ontology", "setting", "rain"), ("ontology", "hiking", "hiking")],
                  queries=[], city_name="Đà Lạt")
    m = the_map(aspect("rain_day_options", "rain day options"), aspect("hiking", "hiking", ref="hiking_trails"))
    by = {a["key"]: a["status"] for a in run(m, data, known=known)["aspects"]}
    assert by == {"rain_day_options": "new", "hiking": "covered_feature"}


def test_a_short_corpus_name_inside_a_long_nominee_is_only_maybe(data):
    m = the_map(aspect("churches", "nhà thờ", nominees=["Nhà thờ Con Gà", "Ga Đà Lạt"]))
    r = run(m, data, places=[Place("g", "Ga Đà Lạt")])
    st = {n["name"]: n["status"] for n in r["aspects"][0]["nominees"]}
    assert st == {"Nhà thờ Con Gà": "maybe", "Ga Đà Lạt": "held"}


def test_match_carries_the_matched_text_for_the_owner(data):
    r = run(the_map(aspect("cloud_view", "săn mây", ref="cloud_view")), data)
    assert r["aspects"][0]["match"]["text"] == "săn mây"


def test_rejected_match_is_honoured(data):
    """The owner review file turns a wrong lexical match back into `new` (the aspect stays in the report)."""
    m = the_map(aspect("cloud_hunting", "Săn mây"), aspect("seasonal_flower_routes", "mùa hoa", ref="cloud_hunting"))
    first = {a["key"]: a["status"] for a in run(m, data)["aspects"]}
    assert first == {"cloud_hunting": "covered_feature", "seasonal_flower_routes": "covered_feature"}
    d = data / "dalat" / "navigate"
    (d / "mining_map_rejected.json").write_text(json.dumps(
        {"rejected": [{"aspect": "seasonal_flower_routes", "ref": "cloud_hunting", "source": "ontology", "reason": "wrong"}]}),
        encoding="utf-8")
    r = {a["key"]: a for a in run(m, data)["aspects"]}
    assert r["cloud_hunting"]["status"] == "covered_feature"
    assert r["seasonal_flower_routes"]["status"] == "new" and r["seasonal_flower_routes"]["match"] is None
    assert r["seasonal_flower_routes"]["approval"] == "pending"
