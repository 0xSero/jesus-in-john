#!/usr/bin/env python3
"""Build the deliverables from the verified extraction.

Inputs:  data/verses.json, data/jesus-ch*.json
Outputs: data/jesus-words.json, jesus-in-john.md, build/content.typ, README.md
Then:    typst compile build/doc.typ jesus-in-john.pdf
"""
from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
BUILD = ROOT / "build"
GENERATED = "2026-11-01"

QUOTES = str.maketrans({
    "\u201c": '"', "\u201d": '"', "\u2018": "'", "\u2019": "'",
    "\u2014": "-", "\u2013": "-", "\u00a0": " ",
})

CHAPTER_SUMMARY = {
    1: "The Word becomes flesh; the first disciples follow, and he speaks for the first time on the road to Galilee.",
    2: "Water into wine at Cana, the temple cleansed, and his body named as the temple that will be raised.",
    3: "Nicodemus comes at night: the new birth, the wind, the lifted serpent, and the light that judges.",
    4: "The woman at the well: living water, worship in spirit, and fields already white for harvest.",
    5: "The lame man at Bethesda, sabbath controversy, and the long defense of the Son who does what the Father does.",
    6: "Bread for five thousand, the bread of life in Capernaum, and the words that cost him the crowd.",
    7: "At the Feast of Tabernacles: rivers of living water, the light of the world, and officers sent to arrest him.",
    8: "The woman taken in adultery, the light of the world, the truth that frees, and the claim that precedes Abraham.",
    9: "A man born blind is healed, and the Shepherd's voice divides those who see from those who say they see.",
    10: "The good shepherd, the door of the sheep, the other sheep, and the claim that he and the Father are one.",
    11: "Lazarus dies and is raised: the resurrection and the life, and a price set on his own head.",
    12: "Anointed at Bethany, welcomed into Jerusalem, and told that a grain of wheat must fall into the earth.",
    13: "The feet washed, the betrayer named, and the new commandment given as the hour begins.",
    14: "The way, the truth and the life, another Comforter promised, and peace left as a legacy.",
    15: "The vine and the branches, the command to love, and the world's hatred foretold.",
    16: "The Comforter, the conviction of the world, and plain speech that ends in tribulation and victory.",
    17: "The prayer to the Father: glory shared before the world was, and oneness as the sign of mission.",
    18: "Arrested in the garden, tried before Pilate, answering for the truth of a kingdom not of this world.",
    19: "Crucified: his mother given a home, the Scriptures fulfilled, and the last word — it is finished.",
    20: "The empty tomb, the risen Christ speaking peace, Thomas believing, and the purpose of the book.",
    21: "Breakfast on the shore of Tiberias: love questioned three times, and a future foretold.",
}

PARTS = [
    ("I", "The Book of Signs", "Chapters 1–12", range(1, 13)),
    ("II", "The Book of Glory", "Chapters 13–21", range(13, 22)),
]

# Verses the narrator reports as words of Jesus but does not speak in a scene.
REPORTED = [
    ("13:29", "Buy what things we need for the feast",
     "Judas leaves the table and the others guess what Jesus had told him."),
    ("18:6", "I am he",
     "The narrator repeats the answer given in the garden a moment earlier (18:5)."),
    ("18:9", "Of those whom you have given me, I have lost none",
     "The narrator quotes a word from the farewell prayer (17:12)."),
    ("21:23", "If I desire that he stay until I come, what is that to you?",
     "The narrator corrects a rumour by re-quoting 21:22."),
]


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s).translate(QUOTES)
    return re.sub(r"\s+", " ", s).strip()


def clean(s: str) -> str:
    """Whitespace-normalise and strip the outer speech marks, keeping WEB typography."""
    t = re.sub(r"\s+", " ", s).strip()
    if t[:1] in '"\u201c' and t[-1:] in '"\u201d':
        t = t[1:-1].strip()
    return t


def wordcount(s: str) -> int:
    return len(re.findall(r"[A-Za-z0-9']+", s))


def load() -> tuple[list[dict], dict[str, str]]:
    verses = {f"{v['chapter']}:{v['verse']}": norm(v["text"])
              for v in json.loads((DATA / "verses.json").read_text())["verses"]}
    sayings = []
    for f in sorted(DATA.glob("jesus-ch*.json")):
        blob = json.loads(f.read_text())
        for ch in blob["chapters"]:
            for s in ch["sayings"]:
                sayings.append({
                    "chapter": ch["chapter"],
                    "ref": s["ref"],
                    "kind": s.get("kind", "full"),
                    "text": clean(s["text"]),
                    "scene": norm(s.get("scene") or s.get("context") or "") or "in conversation",
                    "confidence": s.get("confidence", "high"),
                    "note": norm(s.get("note") or ""),
                })
    sayings.sort(key=lambda s: tuple(int(x) for x in s["ref"].split(":")))
    return sayings, verses


