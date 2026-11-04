"""The Place Decision run as it was before the corpus snapshot (a verbatim copy of decision.pipeline.run, per place
over a list of serving records). Oracle for tests/decision/test_equivalence.py: the table-based run must give the
same view. Update this copy only when the behaviour of run() changes on purpose."""

from collections import Counter
import math

from corpus.serving import conf, feature
from requirements import activity_for

from decision.learning import signals

from decision.cards import card, feature_label, value_label  # noqa: F401
from decision.chunks import assign_chunks, coverage, describe_chunks
from decision.curation import pending
from decision.diversify import pick, sizes, tab
from decision.feasibility import evaluate
from decision.fit import DAYTIME, centers, fit
from decision.model import FIRM, Cand, role_of
from decision.pipeline import Result, _lodging_view, _rule_label, stub, wanted
from decision.rank import safety_priority, score
from decision.screen import screen
from decision.trip_days import trip_days
from decision.window import change, pages, window
from decision.wishes import build as build_wishes


def run_reference(s, records: list[dict], cfg) -> Result:
    by_id = {r["id"]: r for r in records}
    si, st = s.search_input, s.state
    si = si.model_copy(update={'activities': {**si.activities, **st.activities}})
    days = trip_days(si.context, cfg)
    known_days = si.context.days is not None
    wish = set(st.wishlist)
    dropped = {d.place_id for d in st.dropped}
    # lodging is Planning's (corpus list <city>_stay): never a suggestion, not even when named
    stay = {r["id"] for r in records if r["identity"].get("category_group") == "stay"}
    anchors = [a.place_id for a in si.anchors if a.place_id not in wish | dropped | stay]  # a dropped anchor is gone
    keep = (set(anchors) | set(st.selected)) - wish - stay

    cands: dict[str, Cand] = {}
    for r in records:
        if r["id"] in stay:
            continue
        role = role_of(r)
        activity = activity_for(r, si.activities.get(r["id"]), role)
        if role and activity == "eating":
            role = "meal"
        elif role and activity:
            role = "experience"
        if role or r["id"] in keep:
            cands[r["id"]] = Cand(r, role or "experience", keep=r["id"] in keep)
    for pid in sorted(keep - cands.keys()):
        cands[pid] = Cand(stub(pid), "experience", keep=True, missing=True)
    relaxed = {tuple(x) for x in st.relaxed}
    for c in cands.values():
        screen(c, si, days, relaxed)

    ctrs = centers(si, by_id, cfg)
    anchor_areas = {a for pid in anchors if (a := cands[pid].rec["identity"].get("area"))}
    live = [c for c in cands.values() if c.status != "excluded" or c.keep]
    for c in live:
        fit(c, si, days, ctrs, anchor_areas, st.profile, cfg)
    wl = build_wishes(si, records, cfg, None,
                      lambda fid, value: {r["id"] for r in records
                                          if (f := feature(r, fid)) and f["status"] in FIRM and f["value"] == value},
                      lambda pid: by_id[pid]["identity"]["name"] if pid in by_id else None)
    score(live, si, st.profile, cfg, wishes=wl)
    votes = signals(st, si, by_id, cfg) if cfg.wish["session_learning"].get("enabled", False) else {}
    selected = set(st.selected) - {a.place_id for a in si.anchors}
    groups = {by_id[p]["identity"].get("category_group") for p in selected if p in by_id}
    baseline = [r for r in records if r["identity"].get("category_group") in groups]
    cf = cfg.wish["session_learning"]
    terms, total, weighted = {}, 0.0, []
    for key, weight in votes.items():
        fid, value = key
        matching = {r["id"]: conf(f) for r in records if (f := feature(r, fid))
                    and f["value"] == value and f["status"] == "VERIFIED" and f["n"] > 0 and f.get("evidence")}
        if weight > 0 and len(selected) >= cf["consistent_min"]:
            successes = sum(bool(matching.get(p)) for p in selected)
            matches = sum(bool(matching.get(r["id"])) for r in baseline)
            prevalence = (matches + 1) / (len(baseline) + 2)
            if not baseline or matches == len(baseline) or successes / len(selected) <= prevalence:
                continue
            tail = sum(math.comb(len(selected), k) * prevalence ** k * (1 - prevalence) ** (len(selected) - k)
                       for k in range(successes, len(selected) + 1))
            weight *= (1 - tail) * len(selected) / (len(selected) + cf["evidence_prior"])
        weighted.append((key, weight, matching))
    positives = sorted((x for x in weighted if x[1] > 0), key=lambda x: (-x[1], x[0]))[:cf["top_k"]]
    for _, weight, matching in [*positives, *(x for x in weighted if x[1] < 0)]:
        for pid, confidence in matching.items():
            terms[pid] = terms.get(pid, 0.0) + confidence * weight
        total += max(abs(weight), cf["select_weight"])
    if total:
        for c in live:
            delta = round(cf["max_lift"] * terms.get(c.id, 0.0) / total, 4)
            if delta:
                c.parts["session"] = delta
                c.score = round(c.score + delta, 4)
    group_of = {c.id: tab(c, cfg) for c in live}

    visited = set(si.novelty.visited) | set(st.profile.visited)
    listed = [c for c in live if not c.keep and c.status == "main" and c.id not in dropped and c.id not in wish
              and not (si.novelty.level == "new" and c.id in visited)]
    from decision import diet as dietary
    from corpus.snapshot import Region
    diet = dietary.wanted(si, st.profile, st.unmapped)
    tier = dietary.tiers(Region.from_records(records), [i for i in [*st.selected, *(c.id for c in listed)]
                                                       if group_of.get(i) in dietary.TABS], diet)
    pool = [c for c in listed if c.fit >= cfg.min_context_fit and tier.get(c.id, 1) < 3]
    chosen = [cands[i] for i in st.selected if i in cands]
    size = sizes(si, len(days), sum(1 for a in anchors if cands[a].role == "experience"), cfg)
    reps, alts = [], {}
    for role in ("experience", "meal"):
        k = size[role] - sum(1 for c in chosen if c.role == role and c.id not in anchors)
        r_, a_ = pick([c for c in pool if c.role == role], k, cfg)
        reps += r_
        alts.update(a_)
    for c in chosen:
        g = c.rec.get("near_duplicate_group")
        if g is not None and c.id not in alts:
            same = sorted((x for x in pool if x.rec.get("near_duplicate_group") == g), key=lambda x: (-x.score, x.id))
            if same:
                alts[c.id] = same[:3]

    avoid = (st.profile.crowd_tolerance or si.pace.crowd_tolerance) == "avoid"
    day_types = sorted({d.day_type for d in days if d.day_type}) or ["weekday", "weekend"]

    def crowded(c) -> bool:  # Google calls the place busy at some time of the trip's day types
        cbt = c.rec["operation"].get("crowd_by_time")
        return avoid and bool(cbt) and any((cbt.get(dt) or {}).get(b, 0) >= cfg.crowd_busy_pct for dt in day_types for b in DAYTIME)

    ranked: dict[str, list[str]] = {}
    for c in sorted([*(x for x in chosen if x.id not in anchors), *listed],
                    key=lambda c: (safety_priority(c), tier.get(c.id, 1), crowded(c), -c.score, c.id)):
        ranked.setdefault(group_of.get(c.id, "sights"), []).append(c.id)
    picked = {c.id for c in chosen}
    top = set()
    for gid, ids in ranked.items():
        k = sum(1 for c in reps if group_of.get(c.id) == gid)
        top.update([p for p in ids if p not in picked and tier.get(p, 1) < 2][:k])
    # same rule as decision.wishes.reserve, written per wish: a said wish met by a listed place has one in "Hợp nhất"
    said = [w for w in wl if w.kind in ("dish", "kind", "like") and w.places]
    on_list = {p for ids in ranked.values() for p in ids}
    for w in said:
        if set(w.places) & (top | picked):
            continue
        options = sorted((p for p in w.places if p in on_list and p not in picked and tier.get(p, 1) < 2),
                         key=lambda p: (-cands[p].score, p))
        if not options:
            continue
        sole = set()
        for x in said:
            covered = set(x.places) & (top | picked)
            if len(covered) == 1:
                sole |= covered
        spare = sorted(top - sole, key=lambda p: (cands[p].score, p))
        if spare:
            top.remove(spare[0])
        top.add(options[0])

    suggested = next((c.id for c in reps if group_of[c.id] == st.suggest_group), None) if st.suggest_group else None
    want = wanted(si, st.profile)
    labels = cfg.labels["group"]

    def mk(c: Cand) -> dict:
        return card(c, si, cfg, wanted=want, chosen=c.id in st.selected, locked=c.id in st.locked,
                    anchor=c.id in anchors, alternatives=[(x.id, x.name) for x in alts.get(c.id, [])],
                    suggested=c.id == suggested, group=group_of.get(c.id, "sights"), top=c.id in top)

    groups, shown, changed = [], {}, {}
    if anchors:
        groups.append({"id": "anchors", "label": labels["anchors"], "cards": [mk(cands[a]) for a in anchors],
                       "total": len(anchors)})
    for gid in cfg.tabs:
        ids = ranked.get(gid, [])
        win, page = window(ids, st.page.get(gid, 0), cfg)
        if win:
            shown[gid], changed[gid] = win, change(st.shown.get(gid, []), win, cfg)
            groups.append({"id": gid, "label": labels[gid], "cards": [mk(cands[i]) for i in win], "total": len(ids),
                           "page": page, "pages": pages(len(ids), cfg), "page_size": cfg.page_size,
                           "offset": page * cfg.page_size})

    unverified = sorted((c for c in live if not c.keep and c.status == "unverified" and c.id not in dropped),
                        key=lambda c: (-c.score, c.id))
    excluded = Counter(x["reason"] for c in cands.values() if c.status == "excluded" and not c.keep
                       for x in c.checks if x["result"] == "fail")
    feas = evaluate(chosen, si, days, known_days, set(anchors), set(st.locked), ctrs,
                    {f for f in want if f in cfg.timed_features}, cfg)
    pend = pending(st, by_id, si, feas, s.first_shortlist, group_of, cfg)
    allocation = assign_chunks(chosen, st.chunk_assignments, days, cfg)

    def name(pid: str) -> str:
        c = cands.get(pid)
        return c.name if c else (by_id.get(pid) or stub(pid))["identity"]["name"]

    def wish_reason(pid: str) -> str:
        c = cands.get(pid)
        if c and any(x["kind"] == "physical" and x["result"] == "fail" for x in c.checks):
            return "Đóng cửa mọi ngày của chuyến"
        return "Bạn để dành cho dịp khác"

    view = {
        "version": len(s.history),
        "groups": groups,
        "change": changed,
        "shortlist": [x["id"] for g in groups for x in g["cards"]],
        "selected": list(st.selected), "locked": list(st.locked),
        "chunk_assignments": allocation,
        "chunks": describe_chunks(chosen, allocation, days),
        "coverage": coverage(chosen, si, days, feas, cfg, st.free_time),
        "unverified": {"count": len(unverified), "open": any(h.unknown_policy == "flag" for h in si.hard_filters),
                       "cards": [mk(c) for c in unverified[:cfg.unverified_show]]},
        "excluded": {"by_rule": [{"rule": r, "label": _rule_label(r, si, cfg), "count": n}
                                 for r, n in sorted(excluded.items())]},
        "wishlist": [{"id": p, "name": name(p), "reason": wish_reason(p)} for p in st.wishlist],
        "dropped": [{"id": d.place_id, "name": name(d.place_id), "reason": d.reason} for d in st.dropped],
        "feasibility": feas,
        # where the user sleeps, one for the whole trip: `booked` is what Hiểu chuyến đi was told (with a point),
        # `chosen` what the user picked at Lựa chọn (it replaces `booked`); `needed` = neither is known yet
        "lodging": _lodging_view(si, st),
        "pending": pend.model_dump() if pend else None,
        "profile": st.profile.model_dump(),
        "known_days": known_days,
        "days": [{"index": d.index, "date": d.date.isoformat() if d.date else None, "weekday": d.weekday} for d in days],
        "unknowns": list(si.unknowns),
        "unmapped": [*si.unmapped, *st.unmapped],
        "filter": {"active": [], "hidden": 0},  # generated sessions hold no filters or likes; they have their own tests
        "likes": [],
    }
    return Result(view, cands, {k: [x.id for x in v] for k, v in alts.items()}, group_of, days, shown, ranked, allocation,
                  wl)
