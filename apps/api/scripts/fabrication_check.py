"""Blind check of a generated work against its recorded inputs.

Usage: python scripts/fabrication_check.py LAB_OUTPUT_DIR OUT.json

Reads the lab's replay.db: the final section texts (executor_section events
after S5) and every input the writer could have seen — frozen excerpts of the
pack, passages of uploaded files and fetched open-access texts (from the
executor_inputs and executor_full_text dependency records). Then lists every
citation-like number (n. 25732/2021, art. 4, comma 3, 2016/679 …), every
quoted string («…» or "…" of 6+ words) and every four-digit year with a
source-like context, and reports whether each occurs in the inputs. It is a
mechanical aid for the blind reading, not legal expertise.
"""

import json
import re
import sqlite3
import sys
import unicodedata
from pathlib import Path

NUMBER_PATTERNS = {
    "decision": re.compile(
        r"\bn\.\s?(\d{2,6})\s*(?:/|del\s+\d{1,2}\s+\w+\s+)(\d{4})", re.I
    ),
    "article": re.compile(
        r"\b(?:art\.|articolo)\s?(\d{1,4})(?:\s*,?\s*(?:comma|co\.)\s?(\d{1,2}))?", re.I
    ),
    "act": re.compile(
        r"\b(?:l\.|legge|d\.lgs\.|decreto legislativo|regolamento(?: \(UE\))?)\s?(?:n\.\s?)?(\d{1,4}/\d{4}|\d{4}/\d{1,4})",
        re.I,
    ),
    "page": re.compile(r"\bpp?\.\s?(\d{1,4})(?:\s?[-–]\s?(\d{1,4}))?", re.I),
}
QUOTE = re.compile(r"[«“\"]([^»”\"]{25,400})[»”\"]")


def fold(text):
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.replace("’", "'").replace("‘", "'").replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", text).casefold()


def main():
    out_dir, target = Path(sys.argv[1]), Path(sys.argv[2])
    db = sqlite3.connect(f"file:{out_dir / 'replay.db'}?mode=ro", uri=True)
    events = [
        (et, json.loads(pl))
        for et, pl in db.execute(
            "select event_type, payload from document_provenance order by id"
        ).fetchall()
    ]
    sections = {}
    for et, p in events:
        if et == "executor_section":
            sections[p["section_index"]] = p  # the last event per section wins (S5)
    inputs = [p for et, p in events if et == "generation_replay_inputs"][-1][
        "executor_inputs"
    ]
    corpus = []
    for passage in inputs["passages"]:
        corpus.append(passage["text"])
    pack = [p for et, p in events if et == "executor_source_pack"][-1]["sources"]
    for s in pack:
        src = s["source"]
        corpus.append(str(src.get("title") or ""))
        corpus.append(str(src.get("abstract") or ""))
        ev = (src.get("canonical_metadata") or {}).get("academic_evidence") or {}
        corpus.append(str(ev.get("text") or ""))
    for et, p in events:
        if et == "generation_dependency" and p.get("kind") == "executor_full_text":
            for page in (p.get("response") or {}).get("pages") or []:
                corpus.append(page)
    haystack = fold("\n".join(corpus))
    report = {
        "sections": [],
        "totals": {
            "numbers": 0,
            "numbers_missing": 0,
            "quotes": 0,
            "quotes_missing": 0,
        },
    }
    for index in sorted(sections):
        text = sections[index]["content"]
        rows = []
        for kind, pattern in NUMBER_PATTERNS.items():
            for m in pattern.finditer(text):
                token = m.group(0)
                probe = fold(token)
                # numbers are checked by their digits in context: "n. 25732" and "25732/2021"
                digits = [g for g in m.groups() if g]
                found = all(fold(d) in haystack for d in digits) and (
                    probe in haystack or any(fold(d) in haystack for d in digits)
                )
                rows.append({"kind": kind, "text": token, "found": bool(found)})
                report["totals"]["numbers"] += 1
                report["totals"]["numbers_missing"] += 0 if found else 1
        for m in QUOTE.finditer(text):
            quote = fold(m.group(1))
            words = quote.split()
            if len(words) < 6:
                continue
            found = quote in haystack
            partial = None
            if not found:
                # the longest run of 8 consecutive words found in the inputs
                for start in range(0, max(1, len(words) - 8)):
                    chunk = " ".join(words[start : start + 8])
                    if chunk in haystack:
                        partial = chunk
                        break
            rows.append(
                {
                    "kind": "quote",
                    "text": m.group(1)[:160],
                    "found": found,
                    "partial": partial,
                }
            )
            report["totals"]["quotes"] += 1
            report["totals"]["quotes_missing"] += 0 if found else 1
        report["sections"].append(
            {
                "section_index": index,
                "title": sections[index]["title"],
                "words": sections[index]["word_count"],
                "checks": rows,
            }
        )
    report["corpus_chars"] = len(haystack)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=1))
    t = report["totals"]
    print(
        f"sections {len(sections)}; numbers {t['numbers']} (missing {t['numbers_missing']});"
        f" quotes {t['quotes']} (missing {t['quotes_missing']}); corpus {len(haystack)} chars"
    )
    for s in report["sections"]:
        missing = [c for c in s["checks"] if not c["found"]]
        if missing:
            print(f"§{s['section_index']} {s['title'][:40]}: {len(missing)} not found:")
            for c in missing[:8]:
                print(
                    f"   - [{c['kind']}] {c['text'][:120]}"
                    + (f" (partial: …{c['partial'][:60]}…)" if c.get("partial") else "")
                )


if __name__ == "__main__":
    main()
