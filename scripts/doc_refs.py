"""Check that every `docs/<file>.md §<section>` pointer in the repo still lands on a real file and heading.

    python scripts/doc_refs.py check            # list broken pointers, exit 1 if any
    python scripts/doc_refs.py check --summary  # counts per target doc only

A section is either numbered (`§3`, `§6.3`, `§2c`: matches a heading that starts with that number) or named
(`§CLI và API`: matches a heading whose title starts the text after `§`). Plans, logs and reports are not targets.
"""

import argparse
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCAN = ("src", "tests", "scripts", "config", "web/src", "web/scripts", "docs", "README.md", "AGENTS.md", "RULE.md")
SKIP_DIRS = {"node_modules", "__pycache__", "plans", "log", "reports", "dist"}
SUFFIXES = {".py", ".md", ".yaml", ".yml", ".ts", ".tsx", ".mjs", ".js", ".sh", ".json"}
POINTER = re.compile(r"(docs/[\w./-]+?\.md)((?:\s*§[^§\n]*?(?=\s*§|[)`\"',;\]\n]|$)|\s*[–-]\s*§[^§\n]*?(?=[)`\"',;\]\n]|$))*)")
SECTION = re.compile(r"§\s*([^§]+)")
NUMBER = re.compile(r"^(\d+[a-z]?(?:\.\d+)*)\b")
PLACEHOLDER = re.compile(r"docs/[A-Z]\.md")  # RULE.md's "docs/X.md §N" example
HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*$")


def fold(text: str) -> str:
    return unicodedata.normalize("NFC", text).casefold().strip().strip("*` ")


def headings(doc: Path) -> list[str]:
    out, fenced = [], False
    for line in doc.read_text(encoding="utf-8").splitlines():
        if line.lstrip().startswith("```"):
            fenced = not fenced
        elif not fenced and (m := HEADING.match(line)):
            out.append(fold(m.group(1)))
    return out


def found(section: str, titles: list[str]) -> bool:
    section = fold(section)
    if not section:
        return True
    if m := NUMBER.match(section):
        number = m.group(1)
        return any(re.match(rf"{re.escape(number)}(?:[.\s)]|$)", t) for t in titles)
    # named: some heading title starts the pointer text ("§CLI và API: ..." matches "CLI và API"); a heading's own
    # number and an "ⓐ"-style marker are not part of its name
    marker = re.compile(r"^(?:\d+[a-z]?(?:\.\d+)*\.?|[ⓐ-ⓩ])\s*")
    section = marker.sub("", section.rstrip(":.").strip())
    names = [marker.sub("", t) for t in titles]
    return any(section.startswith(t) or t.startswith(section) for t in names if t)


def files():
    for entry in SCAN:
        path = ROOT / entry
        if path.is_file():
            yield path
            continue
        for p in path.rglob("*"):
            if p.is_file() and p.suffix in SUFFIXES and not SKIP_DIRS & set(p.relative_to(ROOT).parts):
                yield p


def broken() -> list[tuple[str, int, str, str]]:
    """(source file, line, target doc, problem) for every pointer that does not resolve."""
    cache: dict[str, list[str] | None] = {}
    out = []
    for src in files():
        try:
            text = src.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for n, line in enumerate(text.splitlines(), 1):
            for m in POINTER.finditer(line):
                target, sections = m.group(1), m.group(2)
                if PLACEHOLDER.fullmatch(target) or any(part in SKIP_DIRS for part in Path(target).parts):
                    continue
                if target not in cache:
                    doc = ROOT / target
                    cache[target] = headings(doc) if doc.is_file() else None
                titles = cache[target]
                rel = src.relative_to(ROOT).as_posix()
                if titles is None:
                    out.append((rel, n, target, "missing file"))
                    continue
                for s in SECTION.findall(sections):
                    if not found(s, titles):
                        out.append((rel, n, target, f"no section §{s.strip()}"))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", choices=["check"])
    ap.add_argument("--summary", action="store_true")
    args = ap.parse_args(argv)
    bad = broken()
    if args.summary:
        for target, count in Counter(t for _, _, t, _ in bad).most_common():
            print(f"{count:4d}  {target}")
    else:
        for src, n, target, problem in bad:
            print(f"{src}:{n}: {target}: {problem}")
    print(f"{len(bad)} broken pointer(s)", file=sys.stderr)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
