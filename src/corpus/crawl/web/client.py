"""The web (one SearXNG source for corpus and Trip, docs/CORPUS.md §Nguồn; Trip: docs/TRIP_UNDERSTANDING.md §18): a
self-hosted SearXNG and a page reader. What it returns is data, never instructions and never evidence about a place.
Both calls are cached on disk; private hosts are refused."""

from __future__ import annotations

import hashlib
import html
import ipaddress
import json
import os
import re
import socket
import time
import unicodedata
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import SplitResult, urljoin, urlsplit

import httpx
import trafilatura
from pydantic import BaseModel, ConfigDict, ValidationError


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class WebHit(_Frozen):
    url: str
    title: str
    domain: str
    snippet: str
    image: str = ""  # the result's thumbnail when the search engine gives one (https only)


class WebPage(_Frozen):
    url: str
    title: str
    domain: str
    text: str
    image: str = ""  # the page's own picture (og:image) when it declares one (https only)


class SearchResult(_Frozen):
    url: str
    title: str
    snippet: str
    engines: tuple[str, ...]


class SearchPage(_Frozen):
    """Every result SearXNG returned for one query, with the engines that answered and those that did not."""
    query: str
    results: tuple[SearchResult, ...]
    unresponsive: tuple[tuple[str, str], ...] = ()
    cached: bool = False

    @property
    def blocked(self) -> bool:
        return not self.results and bool(self.unresponsive)


class WebDocument(_Frozen):
    """A page as text with its `#` headings kept (docs/CORPUS.md §Nguồn: input to local knowledge, not evidence)."""
    url: str
    title: str
    domain: str
    text: str
    chars: int
    cut: bool
    lang: str


class WebError(Exception):
    """A web request failed or its response was unsafe or unusable."""


class BudgetExhausted(WebError):
    """The day's query budget is used up; cached queries still answer."""


_USER_AGENT = "TripGuardian/1.0 (+travel planner; contact via site)"
_SPACE = re.compile(r"\s+")
_BLANKS = re.compile(r"\n{3,}")
_VI_MARKS = set("ăâđêôơưĂÂĐÊÔƠƯ")
_THIN = 3  # a SearXNG page with fewer results also asks Google through the browser


def _utc_day() -> str:
    return datetime.now(UTC).date().isoformat()


def validate_public_url(url: str) -> SplitResult:
    """Check syntax/literal hosts here; DNS is checked and pinned separately at fetch time."""
    if len(url) > 2048 or any(c.isspace() or unicodedata.category(c) in {"Cc", "Cf"} for c in url):
        raise ValueError("blocked URL")
    parsed = urlsplit(url)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname or parsed.username is not None \
            or parsed.password is not None or parsed.port not in {None, 80, 443} or "\\" in url:
        raise ValueError("blocked URL")
    host = parsed.hostname.rstrip(".").lower()
    if host == "localhost" or host.endswith((".localhost", ".local", ".internal")) or "." not in host and ":" not in host:
        raise ValueError("blocked URL")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        if not address.is_global or address.is_multicast:
            raise ValueError("blocked URL")
    return parsed


def _squash(value: str) -> str:
    return _SPACE.sub(" ", value).strip()


def _domain(url: str) -> str:
    host = urlsplit(url).hostname or ""
    return host.lower().removeprefix("www.")


