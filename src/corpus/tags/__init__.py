"""corpus.tags: the tag -> subtag vocabulary and grouping (docs/PLACE_DECISION.md §Tag và subtag), pure functions.

    of_record(record, style_ids) -> PlaceTags      the tags a place carries, each with evidence
    split(places, fixed) -> Split | None           ranked places -> the best axis' subtags (labels in Vietnamese)
    kinds(places, skip) -> Split | None            a vague ask's tags: the biggest kinds of the places (axis "tags")
    trending(tags_by_place, videos, today) -> [..] tags ranked by the TikTok clips of the last 30 days
"""

from .group import Fixed, Split, Subtag, fixed_dishes, kinds, members, split
from .trend import trending
from .covers import approved_covers, save_cover_reviews
from .cover_judge import judge_cover_candidates
from .inputs import export_inputs
from .offline import judge_places
from .dual import compare_judges
from .membership import reader_revision
from .audit import run_audit
from .vocab import AXES, PlaceTags, config, dish_variants, label, load_styles, of_record, parse_ref, ref, resolve_ref

__all__ = ["judge_cover_candidates", "reader_revision", "approved_covers", "save_cover_reviews", "compare_judges", "export_inputs", "judge_places", "run_audit", "AXES", "Fixed", "PlaceTags", "Split", "Subtag", "config", "dish_variants", "fixed_dishes", "kinds", "label", "load_styles", "members",
           "of_record", "parse_ref", "ref", "resolve_ref", "split", "trending"]
