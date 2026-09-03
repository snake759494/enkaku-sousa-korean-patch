"""Verify the PSP stream alignment fix against the generated runtime report.

The PSP interpreter uses word loads for the stream's section destinations and pointer
arrays.  This check is deliberately independent of the ISO checker: it binds the
reported source-to-output map to the actual output bytes, verifies every original
word-aligned target is still word-aligned, and checks that the header words contain
the mapped destinations that the reflow wrote.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path


HEADER_INDICES = tuple(range(8)) + (29, 30)
ALIGNMENT = 4


def fail(message: str) -> None:
    raise SystemExit(f"FAIL {message}")


def expected_sources(original: bytes, arrays_path: Path) -> set[int]:
    sources = {struct.unpack_from("<I", original, index * 4)[0]
               for index in HEADER_INDICES}
    arrays = json.loads(arrays_path.read_text(encoding="utf-8")).get("arrays", [])
    sources.update(int(start) for start, _end in arrays if int(start) % ALIGNMENT == 0)
    if any(source < 0 or source >= len(original) for source in sources):
        fail("alignment target is outside the original stream")
    return sources


def verify_alignment(original: bytes, patched: bytes, report: dict,
                     arrays_path: Path) -> None:
    alignment = report.get("alignment", {})
    details = alignment.get("target_details", [])
    sources = expected_sources(original, arrays_path)

    if report.get("output_size") != len(patched):
        fail("runtime report output size does not match the patched stream")
    if report.get("output_sha256") != hashlib.sha256(patched).hexdigest():
        fail("runtime report output hash does not match the patched stream")
    if alignment.get("alignment") != ALIGNMENT:
        fail("runtime report does not describe 4-byte alignment")
    if alignment.get("targets") != len(sources) or len(details) != len(sources):
        fail("runtime report target count does not match pointer/header inventory")

    mapped_by_source = {}
    for detail in details:
        source = int(detail["source_offset"])
        mapped = int(detail["mapped_offset"])
        if source not in sources:
            fail(f"unexpected alignment target 0x{source:x}")
        if source in mapped_by_source:
            fail(f"duplicate alignment target 0x{source:x}")
        if source % ALIGNMENT or mapped % ALIGNMENT:
            fail(f"unaligned source/output target 0x{source:x}->0x{mapped:x}")
        if not (0 <= mapped < len(patched)):
            fail(f"mapped target outside patched stream 0x{mapped:x}")
        mapped_by_source[source] = mapped

    if set(mapped_by_source) != sources:
        fail("runtime report omitted an alignment target")
    if alignment.get("aligned_targets") != len(sources):
        fail("runtime build did not align every target")

    for index in HEADER_INDICES:
        source = struct.unpack_from("<I", original, index * 4)[0]
        expected = mapped_by_source[source]
        actual = struct.unpack_from("<I", patched, index * 4)[0]
        if actual != expected:
            fail(f"header[{index}] points to 0x{actual:x}, expected 0x{expected:x}")

    padding = alignment.get("padding_spans", [])
    padding_bytes = 0
    for item in padding:
        source = int(item["source_offset"])
        size = int(item["bytes"])
        if source not in mapped_by_source:
            fail(f"padding has no alignment target at 0x{source:x}")
        start = mapped_by_source[source] - size
        if start < 0 or patched[start:mapped_by_source[source]] != bytes(size):
            fail(f"padding bytes are not zero at output 0x{start:x}")
        padding_bytes += size
    if padding_bytes != int(alignment.get("padding_bytes", -1)):
        fail("runtime report padding byte total is inconsistent")

    print(f"OK   4-byte alignment: {len(sources)}/{len(sources)} targets")
    print(f"OK   header destinations: {len(HEADER_INDICES)}/{len(HEADER_INDICES)} remapped")
    print(f"OK   zero padding: {len(padding)} spans, {padding_bytes} bytes")
    print(f"OK   report/output SHA-256: {report['output_sha256']}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original", type=Path, required=True,
                        help="decompressed original stream")
    parser.add_argument("--patched", type=Path, required=True,
                        help="decompressed patched stream")
    parser.add_argument("--report", type=Path, required=True,
                        help="runtime_v312_report.json from build_runtime_refs.py")
    parser.add_argument("--arrays", type=Path,
                        default=Path(r"D:\psp\원격수사\build\pointer_arrays.json"))
    args = parser.parse_args()

    verify_alignment(
        args.original.read_bytes(),
        args.patched.read_bytes(),
        json.loads(args.report.read_text(encoding="utf-8")),
        args.arrays,
    )


if __name__ == "__main__":
    main()