CONTINUES = (",", ";", ":", "-")


def ends_open(text: str) -> bool:
    t = text.rstrip().rstrip('"').rstrip()
    return t.endswith(CONTINUES)


def label_range(a: str, b: str) -> str:
    ca, va = a.split(":")
    cb, vb = b.split(":")
    return f"{ca}:{va}–{vb}" if ca == cb else f"{a}–{b}"


def merge_runs(sayings: list[dict]) -> list[dict]:
    """Join sayings that are one sentence carried across a verse break."""
    runs: list[dict] = []
    for s in sayings:
        prev = runs[-1] if runs else None
        ch, v = (int(x) for x in s["ref"].split(":"))
        can = (
            prev is not None
            and ends_open(prev["segs"][-1]["t"])
            and prev["confidence"] == s["confidence"]
            and prev["note"] == s["note"]
            and prev["chapter"] == ch
            and int(prev["segs"][-1]["ref"].split(":")[1]) == v - 1
        )
        if can:
            prev["segs"].append({"ref": s["ref"], "t": s["text"]})
            prev["ref"] = label_range(prev["segs"][0]["ref"], s["ref"])
            prev["text"] = " ".join(seg["t"] for seg in prev["segs"])
        else:
            runs.append({
                "chapter": ch,
                "ref": s["ref"],
                "segs": [{"ref": s["ref"], "t": s["text"]}],
                "text": s["text"],
                "scene": s["scene"],
                "confidence": s["confidence"],
                "note": s["note"],
                "kind": s["kind"],
            })
    return runs


def note_refs_label(refs: list[str]) -> str:
    first, last = refs[0], refs[-1]
    ch = first.split(":")[0]
    if len(refs) == 1:
        return first
    v0 = int(first.split(":")[1].split("–")[0])
    v1 = int(last.split(":")[1].split("–")[-1])
    return f"{ch}:{v0}–{v1}" if v1 > v0 else f"{first}"


def chapter_notes(blocks: list[dict]) -> list[dict]:
    """One entry per distinct note in a chapter, carrying the refs it covers."""
    notes: list[dict] = []
    for b in blocks:
        for s in b["sayings"]:
            if not s["note"]:
                continue
            for n in notes:
                if n["text"] == s["note"]:
                    n["refs"].append(s["ref"])
                    break
            else:
                notes.append({"text": s["note"], "refs": [s["ref"]]})
    for n in notes:
        n["label"] = note_refs_label(n["refs"])
        del n["refs"]
    return notes


def build_blocks(sayings: list[dict]) -> list[dict]:
    blocks: list[dict] = []
    for s in sayings:
        if blocks and blocks[-1]["scene"] == s["scene"]:
            blocks[-1]["sayings"].append(s)
        else:
            blocks.append({"scene": s["scene"], "sayings": [s]})
    for b in blocks:
        b["sayings"] = merge_runs(b["sayings"])
        b["scene"] = b["scene"][0].upper() + b["scene"][1:]
    return blocks


def stats(sayings: list[dict]) -> dict:
    wc = [(wordcount(s["text"]), s["ref"]) for s in sayings]
    total = sum(w for w, _ in wc)
    longest = max(wc)
    counts = Counter(w.lower().strip("'") for s in sayings
                     for w in re.findall(r"[A-Za-z']+", s["text"]))
    terms = [["Father", counts["father"]]] if counts["father"] else []
    for t in ["believe", "world", "life", "love", "truth", "glory", "light",
              "hour", "work", "works", "sheep", "eternal", "abide", "sent"]:
        if counts[t] > 1:
            terms.append([t, counts[t]])
    terms.sort(key=lambda x: -x[1])
    return {
        "sayings": len(sayings),
        "verses": len({s["ref"] for s in sayings}),
        "chapters": len({s["chapter"] for s in sayings}),
        "words": total,
        "full": sum(1 for s in sayings if s["kind"] == "full"),
        "partial": sum(1 for s in sayings if s["kind"] == "partial"),
        "avg_words": round(total / len(sayings), 1),
        "longest_words": longest[0],
        "longest_ref": longest[1],
        "flagged": sum(1 for s in sayings if s["confidence"] != "high" or s["note"]),
        "terms": terms[:10],
    }


