"""Seven display groups; none blocks planning (owner 2026-11-18: the dates and care questions before planning are gone)."""

from .state import TripState, pending_signals

REQUIRED = ("trip", "companions", "mobility", "care", "pace", "budget", "lodging")
DEFAULT_REQUIRED = REQUIRED
# Nothing is asked before planning (owner 2026-11-18, replacing 2026-11-10's dates + care): with no dates Planning lays
# default_days out, day 1 first (planning.layout fill_first). Only a health hint the user raised in the talk and left
# open ("vợ mình đang bầu", a diet not yet clear) is asked back, since a plan cannot be compiled over it (gate_missing).
GATE_REQUIRED: tuple[str, ...] = ("care",)
PLAN_FILL = ("companions", "mobility", "care", "pace", "budget")  # asked on the Lịch trình page (care since 2026-11-18: no gate)
# Names of the seven groups as the Web designs them: short nouns, never spoken phrases ("Phương tiện", not "cách đi lại").
TITLE = {"trip": "Ngày đi", "companions": "Đi với", "mobility": "Phương tiện", "care": "Lưu ý", "pace": "Nhịp độ",
         "budget": "Ngân sách", "lodging": "Nơi lưu trú"}
# The same groups inside a sentence ("Mình cần thêm: …").
LABEL = {"trip": "ngày đi, giờ giấc", "companions": "người đi cùng", "mobility": "phương tiện", "care": "lưu ý sức khỏe, ăn uống",
         "pace": "nhịp độ", "budget": "ngân sách", "lodging": "nơi lưu trú"}


def boundary_answered(state: TripState, slot: str) -> bool:
    fields = (state.checkin_at, state.frame.arrive, state.inbound) if slot == "start" else (
        state.checkout_at, state.frame.leave, state.outbound)
    index = 0 if slot == "start" else (state.days.value or 0) - 1
    return any(f.known and f.source == "user" for f in fields) or any(
        d.index == index and d.source == "user" and getattr(d, slot) for d in state.frame.days)


def gate_missing(state: TripState) -> list[tuple[str, str]]:
    """What still stops planning: only an open health hint the user raised (an unhandled signal, a diet asked about)."""
    from .diet import question
    return [("care", LABEL["care"])] if pending_signals(state) or question(state) else []


def missing(state: TripState, required: tuple[str, ...] = REQUIRED, *, gate: bool = False) -> list[tuple[str, str]]:
    def answered(field):
        return field.known and field.source == "user"

    from .diet import question
    diet_pending = question(state)
    known = {
        "trip": answered(state.start_date) and answered(state.days) and (
            gate or (boundary_answered(state, "start") and boundary_answered(state, "end"))),
        "companions": (answered(state.companions) or bool(state.companions_other)) and answered(state.people),
        "mobility": answered(state.mobility),
        "care": not pending_signals(state) and not diet_pending and (bool(state.diet_requests) or (answered(state.care) and state.care.value == "none")
                                               or (answered(state.care) and state.care.value == "listed" and bool(state.unmapped))
                                               or any(h.evidence for h in state.hard)),
        "pace": answered(state.pace) and "pace" not in state.meta.conflicts,
        "budget": (answered(state.budget_unlimited) and state.budget_unlimited.value is True)
                  or (answered(state.budget_vnd) and answered(state.budget_scope))
                  or "budget" in state.meta.declined,  # skipped = unknown, not unlimited
        "lodging": answered(state.lodging) or "lodging" in state.meta.declined,  # skipped = "Cứ xếp giúp": the app picks
    }
    # Preserve display skip metadata; dates and care cannot be waived at the planning gate (owner 2026-11-10).
    gated = {d.removeprefix("gate:") for d in state.meta.declined if d.startswith("gate:")}
    if gate:
        gated.difference_update(GATE_REQUIRED)
    elif pending_signals(state) or diet_pending:
        gated.discard("care")
    return [(key, LABEL[key]) for key in required if not known.get(key, False) and key not in gated]
