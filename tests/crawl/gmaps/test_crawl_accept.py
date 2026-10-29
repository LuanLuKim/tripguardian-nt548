from corpus.crawl.gmaps.crawl import too_few

CFG = {"max_reviews_per_place": 5000, "min_reviews_per_place": 40, "accept_reviews": 200}


def test_a_blocked_page_with_a_handful_of_reviews_is_too_few():
    assert too_few(8, "3.413 bài đánh giá", CFG, False)


def test_maps_own_stop_on_a_popular_place_is_taken_whole():
    assert not too_few(490, "2.487 bài đánh giá", CFG, False)
    assert not too_few(1090, "11.797 bài đánh giá", CFG, False)


def test_without_accept_reviews_the_half_rule_still_holds():
    assert too_few(490, "2.487 bài đánh giá", {**CFG, "accept_reviews": 0}, False)


def test_a_small_place_needs_half_of_what_it_shows():
    assert too_few(10, "100 bài đánh giá", CFG, False)
    assert not too_few(60, "100 bài đánh giá", CFG, False)
