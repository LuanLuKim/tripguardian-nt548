"""A search result's URL -> TikTok video / TikTok discover slug / document to read / dropped. Pure functions: a link is
classified by its URL only; nothing here names a place or makes evidence (docs/CORPUS.md §Nguồn)."""

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from urllib.parse import parse_qsl, unquote, urlencode, urlsplit, urlunsplit

SOCIAL = ("facebook.com", "fb.com", "fb.watch", "instagram.com", "youtube.com", "youtu.be", "twitter.com", "x.com",
          "pinterest.com", "threads.net", "threads.com", "linkedin.com", "reddit.com", "zalo.me", "lemon8-app.com",
          "t.me", "snapchat.com", "douyin.com", "bilibili.com")
OTA = ("booking.com", "agoda.com", "traveloka.com", "expedia.com", "trip.com", "tripadvisor.com", "tripadvisor.com.vn",
       "airbnb.com", "klook.com", "kkday.com", "mytour.vn", "ivivu.com", "vntrip.vn", "hotels.com", "trivago.com",
       "google.com")
FILES = (".pdf", ".jpg", ".jpeg", ".png", ".gif", ".webp", ".mp4", ".zip", ".doc", ".docx", ".xls", ".xlsx")
TRACKING = ("fbclid", "gclid")

_VIDEO = re.compile(r"^/@([A-Za-z0-9._]{1,64})/video/(\d{8,25})/?$")
_PHOTO = re.compile(r"^/@[^/]+/photo/\d+/?$")
_DISCOVER = re.compile(r"^/(?:[a-z]{2}(?:-[A-Za-z]{2})?/)?discover/([^/]+)/?$")


@dataclass(frozen=True)
class Link:
    kind: str  # "video" | "discover" | "doc" | "drop"
    url: str  # video: https://www.tiktok.com/@<author>/video/<id>; otherwise as given
    video_id: str = ""
    author: str = ""
    text: str = ""  # discover: the decoded search phrase
    reason: str = ""  # drop: "social" | "ota" | "photo" | "tiktok_other" | "file" | "invalid"


def _fold(text: str) -> str:
    s = unicodedata.normalize("NFD", text.replace("đ", "d").replace("Đ", "D"))
    return " ".join("".join(c for c in s if not unicodedata.combining(c)).lower().split())


def _on(host: str, domains: tuple[str, ...]) -> bool:
    return any(host == d or host.endswith("." + d) for d in domains)


def classify(url: str) -> Link:
    try:
        parts = urlsplit(url.strip())
        host = (parts.hostname or "").lower()
    except ValueError:
        return Link("drop", url, reason="invalid")
    if parts.scheme.lower() not in ("http", "https") or not host:
        return Link("drop", url, reason="invalid")
    path = parts.path
    if _on(host, ("tiktok.com",)):
        if m := _VIDEO.match(path):
            return Link("video", f"https://www.tiktok.com/@{m.group(1)}/video/{m.group(2)}", video_id=m.group(2),
                        author=m.group(1))
        if _PHOTO.match(path):
            return Link("drop", url, reason="photo")
        if m := _DISCOVER.match(path):
            text = unquote(m.group(1)).replace("-", " ").replace("_", " ")
            return Link("discover", url, text=" ".join(unicodedata.normalize("NFC", text).split()))
        return Link("drop", url, reason="tiktok_other")
    if path.lower().endswith(FILES):
        return Link("drop", url, reason="file")
    if _on(host, SOCIAL):
        return Link("drop", url, reason="social")
    if _on(host, OTA) and "/blog" not in path.lower():
        return Link("drop", url, reason="ota")
    return Link("doc", url)


def slug_relevant(text: str, city_name: str) -> bool:
    """The slug names the city, spaced or not ("đà lạt", "dalat")."""
    city = _fold(city_name)
    pattern = r"\b(?:" + re.escape(city) + "|" + re.escape(city.replace(" ", "")) + r")\b"
    return re.search(pattern, _fold(text)) is not None


def canonical_url(url: str) -> str:
    parts = urlsplit(url.strip())
    host = (parts.hostname or "").lower().removeprefix("www.")
    netloc = host + (f":{parts.port}" if parts.port else "")
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if not k.lower().startswith("utm_") and k.lower() not in TRACKING]
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), netloc, path, urlencode(query), ""))


def doc_id(url: str) -> str:
    return hashlib.sha1(canonical_url(url).encode("utf-8")).hexdigest()[:16]
