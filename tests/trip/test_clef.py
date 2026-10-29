import json

import pytest

from trip.infrastructure import clef
from trip.infrastructure.settings import Settings


class Response:
    def __init__(self, answers, body=None):
        self.body = json.dumps(body or {"result": {"answers": answers}}).encode()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self, *a):
        return self.body


def answer(name, choice, p):
    return {"name": name, "choice": choice, "probabilities": {choice: p}}


@pytest.fixture
def cloudflare(monkeypatch):
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "t")
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acc")
    monkeypatch.setattr(clef, "load_dotenv", lambda *_: None)
    for name in ("CLEF_TIMEOUT_S", "CLEF_MODEL", "CLEF_MODEL_ID", "CLEF_BASE_URL", "CLEF_API_KEY"):  # the developer's .env may set these
        monkeypatch.delenv(name, raising=False)


def fake(monkeypatch, answers, seen=None):
    def urlopen(request, timeout):
        if seen is not None:
            seen.append((request, timeout))
        return Response(answers)
    monkeypatch.setattr(clef.urllib.request, "urlopen", urlopen)


def test_judge_vetoes_only_when_sure_and_never_when_clef_is_down(cloudflare, monkeypatch):
    j = clef.Judge(Settings())
    fake(monkeypatch, [answer(clef.SUPPORT, "B", 0.95)])
    assert j.unsupported("yên tĩnh", "khách muốn: x")
    fake(monkeypatch, [answer(clef.SUPPORT, "B", 0.7)])
    assert not j.unsupported("yên tĩnh", "khách muốn: x")
    fake(monkeypatch, [answer(clef.PROMISE, "A", 0.95), answer(clef.INVENT, "B", 0.9)])
    assert j.bad_reply("Mình sẽ gợi ý ngay") == "promises results"
    fake(monkeypatch, [answer(clef.PROMISE, "B", 0.99), answer(clef.INVENT, "A", 0.95)])
    assert j.bad_reply("Quán mở đến 22h") == "states a fact nobody gave"
    monkeypatch.delenv("CLOUDFLARE_API_TOKEN")
    assert not j.unsupported("x", "y") and j.bad_reply("x") is None


def test_judge_ranks_features_by_probability(cloudflare, monkeypatch):
    from trip.domain.state import ontology
    feats = list(ontology().features.values())[:3]
    ids = [f.id for f in feats]
    fake(monkeypatch, [{"name": clef.FEATURE, "choice": ids[1], "probabilities": {ids[0]: 0.1, ids[1]: 0.6, ids[2]: 0.3, "none": 0.0}}])
    assert clef.Judge(Settings()).features("view núi", feats) == [ids[1]]  # 0.3 and 0.1 are below clef_feature_min


def test_judge_asks_clef_only_the_closest_features(cloudflare, monkeypatch):
    """The self-hosted Clef runs out of GPU memory on all ~70 features in one prompt: the embedder keeps the pool."""
    import numpy as np
    from trip.domain.state import ontology
    feats = list(ontology().features.values())[:4]
    vec = {f"{f.id}: {f.hint}": np.eye(4)[i] for i, f in enumerate(feats)} | {"view núi": np.array([0, .9, 0, .5])}
    monkeypatch.setattr(clef, "embed", lambda texts: np.stack([vec[t] for t in texts]))
    seen = []
    fake(monkeypatch, [{"name": clef.FEATURE, "choice": feats[1].id, "probabilities": {feats[1].id: 0.8}}], seen)
    assert clef.Judge(Settings(clef_feature_pool=2)).features("view núi", feats) == [feats[1].id]
    asked = json.loads(seen[0][0].data)["questions"][clef.FEATURE]["criteria"]
    assert set(asked) == {feats[1].id, feats[3].id, clef.NONE}


def test_judge_ranks_nothing_when_the_embedder_is_down(cloudflare, monkeypatch):
    from trip.domain.state import ontology
    def down(texts):
        raise RuntimeError("no GPU")
    monkeypatch.setattr(clef, "embed", down)
    seen = []
    fake(monkeypatch, [], seen)
    assert clef.Judge(Settings(clef_feature_pool=2)).features("view núi", list(ontology().features.values())) == []
    assert not seen  # a prompt over the pool is never sent: it would only run Clef out of memory


def test_self_hosted_clef_is_used_when_base_url_is_set(cloudflare, monkeypatch):
    seen = []
    body = {"systemone": {"answers": {clef.SUPPORT: {"choice": "B", "probabilities": {"B": 0.95}}}}}
    monkeypatch.setattr(clef.urllib.request, "urlopen",
                        lambda request, timeout: seen.append(request) or Response(None, body))
    monkeypatch.setenv("CLEF_BASE_URL", "http://127.0.0.1:30000/v1/clef-flash")
    monkeypatch.setenv("CLEF_API_KEY", "gateway-key")
    monkeypatch.delenv("CLOUDFLARE_API_TOKEN")  # self-host needs no Cloudflare credentials
    assert clef.Judge(Settings()).unsupported("yên tĩnh", "khách muốn: x")
    assert seen[0].full_url == "http://127.0.0.1:30000/v1/clef-flash"
    assert seen[0].get_header("Authorization") == "Bearer gateway-key"