def typst_json(obj) -> str:
    if isinstance(obj, dict):
        return "(" + ", ".join(f'"{k}": {typst_json(v)}' for k, v in obj.items()) + ")"
    if isinstance(obj, list):
        inner = ", ".join(typst_json(v) for v in obj)
        return "(" + inner + ("," if obj else "") + ")"
    if isinstance(obj, str):
        return '"' + obj.replace("\\", "\\\\").replace('"', '\\"') + '"'
    if isinstance(obj, bool):
        return "true" if obj else "false"
    return str(obj)


def main() -> None:
    sayings, verses = load()
    BUILD.mkdir(exist_ok=True)
    json.dump({"translation": "World English Bible (WEB, public domain)",
               "generated": GENERATED,
               "note": "Speech attributed to Jesus in the Gospel of John, verse-keyed. "
                       "confidence != high, or a non-empty note, flags a contested attribution or text.",
               "sayings": sayings},
              open(DATA / "jesus-words.json", "w"), indent=1, ensure_ascii=False)

    by_ch = {n: [s for s in sayings if s["chapter"] == n] for n in range(1, 22)}
    st = stats(sayings)

    content = {
        "translation": "World English Bible",
        "generated": GENERATED,
        "stats": st,
        "reported": [{"ref": r, "quote": q, "why": w} for r, q, w in REPORTED],
        "parts": [
            {"numeral": num, "title": title, "range": rng,
             "chapters": [
                 {"n": n, "summary": CHAPTER_SUMMARY[n],
                  "blocks": build_blocks(by_ch[n]),
                  "notes": chapter_notes(build_blocks(by_ch[n])),
                  "count": len(by_ch[n])}
                 for n in r
             ]}
            for num, title, rng, r in PARTS
        ],
    }
    (BUILD / "content.typ").write_text(
        "// generated by tools/build.py — do not edit\n#let book = "
        + typst_json(content) + "\n")

    # ------------------------------------------------------------- markdown
    md = ["# The Words of Jesus in the Gospel of John", "",
          f"*Every sentence the Fourth Gospel puts in his mouth — {st['sayings']} sayings "
          f"across {st['verses']} verses in 21 chapters.*", "",
          "Text: **World English Bible** (public domain). The narrator's commentary, the Father's "
          "voice from heaven, and every other speaker are removed. Verse references let you find "
          "each line in any Bible. A † marks a line whose attribution or transmission is contested.",
          "", "---", ""]
    for part in content["parts"]:
        md += [f"## Part {part['numeral']} — {part['title']}", "", f"*{part['range']}*", ""]
        for ch in part["chapters"]:
            md += [f"### John {ch['n']}", "", f"*{ch['summary']}*", ""]
            if not ch["blocks"]:
                md += ["*No recorded speech in this chapter.*", ""]
            for b in ch["blocks"]:
                md += [f"**{b['scene']}**", ""]
                for s in b["sayings"]:
                    flag = " †" if (s["confidence"] != "high" or s["note"]) else ""
                    md += [f"> **{s['ref']}**{flag} — {s['text']}", ""]
                md += [""]
            for n in ch["notes"]:
                md += [f"*† {n['label']} — {n['text']}*", ""]
    md += ["---", "",
           "## Appendix — words the gospel reports but does not speak in a scene", "",
           "The narrator refers to things Jesus said without putting them in a scene. They are "
           "speech attributed to him, so they belong in the record, but a red-letter edition does "
           "not print them in red, and neither does the main text above.", ""]
    md += [f"- **{r}** — “{q}” · {w}" for r, q, w in REPORTED]
    md += ["", f"*Compiled {GENERATED} from the World English Bible (public domain).*"]
    (ROOT / "jesus-in-john.md").write_text("\n".join(md).rstrip() + "\n")

    # --------------------------------------------------------------- README
    idx = ["| Chapter | Sayings | Verses | Scene |", "|:--|--:|:--|:--|"]
    for n in range(1, 22):
        ss = by_ch[n]
        vr = f"{ss[0]['ref']} → {ss[-1]['ref']}" if ss else "—"
        short = CHAPTER_SUMMARY[n].split(":")[0].split(",")[0]
        idx.append(f"| John {n} | {len(ss)} | {vr} | {short} |")
    terms = "\n".join(f"- **{t}** — {c}×" for t, c in st["terms"])
    readme = f"""# The Words of Jesus in the Gospel of John

Every sentence the Fourth Gospel attributes to Jesus — pulled out of the narrative, in order,
with the narrator, the crowds, the disciples and the Father's voice from heaven removed.

**{st['sayings']} sayings · {st['verses']} of John's 879 verses · {st['words']:,} words · 21 chapters**

<p align="left">
  <img src="docs/preview-cover.png" width="250" alt="Cover">
  <img src="docs/preview-page.png" width="250" alt="Interior page">
</p>

| | |
|:--|:--|
| **Read on a phone** | [`jesus-in-john.pdf`](jesus-in-john.pdf) — 100 × 200 mm, phone-shaped pages ([latest release download](../../releases/latest)) |
| **Read on GitHub** | [`jesus-in-john.md`](jesus-in-john.md) — the same text in markdown |
| **Reuse the data** | [`data/jesus-words.json`](data/jesus-words.json) — verse-keyed JSON |
| **Translation** | World English Bible (public domain, modern English) |
| **Checked** | every saying machine-verified as a verbatim substring of its verse |

## What is and isn't here

Included: direct speech — questions, commands, one-word replies, prayers to the Father,
Scripture he quotes, and speech after the resurrection. Sayings that run across a verse break are
joined into one paragraph so the sentence reads as a sentence; the verse range stays on the line.

Excluded on purpose:

- the narrator's commentary, even where it sounds like him (1:1–18, 3:31–36, 7:39, 12:37–43);
- the Father's voice from heaven (12:28);
- John the Baptist (1:15–34, 3:27–30), the disciples, the Samaritan woman, Nicodemus, Martha,
  Mary, Pilate, the crowds, and the healed blind man;
- words other characters *report* he said (4:53, 6:41, 7:36, 8:22, 9:11 …) — those are their
  claims, not his speech;
- the narrator's own four citations of his words, which are collected in the appendix instead.

## Where the attribution is contested

Two flags, both marked † in the text and in the data:

1. **3:13–21** — the most famous passage in the book. Many editions print it as the evangelist's
   commentary; many print it in red. It is included here with `confidence: medium` and a note,
   because the brief was *everything attributed* — silently dropping 3:16 would be the bigger error.
2. **8:1–11** (the woman taken in adultery) — absent from the earliest manuscripts and printed in
   brackets in most modern Bibles. The words are unambiguously Jesus inside John's narrative;
   the note is about the text, not the speaker.

## The numbers

| Metric | Value |
|:--|--:|
| Sayings (speech units) | {st['sayings']} |
| Verses containing his speech | {st['verses']} of 879 ({round(100 * st['verses'] / 879)}%) |
| Whole-verse / partial-verse sayings | {st['full']} / {st['partial']} |
| Words spoken | {st['words']:,} |
| Average saying | {st['avg_words']} words |
| Longest single saying | {st['longest_words']} words ({st['longest_ref']}) |
| Sayings carrying a flag | {st['flagged']} |

Most frequent terms in his mouth (English of this translation, not the Greek):

{terms}

## Chapter index

{chr(10).join(idx)}

## How it was checked

`tools/verify.py` enforces four things and exits non-zero on any failure:

1. every reference exists in the source text;
2. every saying's text is a **verbatim substring** of that verse (quote-normalised) — no
   paraphrase, no stitching, no invented words;
3. no duplicated sayings, no crossed chapter boundaries;
4. a coverage pass listing every verse that contains quoted speech near a naming of Jesus and is
   still uncovered, for manual review.

The extraction was done in two independent halves (chapters 1–11 and 12–21) against the same
stored source text, then reconciled; the † flags mark where reasonable readings of John's Greek
differ.

## Reproduce it

```bash
make            # data → verify → PDF → preview images
# or step by step:
python3 tools/build.py     # data/jesus-words.json, jesus-in-john.md, build/content.typ
python3 tools/verify.py    # schema, verbatim, duplicate and coverage checks
typst compile build/doc.typ jesus-in-john.pdf
```

The typesetting lives in [`build/doc.typ`](build/doc.typ) — 100 × 200 mm pages, Charter, one column,
running chapter head, PDF bookmarks per chapter. The structure lives in [`build/content.typ`](build/content.typ),
generated at build time so the prose never drifts from the data.

Source text fetched once from [bible-api.com](https://bible-api.com) (`translation=web`) and stored
in [`data/verses.json`](data/verses.json), so the build is offline and deterministic.

## Notes on the text

The World English Bible is a public-domain modern-English revision of the American Standard
Version of 1901. Only the quotation marks around his speech were removed — nothing else was
edited. Verse numbers are the handle back to the full scene in any Bible.

Compilation, data and tooling: public domain (CC0). The scripture text is public domain.
"""
    (ROOT / "README.md").write_text(readme)
    print(f"built: {st['sayings']} sayings, {st['verses']} verses, {st['words']} words, "
          f"{st['flagged']} flagged")
    print("per chapter:", {n: len(by_ch[n]) for n in range(1, 22)})


if __name__ == "__main__":
    main()
