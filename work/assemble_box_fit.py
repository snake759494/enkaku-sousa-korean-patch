"""Assemble translation v9: rows that overflowed the lower dialogue box, refitted at fixed size.

Issue #3.  Every non-光志 speaker row with more than three text lines is rebuilt so that it holds
in either dialogue box -- three lines of at most 33 half-widths -- and keeps its encoded length
*exactly*.  The save file stores script positions: a build whose rows changed length (v3.15
candidate, 488 bytes longer) hung on loading a save made with an earlier build, while one with
unchanged lengths (v3.14) loaded it.  So no row may move anything that follows it.

Two sources:

* mechanical -- the row re-packs into three lines once a few harmless spaces are dropped (after
  an ellipsis, after ! or ?, between Latin and Hangul, after a comma);
* condensed -- rows that need rewording, checked by check_condensed.py
  (build/condense/out_*.json).

Whatever length the new text is short of the original is padded at the end with ideographic
spaces, which the engine draws as blank, and -- when the shortfall is odd, or the last line would
pass the 19-character re-wrap width -- trailing lines holding only those spaces.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import check_condensed
import encode_korean
import rewrap_lines as R
import translation_text

ROOT = Path(r"D:\psp\원격수사")
BS = chr(92) + "n"
UPPER_ONLY = {"【코우지】"}
DELETABLE = [re.compile(r"(?<=…) (?=\S)"), re.compile(r"(?<=[!?]) (?=\S)"),
             re.compile(r"(?<=[A-Za-z]) (?=[가-힣])"), re.compile(r"(?<=,) (?=\S)")]


def encoded_len(text: str, slots) -> int:
    return len(encode_korean.encode_text(text.replace(BS, "\n"), slots))


def reflow(head: str, body: str):
    """Greedy re-pack by the measured on-screen width and the build's character limit."""
    out, current = [], ""
    for word in body.split():
        candidate = f"{current} {word}".strip()
        if current and (check_condensed.width(candidate) > check_condensed.LIMIT
                        or len(candidate) > check_condensed.MAX_CHARS):
            out.append(current)
            current = word
        else:
            current = candidate
    if current:
        out.append(current)
    if len(out) > check_condensed.TEXT_LINES or any(
            check_condensed.width(l) > check_condensed.LIMIT
            or len(l) > check_condensed.MAX_CHARS for l in out):
        return None
    return [head] + out


def mechanical(lines: list[str], slots, budget: int):
    head, body = lines[0], " ".join(l for l in lines[1:] if l.strip())
    for deletions in range(6):
        squeezed, left = body, deletions
        for pattern in DELETABLE:
            while left:
                m = pattern.search(squeezed)
                if not m:
                    break
                squeezed = squeezed[:m.start()] + squeezed[m.end():]
                left -= 1
        if left:
            return None
        packed = reflow(head, squeezed)
        if packed and encoded_len(BS.join(packed), slots) <= budget:
            return BS.join(packed)
    return None


def pad(text: str, budget: int, slots) -> str:
    short = budget - encoded_len(text, slots)
    if short < 0:
        raise ValueError("text longer than its budget")
    room = check_condensed.MAX_CHARS - len(text.split(BS)[-1])
    for extra in range(0, 40):
        spaces = short - extra                 # each extra line costs its one-byte break
        if spaces < 0 or spaces % 2:
            continue
        spaces //= 2
        if spaces <= room + extra * check_condensed.MAX_CHARS:
            break
    else:
        raise ValueError("cannot pad")
    first = min(spaces, room)
    text += "　" * first
    spaces -= first
    for _ in range(extra):
        take = min(spaces, check_condensed.MAX_CHARS)
        text += BS + "　" * take
        spaces -= take
    assert encoded_len(text, slots) == budget, (encoded_len(text, slots), budget)
    assert all(len(l) <= check_condensed.MAX_CHARS for l in text.split(BS)[1:])
    return text


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ko", type=Path, default=ROOT / "build" / "translation_ko_v7_final.tsv")
    parser.add_argument("--condensed", type=Path, nargs="*",
                        default=sorted((ROOT / "build" / "condense").glob("out_*.json")))
    parser.add_argument("--slots", type=Path, default=ROOT / "build" / "korean_slots_retranslated_v2.json")
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "translation_ko_v9.tsv")
    parser.add_argument("--report", type=Path, default=ROOT / "build" / "box_fit_v9.json")
    args = parser.parse_args()

    slots = {c: int(i) for c, i in json.loads(args.slots.read_text(encoding="utf-8"))["slots"].items()}
    header, ko_rows = translation_text.parse_loose_tsv(args.ko)
    rows = [list(r) for r in ko_rows]
    current = {r[0]: r[2] for r in rows if len(r) >= 3}
    condensed = {}
    for path in args.condensed:
        condensed.update(json.loads(path.read_text(encoding="utf-8")))

    changed, unfixed, rejected = [], [], []
    for row in rows:
        if len(row) < 3:
            continue
        text = row[2]
        lines = text.split(BS)
        if (not R.TAG.match(lines[0]) or lines[0] in UPPER_ONLY
                or text.lstrip().startswith(("［", "[")) or len(lines) - 1 <= check_condensed.TEXT_LINES):
            continue
        budget = encoded_len(text, slots)
        new = mechanical(lines, slots, budget)
        source = "mechanical"
        if new is None and row[0] in condensed:
            issues = check_condensed.problems(row[0], condensed[row[0]], current, slots)
            if issues:
                rejected.append({"offset": row[0], "issues": issues})
            else:
                new, source = condensed[row[0]], "condensed"
        if new is None:
            unfixed.append(row[0])
            continue
        padded = pad(new, budget, slots)
        changed.append({"offset": row[0], "source": source, "before": text, "after": padded})
        row[2] = padded
        row[1] = str(len(padded.split(BS)))

    args.out.write_text(header + "\n" + "\n".join("\t".join(r) for r in rows) + "\n", encoding="utf-8")
    args.report.write_text(json.dumps(
        {"schema": "enkaku_box_fit_v1", "changed": len(changed),
         "mechanical": sum(c["source"] == "mechanical" for c in changed),
         "condensed": sum(c["source"] == "condensed" for c in changed),
         "unfixed": unfixed, "rejected": rejected, "rows": changed},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(changed)} rows refitted "
          f"({sum(c['source'] == 'mechanical' for c in changed)} mechanical, "
          f"{sum(c['source'] == 'condensed' for c in changed)} condensed), "
          f"{len(unfixed)} unfixed, {len(rejected)} rejected")
    print(f"-> {args.out}\n-> {args.report}")


if __name__ == "__main__":
    main()
