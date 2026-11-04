"""Every selectable motive has an explicit include/exclude/example contract."""
from corpus.tags import config
from corpus.tags.offline import definition


def test_judge_uses_specific_category_and_dish_boundaries():
    museum = definition({"tag": "category:museum"})
    assert "di tích" in museum["include"].lower()
    tour = definition({"tag": "category:tour"})
    assert "đại lý" in tour["exclude"].lower()
    grilled = definition({"tag": "dish:nuong"})
    assert "thịt" in grilled["include"].lower()
    assert "bánh" in grilled["exclude"].lower()


def test_every_selectable_tag_has_configured_motive_boundaries():
    cfg = config()
    refs = ([f"category:{k}" for k in cfg["categories"]]
            + [f"dish:{d['id']}" for d in cfg["dishes"]]
            + [f"style:{s}" for s in ("retro", "retro_saigon", "vintage_junk", "french_colonial", "indochine",
                                             "minimal", "industrial", "rustic", "korean", "japanese", "boho", "greenhouse")])
    for ref in refs:
        assert all(cfg["definitions"].get(ref, {}).get(k) for k in ("include", "exclude", "example")), ref
