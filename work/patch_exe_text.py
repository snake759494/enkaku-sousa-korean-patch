"""Write the Korean executable text into BOOT.BIN and the glyphs it needs into the stream font.

Inputs: build/exe_text/units_all.json and units_distinct.json (from exe_text.py) and the
translations build/exe_text/out_*.json (checked by check_exe_text.py).

1. The renderer chooses the executable font for strings inside the executable and the stream
   font otherwise (0x0884BE90 `bnez $v1, 0x0884BEA4`).  That branch becomes a nop, so every
   string is drawn with the stream font -- the one that already holds the dialogue's Hangul.
2. Syllables the dialogue never needed are drawn into free stream-font slots (slots no Korean
   character and no surviving dialogue code uses), with the same face and cell as the rest.
3. The executable font (file 0xE67B4..0x1017B4, 110,592 bytes) is no longer read, so it becomes
   the pool for the Korean strings.  Every unit's line pointers are re-aimed at its new lines;
   spare slots of a ten-line entry point at an empty string.
4. Digits and Latin letters become full-width Shift-JIS (single bytes 0x28..0x7A are hiragana to
   this decoder), a space becomes U+3000, other punctuation passes through as Shift-JIS.

Outputs: the patched executable (also written padded to EBOOT.BIN's size), the stream with the
added glyphs, and the extended slot map.  Nothing in the script stream moves, so saves are
unaffected.
"""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

import build_korean_font as bkf
import exe_text
import font as fontlib
import text_blocks

ROOT = Path(r"D:\psp\원격수사")
BS = chr(92) + "n"
SELECTOR_BRANCH = 0x0884BE90
BRANCH_BYTES = bytes.fromhex("04006014")      # bnez $v1, +4
NOP = bytes(4)
EBOOT_SIZE = 1194496


def to_file(vaddr: int) -> int:
    return vaddr - exe_text.VADDR


