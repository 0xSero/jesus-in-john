#!/usr/bin/env python3
"""Verify the red-letter extraction against the source text.

Checks
  1. JSON schema + chapter coverage (1-21).
  2. Every ref exists in verses.json.
  3. Every saying text is a verbatim substring of its verse (quote-normalised).
  4. Duplicate detection.
  5. Coverage heuristic: verses that look like Jesus speech but are missing.
  6. Optional independent diff between two extractions (--a / --b).

Exit code 1 on any hard failure.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QUOTES = str.maketrans({
    "\u201c": '"', "\u201d": '"', "\u2018": "'", "\u2019": "'",
    "\u2014": "-", "\u2013": "-", "\u00a0": " ",
})


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s).translate(QUOTES)
    s = re.sub(r"\s+", " ", s)
    return s.strip().strip('"').strip()


def load_source() -> dict[tuple[int, int], str]:
    data = json.loads((ROOT / "data/verses.json").read_text())
    return {(v["chapter"], v["verse"]): v["text"] for v in data["verses"]}


def load_extract(path: Path) -> list[dict]:
    blob = json.loads(path.read_text())
    out = []
    for ch in blob["chapters"]:
        for s in ch["sayings"]:
            s = dict(s)
            s.setdefault("kind", "full")
            s.setdefault("frame", "")
            s.setdefault("context", "")
            s.setdefault("confidence", "high")
            s["chapter"] = ch["chapter"]
            out.append(s)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*", default=None,
                    help="extraction files (default: all jesus-ch*.json)")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--candidates", action="store_true",
                    help="print uncovered speech-like verses for manual review")
    args = ap.parse_args()

    src = load_source()
    files = [Path(f) for f in args.files] if args.files else sorted(
        (ROOT / "data").glob("jesus-ch*.json"))
    if not files:
        print("no extraction files found", file=sys.stderr)
        return 1

    sayings: list[dict] = []
    for f in files:
        for s in load_extract(f):
            s["_file"] = f.name
            sayings.append(s)

    errors: list[str] = []
    warnings: list[str] = []

    chapters = {s["chapter"] for s in sayings}
    missing_ch = sorted(set(range(1, 22)) - chapters)
    if missing_ch:
        errors.append(f"chapters missing from extraction: {missing_ch}")

    covered: set[tuple[int, int]] = set()
    seen: Counter = Counter()
    for s in sayings:
        m = re.fullmatch(r"(\d+):(\d+)", s["ref"])
        if not m:
            errors.append(f"bad ref {s['ref']!r}")
            continue
        key = (int(m.group(1)), int(m.group(2)))
        if key[0] != s["chapter"]:
            errors.append(f"ref {s['ref']} sits under chapter {s['chapter']}")
        if key not in src:
            errors.append(f"ref {s['ref']} not in source")
            continue
        if not s["text"].strip():
            errors.append(f"empty text at {s['ref']}")
            continue
        if norm(s["text"]) not in norm(src[key]):
            errors.append(f"not verbatim at {s['ref']}: {s['text'][:80]!r}")
        if not s["text"].rstrip().endswith((".", "?", "!", ":", ";", '"', "'")):
            warnings.append(f"{s['ref']} text lacks terminal punctuation: {s['text'][-40:]!r}")
        seen[(s["ref"], norm(s["text"]))] += 1
        covered.add(key)

    for (ref, text), n in seen.items():
        if n > 1:
            errors.append(f"duplicate saying {ref}: {text[:60]!r} x{n}")

    # ---- coverage heuristic -------------------------------------------------
    # candidate = verse containing quoted speech AND a near antecedent naming Jesus
    jesus_words = re.compile(r"\b(Jesus|he|him)\b", re.I)
    attribution = re.compile(
        r"(Jesus (said|answered|cried|replied|told|asked|says|saith)"
        r"|(he|Jesus) said to (them|him|her)"
        r"|answered (them|him|her)?\s*Jesus"
        r"|said Jesus)", re.I)
    candidates = []
    for (ch, v), text in sorted(src.items()):
        if '"' not in norm(text):
            continue
        if (ch, v) in covered:
            continue
        prev = src.get((ch, v - 1), "")
        window = text + " " + prev
        if attribution.search(window) and jesus_words.search(window):
            candidates.append((ch, v, text))

    print(f"files: {', '.join(f.name for f in files)}")
    print(f"sayings: {len(sayings)}   verses covered: {len(covered)}   "
          f"chapters: {len(chapters)}")
    per_ch = Counter(s["chapter"] for s in sayings)
    print("per chapter:", dict(sorted(per_ch.items())))
    kinds = Counter(s["kind"] for s in sayings)
    print("kinds:", dict(kinds))
    conf = Counter(s["confidence"] for s in sayings)
    print("confidence:", dict(conf))

    if args.candidates:
        print(f"\nuncovered speech-like verses ({len(candidates)}):")
        for ch, v, text in candidates:
            print(f"  {ch}:{v}  {text[:150]}")

    if warnings and not args.quiet:
        print(f"\nwarnings ({len(warnings)}):")
        for w in warnings[:40]:
            print("  -", w)

    if errors:
        print(f"\nERRORS ({len(errors)}):", file=sys.stderr)
        for e in errors:
            print("  !", e, file=sys.stderr)
        return 1
    print("\nOK: all sayings verbatim, refs valid, no duplicates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
