from corpus.observe.gmaps import dish_check as d


def obs(quote, value="bò né"):
    return {"span": {"quote": quote}, "value": value}


def test_quote_must_be_exact_review_words():
    passage = "Quán đẹp.  Mình gọi bò né ăn rất ngon"
    assert d.pre_check(obs("mình gọi bò né"), passage) is None
    assert d.pre_check(obs("mình gọi bò né ngon lắm"), passage) == "quote_not_in_review"


def test_quote_must_name_the_dish_as_words():
    passage = "mình gọi bò né ăn rất ngon"
    assert d.pre_check(obs("mình gọi bò né", "bánh mì"), passage) == "quote_lacks_dish"
    assert d.pre_check(obs("mình gọi bò né", "Bo Ne"), passage) is None  # accents folded


def test_collect_keeps_only_serves_and_counts_authors():
    checks = {"1": {"dish": "Bò né", "quote": "gọi bò né ăn ngon lắm", "author": "a", "verdict": "serves"},
              "2": {"dish": "bò né", "quote": "bò né", "author": "b", "verdict": "serves"},
              "3": {"dish": "pizza", "quote": "bạn thích pizza", "author": "c", "verdict": "unsure"},
              "4": {"dish": "phở", "quote": "ăn phở", "author": "c", "verdict": "quote_lacks_dish"}}
    got = d.collect(checks)
    assert [(x["dish"], x["n"], x["quote"]) for x in got] == [("Bò né", 2, "bò né")]