def code_for(index: int) -> bytes:
    return bytes([0x88 + index // 253, index % 253])


def full_width(ch: str) -> str:
    if ch == " ":
        return "\u3000"
    if "!" <= ch <= "~":
        return chr(ord(ch) - 0x21 + 0xFF01)
    if ch == "\u00b7":
        return "\u30fb"
    return ch


def free_slots(stream: bytes, used: set[int]) -> list[int]:
    """Slots that neither a Korean character nor any code left in the dialogue refers to."""
    referenced = set()
    for block in text_blocks.find_blocks(stream):
        i = block.text
        while i < block.text_end:
            x = stream[i]
            if exe_text.lead(x):
                code = (x << 8) | stream[i + 1]
                if code >= 0x8800:
                    referenced.add(((code - 0x8800) >> 8) * 253 + (code & 0xFF))
                i += 2
            else:
                i += 1
    return [i for i in range(bkf.TOTAL_SLOTS) if i not in used and i not in referenced]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--boot", type=Path, default=exe_text.BOOT)
    parser.add_argument("--font-stream", type=Path,
                        default=ROOT / "build" / "stream1_ko_retranslated_v2_font.bin")
    parser.add_argument("--layout-stream", type=Path, default=ROOT / "build" / "stream1_ko_v318.bin",
                        help="current built stream, to find codes the dialogue still uses")
    parser.add_argument("--slots", type=Path,
                        default=ROOT / "build" / "korean_slots_retranslated_v2.json")
    parser.add_argument("--out-boot", type=Path, default=ROOT / "build" / "BOOT_v317.bin")
    parser.add_argument("--out-eboot", type=Path, default=ROOT / "build" / "EBOOT_v317.bin")
    parser.add_argument("--out-font-stream", type=Path,
                        default=ROOT / "build" / "stream1_ko_font_v317.bin")
    parser.add_argument("--out-slots", type=Path, default=ROOT / "build" / "korean_slots_v317.json")
    parser.add_argument("--report", type=Path,
                        default=ROOT / "build" / "exe_text" / "patch_report.json")
    args = parser.parse_args()

    boot = bytearray(args.boot.read_bytes())
    exe_dir = ROOT / "build" / "exe_text"
    units = json.loads((exe_dir / "units_all.json").read_text(encoding="utf-8"))
    distinct = json.loads((exe_dir / "units_distinct.json").read_text(encoding="utf-8"))
    by_ja = {d["ja"]: d["id"] for d in distinct}
    ko: dict[str, str] = {}
    for path in sorted(exe_dir.glob("out_*.json")):
        ko.update(json.loads(path.read_text(encoding="utf-8")))
    missing = [d["id"] for d in distinct if d["id"] not in ko]
    if missing:
        raise SystemExit(f"untranslated units: {missing[:10]} ({len(missing)})")

    slot_map = json.loads(args.slots.read_text(encoding="utf-8"))
    slots = {c: int(i) for c, i in slot_map["slots"].items()}
    font_stream = bytearray(args.font_stream.read_bytes())
    pool_free = free_slots(args.layout_stream.read_bytes(), set(slots.values()))
    new_chars: list[str] = []

    def encode(line: str) -> bytes:
        out = bytearray()
        for ch in line:
            if ch == "\x11":
                out.append(0x11)
                continue
            ch = full_width(ch)
            if "\uac00" <= ch <= "\ud7a3":
                if ch not in slots:
                    if not pool_free:
                        raise SystemExit("stream font has no free slot left")
                    slots[ch] = pool_free.pop(0)
                    new_chars.append(ch)
                out += code_for(slots[ch])
            else:
                code = ch.encode("cp932")
                if len(code) != 2 or not (0x81 <= code[0] <= 0x84):
                    raise SystemExit(f"cannot encode {ch!r} in {line!r}")
                out += code
        return bytes(out)

    pool_start, pool_end = exe_text.FONT
    boot[pool_start:pool_end] = bytes(pool_end - pool_start)
    empty = pool_start
    at = pool_start + 1
    placed: dict[bytes, int] = {}
    rewired = 0
    for unit in units:
        text = ko[by_ja[unit["ja"]]]
        lines = text.split(BS) if BS in text else text.split("\n")
        if unit["kind"] == "multiline":
            # one string holding its own 0x11 line breaks
            lines = ["\x11".join(lines)]
        if len(lines) > len(unit["slots"]):
            raise SystemExit(f"{len(lines)} lines for {len(unit['slots'])} slots: {unit['ja'][:30]}")
        for slot_index, pointer in enumerate(unit["slots"]):
            target = empty
            if slot_index < len(lines) and lines[slot_index]:
                data = encode(lines[slot_index])
                if data not in placed:
                    if at + len(data) + 1 > pool_end:
                        raise SystemExit("string pool overflow")
                    boot[at:at + len(data)] = data
                    placed[data] = at
                    at += len(data) + 1
                target = placed[data]
            struct.pack_into("<I", boot, pointer, target + exe_text.VADDR)
            rewired += 1

    branch = to_file(SELECTOR_BRANCH)
    if bytes(boot[branch:branch + 4]) != BRANCH_BYTES:
        raise SystemExit(f"unexpected instruction at 0x{SELECTOR_BRANCH:08x}")
    boot[branch:branch + 4] = NOP

    if new_chars:
        glyphs = fontlib.tiles_to_glyphs(bytes(font_stream), bkf.FONT_OFFSET, bkf.FONT_TILES)
        face = Path(slot_map["font"]) if Path(slot_map["font"]).exists() else bkf.HANGANG
        bitmaps = bkf.render("".join(new_chars), face, slot_map["px"], slot_map["dy"])
        for ch, bitmap in zip(new_chars, bitmaps):
            glyphs[slots[ch]] = bitmap
        font_stream[bkf.FONT_OFFSET:bkf.FONT_OFFSET + bkf.FONT_TILES * 256] = \
            fontlib.glyphs_to_tiles(glyphs)

    if len(boot) > EBOOT_SIZE:
        raise SystemExit("patched executable larger than EBOOT.BIN")
    args.out_boot.write_bytes(bytes(boot))
    args.out_eboot.write_bytes(bytes(boot) + bytes(EBOOT_SIZE - len(boot)))
    args.out_font_stream.write_bytes(bytes(font_stream))
    slot_map["slots"] = slots
    slot_map["codes"] = {c: code_for(i).hex() for c, i in slots.items()}
    args.out_slots.write_text(json.dumps(slot_map, ensure_ascii=False, indent=1), encoding="utf-8")
    report = {"units": len(units), "pointers_rewired": rewired, "strings_written": len(placed),
              "pool_used": at - pool_start, "pool_size": pool_end - pool_start,
              "new_glyphs": len(new_chars), "new_chars": "".join(new_chars),
              "free_slots_left": len(pool_free)}
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
