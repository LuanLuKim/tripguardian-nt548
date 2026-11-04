"""Applicability precedes evidence. Category identifies an activity, never proves a dietary option."""

from typing import Mapping

from corpus import category_group
from corpus.serving import check, feature

from .contract import Activity, ontology

FOOD = {"vegetarian_options", "vegan_options", "food_quality", "portion_size", "local_specialty_food"}
DRINK = {"drink_quality", "alcohol_required", "wine_tasting_available"}
ACTIVITY_SCOPE = {"eating": "eating", "coffee": "drinking", "drinking": "drinking", "tasting": "drinking",
                  "wine_tasting": "drinking", "alcohol_consumption": "drinking", "sightseeing": "sightseeing",
                  "photography": "sightseeing", "walking": "sightseeing", "nightlife": "sightseeing",
                  "accommodation": "accommodation", "travel": "travel"}


def scope_for(fid: str) -> str:
    return "eating" if fid in FOOD else "drinking" if fid in DRINK else "all"


def category_for(rec: dict) -> str | None:
    ident = rec.get("identity") or {}
    group = ident.get("category_group")
    if group and group not in {"other", "x"}:
        return group
    category = ident.get("category")
    derived = category_group(category)["id"] if category and category != "x" else None
    return derived if derived != "other" else None


def activity_for(rec: dict, activity: Activity | None = None, role: str | None = None) -> Activity | None:
    if activity:
        return activity
    group = category_for(rec)
    usable = rec.get("usable_as") or []
    if group == "cafe":
        return "coffee"
    if role == "meal" or ("meal" in usable and "experience" not in usable) or group in {"restaurant", "dessert", "food_vendor"}:
        return "eating"
    if group == "bar":
        return "drinking"
    if group == "stay":
        return "accommodation"
    if group == "rental":
        return "travel"
    if group or role == "experience" or "experience" in usable:
        return "sightseeing"
    return None


def _get(requirement, key, default=None):
    return requirement.get(key, default) if isinstance(requirement, Mapping) else getattr(requirement, key, default)


def safety_requirement(requirement) -> bool:
    """Safety unknowns remain eligible, never pass evidence checks (owner decision 2026-11-04)."""
    fid = _get(requirement, "feature")
    f = ontology().features.get(fid)
    return fid.startswith("fit.") or bool(f and f.group in {"effort", "suitability"})


def scope_allows(requirement, selected: Activity | None) -> bool:
    """The scope part of applicable(): does a requirement apply to a place whose activity is `selected`?"""
    fid = _get(requirement, "feature")
    canonical = scope_for(fid)
    scope = _get(requirement, "scope") or canonical
    f = ontology().features.get(fid)
    if canonical != "all":
        scope = canonical
    elif fid in {"venue_category", "activity"} or (f and f.group in {"effort", "suitability"}):
        scope = "all"                  # raw public inputs cannot narrow a protected scope
    # Unknown activity cannot be used as a reason to bypass a hard requirement.
    return scope == "all" or selected is None or ACTIVITY_SCOPE[selected] == scope


def applicable(rec: dict, requirement, activity: Activity | None = None, role: str | None = None) -> bool:
    selected = activity_for(rec, activity, role)
    fid = _get(requirement, "feature")
    ont = ontology()
    if selected == "accommodation" and fid in ont.features:
        if fid not in ont.stay and not any(item.startswith(fid + "=") for item in ont.stay):
            return False  # Accommodation cannot carry evidence outside the ontology's stay set.
    if fid == "wine_tasting_available":
        if activity is not None:
            return selected in {"wine_tasting", "tasting", "alcohol_consumption", "drinking"}
        offered = feature(rec, "wine_tasting_available")
        return offered is not None or selected in {"wine_tasting", "tasting", "alcohol_consumption", "drinking"} or selected is None
    return scope_allows(requirement, selected)


def hard_result(rec: dict, requirement, activity: Activity | None = None, role: str | None = None) -> tuple[str, str | None]:
    if not applicable(rec, requirement, activity, role):
        return "not_applicable", None
    fid, val, op = (_get(requirement, k) for k in ("feature", "value", "op"))
    if fid in {"venue_category", "activity"}:
        actual = category_for(rec) if fid == "venue_category" else activity_for(rec, activity, role)
        if actual is None:
            return "unknown", None
        if fid == "activity" and val == "alcohol_consumption":
            if actual in {"wine_tasting", "alcohol_consumption"}:
                match = True
            elif actual in {"tasting", "drinking", "coffee", "eating"}:
                alcohol = feature(rec, "alcohol_required")
                if alcohol is None:
                    if actual == "tasting":
                        return "unknown", None
                    match = False
                elif alcohol["status"] not in {"VERIFIED", "OUTDATED"} or set(alcohol["distribution"]) != {alcohol["value"]}:
                    return "unknown", None
                else:
                    match = alcohol["value"] == "yes"
            else:
                match = False
        else:
            match = actual == val
        return ("pass" if match == (op == "eq") else "fail"), None
    f = feature(rec, fid)
    if op == "eq":
        if f is None or f["status"] not in {"VERIFIED", "OUTDATED"}:
            return "unknown", None
        if f["value"] != val:
            return "fail", None
        return ("pass", None) if set(f["distribution"]) <= {val} else ("unknown", None)
    return check(rec, fid, val), None


def allowed(rec: dict, requirement, activity: Activity | None = None, role: str | None = None) -> bool:
    result, _ = hard_result(rec, requirement, activity, role)
    safety_visible = (safety_requirement(requirement) and _get(requirement, "feature") != "pets"
                      and activity_for(rec, activity, role) != "accommodation")
    return result in {"pass", "not_applicable"} or (result == "unknown" and (
        safety_visible or _get(requirement, "unknown_policy") == "flag"))
