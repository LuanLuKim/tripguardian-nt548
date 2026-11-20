"""Exact commands and common wishes read without the model (docs/PLACE_DECISION.md §18); any unconsumed intent remains
an LLM task. Only the general feedback acts (far, crowded, pricey) come from here: a taste ("view đẹp") is Trip's."""

import re

from trip import squash

from .guard import names_in

# words that do not change what the user asks for; any other word left over sends the message to the model
FILLER = frozenset("toi minh muon can tim kiem cho nhung cac va voi hon chut nhe nha a la thi quan noi dia diem nao nhieu "
                   "mot it hoi that rat thich uu tien thoi duoc".split())
# the model decides these: they name or reject a place, or move the trip
PLACE_VERBS = re.compile(r"\b(?:chon|them|bo|xoa|khoa|giu|loai|thay|chot|da di|di roi|den roi|toi roi|cai|thu \d+)\b")

# wish -> (regex over squashed text, the actions it is). A message made only of these (and FILLER) is answered here.
CROWD = (r"yen tinh|im lang|it dong(?: nguoi)?|vang ve|khong (?:thich )?(?:(?:quan|cho|noi) )?(?:dong|dong nguoi|on ao)|"
         r"tranh dong|do dong|bot dong|dong qua|dong nguoi qua")
PRICE = r"re|re hon|gia re|binh dan|tiet kiem|khong dat|do dat|bot dat|dat qua|gia mem"
FAR = r"gan(?: trung tam)?|gan hon|do xa|bot xa|khong xa|xa qua|it di chuyen"
POINTS_AT = re.compile(r"\b(?:dau|tien|nay|do|kia|ay|thu|cuoi|tren|duoi|giua|tab|muc|trang|hang|vua roi|truoc|sau)\b")  # "quán đầu", "nơi này"
UNDO = re.compile(r"\b(?:hoan tac|undo|quay lai nhu truoc|huy thay doi|khong phai y minh)\b")  # a change to take back: the assistant's tool, not a trip wish
QUESTION = re.compile(r"\b(?:sao|nghi|gi|tai sao|vi sao|la gi|the nao|nhu nao|bao nhieu|o dau|co nen|nen khong|co the|giai thich|so sanh|hay hon|khac nhau|cam on|xin chao)\b")


OPENS = re.compile(r"^(?:(?:toi|minh) )?chi (?:can |muon )?(?:xem|lay|hien) (?:(?:cac|nhung) )?(?:quan|cho|noi) mo (?:truoc|tu|som hon) "
                   r"(\d{1,2}) ?(?:h|gio|:| )?(?: ?(\d{2}))?(?: thoi| nhe| nha)?$")
UNFILTER = re.compile(r"^(?:(?:toi|minh) )?(?:bo|xoa|tat|huy) (?:het )?(?:bo )?loc(?: di| het| nhe| giup)?$")


def filter_command(text: str) -> tuple[list[dict], str] | None:
    """"chỉ xem quán mở trước 7h" -> a session filter, "bỏ lọc" -> remove them: the whole message, nothing else."""
    t = squash(text)
    if UNFILTER.match(t):
        return [{"type": "unfilter"}], "Mình đã bỏ lọc, danh sách hiện lại đủ."
    m = OPENS.match(t)
    if m and int(m[1]) < 24 and int(m[2] or 0) < 60:
        hhmm = f"{int(m[1]):02d}:{int(m[2] or 0):02d}"
        return [{"type": "filter", "key": "opens_by", "value": hhmm}], f"Mình chỉ hiện nơi mở cửa lúc {hhmm} hoặc sớm hơn."
    return None


def exact_command(text: str, aliases: dict[str, dict]) -> list[dict] | None:
    command, _, name = squash(text).partition(' ')
    operation = {'chon': 'select', 'them': 'select', 'bo': 'drop', 'khoa': 'lock'}.get(command)
    if not operation or not name:
        return None
    matches = {place['id'] for place in aliases.values() if squash(place['name']) == name}
    if len(matches) != 1:
        return None
    return [{'type': operation, 'place_id': next(iter(matches))}]


