"""The web search phase's queries: the navigator's mining map (else fixed seeds), then TikTok discover slugs found by
earlier runs, then questions Trip could not answer (data/trip/gaps.jsonl). Duplicates go; hot groups go first."""

import hashlib
import json
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from .links import _fold

TT = "site:tiktok.com "

# (group, phrase, also a TikTok query). {city} inside a phrase is replaced in place; otherwise the city goes last.
DISC = [
    ("cafe_view", "quán cà phê view đồi thông thung lũng"),
    ("cloud", "quán cà phê săn mây"),
    ("early", "quán cà phê mở cửa sớm 6h sáng"),
    ("laptop", "quán cà phê yên tĩnh làm việc laptop"),
    ("music", "quán nhạc sống buổi tối"),
    ("veg", "quán chay ngon"),
    ("kids", "điểm tham quan cho trẻ nhỏ"),
    ("elderly", "điểm tham quan cho người lớn tuổi ít dốc"),
    ("pets", "quán cà phê cho mang thú cưng"),
    ("sunset", "chỗ ngắm hoàng hôn đẹp"),
    ("pick", "vườn dâu tự hái"),
    ("lau_ga", "lẩu gà lá é"),
    ("banh_can", "bánh căn"),
    ("xiu_mai", "bánh mì xíu mại"),
    ("parking", "quán cà phê có chỗ đỗ ô tô"),
]
GEN = [
    ("transport", "thuê xe máy giá một ngày giấy tờ", False),
    ("transport", "đèo Prenn hay đèo Mimosa lái ô tô an toàn hơn", False),
    ("transport", "gửi ô tô ở trung tâm giá bao nhiêu", False),
    ("transport", "Grab xe công nghệ đi Langbiang giá", False),
    ("transport", "từ Nha Trang lên {city} đi đường nào mất bao lâu", False),
    ("budget", "3 ngày 2 đêm cho 2 người chi phí tiết kiệm", False),
    ("stay", "nên ở khu nào yên tĩnh gần trung tâm", False),
    ("stay", "đặt phòng dịp 30/4 trước bao lâu", False),
    ("crowd", "đông nhất vào những dịp nào trong năm", False),
    ("crowd", "Langbiang ngày thường hay cuối tuần đông mấy giờ", False),
    ("safety", "chặt chém lừa khách kinh nghiệm", False),
    ("safety", "đường đèo mùa mưa sạt lở đoạn nào cần chú ý", False),
    ("health", "người bệnh tim huyết áp cần lưu ý", False),
    ("health", "bệnh viện lớn cấp cứu", False),
    ("custom", "đi chùa ăn mặc thế nào cấm chụp ảnh", False),
    ("weather", "tháng 12 ban đêm lạnh mấy độ mặc gì", False),
    ("weather", "tháng 7 mưa nhiều không đi chơi buổi nào", False),
    ("season", "hoa phượng tím nở tháng mấy", True),
    ("season", "mùa hồng chín tháng nào", True),
    ("season", "mimosa vàng tháng mấy", True),
    ("food", "ăn sáng ăn gì mấy giờ quán đông", True),
    ("food", "đặc sản mua làm quà ở đâu giá mứt atiso", True),
    ("night", "buổi tối ngoài chợ đêm đi đâu chơi", True),
    ("kids", "đi với bé 3 tuổi chuẩn bị gì nên tránh gì", True),
    ("photo", "chụp ảnh bình minh chỗ nào đẹp", True),
    ("event", "lễ hội sự kiện tháng 3", True),
    ("area", "Trại Mát Cầu Đất cách trung tâm bao xa đi chung buổi", False),
    ("plan", "một ngày Langbiang sáng chiều đồi chè Cầu Đất", False),
]


@dataclass(frozen=True)
class Query:
    text: str
    group: str  # what the query is scored by: aspect key | seed key | "slug" | "gap"
    source: str  # "mining_map" | "seed" | "slug" | "gap"


def query_hash(text: str) -> str:
    norm = " ".join(unicodedata.normalize("NFC", text).casefold().split())
    return hashlib.sha1(norm.encode("utf-8")).hexdigest()[:16]


