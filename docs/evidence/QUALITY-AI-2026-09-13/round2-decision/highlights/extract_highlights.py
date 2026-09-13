"""Extract Compilatio Studium underlines from a detailed report PDF (section 3/3).

Underlines are thin filled rectangles just below text lines; their fill colour
tells the category. Output: per-line records with the flagged colour and the
words under the underline, plus per-file totals to validate against the report.
Usage: python extract_highlights.py REPORT.pdf OUT.json
"""
import json
import sys
from collections import Counter, defaultdict

import pymupdf

CYAN = (0.0, 0.75, 1.0)  # observed under AI-flagged lines


def colour_key(fill):
    return tuple(round(c, 2) for c in fill)


def extract(path):
    doc = pymupdf.open(path)
    start = next(
        (
            i
            for i in range(len(doc))
            if "sezione 3/3" in doc[i].get_text("text")
            or "section 3/3" in doc[i].get_text("text")
            or "Punti di interesse" in doc[i].get_text("text")
            or "Points of interest" in doc[i].get_text("text")
        ),
        None,
    )
    if start is None:
        raise SystemExit("section 3/3 not found")
    records, colours = [], Counter()
    for pno in range(start, len(doc)):
        page = doc[pno]
        words = page.get_text("words")  # x0,y0,x1,y1,word,block,line,wordno
        lines = defaultdict(list)
        for w in words:
            lines[(w[5], w[6])].append(w)
        underlines = [
            d
            for d in page.get_drawings()
            if d.get("fill") is not None
            and d["rect"].height <= 3
            and d["rect"].width >= 5
        ]
        for key, ws in lines.items():
            ws.sort(key=lambda w: w[0])
            x0, y0 = min(w[0] for w in ws), min(w[1] for w in ws)
            x1, y1 = max(w[2] for w in ws), max(w[3] for w in ws)
            flagged = {}
            for d in underlines:
                r = d["rect"]
                if y1 - 1.5 <= r.y0 <= y1 + 4.5 and r.x1 > x0 and r.x0 < x1:
                    ck = colour_key(d["fill"])
                    for w in ws:
                        if w[2] > r.x0 and w[0] < r.x1:
                            flagged[w[7]] = ck
            text = " ".join(w[4] for w in ws)
            flagged_words = [w[4] for w in ws if w[7] in flagged]
            for ck in set(flagged.values()):
                colours[ck] += sum(1 for w in ws if flagged.get(w[7]) == ck)
            records.append(
                {
                    "page": pno + 1,
                    "block": key[0],
                    "y": round(y0, 1),
                    "text": text,
                    "words": len(ws),
                    "flagged_words": len(flagged_words),
                    "ai_flags": [1 if flagged.get(w[7]) == CYAN else 0 for w in ws],
                    "colours": sorted({str(c) for c in flagged.values()}),
                }
            )
    total_words = sum(r["words"] for r in records)
    return {
        "file": path,
        "section3_first_page": start + 1,
        "total_words_in_section3": total_words,
        "flagged_words_by_colour": {str(k): v for k, v in colours.items()},
        "flagged_share_by_colour": {
            str(k): round(v / total_words, 4) for k, v in colours.items()
        },
        "lines": records,
    }


if __name__ == "__main__":
    out = extract(sys.argv[1])
    json.dump(out, open(sys.argv[2], "w"), ensure_ascii=False, indent=1)
    print(
        out["file"].split("/")[-1],
        "words",
        out["total_words_in_section3"],
        "shares",
        out["flagged_share_by_colour"],
    )