def common_wish(text: str, aliases: dict[str, dict]) -> tuple[list[dict], str] | None:
    """(actions, reply) when the whole message is a general wish the session profile already holds: quieter, cheaper,
    closer. None as soon as a word is left over, a place on screen is named, or the user rejects / picks."""
    t = squash(text)
    if (cmd := filter_command(text)) is not None and not any(names_in(text, a["name"]) for a in aliases.values()):
        return cmd
    if not t or len(t) > 120 or PLACE_VERBS.search(t) or any(names_in(text, a["name"]) for a in aliases.values()):
        return None
    actions: list[dict] = []
    said: list[str] = []

    def take(pattern: str, make, reply: str) -> None:
        nonlocal t
        if re.search(rf"\b(?:{pattern})\b", t):
            t = re.sub(rf"\b(?:{pattern})\b", " ", t)
            actions.extend(make)
            said.append(reply)

    take(CROWD, [{"type": "feedback", "reason": "crowded"}], "ưu tiên nơi ít đông")
    take(PRICE, [{"type": "feedback", "reason": "pricey"}], "ưu tiên nơi giá mềm hơn")
    take(FAR, [{"type": "feedback", "reason": "far"}], "ưu tiên nơi gần hơn")
    if not actions or any(w not in FILLER for w in t.split()):
        return None
    return actions, "Mình sẽ " + ", ".join(said) + "."


def general_wish(text: str, aliases: dict[str, dict]) -> bool:
    """The message names no place on screen and picks or rejects none: it is a wish about the trip, which Trip
    Understanding reads. The Decision model has nothing to add, so it is not called."""
    t = squash(text)
    if ("?" in text or QUESTION.search(t) or UNDO.search(t) or POINTS_AT.search(t) or len(t.split()) < 2 or len(t) > 240
            or PLACE_VERBS.search(t)):
        return False  # a question, a greeting or a command for the model to answer
    return not any(names_in(text, a["name"]) for a in aliases.values())


# The one chat of Lựa chọn (and the home page) has two agents behind it: Decision's acts on the lists and Trip's conversation
# (discovery, events, trends, what a place is like, dates, who goes, photos, links, stays). These words are about the lists.
LIST_WORDS = re.compile(r"\b(?:loc|bo loc|so sanh|sap xep|xep theo|chia nhom|nhom nao|danh sach|tab|hoan tac|undo|da chon|"
                        r"vi sao khong|tai sao khong|sao khong (?:co|goi y|thay)|giong (?:quan|cho|noi) (?:nay|do|kia)|"
                        r"lap lich|xep lich|chot|khoa|da di|di roi|den roi|toi roi)\b")
# "tìm thêm quán cà phê", "gợi ý thêm": more of a kind is discovery (Trip's photo cards), not a pick
DISCOVER = re.compile(r"\b(?:tim them|goi y them|kham pha|co (?:quan|cho|noi|gi) nao|nen di dau|nen an gi|o dau)\b")


# On Lịch trình the schedule's assistant answers by default (moves, adds, why, times, the places of the plan); Trip takes what is
# discovery or the city's pulse, which the schedule's tools do not hold.
PULSE = re.compile(r"\b(?:su kien|le hoi|festival|dang hot|xu huong|dao nay|mua (?:gi|hoa|nay)|vao mua|dang mua|tiktok|moi mo)\b")


def plan_route(text: str) -> str:
    """"trip" for discovery and the city's pulse (events, seasons, what is hot), else "planning". No model."""
    t = squash(text)
    return "trip" if t and (DISCOVER.search(t) or PULSE.search(t)) else "planning"


def route(text: str, aliases: dict[str, dict]) -> str:
    """"decision" when the message acts on or asks about the lists on screen (a pick, a drop, a filter, a place named or
    pointed at, why one is missing, undo); "unsure" when it has a verb about places but names or points at none ("bỏ mấy
    quán cà phê đi": the lists, or a wish about the trip?), which Clef settles; "trip" for everything else. No model."""
    t = squash(text)
    if not t:
        return "trip"
    if exact_command(text, aliases) is not None or common_wish(text, aliases) is not None or UNDO.search(t) or LIST_WORDS.search(t):
        return "decision"
    if DISCOVER.search(t) and not any(names_in(text, a["name"]) for a in aliases.values()):
        return "trip"
    if any(names_in(text, a["name"]) for a in aliases.values()):
        return "decision"
    if PLACE_VERBS.search(t):
        return "decision" if POINTS_AT.search(t) else "unsure"  # "chọn quán đầu", "bỏ nơi thứ hai" / "bỏ mấy quán cà phê"
    return "trip"
