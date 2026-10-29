"""Profile entries like ChatGPT memory (docs/TRIP_UNDERSTANDING.md §17): kind / statement / signal / evidence / status."""

from datetime import date, timedelta

from trip.domain.patterns import Edit, Summary, detect, entries, entry_id, observe, votes_from_state
from trip.domain.state import Anchor, Evidence, TripState, Update, apply
from trip.infrastructure.settings import PatternSettings

TODAY = date(2026, 10, 28)
CFG = PatternSettings(enabled=True, min_sessions=3, window=8, agreement=0.75, stale_days=365, max_places=2)


def put(state, field, value, source="user", quote="x", tool=None, op="set"):
    return apply(state, Update(field=field, op=op, value=value, source=source, confidence="high",
                               evidence=Evidence(turn=1, quote=quote, tool=tool)))


def sessions(key, values, start=TODAY - timedelta(days=30), how="said"):
    return [Summary(sid=f"s{i}", day=start + timedelta(days=i), votes={key: v}, how={key: how}, quotes={key: f"q{i}"})
            for i, v in enumerate(values)]


def one(history, key, value, **kw):
    (e,) = [e for e in entries(history, **{"cfg": CFG, "today": TODAY, **kw}) if (e.key, e.value) == (key, value)]
    return e


# ---------- observe: explicit signals only ----------

def test_observe_keeps_how_and_quote_of_explicit_choices():
    s = put(TripState(), "pace", "slow", quote="đi chậm thôi")
    s = put(s, "soft", ("crowd=low", "love"), quote=None, tool="chip:c_crowd", op="add")
    seen = observe(s)
    assert seen["pace"] == ("slow", "said", "đi chậm thôi")
    assert seen["soft:crowd=low"] == ("love", "picked", None)
    assert votes_from_state(s) == {k: v[0] for k, v in seen.items()}


def test_observe_never_takes_guesses_unknowns_visited_hard_limits_or_trip_facts(catalog):
    s = put(TripState(), "soft", ("scenic_view=present", "love"), source="inferred", op="add")
    s = put(s, "hard", {"feature": "steep_or_stairs", "op": "ne", "value": "present"}, op="add")
    for field, value in (("days", 3), ("people", 2), ("month", 11), ("start_date", date(2026, 11, 20))):
        s = put(s, field, value)
    s = put(s, "companions", "partner", op="add")
    s = put(s, "visited", catalog.places[0].id, op="add")
    s = put(s, "anchor", Anchor(text="somewhere", state="missing"), op="add")
    assert observe(s) == {}


def test_a_long_quote_is_cut():
    s = put(TripState(), "pace", "slow", quote="chậm " * 100)
    assert len(observe(s)["pace"][2]) <= 120


# ---------- status ----------

def test_one_session_is_a_candidate_and_not_used():
    e = one(sessions("pace", ["slow"]), "pace", "slow")
    assert (e.status, e.used, e.kind) == ("candidate", False, "habit")


def test_min_sessions_make_an_active_entry_with_its_evidence():
    e = one(sessions("pace", ["slow"] * 3), "pace", "slow")
    assert e.status == "active" and e.used
    assert [(p.session_id, p.how, p.quote) for p in e.evidence] == [("s0", "said", "q0"), ("s1", "said", "q1"),
                                                                     ("s2", "said", "q2")]
    assert (e.first_seen, e.last_seen) == (TODAY - timedelta(days=30), TODAY - timedelta(days=28))
    assert e.statement and e.id == entry_id("pace", "slow")


def test_one_later_contradiction_makes_it_weak_two_retire_it():
    assert one(sessions("pace", ["slow"] * 3 + ["packed"]), "pace", "slow").status == "weak"
    assert one(sessions("pace", ["slow"] * 3 + ["packed"] * 2), "pace", "slow").status == "retired"


def test_stale_entry_is_retired():
    e = one(sessions("pace", ["slow"] * 3, start=TODAY - timedelta(days=500)), "pace", "slow")
    assert e.status == "retired" and not e.used


def test_strength_fades_with_time():
    fresh = one(sessions("pace", ["slow"] * 3), "pace", "slow").strength
    old = one(sessions("pace", ["slow"] * 3, start=TODAY - timedelta(days=300)), "pace", "slow").strength
    assert fresh > old > 0


