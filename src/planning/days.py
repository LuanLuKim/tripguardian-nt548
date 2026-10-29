"""The day-level risk terms the objectives read (objectives.metrics): rain on weather-exposed places, repeats of one
kind on a day, how much of what the user wants most sits on a risky day. Which places go on which day is layout.py's.
"""

from .schedule import DayCtx
from .traits import exposure, kind_group


def day_risk(ctx: DayCtx) -> float:
    """How likely the day is to go wrong for a place on it: its rain probability (0 when unknown) plus how much
    shorter than a full day it is (an arrival or departure day)."""
    full = ctx.cfg.day_end - ctx.cfg.day_start
    short = max(0.0, 1 - (ctx.day.end - ctx.day.start) / full) if full > 0 else 0.0
    return (ctx.wet or 0.0) + short


def exposed_risk(ids: list[str], ctx: DayCtx) -> float:
    """Weather-exposed places on the day, times its rain probability. No forecast -> 0."""
    return sum(exposure(ctx.places[i]) == "exposed" for i in ids) * (ctx.wet or 0.0)


def repeats(ids: list[str], ctx: DayCtx) -> int:
    """Places of a kind already on the day: 0 when every place is a different kind. Unknown kinds do not repeat."""
    kinds = [kind_group(ctx.places[i]) for i in ids]
    known = [k for k in kinds if k]
    return len(known) - len(set(known))


def pref_risk(ids: list[str], ctx: DayCtx) -> float:
    """How much of what the user wants most sits on a risky day."""
    prefs = ctx.prefs or {}
    return sum(prefs.get(i, 0.0) for i in ids) * day_risk(ctx)
