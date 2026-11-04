"""Date-local dietary checks; a member needs verified options, not a dedicated venue."""

from corpus.serving import feature
from requirements import hard_result

from .roles import takes_meal_slot


def result(place, rule) -> str:
    activity = "eating" if takes_meal_slot(place) else place.activity
    verdict = hard_result(place.rec, rule, activity, place.kind)[0]
    if verdict == "pass":
        fact = feature(place.rec, rule["feature"])
        if fact is None or fact["status"] != "VERIFIED":
            return "unknown"
    return verdict


def allowed(place, ctx) -> bool:
    return all(result(place, rule) in {"pass", "not_applicable"} for rule in ctx.diet_days)


def explanation(rule, meal: str | None = None) -> str:
    who = rule.get("member") if rule["subject"] == "member" else "cả nhóm"
    option = "thuần chay" if rule["feature"] == "vegan_options" else "chay"
    label = {"breakfast": "bữa sáng", "lunch": "bữa trưa", "dinner": "bữa tối"}.get(meal, "bữa ăn")
    return f'Ngày {rule["date"]}, {who}: {label} chưa có món {option} đã xác minh; cần chọn quán đáp ứng.'


MEAL_LABEL = {"breakfast": "bữa sáng", "lunch": "bữa trưa", "dinner": "bữa tối"}


def warnings(ctxs, results) -> list[dict]:
    """What a diet day still leaves open, said plainly (never blocking: only evidence of no such dish blocks, in
    validate): a meal stop whose dish is not verified, and a meal of that day with no verified stop."""
    from .roles import takes_meal_slot
    from .schedule import day_meals
    out = []
    for cx, r in zip(ctxs, results):
        if not cx.diet_days:
            continue
        served = set()
        for it in r.items:
            if it.kind != "visit":
                continue
            p = cx.places[it.place_id]
            if not takes_meal_slot(p):
                continue
            for rule in cx.diet_days:
                verdict = result(p, rule)
                if verdict == "unknown":
                    who, option = _who(rule)
                    out.append({"code": "diet_unknown", "day": cx.day.index, "place_id": p.id,
                                "text": f"{_day(cx, rule)}: {p.name} chưa rõ có món {option} cho {who}; "
                                        "hỏi quán trước khi đến."})
                elif verdict == "pass":
                    served.add(it.start)
        meals = [n for n in day_meals(cx)]
        verified = {n for n in meals for it in r.items if it.kind == "visit" and takes_meal_slot(cx.places[it.place_id])
                    and cx.cfg.meal_windows[n][0] <= it.start <= cx.cfg.meal_windows[n][1] and it.start in served}
        for n in meals:
            if n in verified:
                continue
            for rule in cx.diet_days:
                who, option = _who(rule)
                out.append({"code": "diet_meal_open", "day": cx.day.index, "meal": n,
                            "text": f"{_day(cx, rule)}, {who}: {MEAL_LABEL.get(n, 'bữa ăn')} chưa có quán "
                                    f"{option} đã xác minh trong lịch; ô ăn có gợi ý quán {option} đã xác minh."})
    return out


def _day(cx, rule) -> str:
    """"Ngày 2 (2026-12-13)": the plan's day and the date the diet holds on."""
    return f"Ngày {cx.day.index + 1} ({rule['date']})"


def _who(rule) -> tuple[str, str]:
    who = rule.get("member") if rule["subject"] == "member" else "cả nhóm"
    return who, "thuần chay" if rule["feature"] == "vegan_options" else "chay"