def _with_city(phrase: str, city_name: str) -> str:
    if "{city}" in phrase:
        return phrase.replace("{city}", city_name)
    return phrase if _fold(city_name) in _fold(phrase) else f"{phrase} {city_name}"


def seed_queries(city_name: str) -> list[Query]:
    qs = [Query(f"site:tiktok.com/discover {city_name}", "discover", "seed"),
          Query(f"site:tiktok.com/discover du lịch {city_name}", "discover", "seed")]
    for group, phrase in DISC:
        text = _with_city(phrase, city_name)
        qs += [Query(text, group, "seed"), Query(TT + text, group, "seed")]
    for group, phrase, tiktok in GEN:
        text = _with_city(phrase, city_name)
        qs.append(Query(text, group, "seed"))
        if tiktok:
            qs.append(Query(TT + text, group, "seed"))
    return qs


def mining_queries(root: Path, city: str, city_name: str) -> list[Query] | None:
    """The navigator's map (P3): each aspect's queries, plus a TikTok query when its sources name tiktok. None when
    the map is missing, malformed or holds no valid query (the caller then uses the seeds)."""
    path = root / city / "navigate" / "mining_map.json"
    if not path.exists():
        return None
    try:
        aspects = json.loads(path.read_text(encoding="utf-8")).get("aspects")
    except (OSError, ValueError, AttributeError):
        aspects = None
    if not isinstance(aspects, list):
        print(f"web: {path} is not a mining_map (no aspects list); using the seed queries")
        return None
    qs = []
    for aspect in aspects:
        if not isinstance(aspect, dict) or not isinstance(aspect.get("key"), str) \
                or not isinstance(aspect.get("queries"), list):
            continue
        sources = aspect.get("sources") if isinstance(aspect.get("sources"), list) else []
        tiktok = any(isinstance(s, str) and s.lower() == "tiktok" for s in sources)
        for raw in aspect["queries"]:
            if not isinstance(raw, str) or not 1 <= len(raw.strip()) <= 200:
                continue
            text = _with_city(raw.strip(), city_name)
            qs.append(Query(text, aspect["key"], "mining_map"))
            if tiktok:
                qs.append(Query(TT + text, aspect["key"], "mining_map"))
    return [q for q in qs if len(q.text) <= 200] or None


def _jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def slug_queries(web_root: Path, city: str, limit: int) -> list[Query]:
    """TikTok discover slugs found earlier (discover_slugs.jsonl), each once: a slug whose query has a search file is
    done."""
    qs = []
    for row in _jsonl(web_root / "discover_slugs.jsonl"):
        text = row.get("text")
        if not isinstance(text, str) or not text.strip():
            continue
        q = Query(TT + text.strip(), "slug", "slug")
        if len(q.text) > 200 or (web_root / "search" / f"{query_hash(q.text)}.json").exists():
            continue
        qs.append(q)
        if len(qs) >= limit:
            break
    return qs


def gap_queries(trip_gaps: Path, city_name: str, limit: int) -> list[Query]:
    """Questions Trip had no data for, most asked first."""
    rows = [r for r in _jsonl(trip_gaps) if r.get("kind") == "no_data" and isinstance(r.get("phrase"), str)
            and 1 <= len(r["phrase"].strip()) <= 120]
    rows.sort(key=lambda r: -(r.get("count") if isinstance(r.get("count"), int) else 0))
    return [Query(f"{r['phrase'].strip()} {city_name}", "gap", "gap") for r in rows[:limit]]


def plan(city: str, city_name: str, cfg_web: dict, root: Path, hot: set[str] = frozenset()) -> list[Query]:
    """root = data_dir(). Mining map (else seeds), then slugs, then gaps; one query per hash; hot groups first."""
    qs = mining_queries(root, city, city_name) or seed_queries(city_name)
    qs += slug_queries(root / "web" / city, city, int(cfg_web.get("slug_queries_per_run", 25)))
    qs += gap_queries(root / "trip" / "gaps.jsonl", city_name, int(cfg_web.get("gap_queries_per_run", 20)))
    seen, out = set(), []
    for q in qs:
        h = query_hash(q.text)
        if h not in seen:
            seen.add(h)
            out.append(q)
    return sorted(out, key=lambda q: q.group not in hot)
