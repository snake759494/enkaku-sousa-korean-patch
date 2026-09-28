"""Check condensed rewrites of dialogue rows against the text-box and save-layout limits.

Issue #3: rows spoken in the lower dialogue box ran past three lines and drew over the command
bar.  A row is repaired by rewriting it so that it holds in *either* box:

* speaker label unchanged, on its own line;
* at most three text lines, none wider than 33 units -- the narrower of the two boxes.  Measured
  in game: every glyph, Latin letters and digits included, advances 16px (2 units) and only the
  space advances 8px (1 unit); ruby takes no room;
* no line longer than 19 characters, the width at which translation_text re-wraps a line during
  the build (a re-wrap would add a line and change the byte count);
* every character present in the Korean font slot map;
* encoded length no greater than the row's current encoded length.  The save file stores
  script positions, so every row keeps its byte length exactly; the shortfall is padded later.

Input JSON: {"0x00047e11": "【노리코】\n...\n...", ...}.  Prints one line per failing row.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import encode_korean
import rewrap_lines as R
import translation_text

ROOT = Path(r"D:\psp\원격수사")
BS = chr(92) + "n"
LIMIT = 33
TEXT_LINES = 3
MAX_CHARS = 19


def width(line: str) -> int:
    """Units on screen: a space is 1, every other character 2, ruby 0."""
    visible = R.RUBY.sub("", line)
    return sum(1 if c == " " else 2 for c in visible)


def load_current(path: Path) -> dict[str, str]:
    _, rows = translation_text.parse_loose_tsv(path)
    return {r[0]: r[2] for r in rows if len(r) >= 3}


def problems(offset: str, text: str, current: dict[str, str], slots: dict[str, int]) -> list[str]:
    out = []
    old = current.get(offset)
    if old is None:
        return ["unknown offset"]
    lines = text.split(BS)
    if lines[0] != old.split(BS)[0]:
        out.append(f"speaker label changed: {lines[0]!r} != {old.split(BS)[0]!r}")
    body = lines[1:]
    if len(body) > TEXT_LINES:
        out.append(f"{len(body)} text lines (max {TEXT_LINES})")
    for i, line in enumerate(body, 1):
        if width(line) > LIMIT:
            out.append(f"line {i} is {width(line)} units (max {LIMIT}): {line}")
        if len(line) > MAX_CHARS:
            out.append(f"line {i} has {len(line)} characters (max {MAX_CHARS}): {line}")
        if not line.strip():
            out.append(f"line {i} is blank")
    new_bytes = encode_korean.encode_text(text.replace(BS, "\n"), slots)
    if new_bytes is None:
        missing = sorted({c for c in text.replace(BS, "") if c not in slots
                          and c not in encode_korean.PASSTHROUGH})
        out.append(f"characters not in the font: {''.join(missing)}")
    else:
        budget = len(encode_korean.encode_text(old.replace(BS, "\n"), slots))
        if len(new_bytes) > budget:
            out.append(f"{len(new_bytes)} bytes > budget {budget} (cut {len(new_bytes) - budget})")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidates", type=Path)
    parser.add_argument("--current", type=Path, default=ROOT / "build" / "translation_ko_v7_final.tsv")
    parser.add_argument("--slots", type=Path, default=ROOT / "build" / "korean_slots_retranslated_v2.json")
    args = parser.parse_args()
    current = load_current(args.current)
    slots = {c: int(i) for c, i in json.loads(args.slots.read_text(encoding="utf-8"))["slots"].items()}
    rows = json.loads(args.candidates.read_text(encoding="utf-8"))
    bad = 0
    for offset, text in rows.items():
        issues = problems(offset, text, current, slots)
        if issues:
            bad += 1
            print(f"FAIL {offset}: " + " | ".join(issues))
    print(f"{len(rows) - bad}/{len(rows)} pass")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
