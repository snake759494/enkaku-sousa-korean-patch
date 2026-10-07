"""Executable-resident text: the info list, dictionary, clue popups and system messages.

These strings live in BOOT.BIN (EBOOT.BIN on the disc), not in the script stream, and are
drawn with a second font inside the executable (0x88EA760, 864 glyphs, no Hangul).  The
renderer picks the font by the string's address (0x0884BE84): below [0x08A02C14] the
executable font, otherwise the stream font at [0x089F5E18].

Layout found by walking the file:

* font     file 0xE67B4..0x1017B4, 432 tiles, glyph code = 0x88 + i // 253, i % 253;
* strings  file 0x1017B4..0x11B050 are game text; 0x11B054.. are developer flags/event names;
* a string may hold 0x11 line breaks (the one-line person summaries are two lines in one string);
* every game string is reached from exactly one aligned pointer, and the pointers sit in 23
  tables.  Description tables give each entry ten line slots; unused slots point at a lone NUL.

Units written here are what gets translated: a whole ten-slot entry for description tables
(so Korean can be re-wrapped into up to ten lines), a single string for list tables.
"""

from __future__ import annotations

import json
import re
import struct
from pathlib import Path

ROOT = Path(r"D:\psp\원격수사")
BOOT = ROOT / "iso_extract" / "PSP_GAME" / "SYSDIR" / "BOOT.BIN"
VADDR = 0x8803FAC
FONT = (0xE67B4, 0x1017B4)
STRINGS = (0x1017B4, 0x11B050)
KANA_TABLE = 0x88EA394
CHARS = Path(__file__).with_name("exe_font_chars.json")
RECORD = 10
# description tables: first pointer word -> phase of the ten-slot entries within the run
RECORD_TABLES = {0x103EFC: 0, 0x104A34: 0, 0x105654: 0, 0x109800: 0, 0x10C120: 0,
                 0x10E604: 0, 0x110A00: 0, 0x112EAC: 0}


def lead(x: int) -> bool:
    return 0x81 <= x < 0xA0 or 0xE0 <= x < 0xFD


def string_end(b: bytes, i: int) -> int:
    while b[i]:
        i += 2 if lead(b[i]) else 1
    return i


def decoder(b: bytes):
    kana = {0xA7 + k: int.from_bytes(b[KANA_TABLE - VADDR + k * 2:KANA_TABLE - VADDR + k * 2 + 2], "big")
            for k in range(0xDE - 0xA7)}
    chars = {int(k): v for k, v in json.loads(CHARS.read_text(encoding="utf-8")).items()}

    def decode(i: int, e: int) -> tuple[str, bool]:
        out, bad = [], False
        while i < e:
            x = b[i]
            if lead(x):
                code = (x << 8) | b[i + 1]
                i += 2
                if code >= 0x8800:
                    n = ((code - 0x8800) >> 8) * 253 + (code & 0xFF)
                    if n >= 864 or n not in chars:
                        bad = True
                        out.append(f"〔{n}〕")
                    else:
                        out.append(chars[n])
                else:
                    try:
                        out.append(code.to_bytes(2, "big").decode("cp932"))
                    except UnicodeDecodeError:
                        bad = True
                        out.append(f"<{code:04x}>")
            elif 0xA7 <= x < 0xDE:
                out.append(kana[x].to_bytes(2, "big").decode("cp932", "replace"))
                i += 1
            elif 0x28 <= x < 0x7B:
                out.append((0x8200 | (x + 0x77)).to_bytes(2, "big").decode("cp932", "replace"))
                i += 1
            elif x == 0x11:
                out.append("\n")          # a line break inside one string
                i += 1
            else:
                bad = True
                out.append(f"<{x:02x}>")
                i += 1
        return "".join(out), bad
    return decode


