"""Engine.effect (the report an assistant tool gets after rerank / like) must not re-read .env once per card: that made
a rerank turn 2+ s of pure file parsing. The result must equal a plain pipeline run on the same State."""

from test_decision_engine import CFG, data, trip

from corpus.crawl.common import files
from decision.engine import Engine
from decision.pipeline import run
from decision.session import Store


def test_data_dir_reads_dotenv_once(monkeypatch):
    calls = []
    files._load_env.cache_clear()
    monkeypatch.setattr(files, "load_dotenv", lambda *a, **k: calls.append(a))
    monkeypatch.setenv("DATA_DIR", "/x/one")
    assert str(files.data_dir()) == "/x/one"
    monkeypatch.setenv("DATA_DIR", "/x/two")  # the env is still read on every call
    assert str(files.data_dir()) == "/x/two"
    assert len(calls) == 1
    files._load_env.cache_clear()


def test_effect_matches_a_plain_pipeline_run():
    e = Engine(data(), CFG, Store(None))
    sid = e.create(trip())["id"]
    s = e.store.get(sid)
    before = e._result(s)
    pid = next(c["id"] for g in before.view["groups"] for c in g["cards"])
    for act in ({"type": "feedback", "reason": "crowded"}, {"type": "like", "place_id": pid}):
        new, _, _ = e._apply(s, [act], before, strict=True)
        res, eff = e.effect(s, before, new, True)
        ref = run(s.model_copy(update={"state": new}), e.data, e.cfg, {})
        assert res.view == ref.view and res.ranked == ref.ranked
        assert eff["chosen_now"] == len(ref.view["selected"])
