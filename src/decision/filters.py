"""Session filters (docs/PLACE_DECISION.md §12.1): a filter only hides a place from the tabs. It never changes a score
or a status, and a place whose value is not firmly known does not pass (unknown is not "yes")."""

from collections.abc import Iterable

from corpus.snapshot import Region

from .cards import phrase
from .geo import to_min
from .guard import OPENS_BY
from .trip_days import DAYS

FIRM = ("VERIFIED", "OUTDATED")


def label(key: str, value: str, cfg) -> str:
    return f"Mở cửa lúc {value} hoặc sớm hơn" if key == OPENS_BY else phrase(key, value, cfg)


def _opens_by(region: Region, pid: str, limit: int, weekdays: Iterable[str]) -> bool:
    """The firm opening hours show a first opening at or before `limit` (minutes) on at least one trip day."""
    hours = ((region.record(pid) or {}).get("operation") or {}).get("hours") or {}
    if hours.get("status") not in FIRM:
        return False
    for day in weekdays:
        starts = [to_min(r[0]) for r in (hours.get("value") or {}).get(day) or []]
        if starts and min(starts) <= limit:
            return True
    return False


def passing(region: Region, filters: list[tuple[str, str]], days, ids: Iterable[str]) -> set[str]:
    """The ids among `ids` that pass every filter."""
    ok = set(ids)
    weekdays = {d.weekday for d in days}
    weekdays = list(DAYS) if None in weekdays or not weekdays else sorted(weekdays)
    for key, value in filters:
        if key == OPENS_BY:
            limit, status, has = to_min(value), region.column("hours_status"), region.column("has_hours_value")
            ok = {p for p in ok if (i := region.index.get(p)) is not None and status[i] in FIRM and has[i]
                  and _opens_by(region, p, limit, weekdays)}  # records are parsed only for places with firm hours
        else:
            col = region.feature(key)
            ok = {p for p in ok if (i := region.index.get(p)) is not None and col.firm[i] and col.value[i] == value}
    return ok