def inventory(b: bytes):
    decode = decoder(b)
    strings = {}
    i = STRINGS[0]
    while i < STRINGS[1]:
        if b[i] == 0:
            i += 1
            continue
        e = string_end(b, i)
        text, bad = decode(i, e)
        if not bad:
            strings[i] = {"len": e - i, "ja": text}
        i = e + 1

    # A string can sit right after a pointer table with no NUL between them (辞典について
    # follows the help-topic table directly), so walking NUL to NUL glues it to the table
    # bytes and loses it.  Every pointer target is therefore also tried as a string start.
    for p in range(0x54, len(b) - 3, 4):
        o = struct.unpack_from("<I", b, p)[0] - VADDR
        if STRINGS[0] <= o < STRINGS[1] and o not in strings and b[o] and b[o - 1]:
            e = string_end(b, o)
            text, bad = decode(o, e)
            if not bad and len(text) >= 2:
                strings[o] = {"len": e - o, "ja": text}

    def kind(v: int):
        o = v - VADDR
        if o in strings:
            return "S", o
        if STRINGS[0] <= o < STRINGS[1] and b[o] == 0:
            return "E", o
        return None, None

    words = []
    for p in range(0x54, len(b) - 3, 4):
        k, o = kind(struct.unpack_from("<I", b, p)[0])
        if k:
            words.append((p, k, o))
    runs = []
    for w in words:
        if runs and w[0] == runs[-1][-1][0] + 4:
            runs[-1].append(w)
        else:
            runs.append([w])
    return strings, [r for r in runs if any(k == "S" for _, k, _ in r)]


def units(b: bytes) -> list[dict]:
    strings, runs = inventory(b)
    out = []
    for run in runs:
        table = run[0][0]
        width = max(len(strings[o]["ja"]) for _, k, o in run if k == "S")
        if table in RECORD_TABLES:
            phase = RECORD_TABLES[table]
            groups, cur = [], []
            for idx, w in enumerate(run):
                if (idx - phase) % RECORD == 0 and cur:
                    groups.append(cur)
                    cur = []
                cur.append(w)
            if cur:
                groups.append(cur)
            for g in groups:
                if not any(k == "S" for _, k, _ in g):
                    continue
                last = max(i for i, (_, k, _) in enumerate(g) if k == "S")
                lines = [strings[o]["ja"] if k == "S" else "" for _, k, o in g[:last + 1]]
                out.append({"kind": "record", "table": table, "slots": [p for p, _, _ in g],
                            "ja": "\n".join(lines), "width": width, "max_lines": len(g)})
        else:
            line_width = max(len(part) for _, k, o in run if k == "S"
                             for part in strings[o]["ja"].split("\n"))
            for p, k, o in run:
                if k == "S":
                    ja = strings[o]["ja"]
                    lines = ja.count("\n") + 1
                    out.append({"kind": "line" if lines == 1 else "multiline", "table": table,
                                "slots": [p], "ja": ja,
                                "width": width if lines == 1 else line_width,
                                "max_lines": lines})
    return out


def main() -> None:
    b = BOOT.read_bytes()
    us = units(b)
    texts = {}
    for u in us:
        texts.setdefault(u["ja"], []).append(u)
    distinct = [{"id": f"u{n:04d}", "ja": ja, "kind": g[0]["kind"],
                 "width": min(u["width"] for u in g), "max_lines": min(u["max_lines"] for u in g),
                 "tables": sorted({hex(u["table"]) for u in g}), "uses": len(g)}
                for n, (ja, g) in enumerate(texts.items())]
    out = ROOT / "build" / "exe_text"
    out.mkdir(parents=True, exist_ok=True)
    (out / "units_all.json").write_text(json.dumps(
        [{**u, "table": hex(u["table"])} for u in us], ensure_ascii=False, indent=0), encoding="utf-8")
    (out / "units_distinct.json").write_text(json.dumps(distinct, ensure_ascii=False, indent=1),
                                             encoding="utf-8")
    print(f"{len(us)} units, {len(distinct)} distinct, "
          f"{sum(len(d['ja']) for d in distinct)} Japanese characters to translate")


if __name__ == "__main__":
    main()
