"""Item -> the bulletin's words (docs/CORPUS.md §Nhịp). Fixed sentence templates over an item's fields; no model writes
a bulletin. Dates are absolute (dd/mm): the bulletin is a snapshot, so "3 ngày trước" would go stale in the page."""

SECTIONS = (("hot", "Đang hot"), ("top", "Nhiều nguồn cùng nhắc"), ("event", "Sự kiện sắp tới"),
            ("season", "Mùa đang diễn ra"), ("new", "Mới xuất hiện"), ("closed", "Đã đóng cửa"))
TITLES = dict(SECTIONS)
SOURCE_WORDS = {"tiktok": "video TikTok mới", "reviews": "đánh giá Maps mới", "rating_up": "điểm Maps đang tăng", "web": "trang web nhắc"}


def dm(iso: str) -> str:
    """'2026-10-26' -> '26/10'."""
    return f"{int(iso[8:10]):02d}/{int(iso[5:7]):02d}"


def months(ms: list[int]) -> str:
    ms = sorted(ms)
    return f"tháng {ms[0]}" if len(ms) == 1 else f"tháng {ms[0]}–{ms[-1]}" if ms == list(range(ms[0], ms[-1] + 1)) else "tháng " + ", ".join(map(str, ms))


def _hot(i: dict) -> str:
    s = i["signals"]
    return f"{s['videos']} video mới trong {s['window_days']} ngày, {s['authors']} tác giả khác nhau · mới nhất {dm(s['newest'])}"


def _top(i: dict) -> str:
    s, parts = i["signals"], []
    if "tiktok" in s:
        parts.append(f"{s['tiktok']['videos']} video TikTok mới của {s['tiktok']['authors']} tác giả")
    if "reviews" in s:
        parts.append(f"{s['reviews']['n']} đánh giá Maps mới, trung bình {s['reviews']['mean_stars']:g} sao".replace(".", ","))
    if "rating_trend" in s:
        parts.append("điểm Maps đang tăng")
    if "web_domains" in s:
        parts.append(f"{len(s['web_domains'])} trang web nhắc")
    return " · ".join(parts)


def _event(i: dict) -> str:
    s, d = i["signals"], i["dates"]
    if s["source"] == "calendar":
        return f"Ngày {dm(d['on'])}"
    tag = "" if s["status"] in ("kept", "confirmed") else " (tham khảo)"
    return f"Diễn ra {months(s['months'])}{tag} · {s['sources']} nguồn"


def _season(i: dict) -> str:
    s = i["signals"]
    text = f"Đang vào mùa {i['subject']['name']} ({months(s['months'])})"
    if s.get("latest_video"):
        text += f" · video mới nhất nhắc tới {i['subject']['name']}: {dm(s['latest_video']['date'])}"
    if s["status"] not in ("kept", "confirmed"):
        text += f" · tham khảo, {s['sources']} nguồn"
    return text


def _new(i: dict) -> str:
    s = i["signals"]
    when = f"ngày {dm(s['first_review'])}" if s["exact"] else f"khoảng tháng {int(s['first_review'][5:7])}/{s['first_review'][:4]}"
    return f"Đánh giá đầu tiên trên Maps {when} · {s['reviews']} đánh giá"


def _closed(i: dict) -> str:
    s = i["signals"]
    base = f"Google Maps ghi đóng cửa vĩnh viễn (tra ngày {dm(i['dates']['checked'])})"
    return base + (" · mới thấy từ lần cập nhật này" if s.get("new_since_last") else "")


TEMPLATES = {"hot": _hot, "top": _top, "event": _event, "season": _season, "new": _new, "closed": _closed}


def item(i: dict) -> dict:
    """{id, kind, title, text, place_id, newest, sources[{type, url?, date?, label}]} of one stored item."""
    sources = []
    for e in i["evidence"]:
        label = {"tiktok_video": "Video TikTok", "web_document": e.get("domain") or "Trang web", "maps_reviews": "Đánh giá Maps",
                 "maps_rating_trend": "Xu hướng điểm Maps", "web_documents": "Trang web", "maps_status": "Google Maps",
                 "calendar": "Lịch ngày lễ"}.get(e["type"], e["type"])
        sources.append({k: v for k, v in {"type": e["type"], "label": label, "url": e.get("url"), "date": e.get("date") or e.get("to")}.items() if v})
    return {"id": i["id"], "kind": i["kind"], "title": i["subject"]["name"], "text": TEMPLATES[i["kind"]](i),
            "place_id": i["subject"]["id"] if i["subject"]["type"] == "place" and i["kind"] != "closed" else None, "sources": sources}
