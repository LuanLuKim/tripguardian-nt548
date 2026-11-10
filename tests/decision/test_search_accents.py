"""Place Decision search: a place that matches the accents the user typed comes before one that matches accents aside."""

from decision import Data, Engine, Store, load_settings
from fixtures import si, srec


def engine():
    return Engine(Data([
        srec("che_plain", name="Che Garden Cafe", voices=3000),     # most reviewed, matches "chè" only accents aside
        srec("che_tea", name="Quán Chè Bà Tư", voices=10),          # accents match in the name
        srec("che_build", name="Chế Tác Gốm Cafe", voices=2000),     # "chế": another word, accents aside
    ]), load_settings(), Store(None))


def test_accent_exact_name_matches_rank_first():
    e = engine()
    sid = e.create(si().model_dump(mode="json"))["id"]
    ids = [c["id"] for c in e.search(sid, "chè")["cards"]]
    assert ids[0] == "che_tea" and set(ids) >= {"che_plain", "che_build"}


def test_typed_without_accents_prefers_the_plain_spelling():
    e = engine()
    sid = e.create(si().model_dump(mode="json"))["id"]
    assert e.search(sid, "che")["cards"][0]["id"] == "che_plain"
