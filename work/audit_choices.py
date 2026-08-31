"""Audit that selectable investigation answers are translated in the runtime TSV."""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path


JAPANESE = re.compile(r"[ぁ-んァ-ヶ一-龯々〆ヵヶ]")
EXPECTED = {
    "［押してみる］": "［눌러 본다］",
    "［押さない］": "［누르지 않는다］",
}


def read_rows(path: Path) -> dict[str, str]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = csv.DictReader(handle, delimiter="\t")
        if rows.fieldnames != ["offset", "lines", "text"]:
            raise SystemExit(f"{path}: unexpected columns {rows.fieldnames!r}")
        return {row["offset"]: row["text"] for row in rows}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ja", type=Path, required=True, help="original Japanese TSV")
    parser.add_argument("--ko", type=Path, required=True, help="translated Korean TSV")
    args = parser.parse_args()

    ja = read_rows(args.ja)
    ko = read_rows(args.ko)
    missing = sorted(set(ja) - set(ko))
    extra = sorted(set(ko) - set(ja))
    if missing or extra:
        raise SystemExit(f"offset mismatch: missing={missing[:3]} extra={extra[:3]}")

    selected = [(offset, text, ko[offset]) for offset, text in ja.items() if "［" in text]
    residual = [(offset, source, translated) for offset, source, translated in selected
                if JAPANESE.search(translated)]
    if residual:
        details = ", ".join(f"{offset}:{translated}" for offset, _, translated in residual[:5])
        raise SystemExit(f"Japanese remains in {len(residual)} choice rows: {details}")

    for source, expected in EXPECTED.items():
        actual = [translated for _, text, translated in selected if text == source]
        if not actual or any(value != expected for value in actual):
            raise SystemExit(f"answer mapping mismatch: {source} -> {actual!r}, expected {expected!r}")

    print(f"choice rows: {len(selected)}")
    print("Japanese residuals: 0")
    print("answer mappings:押してみる/押さない -> 눌러 본다/누르지 않는다")


if __name__ == "__main__":
    main()
