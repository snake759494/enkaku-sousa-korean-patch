"""Check Korean for the executable's text units (build/exe_text/out_*.json).

Rules, per unit from units_distinct.json:
* at most `max_lines` lines (records) or exactly one line (list entries);
* every line at most `width` characters -- the widest Japanese line of the same table, each
  character one cell (the renderer advances every glyph, space included, by a full cell);
* Korean only: Hangul, spaces, digits/Latin (written as full-width), and Shift-JIS punctuation
  the executable's symbol font already has.  No kana or kanji may remain.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(r"D:\psp\원격수사")
BS = chr(92) + "n"


def symbol_ok(ch: str) -> bool:
    if ch == " " or "가" <= ch <= "힣":
        return True
    if ch.isascii():
        return ch.isprintable()
    try:
        code = ch.encode("cp932")
    except UnicodeEncodeError:
        return False
    if len(code) != 2 or not (0x81 <= code[0] <= 0x84):
        return False
    # no kana: 0x829F-0x82F1 hiragana, 0x8340-0x8396 katakana
    v = (code[0] << 8) | code[1]
    return not (0x829F <= v <= 0x82F1 or 0x8340 <= v <= 0x8396)


def problems(unit: dict, text: str) -> list[str]:
    out = []
    lines = text.split(BS) if BS in text else text.split("\n")
    if unit["kind"] == "line" and len(lines) != 1:
        out.append("list entry must be one line")
    if len(lines) > unit["max_lines"]:
        out.append(f"{len(lines)} lines (max {unit['max_lines']})")
    for i, line in enumerate(lines, 1):
        if len(line) > unit["width"]:
            out.append(f"line {i} has {len(line)} cells (max {unit['width']}): {line}")
    bad = sorted({c for c in text.replace(BS, "") if c != "\n" and not symbol_ok(c)})
    if bad:
        out.append("not allowed: " + "".join(bad))
    if unit["ja"].strip() and not text.strip():
        out.append("empty translation")
    return out


def main() -> None:
    units = {u["id"]: u for u in json.loads(
        (ROOT / "build" / "exe_text" / "units_distinct.json").read_text(encoding="utf-8"))}
    path = Path(sys.argv[1])
    data = json.loads(path.read_text(encoding="utf-8"))
    bad = 0
    for uid, text in data.items():
        if uid not in units:
            print(f"FAIL {uid}: unknown id")
            bad += 1
            continue
        issues = problems(units[uid], text)
        if issues:
            bad += 1
            print(f"FAIL {uid}: " + " | ".join(issues))
    if len(sys.argv) > 2:
        expected = set(json.loads(Path(sys.argv[2]).read_text(encoding="utf-8")))
        missing = expected - set(data)
        if missing:
            bad += len(missing)
            print(f"FAIL missing ids: {sorted(missing)[:20]} ({len(missing)})")
    print(f"{len(data) - bad}/{len(data)} pass")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
