"""Safety uncertainty is not a failed physical check; report it for actual visits."""

from requirements import hard_result, safety_requirement

from .feature_ontology import ontology


def unknown_features(record: dict, hard: list[dict], activity=None, role=None) -> list[str]:
    return sorted({f["feature"] for f in hard if f["feature"] != "pets" and safety_requirement(f)
                   and hard_result(record, f, activity, role)[0] == "unknown"})


def reason(fid: str) -> str:
    phrases = {"steep_or_stairs": "Chưa rõ có dốc, nhiều bậc", "long_walk": "Chưa rõ có phải đi bộ xa",
               "rough_road_access": "Chưa rõ đường vào có khó đi", "car_access": "Chưa rõ ô tô có vào được",
               "coach_access": "Chưa rõ xe lớn có vào được"}
    if fid in phrases:
        return phrases[fid]
    onto = ontology()
    companion = next((c.vi for c in onto.companions.values()
                      if fid in {f"fit.{c.id}", c.suitability}), None)
    if companion:
        return f"Chưa rõ có phù hợp với {companion.lower()}"
    definition = onto.features.get(fid)
    claim = next(iter(definition.claims.values()), None) if definition else None
    return f"Chưa rõ liệu {claim}" if claim else "Chưa rõ có đáp ứng lưu ý an toàn đã ghi nhận"


def warnings(places, hard: list[dict]) -> list[dict]:
    """One line per place naming every safety point still unknown there: four lines for one restaurant pushed the
    other places' warnings off the screen (Lịch trình shows the first few)."""
    out = []
    for p in places:
        fids = unknown_features(p.rec, hard, p.activity, p.kind)
        if not fids:
            continue
        said = [reason(fid) for fid in fids]
        text = "; ".join([said[0], *(r[0].lower() + r[1:] for r in said[1:])])
        out.append({"code": "safety_unknown", "place_id": p.id, "feature": fids[0], "features": fids, "status": "unknown",
                    "text": f"{p.name}: {text}. Hãy kiểm tra với địa điểm trước khi đi."})
    return out


def visit_warnings(ctxs: list, results: list, hard: list[dict]) -> list[dict]:
    places = {i.place_id: cx.places[i.place_id] for cx, result in zip(ctxs, results)
              for i in result.items if i.kind == "visit"}
    return warnings(places.values(), hard)