def test_judge_flag_lowers_an_active_entry_to_weak():
    h = sessions("pace", ["slow"] * 3)
    e = one(h, "pace", "slow", flags={entry_id("pace", "slow"): "overgeneral"})
    assert (e.status, e.flag, e.used) == ("weak", "overgeneral", False)


def test_user_edit_wins_every_rule_and_pause_stops_use():
    h = sessions("pace", ["slow"])
    eid = entry_id("pace", "slow")
    e = one(h, "pace", "slow", edits={eid: Edit(statement="Mình thích đi thong thả")})
    assert (e.status, e.user_edited, e.statement, e.used) == ("active", True, "Mình thích đi thong thả", True)
    e = one(sessions("pace", ["slow"] * 3), "pace", "slow", edits={eid: Edit(paused=True)})
    assert e.paused and not e.used


# ---------- statements and kinds ----------

def test_statements_are_vietnamese_sentences(catalog):
    pid = catalog.places[0].id
    h = [Summary(sid="a", day=TODAY, votes={"soft:crowd=high": "avoid", "soft:scenic_view=present": "love",
                                             f"place:{pid}": "love", "mobility": "motorbike", "budget_vnd": "3000000"})]
    got = {e.key: e for e in entries(h, cfg=CFG, today=TODAY, catalog=catalog)}
    assert got["soft:crowd=high"].kind == "avoid" and got["soft:crowd=high"].statement.startswith("Tránh")
    assert got["soft:scenic_view=present"].kind == "taste" and got["soft:scenic_view=present"].statement.startswith("Thích")
    assert catalog.places[0].name in got[f"place:{pid}"].statement
    assert got["mobility"].kind == "practical" and "xe máy" in got["mobility"].statement
    assert "3.000.000" in got["budget_vnd"].statement


def test_detect_is_the_used_entries():
    h = sessions("pace", ["slow"] * 3) + sessions("soft:crowd=low", ["love"])
    assert [(p.key, p.value) for p in detect(h, CFG, TODAY)] == [("pace", "slow")]


def test_old_files_without_how_still_load():
    s = Summary.model_validate({"sid": "a", "day": "2026-10-01", "votes": {"pace": "slow"}})
    (e,) = entries([s], cfg=CFG, today=TODAY)
    assert e.evidence[0].how == "picked" and e.evidence[0].quote is None


# ---------- needs: health / body / diet the user said about themselves (owner 2026-10-28) ----------

def test_a_need_the_user_said_about_themselves_is_stored_with_their_words():
    s = put(TripState(), "signal", "vegetarian", quote="mình ăn chay trường", op="add")
    assert observe(s) == {"need:vegetarian": ("yes", "said", "mình ăn chay trường")}


def test_needs_never_stored_from_guesses_the_app_others_or_trip_only_kinds():
    for field_value, quote, source, tool in (
            ("knee", "mẹ mình đau gối", "user", None),            # about someone else
            ("vegetarian", "vợ mình ăn chay", "user", None),
            ("knee", "đau gối", "inferred", None),                # a guess
            ("vegetarian", None, "user", "next:strictest"),
            ("kids", "đi với con nhỏ", "user", None),             # this trip's companions
            ("elderly", "mình lớn tuổi rồi", "user", None),
            ("pregnant", "mình đang mang thai", "user", None)):   # a passing condition
        s = put(TripState(), "signal", field_value, source=source, quote=quote, tool=tool, op="add")
        assert observe(s) == {}, (field_value, quote, tool)


def test_a_said_need_is_active_at_once_and_reads_as_the_users_words():
    h = [Summary(sid="a", day=TODAY, votes={"need:knee": "yes"}, how={"need:knee": "said"},
                 quotes={"need:knee": "mình bị đau gối"})]
    (e,) = entries(h, cfg=CFG, today=TODAY)
    assert (e.kind, e.status, e.used) == ("need", "active", True)
    assert e.statement == "Bạn từng nói: “mình bị đau gối”"


NEED_HISTORY = {"vegetarian": "mình ăn chay", "knee": "mình đau gối"}


