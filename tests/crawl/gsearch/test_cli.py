"""python -m corpus gsearch run --query ... | --from-file ... [--pages N]."""

import sys

import corpus.__main__ as cli
import corpus.crawl.gsearch as gsearch


def _main(monkeypatch, *argv):
    calls = []
    monkeypatch.setattr(gsearch, "run", lambda city, queries, pages=1, headed=False, account="gmaps_a":
                        calls.append((city, queries, pages, headed, account)))
    monkeypatch.setattr(sys, "argv", ["corpus", "gsearch", *argv])
    cli.main()
    return calls


def test_query_and_pages(monkeypatch):
    assert _main(monkeypatch, "run", "--query", "săn mây", "--query", "bánh căn", "--pages", "2") == \
        [("dalat", ["săn mây", "bánh căn"], 2, False, "gmaps_a")]


def test_from_file_skips_blank_and_comment_lines(monkeypatch, tmp_path):
    f = tmp_path / "q.txt"
    f.write_text("# seeds\nsăn mây\n\n bánh căn \n", encoding="utf-8")
    assert _main(monkeypatch, "run", "--from-file", str(f), "--city", "dalat", "--headed") == \
        [("dalat", ["săn mây", "bánh căn"], 1, True, "gmaps_a")]


def test_profile_picks_another_signed_in_account(monkeypatch):
    assert _main(monkeypatch, "run", "--query", "q", "--profile", "gmaps_b2") == [("dalat", ["q"], 1, False, "gmaps_b2")]


def test_login_gsearch_opens_a_search_page_for_the_person():
    from corpus.crawl.common import browser
    assert browser.LOGIN_URL["gsearch"].startswith("https://www.google.com/search?")
