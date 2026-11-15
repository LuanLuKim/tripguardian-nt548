"""Item -> the bulletin's words (docs/CORPUS.md §Nhịp). Fixed sentence templates over an item's fields; no model writes
a bulletin. Dates are absolute (dd/mm): the bulletin is a snapshot, so "3 ngày trước" would go stale in the page."""

from datetime import date

SECTIONS = (("trend", "Xu hướng"), ("hot", "Đang hot"), ("top", "Nhiều nguồn cùng nhắc"), ("event", "Sự kiện sắp tới"),
            ("season", "Mùa đang diễn ra"), ("new", "Mới xuất hiện"), ("closed", "Đã đóng cửa"))
TITLES = dict(SECTIONS)
SOURCE_WORDS = {"tiktok": "video TikTok mới", "reviews": "đánh giá Maps mới", "rating_up": "điểm Maps đang tăng", "web": "trang web nhắc"}


def dm(iso: str) -> str:
    """'2026-10-26' -> '26/10'."""
    return f"{int(iso[8:10]):02d}/{int(iso[5:7]):02d}"


def months(ms: list[int]) -> str:
    ms = sorted(ms)
    return f"tháng {ms[0]}" if len(ms) == 1 else f"tháng {ms[0]}–{ms[-1]}" if ms == list(range(ms[0], ms[-1] + 1)) else "tháng " + ", ".join(map(str, ms))


# One short phrase for the signal that lifted a place most (compute.trending `lead`); the numbers never reach the page.
TREND_LABELS = {"tiktok": "Hot trên TikTok", "tiktok_recent": "Hot tuần này", "reviews": "Khách đang đổ về",
                "rising": "Điểm đang lên", "web": "Nhiều trang nhắc"}


def _trend(i: dict) -> str:
    s = i["signals"]
    parts = [f"{s['tiktok_authors']} tác giả TikTok" if s["tiktok_authors"] else "", f"{s['review_authors']} người đánh giá Maps" if s["review_authors"] else "",
             "điểm Maps đang tăng" if s["rising"] else "", f"{s['web_domains']} trang web nhắc" if s["web_domains"] else ""]
    return f"Điểm xu hướng {s['score']}/100 · " + " · ".join(p for p in parts if p)


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


def days(start: str, end: str) -> str:
    """'13–15/11', '30/11–02/12', '19/12'."""
    if start == end:
        return dm(start)
    return f"{int(start[8:10]):02d}–{dm(end)}" if start[5:7] == end[5:7] else f"{dm(start)}–{dm(end)}"


def _event(i: dict) -> str:
    s, d = i["signals"], i["dates"]
    if s["source"] == "web":  # a dated event read from this month's pages (corpus.events)
        return " · ".join(x for x in (days(d["from"], d["to"]) + (f", {s['time']}" if s["time"] else ""), s["venue"]) if x)
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


def _short(i: dict) -> dict:
    """The rail's fields: one short signal and the numbers behind it, so the page never parses `text`.
    {signal, signal_kind, count, score, window_days, newest, on, rising, reference}; `score` = the 0-100 trend rank of a "trend" item; absent values are None / False."""
    s, kind = i["signals"], i["kind"]
    out = {"signal": "", "signal_kind": kind, "count": None, "score": None, "window_days": s.get("window_days"), "newest": None, "on": None,
           "rising": False, "reference": False}
    if kind == "trend":
        # a clip posted within the last week outranks the month's volume as the reason: "Hot tuần này"
        lead = "tiktok_recent" if s["tiktok_recent_authors"] >= 2 and s["lead"] == "tiktok" else s["lead"]
        out.update(signal=TREND_LABELS[lead], signal_kind="trend", score=s["score"], newest=s["newest"], rising=s["rising"])
    elif kind == "hot":
        out.update(signal=f"{s['videos']} clip TikTok mới", signal_kind="tiktok", count=s["videos"], newest=s["newest"])
    elif kind == "top":
        tt, rv = s.get("tiktok"), s.get("reviews")
        out["rising"] = "rating_trend" in s
        if tt:
            out.update(signal=f"{tt['videos']} clip TikTok mới", signal_kind="tiktok", count=tt["videos"], newest=tt["newest"])
        elif rv:
            out.update(signal=f"{rv['n']} đánh giá mới", signal_kind="reviews", count=rv["n"], newest=rv["newest"])
        elif out["rising"]:
            out.update(signal="Điểm Maps đang tăng", signal_kind="rising")
        else:
            out.update(signal="Nhiều trang nhắc tới", signal_kind="web")
        d = i["dates"]
        out["window_days"] = (date.fromisoformat(d["to"]) - date.fromisoformat(d["from"])).days
    elif kind == "event":
        if s["source"] == "web":
            out.update(signal=days(i["dates"]["from"], i["dates"]["to"]), signal_kind="date", on=i["dates"]["from"])
        elif s["source"] == "calendar":
            out.update(signal=dm(i["dates"]["on"]), signal_kind="date", on=i["dates"]["on"])
        else:
            out["reference"] = s["status"] not in ("kept", "confirmed")
            out.update(signal=months(s["months"]).capitalize() + (" (tham khảo)" if out["reference"] else ""), signal_kind="date")
    elif kind == "season":
        out.update(signal=f"Đang vào mùa · {months(s['months'])}", reference=s["status"] not in ("kept", "confirmed"))
    elif kind == "new":
        out.update(signal="Mới có đánh giá đầu tiên", newest=s["first_review"])
    elif kind == "closed":
        out.update(signal="Đóng cửa vĩnh viễn")
    return out


TEMPLATES = {"trend": _trend, "hot": _hot, "top": _top, "event": _event, "season": _season, "new": _new, "closed": _closed}


def item(i: dict) -> dict:
    """{id, kind, title, text, place_id, newest, sources[{type, url?, date?, label}]} of one stored item."""
    sources = []
    for e in i["evidence"]:
        label = {"tiktok_video": "Video TikTok", "web_document": e.get("domain") or "Trang web", "maps_reviews": "Đánh giá Maps",
                 "maps_rating_trend": "Xu hướng điểm Maps", "web_documents": "Trang web", "maps_status": "Google Maps",
                 "calendar": "Lịch ngày lễ"}.get(e["type"], e["type"])
        sources.append({k: v for k, v in {"type": e["type"], "label": label, "url": e.get("url"), "date": e.get("date") or e.get("to")}.items() if v})
    extra = {k: i["signals"][k] for k in ("summary", "image") if i["kind"] == "event" and i["signals"].get(k)}
    return {"id": i["id"], "kind": i["kind"], "title": i["subject"]["name"], "text": TEMPLATES[i["kind"]](i), **_short(i), **extra,
            "place_id": i["subject"]["id"] if i["subject"]["type"] == "place" and i["kind"] != "closed" else None, "sources": sources}
