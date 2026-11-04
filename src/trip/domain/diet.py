"""Resolve explicit day-scoped diets without turning them into whole-trip filters."""
import re
from datetime import date, timedelta

from .state import DietDay, DietRequest, Evidence, TripState
from .text import fold

DIET = re.compile(r"\b(an chay|chay truong|thuan chay|vegan)\b")
DAY = re.compile(r"\bngay\s+(?:thu\s+)?(\d{1,2})(?:/(\d{1,2})(?:/(\d{4}))?)?\b")
LUNAR = re.compile(r"\b(ram|mung mot|mong mot|am lich)\b")


def _subject(raw):
    low = fold(raw)
    if re.search(r"\b(ca nhom|ca nha|tat ca|moi nguoi)\b", low):
        return "group", None
    if m := re.search(r"\b(me|bo|ba|ong|vo|chong|con|toi|minh)\b", low):
        return "member", raw[m.start():m.end()]
    return "unspecified", None


def record(state: TripState, text: str, turn: int) -> tuple[TripState, bool]:
    """Capture each person's dated diet in its own clause."""
    clauses = [s.strip() for s in re.split(r"[,;.!?]", text) if DIET.search(fold(s))]
    if len(clauses) <= 1:
        return _record(state, text, turn)
    scoped = False
    for clause in clauses:
        state, captured = _record(state, clause, turn)
        scoped = scoped or captured
    return state, scoped


def _record(state: TripState, text: str, turn: int) -> tuple[TripState, bool]:
    """Capture a scoped statement, or a direct answer to its unresolved date/subject."""
    low = fold(text)
    match = DIET.search(low)
    prior = next((r for r in reversed(state.diet_requests) if unresolved(state, r)), None)
    scoped = bool(match and (DAY.search(low) or LUNAR.search(low)))
    if not scoped and not (prior and not match):
        return state, False
    if re.search(r"\b(khong|chang|chua|muon thu|thich thu|thu mon)\b", low):
        return state, scoped
    if scoped:
        # Keep the clause containing the diet; a later clause can describe the other days.
        clause = next((s for s in re.split(r"[,;.!?]", text) if DIET.search(fold(s))), text)
        request = DietRequest(feature="vegan_options" if match[1] in {"thuan chay", "vegan"} else "vegetarian_options",
                              subject=_subject(clause)[0], member=_subject(clause)[1],
                              evidence=(Evidence(turn=turn, quote=text),))
        target = fold(clause)
    else:
        request, target = prior, low
    changes = {}
    m = DAY.search(target)
    if not m and not scoped:
        m = re.fullmatch(r"\s*(\d{1,2})/(\d{1,2})(?:/(\d{4}))?[.!]?\s*", target)
    if m:
        number, month, year = m.groups()
        if month and re.search(r"\bam lich\b", target):
            changes.update(lunar_day=int(number), lunar_month=int(month), lunar_year=int(year) if year else None,
                           day=None, date=None)
        elif month:
            changes.update(solar_day=int(number), solar_month=int(month), solar_year=int(year) if year else None,
                           date=None, day=None, lunar_day=None, lunar_month=None, lunar_year=None)
        elif LUNAR.search(target):
            changes.update(lunar_day=int(number), day=None, date=None)
        else:
            changes.update(day=int(number), date=None, lunar_day=None)
    elif LUNAR.search(target):
        changes.update(lunar_day=15 if "ram" in target else 1, date=None, day=None)
    subject, member = _subject(clause if scoped else text)
    if subject != "unspecified":
        changes.update(subject=subject, member=member)
    if not scoped and changes:
        changes["evidence"] = (*request.evidence, Evidence(turn=turn, quote=text))
    if changes.get("lunar_day") or changes.get("day"):
        changes.update(solar_day=None, solar_month=None, solar_year=None)
    request = DietRequest.model_validate({**request.model_dump(), **changes})
    requests = tuple(r for r in state.diet_requests if r is not prior) if not scoped else state.diet_requests
    if request not in requests:
        requests += (request,)
    return state.model_copy(update={"diet_requests": requests}), scoped or bool(prior and changes)


def dates(state, request):
    if not state.start_date.known or not state.days.known:
        return ()
    first = state.start_date.value
    last = first + timedelta(days=state.days.value - 1)
    if request.solar_day and request.solar_month:
        years = (request.solar_year,) if request.solar_year else range(first.year, last.year + 1)
        candidates = []
        for year in years:
            try:
                candidates.append(date(year, request.solar_month, request.solar_day))
            except ValueError:
                pass
        return tuple(d for d in candidates if first <= d <= last)
    candidates = ((request.date,) if request.date else
                  (first + timedelta(days=request.day - 1),) if request.day else
                  tuple(d.date for d in state.diet_days if d.feature == request.feature and
                        d.subject == request.subject and d.member == request.member and
                        d.evidence == request.evidence))
    return tuple(d for d in candidates if first <= d <= last)


def unresolved(state, request):
    return request.subject == "unspecified" or not dates(state, request)


def resolved(state: TripState, calendar=None) -> tuple[DietDay, ...]:
    out = []
    for r in state.diet_requests:
        if r.subject == "unspecified":
            continue
        days = dates(state, r)
        if r.lunar_day and calendar and state.start_date.known and state.days.known:
            first = state.start_date.value
            last = first + timedelta(days=state.days.value - 1)
            days = tuple(date.fromisoformat(row["date"]) for row in calendar
                         if (row.get("lunar") or {}).get("day") == r.lunar_day
                         and (r.lunar_month is None or (row.get("lunar") or {}).get("month") == r.lunar_month)
                         and (r.lunar_year is None or (row.get("lunar") or {}).get("year") == r.lunar_year)
                         and first.isoformat() <= row.get("date", "") <= last.isoformat())
        for d in days:
            rule = DietDay(date=d, feature=r.feature, subject=r.subject, member=r.member, evidence=r.evidence)
            if rule not in out:
                out.append(rule)
    return tuple(out)


def progress(state):
    """Semantic progress only: another quote for the same answer cannot restart a question."""
    requests = tuple((r.feature, r.subject, fold(r.member or ""), r.day, r.date,
                      r.solar_day, r.solar_month, r.solar_year, r.lunar_day, r.lunar_month, r.lunar_year)
                     for r in state.diet_requests)
    days = tuple((r.date, r.feature, r.subject, fold(r.member or "")) for r in state.diet_days)
    return requests, days, state.start_date.value, state.days.value


def refresh(state):
    """Resolve yearless solar dates against the current trip, including date corrections."""
    requests = []
    for r in state.diet_requests:
        if r.solar_day and r.solar_month:
            days = dates(state, r)
            explicit = None
            if r.solar_year:
                try:
                    explicit = date(r.solar_year, r.solar_month, r.solar_day)
                except ValueError:
                    pass
            r = r.model_copy(update={"date": explicit or (days[0] if len(days) == 1 else None)})
        requests.append(r)
    return state.model_copy(update={"diet_requests": tuple(requests)})


def question(state):
    pending = [r for r in state.diet_requests if unresolved(state, r)]
    if not pending:
        return None
    r = pending[0]
    parts = []
    if r.subject == "unspecified":
        parts.append("Ai ăn chay ngày này: cả nhóm hay một người? Nếu một người, bạn cho mình biết là ai nhé.")
    if not dates(state, r):
        parts.append("Bạn cho mình ngày dương lịch ăn chay trong chuyến đi nhé; mình chưa quy được ngày áp dụng.")
    return " ".join(parts)
