"""Validate the parts of a patched PSP ISO that must remain hardware-compatible.

This is intentionally stricter than checking that an emulator can open the file.  It checks
the ISO9660 volume and directory layout, the PSP boot files, the two in-place replacement
records, the runtime LZ11 streams, and the two block-identifier forms used by USRDIR/0001.
It does not claim to replace a physical PSP test; it catches the layout and archive regressions
that can make a real PSP ISO loader reject an otherwise readable image.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import iso9660
import lzss

ROOT = Path(r"D:\psp\원격수사")
BLOCK = 0x800
HEADER = 0x40
STREAM0 = 0x000000
SGXD_START = 0x1B7000
STREAM1 = 0x27E000
CRITICAL_UNTOUCHED = (
    "/PSP_GAME/PARAM.SFO",
    "/PSP_GAME/SYSDIR/EBOOT.BIN",
    "/PSP_GAME/SYSDIR/BOOT.BIN",
    "/UMD_DATA.BIN",
)


def align_up(value: int, alignment: int) -> int:
    return (value + alignment - 1) // alignment * alignment


def record_payload(iso: bytes, record: iso9660.DirectoryRecord) -> bytes:
    start = record.extent * iso9660.BLOCK
    return iso[start:start + record.size]


def layout_signature(iso: bytes):
    return [(r.offset, r.name, r.extent, r.size, r.flags) for r in iso9660.list_records(iso)]


def assert_equal(label: str, actual, expected) -> None:
    if actual != expected:
        raise SystemExit(f"FAIL {label}")
    print(f"OK   {label}")


def compare_chunks(left: bytes, right: bytes, start: int, end: int,
                   chunk: int = 4 << 20) -> bool:
    for at in range(start, end, chunk):
        if left[at:min(at + chunk, end)] != right[at:min(at + chunk, end)]:
            return False
    return True


def read_stream(blob: bytes, offset: int) -> tuple[bytes, int]:
    return lzss.decompress(blob, offset, limit=64 << 20)


def validate_0000(original: bytes, patched: bytes,
                  record: iso9660.DirectoryRecord) -> None:
    old = record_payload(original, record)
    new = record_payload(patched, record)
    old0, old0_used = read_stream(old, STREAM0)
    new0, new0_used = read_stream(new, STREAM0)
    old1, old1_used = read_stream(old, STREAM1)
    new1, new1_used = read_stream(new, STREAM1)
    assert_equal("0000 stream 0 decompressed size unchanged", len(new0), len(old0))
    if new0_used > old0_used:
        raise SystemExit("FAIL 0000 stream 0 grew beyond its original slot")
    if new1_used > old1_used:
        raise SystemExit("FAIL 0000 stream 1 grew beyond its original slot")
    assert_equal("0000 SGXD sound bank unchanged", new[SGXD_START:STREAM1],
                 old[SGXD_START:STREAM1])
    old_tail = STREAM1 + old1_used
    assert_equal("0000 trailing data unchanged", new[old_tail:], old[old_tail:])
    print(f"OK   0000 LZ11 streams valid (stream0 0x{old0_used:x}->0x{new0_used:x}, "
          f"stream1 0x{old1_used:x}->0x{new1_used:x}; "
          f"plain1 {len(old1):,}->{len(new1):,} bytes)")


def validate_0001(original: bytes, patched: bytes,
                  record: iso9660.DirectoryRecord, ledger_path: Path) -> None:
    old = record_payload(original, record)
    new = record_payload(patched, record)
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    starts = sorted({int(item["block"], 16) if isinstance(item["block"], str)
                     else int(item["block"])
                     for item in ledger["images"]})
    if not starts:
        raise SystemExit("FAIL container ledger has no blocks")

    modes = {"md5": 0, "opaque": 0}
    previous_end = 0
    for at in starts:
        if at % BLOCK:
            raise SystemExit(f"FAIL 0001 block is not 0x800-aligned: 0x{at:x}")
        if at < previous_end:
            raise SystemExit(f"FAIL 0001 blocks overlap at 0x{at:x}")
        old_plain, old_used = read_stream(old, at + HEADER)
        new_plain, new_used = read_stream(new, at + HEADER)
        assert_equal(f"0001 block 0x{at:x} plain size unchanged",
                     len(new_plain), len(old_plain))
        if new_used > old_used:
            raise SystemExit(f"FAIL 0001 block 0x{at:x} grew beyond its original slot")
        span_end = align_up(at + HEADER + old_used, BLOCK)
        if span_end > len(old) or span_end > len(new):
            raise SystemExit(f"FAIL 0001 block 0x{at:x} runs past archive")
        old_header = old[at:at + 0x10]
        new_header = new[at:at + 0x10]
        if old[at + 0x10:at + HEADER] != bytes(0x30):
            raise SystemExit(f"FAIL 0001 block 0x{at:x} has an invalid header pad")
        if new[at + 0x10:at + HEADER] != old[at + 0x10:at + HEADER]:
            raise SystemExit(f"FAIL 0001 block 0x{at:x} header pad changed")
        old_digest = hashlib.md5(old[at + HEADER:span_end]).digest()
        if old_header == old_digest:
            modes["md5"] += 1
            expected = hashlib.md5(new[at + HEADER:span_end]).digest()
            if new_header != expected:
                raise SystemExit(f"FAIL 0001 block 0x{at:x} has a stale MD5")
        else:
            modes["opaque"] += 1
            if new_header != old_header:
                raise SystemExit(f"FAIL 0001 opaque identifier changed at 0x{at:x}")
        previous_end = span_end

    if modes["opaque"] == 0:
        raise SystemExit("FAIL 0001 ledger did not exercise opaque duplicate identifiers")
    print(f"OK   0001 LZ11 blocks: {len(starts)} valid; "
          f"{modes['md5']} MD5 identifiers, {modes['opaque']} opaque identifiers preserved")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original", type=Path, required=True)
    parser.add_argument("--patched", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, default=ROOT / "work" / "container_ko.json")
    args = parser.parse_args()

    original = args.original.read_bytes()
    patched = args.patched.read_bytes()
    assert_equal("ISO size unchanged", len(patched), len(original))
    assert_equal("ISO sector alignment", len(patched) % iso9660.BLOCK, 0)
    assert_equal("ISO system/PVD area unchanged", patched[:16 * iso9660.BLOCK],
                 original[:16 * iso9660.BLOCK])
    assert_equal("ISO9660 directory layout unchanged", layout_signature(patched),
                 layout_signature(original))

    old_records = {r.name.upper(): r for r in iso9660.list_records(original)}
    new_records = {r.name.upper(): r for r in iso9660.list_records(patched)}
    for path in CRITICAL_UNTOUCHED:
        key = path.upper()
        if key not in old_records or key not in new_records:
            raise SystemExit(f"FAIL missing critical file {path}")
        assert_equal(f"{path} unchanged", record_payload(patched, new_records[key]),
                     record_payload(original, old_records[key]))

    replace_paths = ("/PSP_GAME/USRDIR/0000", "/PSP_GAME/USRDIR/0001")
    ranges = []
    for path in replace_paths:
        key = path.upper()
        old_record = old_records[key]
        new_record = new_records[key]
        assert_equal(f"{path} record size unchanged", new_record.size, old_record.size)
        assert_equal(f"{path} record LBA unchanged", new_record.extent, old_record.extent)
        ranges.append((old_record.extent * iso9660.BLOCK,
                       old_record.extent * iso9660.BLOCK + old_record.size))
    ranges.sort()
    cursor = 0
    for start, end in ranges:
        if not compare_chunks(original, patched, cursor, start):
            raise SystemExit(f"FAIL bytes outside replacement records changed before 0x{start:x}")
        cursor = end
    if not compare_chunks(original, patched, cursor, len(original)):
        raise SystemExit("FAIL bytes outside replacement records changed after the archives")
    print("OK   only 0000/0001 replacement record ranges differ")

    validate_0000(original, patched, old_records["/PSP_GAME/USRDIR/0000"])
    validate_0001(original, patched, old_records["/PSP_GAME/USRDIR/0001"], args.ledger)
    print("\nHardware-format validation passed (physical PSP test still required for final device confirmation).")


if __name__ == "__main__":
    main()
