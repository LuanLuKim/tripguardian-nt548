"""Google's result page (HTML) -> organic results, "Mọi người cũng hỏi" questions, a next-page flag. Pure: no browser.

Organic = links with a title (h3) inside #rso; ads (#tads, #bottomads, data-text-ad) and Google's own links (maps,
images, …) are left out, a URL seen higher on the page is not repeated. A missing snippet stays empty."""

import re
import unicodedata
from dataclasses import dataclass
from urllib.parse import parse_qs, urlsplit

import lxml.html

_CAPTCHA = re.compile(r"unusual traffic|lưu lượng truy cập bất thường", re.I)
_AD = "ancestor-or-self::*[@id='tads' or @id='tadsb' or @id='bottomads' or @data-text-ad]"
_SNIPPET = (".//*[contains(concat(' ', normalize-space(@class), ' '), ' VwiC3b ') or @data-sncf]")
_BLOCK = "ancestor::*[contains(concat(' ', normalize-space(@class), ' '), ' MjjYud ') or " \
         "contains(concat(' ', normalize-space(@class), ' '), ' g ')][1]"


@dataclass(frozen=True)
class SerpResult:
    rank: int  # 1-based on its page
    url: str
    title: str
    snippet: str


@dataclass(frozen=True)
class Serp:
    results: tuple[SerpResult, ...]
    related: tuple[str, ...]  # "People also ask" questions
    has_next: bool
    captcha: bool  # Google's /sorry/ page ("unusual traffic")


def _text(node) -> str:
    return " ".join(unicodedata.normalize("NFC", node.text_content()).split())


def _target(href: str) -> str | None:
    if href.startswith("/url?"):
        href = (parse_qs(urlsplit(href).query).get("q") or [""])[0]
    parts = urlsplit(href)
    host = (parts.hostname or "").lower()
    if parts.scheme not in ("http", "https") or not host:
        return None
    if re.fullmatch(r"(?:[\w-]+\.)*google\.[a-z.]+", host):
        return None  # Maps, images, "more results": Google's own pages, not a result
    return href


def parse(html: str) -> Serp:
    root = lxml.html.fromstring(html or "<html></html>")
    if _CAPTCHA.search(_text(root)) or root.xpath("//form[@id='captcha-form']"):
        return Serp((), (), False, True)
    rows, seen = [], set()
    for a in root.xpath("//*[@id='rso']//a[@href][.//h3]"):
        if a.xpath(_AD):
            continue
        url = _target(a.get("href", ""))
        if url is None or url in seen:
            continue
        seen.add(url)
        block = (a.xpath(_BLOCK) or [a.getparent()])[0]
        snippet = block.xpath(_SNIPPET)
        rows.append(SerpResult(rank=len(rows) + 1, url=url, title=_text(a.xpath(".//h3")[0]),
                               snippet=_text(snippet[0])[:300] if snippet else ""))
    related = []
    for q in root.xpath("//*[@id='rso']//*[@data-q]/@data-q"):
        q = " ".join(unicodedata.normalize("NFC", q).split())
        if q and q not in related:
            related.append(q)
    return Serp(tuple(rows), tuple(related), bool(root.xpath("//a[@id='pnnext']")), False)
