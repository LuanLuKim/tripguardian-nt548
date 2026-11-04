"""Unchanged inputs reuse Decision work; source and input changes invalidate it."""
from unittest.mock import Mock

from fixtures import si, srec
from decision import Data, Engine, Store, Tools, load_settings, run_pipeline
from decision import pipeline
from decision.session import Session

CFG = load_settings()


def test_unchanged_pipeline_does_not_rediversify(monkeypatch):
    data = Data([srec("a"), srec("b")])
    session, memo = Session(id="0123456789ab", search_input=si()), {}
    pick = Mock(wraps=pipeline.pick)
    monkeypatch.setattr(pipeline, "pick", pick)
    first = run_pipeline(session, data, CFG, memo)
    calls = pick.call_count
    assert run_pipeline(session, data, CFG, memo).view == first.view
    assert pick.call_count == calls
    session.state.selected.append("a")
    assert run_pipeline(session, data, CFG, memo).view["selected"] == ["a"]
    assert pick.call_count > calls


def test_restore_and_rebase_unchanged_input_keep_result_identity():
    e = Engine(Data([srec("a"), srec("b")]), CFG, Store(None))
    tools = Tools(e)
    inp = si().model_dump(mode="json")
    sid = tools.create({"search_input": inp})["id"]
    result = e._results[sid]
    tools.restore(tools.snapshot(sid))
    assert e.load(sid)["view"] is result.view
    assert tools.rebase(sid, {"search_input": inp})["view"] is result.view
    changed = si(excluded_places=[{"place_id": "b", "name": "b", "source": "user"}]).model_dump(mode="json")
    assert "b" not in tools.rebase(sid, {"search_input": changed})["view"]["shortlist"]


def test_name_search_does_not_materialize_nonmatching_candidates(monkeypatch):
    e = Engine(Data([srec("a", name="Quán Riêng"), srec("b", name="Quán Khác")]), CFG, Store(None))
    sid = e.create(si().model_dump(mode="json"))["id"]
    e._results[sid].cands._made.clear()
    score = Mock(wraps=pipeline.score)
    monkeypatch.setattr(pipeline, "score", score)
    assert e.search(sid, "Riêng")["cards"][0]["id"] == "a"
    assert score.call_count == 1


def test_frame_memo_invalidates_when_source_region_changes():
    session, memo = Session(id="0123456789ab", search_input=si()), {}
    run_pipeline(session, Data([srec("a")]), CFG, memo)
    other = run_pipeline(session, Data([srec("b"), srec("c")]), CFG, memo)
    assert set(other.view["shortlist"]) == {"b", "c"}
