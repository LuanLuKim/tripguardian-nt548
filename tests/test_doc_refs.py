"""Every `docs/<file>.md §<section>` pointer in the repo lands on a real file and heading (scripts/doc_refs.py)."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("doc_refs", ROOT / "scripts" / "doc_refs.py")
doc_refs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(doc_refs)

TITLES = [doc_refs.fold(t) for t in ("5. Chọn câu hỏi tiếp theo", "6.3 Xung đột với địa điểm user chọn", "CLI và API",
                                     "ⓗ Dự phòng — `backup.py`", "20. Tag và subtag")]


def test_numbered_sections_match_the_heading_number_only():
    assert doc_refs.found("5", TITLES) and doc_refs.found("6.3", TITLES)
    assert not doc_refs.found("6.4", TITLES) and not doc_refs.found("50", TITLES)


def test_named_sections_ignore_heading_numbers_markers_and_trailing_prose():
    assert doc_refs.found("CLI và API: the server part", TITLES)
    assert doc_refs.found("ⓗ Dự phòng", TITLES) and doc_refs.found("Tag và subtag", TITLES)
    assert not doc_refs.found("API và web", TITLES)


def test_no_pointer_in_the_repo_is_broken():
    bad = doc_refs.broken()
    assert not bad, "\n".join(f"{src}:{n}: {target}: {problem}" for src, n, target, problem in bad)