def _seeded(catalog, kind):
    from trip.domain.patterns import seed
    h = [Summary(sid="a", day=TODAY, votes={f"need:{kind}": "yes"}, how={f"need:{kind}": "said"},
                 quotes={f"need:{kind}": NEED_HISTORY.get(kind, "x")})]
    return seed(TripState(), detect(h, CFG, TODAY), catalog, CFG)


def test_a_stored_need_is_a_silent_soft_prior_never_a_constraint(catalog):
    for kind, keys in (("vegetarian", {"vegetarian_options=yes": "love"}),
                       ("vegan", {"vegan_options=yes": "love"}),
                       ("knee", {"steep_or_stairs=present": "avoid", "long_walk=present": "avoid"})):
        s = _seeded(catalog, kind)
        assert s.signals == () and s.hard == () and s.care.value is None, kind
        assert {k: f.value for k, f in s.soft.items()} == keys, kind
        assert all(f.source == "profile" and f.evidence[0].tool == f"profile:need:{kind}" for f in s.soft.values())
        assert f"need:{kind}" in s.meta.prior


def test_a_need_with_no_ontology_feature_stays_in_the_profile_only(catalog):
    for kind in ("wheelchair", "motion_sick", "height"):
        s = _seeded(catalog, kind)
        assert s.soft == {} and s.signals == () and s.hard == () and f"need:{kind}" in s.meta.prior


def test_no_card_asks_the_stored_need_back(catalog, cfg):
    from trip.domain.deck import confirm_tabs
    s = _seeded(catalog, "vegetarian")
    assert not [t for t in confirm_tabs(s, catalog, cfg) if "need" in t.qid]


def test_this_trip_wins_over_a_stored_need(catalog):
    s = _seeded(catalog, "knee")
    s = put(s, "soft", ("steep_or_stairs=present", "love"), quote="mình leo dốc được", op="add")
    assert s.soft["steep_or_stairs=present"].source == "user" and s.soft["steep_or_stairs=present"].value == "love"
    said_none = put(_seeded(catalog, "vegetarian"), "care", "none", quote="không ai cần lưu ý gì")
    from trip.domain.state import settle
    assert settle(said_none).soft == {}  # this trip says no special care: the stored need prior goes


def test_a_user_correction_of_a_stored_need_is_voted_no(catalog):
    s = _seeded(catalog, "vegetarian")
    assert "need:vegetarian" not in observe(s)  # the prior itself is no vote
    fixed = put(s, "soft", ("vegetarian_options=yes", "avoid"), quote="giờ mình ăn mặn lại rồi", op="add")
    assert observe(fixed)["need:vegetarian"] == ("no", "said", "giờ mình ăn mặn lại rồi")
    still = put(s, "soft", ("scenic_view=present", "love"), quote="thích view", op="add")
    assert "need:vegetarian" not in observe(still)


def test_a_no_vote_retires_the_old_yes_entry_and_stops_the_prior(catalog):
    h = [Summary(sid="a", day=TODAY - timedelta(days=5), votes={"need:vegetarian": "yes"}, how={"need:vegetarian": "said"},
                 quotes={"need:vegetarian": "mình ăn chay"}),
         Summary(sid="b", day=TODAY - timedelta(days=1), votes={"need:vegetarian": "no"}, how={"need:vegetarian": "said"},
                 quotes={"need:vegetarian": "giờ mình ăn mặn lại rồi"})]
    assert one(h, "need:vegetarian", "yes").status == "weak"
    assert [p for p in detect(h, CFG, TODAY) if p.value == "yes"] == []


def test_a_stored_need_reaches_decision_marked_as_a_profile_prior(catalog):
    from trip.domain.compile import compile_search_input
    si = compile_search_input(_seeded(catalog, "vegetarian"))
    (w,) = [w for w in si.soft_weights if w.feature == "vegetarian_options"]
    assert (w.value, w.weight, w.source) == ("yes", 1, "profile") and si.hard_filters == ()


def test_a_corrected_need_reads_as_no_longer_not_as_a_need():
    h = [Summary(sid="b", day=TODAY, votes={"need:vegetarian": "no"}, how={"need:vegetarian": "said"},
                 quotes={"need:vegetarian": "giờ mình ăn mặn lại rồi"})]
    assert one(h, "need:vegetarian", "no").statement == "Không còn: ăn chay. Bạn nói: “giờ mình ăn mặn lại rồi”"