class Web:
    def __init__(self, base_url: str, cache_dir: Path, timeout_s: float = 6.0, ttl_days: int = 30,
                 max_bytes: int = 2_000_000, client: httpx.Client | None = None, *, state_dir: Path | None = None,
                 daily_queries: int | None = None, min_interval_s: float = 0.0, clock=time.monotonic,
                 sleep=time.sleep, today=_utc_day, serpapi_key: str | None = None, serpapi_monthly: int = 0,
                 google=None):
        """state_dir / daily_queries / min_interval_s are the corpus crawl's: a budget per UTC day (budget.json), a
        pause between two real queries and an engine log (engines.jsonl). serpapi_key / serpapi_monthly: SerpApi
        answers a query only when every SearXNG engine is blocked, at most serpapi_monthly a UTC month
        (serpapi.json). google: query -> SearchPage (Google through the browser, corpus.crawl.gsearch), asked when the
        SearXNG page is blocked or has fewer than 3 results; SerpApi then only when both are blocked. Trip passes none
        of them."""
        self.google = google
        self.serpapi_key = serpapi_key or None
        self.serpapi_monthly = serpapi_monthly
        self.state_dir = Path(state_dir) if state_dir is not None else None
        self.daily_queries = daily_queries
        self.min_interval_s = min_interval_s
        self._clock, self._sleep, self._today = clock, sleep, today
        self._last_end: float | None = None
        self.base_url = base_url.rstrip("/")
        self.cache_dir = Path(cache_dir)
        self.timeout_s = timeout_s
        self.ttl_s = ttl_days * 86400
        self.max_bytes = max_bytes
        self.client = client or httpx.Client(timeout=timeout_s, headers={"User-Agent": _USER_AGENT},
                                             follow_redirects=False, trust_env=False)

    @classmethod
    def from_config(cls, cfg_web: dict, root: Path, client: httpx.Client | None = None,
                    city: str | None = None) -> "Web":
        """config/queries.yaml `web:` block; root = data_dir()/"web" (cache in root/cache, budget and log in root).
        city: the corpus crawl's city; with it, thin or blocked pages also ask Google through the browser."""
        root = Path(root)
        google = None
        if city is not None:
            def google(query: str) -> SearchPage:
                from .. import gsearch  # lazy: gsearch imports this module
                return gsearch.search_pages([query], city, pages=1)[0]
        return cls(cfg_web["base_url"], root / "cache", timeout_s=float(cfg_web.get("timeout_s", 10.0)),
                   ttl_days=int(cfg_web.get("cache_ttl_days", 30)), client=client, state_dir=root,
                   daily_queries=cfg_web.get("daily_queries"), min_interval_s=float(cfg_web.get("min_interval_s", 0.0)),
                   serpapi_key=os.environ.get("SerpAPI_API_KEY", "").strip().strip('"') or None,
                   serpapi_monthly=int(cfg_web.get("serpapi_monthly", 0)), google=google)

    def _budget(self) -> dict:
        day = self._today()
        try:
            item = json.loads((self.state_dir / "budget.json").read_text(encoding="utf-8"))
            if item.get("day") == day:
                return {"day": day, "used": int(item.get("used", 0))}
        except (OSError, ValueError, TypeError, AttributeError):
            pass
        return {"day": day, "used": 0}

    def budget_left(self) -> int | None:
        if self.daily_queries is None or self.state_dir is None:
            return None
        return max(0, self.daily_queries - self._budget()["used"])

    def _write_state(self, name: str, text: str, append: bool = False) -> None:
        path = self.state_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if append:
            with path.open("a", encoding="utf-8") as f:
                f.write(text)
            return
        temp = path.with_name(path.name + f".{os.getpid()}.{time.time_ns()}.tmp")
        temp.write_text(text, encoding="utf-8")
        os.replace(temp, path)

    def _spend(self) -> None:
        """Before a real query: refuse past the budget, pause, count the query (a timeout counts: the engines ran)."""
        if self.daily_queries is not None and self.state_dir is not None:
            budget = self._budget()
            if budget["used"] >= self.daily_queries:
                raise BudgetExhausted(f"daily query budget used up ({budget['used']}/{self.daily_queries})")
        if self.min_interval_s > 0 and self._last_end is not None:
            wait = self.min_interval_s - (self._clock() - self._last_end)
            if wait > 0:
                self._sleep(wait)
        if self.daily_queries is not None and self.state_dir is not None:
            budget["used"] += 1
            self._write_state("budget.json", json.dumps(budget))

    def _log_engines(self, row: dict) -> None:
        if self.state_dir is not None:
            self._write_state("engines.jsonl", json.dumps({"at": datetime.now(UTC).isoformat(timespec="seconds"),
                                                           **row}, ensure_ascii=False) + "\n", append=True)

    def _cache_path(self, kind: str, key: str) -> Path:
        digest = hashlib.sha256((kind + key).encode("utf-8")).hexdigest()[:24]
        return self.cache_dir / f"{digest}.json"

    def _cached(self, kind: str, key: str):
        try:
            item = json.loads(self._cache_path(kind, key).read_text(encoding="utf-8"))
            age = time.time() - float(item["fetched_at"])
            if 0 <= age <= self.ttl_s:
                return item["value"]
        except (OSError, ValueError, TypeError, KeyError):
            pass
        return None

    def _store(self, kind: str, key: str, value) -> None:
        path = self._cache_path(kind, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_name(path.name + f".{os.getpid()}.{time.time_ns()}.tmp")
        try:
            temp.write_text(json.dumps({"fetched_at": time.time(), "value": value}, ensure_ascii=False),
                            encoding="utf-8")
            os.replace(temp, path)
        finally:
            try:
                temp.unlink()
            except FileNotFoundError:
                pass

    def _get(self, url: str, params: dict | None = None, *, check_host: bool = False,
             limit: int | None = None) -> tuple[str, str, str, bytes]:
        """-> (final url, content type, encoding, body read up to `limit` bytes). Redirects are followed by hand (at
        most 3), each target checked again when check_host."""
        current = url
        deadline = time.monotonic() + self.timeout_s
        for redirects in range(4):
            headers = {"User-Agent": _USER_AGENT}
            extensions = {}
            target = current
            if check_host:
                address = self._check_url(current)
                parsed = urlsplit(current)
                original = httpx.URL(current)
                target = original.copy_with(host=address)
                headers.update({"Host": original.netloc.decode("ascii"), "Connection": "close"})
                extensions["sni_hostname"] = parsed.hostname
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise WebError("web request timed out")
            try:
                with self.client.stream("GET", target, params=params if redirects == 0 else None,
                                        timeout=remaining, headers=headers, extensions=extensions,
                                        follow_redirects=False) as response:
                    if response.status_code in (301, 302, 303, 307, 308):
                        location = response.headers.get("location")
                        if not location:
                            raise WebError("redirect without a location")
                        current = urljoin(current, location)
                        continue
                    response.raise_for_status()
                    body = bytearray()
                    for chunk in response.iter_bytes():
                        if time.monotonic() >= deadline:
                            raise WebError("web request timed out")
                        room = (limit or self.max_bytes) - len(body)
                        body.extend(chunk[:room])
                        if len(body) >= (limit or self.max_bytes):
                            break
                    return (current if check_host else str(response.url), response.headers.get("content-type", ""),
                            response.encoding or "utf-8", bytes(body))
            except httpx.TimeoutException as exc:
                raise WebError("web request timed out") from exc
            except httpx.HTTPError as exc:
                raise WebError("web request failed") from exc
        raise WebError("too many redirects")

    def search(self, query: str, k: int = 5, per_domain: int = 1) -> list[WebHit]:
        """The first `k` results, at most `per_domain` from one site (a news roundup and a social post of the same site
        can both carry what is asked)."""
        query = query.strip()
        if not 1 <= len(query) <= 200:
            raise ValueError("query must contain 1 to 200 characters")
        key = json.dumps([query, k] if per_domain == 1 else [query, k, per_domain], ensure_ascii=False)
        cached = self._cached("search", key)
        if cached is not None:
            try:
                return [WebHit.model_validate(row) for row in cached]
            except (ValidationError, TypeError):
                pass
        _, _, _, body = self._get(self.base_url + "/search", {
            "q": query, "format": "json", "language": "vi-VN", "safesearch": 1,
        })
        try:
            payload = json.loads(body)
        except ValueError as exc:
            raise WebError("invalid search response") from exc
        results = payload.get("results") if isinstance(payload, dict) else None
        if not isinstance(results, list):
            raise WebError("invalid search response")
        hits, seen_urls, seen_domains = [], set(), {}
        for result in results:
            if not isinstance(result, dict):
                continue
            url = result.get("url")
            if not isinstance(url, str) or urlsplit(url).scheme.lower() not in ("http", "https") or not urlsplit(url).hostname:
                continue
            domain = _domain(url)
            if url in seen_urls or seen_domains.get(domain, 0) >= per_domain:
                continue
            seen_urls.add(url)
            seen_domains[domain] = seen_domains.get(domain, 0) + 1
            hits.append(WebHit(url=url, title=_squash(str(result.get("title") or "")), domain=domain,
                               snippet=_squash(str(result.get("content") or result.get("snippet") or ""))[:300],
                               image=_https(result.get("thumbnail") or result.get("img_src"))))
            if len(hits) >= max(0, k):
                break
        self._store("search", key, [hit.model_dump() for hit in hits])
        return hits

    def images(self, query: str, k: int = 30) -> list[dict]:
        """The first `k` image results of one SearXNG query (`categories=images`), each {img_src, url, title, resolution}
        as the engines give them; the caller decides which picture stands (corpus.events.picture). An empty answer is
        not cached, so the next run asks again."""
        query = query.strip()
        if not 1 <= len(query) <= 200:
            raise ValueError("query must contain 1 to 200 characters")
        key = json.dumps([query, k], ensure_ascii=False)
        cached = self._cached("images", key)
        if isinstance(cached, list):
            return cached
        self._spend()
        try:
            _, _, _, body = self._get(self.base_url + "/search", {
                "q": query, "format": "json", "language": "vi-VN", "safesearch": 1, "categories": "images",
            })
        finally:
            self._last_end = self._clock()
        try:
            payload = json.loads(body)
        except ValueError as exc:
            raise WebError("invalid search response") from exc
        results = payload.get("results") if isinstance(payload, dict) else None
        if not isinstance(results, list):
            raise WebError("invalid search response")
        rows = [{"img_src": str(r.get("img_src") or ""), "url": str(r.get("url") or ""),
                 "title": _squash(str(r.get("title") or "")), "resolution": str(r.get("resolution") or "")}
                for r in results if isinstance(r, dict) and r.get("img_src")][:max(0, k)]
        if rows:
            self._store("images", key, rows)
        return rows

    def search_page(self, query: str) -> SearchPage:
        """Every result of one SearXNG query (no domain dedupe) with its engines. A blocked page (no result, some
        engine unresponsive) is not cached, so the next run asks again."""
        query = query.strip()
        if not 1 <= len(query) <= 200:
            raise ValueError("query must contain 1 to 200 characters")
        cached = self._cached("page", query)
        if cached is not None:
            try:
                return SearchPage.model_validate({**cached, "cached": True})
            except (ValidationError, TypeError):
                pass
        self._spend()
        try:
            _, _, _, body = self._get(self.base_url + "/search", {
                "q": query, "format": "json", "language": "vi-VN", "safesearch": 1,
            })
            try:
                payload = json.loads(body)
            except ValueError as exc:
                raise WebError("invalid search response") from exc
            results = payload.get("results") if isinstance(payload, dict) else None
            if not isinstance(results, list):
                raise WebError("invalid search response")
        except WebError as exc:
            self._log_engines({"query": query, "error": str(exc)})
            raise
        finally:
            self._last_end = self._clock()
        rows, seen = [], set()
        for result in results:
            if not isinstance(result, dict):
                continue
            url = result.get("url")
            if not isinstance(url, str) or urlsplit(url).scheme.lower() not in ("http", "https") \
                    or not urlsplit(url).hostname or url in seen:
                continue
            seen.add(url)
            engines = result.get("engines")
            engines = tuple(str(e) for e in engines) if isinstance(engines, list) else ()
            rows.append(SearchResult(url=url, title=_squash(str(result.get("title") or "")),
                                     snippet=_squash(str(result.get("content") or result.get("snippet") or ""))[:300],
                                     engines=engines))
        unresponsive = []
        for item in payload.get("unresponsive_engines") or []:
            if isinstance(item, (list, tuple)) and len(item) == 2:
                unresponsive.append((str(item[0]), str(item[1])))
        page = SearchPage(query=query, results=tuple(rows), unresponsive=tuple(unresponsive))
        extra = {}
        searx_blocked = page.blocked
        if self.google is not None and len(page.results) < _THIN:
            try:
                other = self.google(query)
            except Exception as exc:  # a browser that does not start is a blocked engine, never a failed query
                other = SearchPage(query=query, results=(), unresponsive=(("google-browser", "error"),))
                extra["fallback_error"] = f"google-browser: {type(exc).__name__}: {exc}"[:300]
            if other.results:
                page = page.model_copy(update={"results": _merge(page.results, other.results)})
                extra["fallback"] = "google-browser"
            else:
                page = page.model_copy(update={"unresponsive": page.unresponsive + tuple(other.unresponsive)})
        if searx_blocked and not page.results and self._serpapi_left() > 0:
            try:
                page = page.model_copy(update={"results": self._serpapi(query)})
                extra["fallback"] = "serpapi"
            except WebError as exc:
                extra["fallback_error"] = "; ".join(filter(None, [extra.get("fallback_error"), f"serpapi: {exc}"]))
        counts: dict[str, int] = {}
        for row in page.results:
            for engine in row.engines:
                counts[engine] = counts.get(engine, 0) + 1
        self._log_engines({"query": query, "n": len(page.results), "engines": counts,
                           "unresponsive": [list(u) for u in unresponsive], **extra})
        if not page.blocked:
            self._store("page", query, page.model_dump(mode="json", exclude={"cached"}))
        return page

    def _serpapi_left(self) -> int:
        if not self.serpapi_key or self.state_dir is None or self.serpapi_monthly <= 0:
            return 0
        month = self._today()[:7]
        try:
            item = json.loads((self.state_dir / "serpapi.json").read_text(encoding="utf-8"))
            used = int(item.get("used", 0)) if item.get("month") == month else 0
        except (OSError, ValueError, TypeError, AttributeError):
            used = 0
        return max(0, self.serpapi_monthly - used)

    def _serpapi(self, query: str) -> tuple[SearchResult, ...]:
        """Google results through SerpApi; a call counts against the month even when it fails. The key never reaches
        an error message or a log."""
        month = self._today()[:7]
        used = self.serpapi_monthly - self._serpapi_left()
        self._write_state("serpapi.json", json.dumps({"month": month, "used": used + 1}))
        _, _, _, body = self._get("https://serpapi.com/search.json", {
            "engine": "google", "q": query, "hl": "vi", "gl": "vn", "num": 20, "api_key": self.serpapi_key,
        })
        try:
            payload = json.loads(body)
        except ValueError as exc:
            raise WebError("invalid serpapi response") from exc
        organic = payload.get("organic_results") if isinstance(payload, dict) else None
        if not isinstance(organic, list):
            raise WebError("invalid serpapi response")
        out, seen = [], set()
        for item in organic:
            url = item.get("link") if isinstance(item, dict) else None
            if not isinstance(url, str) or urlsplit(url).scheme.lower() not in ("http", "https") \
                    or not urlsplit(url).hostname or url in seen:
                continue
            seen.add(url)
            out.append(SearchResult(url=url, title=_squash(str(item.get("title") or "")),
                                    snippet=_squash(str(item.get("snippet") or ""))[:300], engines=("serpapi",)))
        return tuple(out)

    def _check_url(self, url: str) -> str:
        try:
            parsed = validate_public_url(url)
        except ValueError as exc:
            raise WebError("blocked URL") from exc
        host = parsed.hostname.rstrip(".").lower()
        try:
            literal = ipaddress.ip_address(host)
        except ValueError:
            literal = None
        if literal is not None:
            return str(literal)
        try:
            records = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
        except (OSError, ValueError) as exc:
            raise WebError("could not resolve URL host") from exc
        addresses = []
        for record in records:
            try:
                address = ipaddress.ip_address(record[4][0].split("%", 1)[0])
            except ValueError:
                raise WebError("invalid resolved address")
            if not address.is_global or address.is_multicast:
                raise WebError("blocked URL")
            addresses.append(str(address))
        if not addresses:
            raise WebError("could not resolve URL host")
        return addresses[0]

    def read(self, url: str, max_chars: int = 6000) -> WebPage:
        self._check_url(url)
        key = json.dumps([url, max_chars, self.max_bytes], ensure_ascii=False)
        cached = self._cached("read", key)
        if cached is not None:
            try:
                return WebPage.model_validate(cached)
            except (ValidationError, TypeError):
                pass
        final, media_type, content = self._fetch_page(url)
        title, image = "", ""
        if media_type == "text/html":
            extracted = trafilatura.extract(content, include_comments=False, include_tables=False)
            title = _page_title(content)
            image = _https(getattr(trafilatura.extract_metadata(content), "image", None))
            text = _squash(extracted or "")
        else:
            text = _squash(content)
        if not text:
            raise WebError("empty page")
        page = WebPage(url=final, title=title, domain=_domain(final), text=text[:max_chars], image=image)
        self._store("read", key, page.model_dump())
        return page

    def _fetch_page(self, url: str) -> tuple[str, str, str]:
        """-> (final url, media type, decoded content) of an HTML or plain-text page."""
        final, ctype, encoding, body = self._get(url, check_host=True)
        media_type = ctype.split(";", 1)[0].strip().lower()
        if media_type not in ("text/html", "text/plain"):
            raise WebError("unsupported content type")
        return final, media_type, body.decode(encoding, errors="replace")

    def read_document(self, url: str, max_chars: int = 40_000) -> WebDocument:
        """A page as text that keeps its headings as `#` lines; `chars` is the length before the cut."""
        self._check_url(url)
        key = json.dumps([url, max_chars, self.max_bytes], ensure_ascii=False)
        cached = self._cached("doc", key)
        if cached is not None:
            try:
                return WebDocument.model_validate(cached)
            except (ValidationError, TypeError):
                pass
        final, media_type, content = self._fetch_page(url)
        title = ""
        if media_type == "text/html":
            text = trafilatura.extract(content, output_format="txt", include_formatting=True,
                                       include_comments=False, include_tables=False) or ""
            title = _page_title(content)
        else:
            text = content
        text = _BLANKS.sub("\n\n", "\n".join(line.rstrip() for line in text.splitlines())).strip()
        if not text:
            raise WebError("empty page")
        marks = sum(c in _VI_MARKS for c in text)
        doc = WebDocument(url=final, title=title, domain=_domain(final), text=text[:max_chars], chars=len(text),
                          cut=len(text) > max_chars, lang="vi" if marks >= 0.01 * len(text) else "und")
        self._store("doc", key, doc.model_dump())
        return doc


def _merge(first: tuple[SearchResult, ...], second: tuple[SearchResult, ...]) -> tuple[SearchResult, ...]:
    """first in its order, then second's new URLs; a URL in both carries both engine lists."""
    rows = {r.url: r for r in first}
    for r in second:
        if r.url in rows:
            old = rows[r.url]
            rows[r.url] = old.model_copy(update={"engines": old.engines + tuple(e for e in r.engines
                                                                               if e not in old.engines)})
        else:
            rows[r.url] = r
    return tuple(rows.values())


def _https(url) -> str:
    """An absolute https picture URL, else "" (a page served over https may not show an http picture)."""
    url = str(url or "").strip()
    return url if url.lower().startswith("https://") and urlsplit(url).hostname and len(url) <= 2000 else ""


def _page_title(content: str) -> str:
    metadata = trafilatura.extract_metadata(content)
    title = _squash(metadata.title or "") if metadata else ""
    if not title:
        match = re.search(r"<title\b[^>]*>(.*?)</title\s*>", content, flags=re.I | re.S)
        if match:
            title = _squash(html.unescape(re.sub(r"<[^>]+>", " ", match.group(1))))
    return title
