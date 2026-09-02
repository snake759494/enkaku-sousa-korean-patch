"""Change only PSP_SYSTEM_VER in a PSP PARAM.SFO without changing its layout."""

from __future__ import annotations

import argparse
import struct
from pathlib import Path


def locate_system_version(data: bytes) -> tuple[int, int, str]:
    """Return the byte range and decoded value of the PSP_SYSTEM_VER field."""
    if data[:4] != b"\x00PSF":
        raise SystemExit("not a PARAM.SFO file")
    _, _version, key_start, data_start, count = struct.unpack_from("<4s4I", data, 0)
    for index in range(count):
        entry = struct.unpack_from("<HHIII", data, 20 + index * 16)
        key_offset, _format, data_length, _max_length, data_offset = entry
        key_at = key_start + key_offset
        key_end = data.find(b"\0", key_at)
        if key_end < 0:
            raise SystemExit("unterminated PARAM.SFO key")
        key = data[key_at:key_end].decode("ascii")
        if key != "PSP_SYSTEM_VER":
            continue
        value_at = data_start + data_offset
        value_end = value_at + data_length
        if value_end > len(data):
            raise SystemExit("PARAM.SFO value runs past the file")
        raw = data[value_at:value_end].split(b"\0", 1)[0]
        return value_at, value_end, raw.decode("ascii")
    raise SystemExit("PARAM.SFO has no PSP_SYSTEM_VER field")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--src", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--from-version", default="5.02")
    parser.add_argument("--to-version", default="5.00")
    args = parser.parse_args()

    original = args.src.read_bytes()
    start, end, old_version = locate_system_version(original)
    if old_version != args.from_version:
        raise SystemExit(
            f"expected PSP_SYSTEM_VER {args.from_version}, found {old_version}")
    encoded = (args.to_version + "\0").encode("ascii")
    if len(encoded) != end - start:
        raise SystemExit(
            f"new version needs {len(encoded)} bytes, field has {end - start}")

    patched = bytearray(original)
    patched[start:end] = encoded
    changed = [at for at, (left, right) in enumerate(zip(original, patched))
               if left != right]
    if any(at < start or at >= end for at in changed):
        raise SystemExit("PARAM.SFO changed outside PSP_SYSTEM_VER")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(bytes(patched))
    print(f"PSP_SYSTEM_VER: {old_version} -> {args.to_version}")
    print(f"   field: 0x{start:x}-0x{end:x}; {len(changed)} bytes changed")
    print(f"   size unchanged: {len(original):,} bytes")
    print(f"-> {args.out}")


if __name__ == "__main__":
    main()
