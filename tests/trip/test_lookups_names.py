"""T1 / T2 (prod e2e 2026-11-03): corpus lookups on the message keep place names and kinds out of the dish."""

from types import SimpleNamespace

import pytest
from trip_fixtures import served
from trip.infrastructure.catalog import Catalog

from trip.agent import lookups


class FakeCatalog:
    """dishes(): 'bánh căn' is on a menu; 'bánh căn nhà' is in one review line; 'cà phê' is on every menu."""
    places = [SimpleNamespace(name="Bánh Căn Nhà Cổ", category="Quán ăn"), SimpleNamespace(name="Lẩu Gà Lá É Tao Ngộ 5", category="Quán ăn"),
              SimpleNamespace(name="Cafe A", category="Quán cà phê")]

    def dishes(self, query):
        from trip.domain.text import fold
        q = fold(query)
        menu = {"banh can": 6, "lau ga": 3, "ca phe": 448}
        if q in menu:
            named = {"lau ga": [{"id": "t", "name": "Lẩu Gà Lá É Tao Ngộ 5", "evidence": [{"source": "menu"}]}]}.get(q, [])
            return named + [{"id": str(i), "name": f"Quán {i}", "evidence": [{"source": "menu"}]} for i in range(menu[q] - len(named))]
        if q.startswith("banh can nha") or q.startswith("lau ga tao"):  # a review / menu line that holds the place's name
            return [{"id": "x", "evidence": [{"source": "review_order"}]}]
        return []

    def kinds(self, query):
        from trip.domain.text import squash
        return [p for p in self.places if squash(query) and f" {squash(query)} " in f" {squash(p.category)} "]


def test_a_dish_followed_by_a_street_name_is_the_dish_alone():
    out = lookups("không có gì. cho tui quán bánh căn Nhà Chung", FakeCatalog())
    assert out["dishes"] == [{"dish": "bánh căn", "places": 6, "also_named": "Nhà Chung", "dish_places_with_that_name": 0}]


def test_a_name_the_corpus_holds_is_marked_so():
    out = lookups("quán lẩu gà Tao Ngộ đóng cửa rồi", FakeCatalog())
    assert out["dishes"][0]["dish"] == "lẩu gà" and out["dishes"][0]["dish_places_with_that_name"] == 1


@pytest.mark.parametrize("dish", ["mì Quảng", "bún bò Huế", "cà phê muối", "cà phê trứng"])
def test_menu_dish_with_a_capitalised_region_is_not_split(dish):
    record = served("p1", "Quán A", {}, group="restaurant", category="Quán ăn")
    record["menu"] = {"dishes": [{"name": "Mì Quảng"}, {"name": "Bún bò Huế"},
                                  {"name": "Cà phê muối"}, {"name": "Cà phê trứng"}, {"name": "Bánh mì"}]}
    catalog = Catalog.from_records([], 1, evidence={"p1": record})
    assert lookups(dish, catalog)["dishes"] == [{"dish": dish, "places": 1}]


def test_bare_cafe_is_a_kind_of_place_not_a_dish():
    out = lookups("cà phê vắng nhìn rừng thông, không phải mấy chỗ đông", FakeCatalog())
    assert out["dishes"] == [] and out["kinds"] == [{"kind": "cà phê", "places": 1}]
