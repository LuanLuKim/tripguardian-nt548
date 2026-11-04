import pytest

from harness import Harness, Request, Store
from test_dispatch import Tools


def bundle():
    return {stage: Tools(stage) for stage in ("trip", "decision", "planning")}


def send(harness, view, operation, request_id):
    return harness.request(view["id"], Request(stage=view["stage"], operation=operation,
                           expected_revision=view["revision"], request_id=request_id))


def test_journey_pins_all_handoffs_and_restore_to_its_release(tmp_path):
    from corpus.releases import Binding
    old, new = Binding(release_id="r-old", region="dalat"), Binding(release_id="r-new", region="dalat")
    bundles = {"r-old": bundle(), "r-new": bundle()}
    opened = []

    def factory(binding):
        opened.append(binding.release_id)
        return bundles[binding.release_id]

    store = Store(tmp_path)
    h = Harness(**{f"{s}_tools": t for s, t in bundles["r-old"].items()}, store=store,
                corpus_binding=old, tools_for_binding=factory)
    v = h.create()
    assert store.get(v["id"]).corpus_binding == old
    v = send(h, v, "turn", "t1")
    v = send(h, v, "advance", "d1")
    assert v["outputs"]["trip"]["corpus_binding"] == old.model_dump(mode="json")
    bundles["r-old"]["decision"].states[v["sessions"]["decision"]]["selected"] = ["keep-me"]
    h.store.save(h.store.get(v["id"]).model_copy(update={"snapshots": {**h.store.get(v["id"]).snapshots,
        "decision": bundles["r-old"]["decision"].snapshot(v["sessions"]["decision"])}}))
    # Restart with a different default. Old tools restore only from the old release.
    restored = bundle()
    bundles["r-old"] = restored
    h2 = Harness(**{f"{s}_tools": t for s, t in bundles["r-new"].items()}, store=Store(tmp_path),
                 corpus_binding=new, tools_for_binding=factory)
    loaded = h2.load(v["id"])
    assert loaded["result"]["view"]["selected"] == ["keep-me"]
    assert opened == ["r-old"]
    assert not bundles["r-new"]["decision"].states
    advanced = send(h2, loaded, "advance", "p1")
    assert advanced["outputs"]["decision"]["corpus_binding"] == old.model_dump(mode="json")
    assert len(restored["planning"].states) == 1


def test_release_cache_is_bounded_and_evicted_journey_restores_again(tmp_path):
    from corpus.releases import Binding
    active = Binding(release_id="r-active", region="dalat")
    tools = bundle()
    opened = []

    def factory(binding):
        opened.append(binding.release_id)
        return bundle()

    store = Store(tmp_path)
    h = Harness(**{f"{s}_tools": t for s, t in tools.items()}, store=store,
                corpus_binding=active, tools_for_binding=factory)
    views = []
    for name in ("r-one", "r-two", "r-three", "r-four"):
        maker = Harness(**{f"{s}_tools": t for s, t in bundle().items()}, store=store,
                        corpus_binding=Binding(release_id=name, region="dalat"))
        view = maker.create()
        views.append(view)
        assert h.load(view["id"])["id"] == view["id"]
    assert len(h._corpus_tools) <= 3
    assert h.load(views[0]["id"])["id"] == views[0]["id"]
    assert opened.count("r-one") == 2


def test_missing_pinned_release_fails_before_snapshot_restore(tmp_path):
    from corpus.releases import Binding
    tools = bundle()
    old = Binding(release_id="r-old", region="dalat")
    h = Harness(**{f"{s}_tools": t for s, t in tools.items()}, store=Store(tmp_path), corpus_binding=old)
    v = h.create()

    def missing(binding):
        raise FileNotFoundError("pinned release missing")

    current = bundle()
    restarted = Harness(**{f"{s}_tools": t for s, t in current.items()}, store=Store(tmp_path),
                        corpus_binding=Binding(release_id="r-new", region="dalat"), tools_for_binding=missing)
    with pytest.raises(FileNotFoundError, match="pinned release missing"):
        restarted.load(v["id"])
    assert not current["trip"].states


def test_legacy_journey_never_adopts_current_release(tmp_path):
    from corpus.releases import Binding
    legacy = bundle()
    h = Harness(**{f"{s}_tools": t for s, t in legacy.items()}, store=Store(tmp_path))
    v = h.create()
    current = bundle()
    opened = []

    def factory(binding):
        opened.append(binding)
        return legacy

    restarted = Harness(**{f"{s}_tools": t for s, t in current.items()}, store=Store(tmp_path),
                        corpus_binding=Binding(release_id="r-new", region="dalat"), tools_for_binding=factory)
    restarted.load(v["id"])
    assert opened == [None]
    assert restarted.store.get(v["id"]).corpus_binding is None


def test_the_sidebar_list_and_an_old_release_build_never_make_the_active_release_wait(tmp_path):
    """Cold start found 2026-10-30: /trips restored every journey, building the engines of each old release under one lock, so the
    first turn of a NEW chat waited ~75 s. A line now reads the saved copy, and a release is built under its own lock."""
    import threading
    import time
    from corpus.releases import Binding
    old, new = Binding(release_id="r-old", region="dalat"), Binding(release_id="r-new", region="dalat")
    bundles = {"r-old": bundle(), "r-new": bundle()}
    h = Harness(**{f"{s}_tools": t for s, t in bundles["r-old"].items()}, store=Store(tmp_path), corpus_binding=old)
    v = h.create(owner="a" * 32)
    v = send(h, v, "turn", "t1")
    v = send(h, v, "advance", "d1")
    gate, building = threading.Event(), threading.Event()

    def slow(binding):  # opening the old release takes as long as the test lets it
        building.set()
        gate.wait(5)
        return bundles["r-old"]

    h2 = Harness(**{f"{s}_tools": t for s, t in bundles["r-new"].items()}, store=Store(tmp_path), corpus_binding=new,
                 tools_for_binding=slow)
    lines = h2.trips("a" * 32)  # a journey of the old release: its line is read from the saved copy, nothing is opened
    assert [x["id"] for x in lines] == [v["id"]] and not building.is_set()
    opener = threading.Thread(target=lambda: h2.load(v["id"], owner="a" * 32))
    opener.start()
    assert building.wait(2)
    started = time.monotonic()
    fresh = h2.create(owner="a" * 32)  # the active release answers while the old one is still opening
    assert time.monotonic() - started < 1 and fresh["id"] != v["id"]
    gate.set()
    opener.join(5)
