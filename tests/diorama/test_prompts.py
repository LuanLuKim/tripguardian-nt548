import re

from auto3d import prompts


def test_kits_summary_glosses_preserve_names_and_order():
    summary = prompts.kits_summary()
    assert re.search(r"nature_line \([^\n]*?cabin[^\n]*?\)", summary)
    expected = []
    for file in sorted((prompts.CODE / "kits/catalog").glob("*.md")):
        text = file.read_text().splitlines()
        selected = [line for i, line in enumerate(text) if i < 32 or line.startswith("#")
                    or line.startswith("| `") or re.match(r"`[a-z][a-z0-9_]*`\s*[—–-]", line)]
        names = sorted({name for name in re.findall(r"`([a-z][a-z0-9_]+)(?:`|\.)", "\n".join(selected))
                        if name == file.stem or name.startswith(file.stem + "_")
                        or (file.stem == "church" and "_" in name)
                        or name in ("buddhist_altar", "quan_am_gallery")})
        expected.append(f"- {file.stem}: {', '.join(names)}")
    without_glosses = re.sub(r" \(.*?\)(?=, [a-z][a-z0-9_]*(?: \(|, |$)|$)", "", summary, flags=re.M)
    assert without_glosses == "\n".join(expected)
    assert len(summary) < 25_000
