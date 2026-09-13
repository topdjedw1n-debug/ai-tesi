"""Contrastive analysis of AI-underlined vs clean text in Compilatio reports.

Input: *.lines.json from extract_highlights.py plus the section titles of the
work (from the lab report). Output: per-section shares, paragraph-position
effect, sentence-feature rates, and example paragraphs for reading.
"""
import json
import re
import sys
from collections import defaultdict

FEATURES = {
    "cita_(Autore, anno)": re.compile(r"\([A-ZÀ-Ý][^()]{1,60}, \d{4}[a-z]?\)"),
    "menziona_estratti/excerpt/abstract": re.compile(r"\b(estratt[oi]|excerpt|abstract|fonti (?:disponibili|esaminate)|letteratura (?:disponibile|esaminata|analizzata))\b", re.I),
    "formula_non_consente": re.compile(r"non consent[ei]", re.I),
    "cifre": re.compile(r"\d"),
    "virgolette_«»": re.compile(r"[«»]"),
    "connettivo_iniziale": re.compile(r"^(Tuttavia|Inoltre|In particolare|Pertanto|Infine|Al contempo|Ne consegue|In tal senso|Di conseguenza|Peraltro|Dunque|Quindi|In questa prospettiva|In tale prospettiva|Sul piano)", re.I),
    "norma_(art./comma/d.lgs./legge)": re.compile(r"\b(art\.|artt\.|comma|d\.lgs\.|legge|l\. n\.|Regolamento|GDPR)\b"),
    "giurisprudenza_(Cass./Corte/sent.)": re.compile(r"\b(Cass\.|Corte|sent\.|sentenza|CEDU|CGUE|Garante)\b"),
    "prima_persona_(riteniamo/nostr)": re.compile(r"\b(riteniamo|nostr[aoie]|abbiamo)\b", re.I),
}
NOMINAL = re.compile(r"\w+(?:zione|zioni|mento|menti|ità|enza|anza)\b")


def sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+(?=[A-ZÀ-Ý«(])", text) if s.strip()]


def analyze(lines_path, titles):
    data = json.load(open(lines_path))
    lines = data["lines"]
    # paragraphs = (page, block); rebuild text and flags
    paras = []
    for line in lines:
        key = (line["page"], line["block"])
        if paras and paras[-1]["key"] == key:
            paras[-1]["words"] += line["text"].split()
            paras[-1]["flags"] += line["ai_flags"]
        else:
            paras.append({"key": key, "words": line["text"].split(), "flags": list(line["ai_flags"])})
    # sections: a paragraph whose text equals a title starts a section
    norm = lambda s: re.sub(r"\W+", " ", s).strip().lower()
    title_set = {norm(t): t for t in titles}
    section = None
    per_section = defaultdict(lambda: [0, 0])
    para_pos = defaultdict(lambda: [0, 0])
    sent_rows = []
    sec_paras = defaultdict(list)
    for p in paras:
        text = " ".join(p["words"])
        if norm(text) in title_set:
            section = title_set[norm(text)]
            continue
        if section is None or len(p["words"]) < 25:
            continue
        sec_paras[section].append(p)
    for sec, plist in sec_paras.items():
        for i, p in enumerate(plist):
            n, f = len(p["words"]), sum(p["flags"])
            per_section[sec][0] += n
            per_section[sec][1] += f
            pos = "primo" if i == 0 else ("ultimo" if i == len(plist) - 1 else "medio")
            para_pos[pos][0] += n
            para_pos[pos][1] += f
            # sentence-level: map flags by word index
            text = " ".join(p["words"])
            idx = 0
            for s in sentences(text):
                k = len(s.split())
                fl = p["flags"][idx: idx + k]
                idx += k
                if not fl:
                    continue
                sent_rows.append({"section": sec, "pos": pos, "text": s, "n": k, "share": sum(fl) / len(fl)})
    total = sum(v[0] for v in per_section.values())
    flagged = sum(v[1] for v in per_section.values())
    out = {
        "file": lines_path.split("/")[-1],
        "words_in_sections": total,
        "ai_share_in_sections": round(flagged / total, 4) if total else None,
        "per_section": {s: {"words": v[0], "ai_share": round(v[1] / v[0], 3)} for s, v in per_section.items()},
        "paragraph_position": {k: {"words": v[0], "ai_share": round(v[1] / v[0], 3)} for k, v in para_pos.items()},
        "sentence_features": {},
        "sentence_length_bins": {},
        "examples": {},
    }
    def rate(rows):
        w = sum(r["n"] for r in rows); f = sum(r["n"] * r["share"] for r in rows)
        return (round(f / w, 3) if w else None, len(rows))
    for name, rx in FEATURES.items():
        with_f = [r for r in sent_rows if rx.search(r["text"])]
        without = [r for r in sent_rows if not rx.search(r["text"])]
        out["sentence_features"][name] = {"con": rate(with_f), "senza": rate(without)}
    nominal_hi = [r for r in sent_rows if len(NOMINAL.findall(r["text"])) / max(1, r["n"]) >= 0.12]
    nominal_lo = [r for r in sent_rows if len(NOMINAL.findall(r["text"])) / max(1, r["n"]) < 0.12]
    out["sentence_features"]["nominalizzazioni_>=12%"] = {"con": rate(nominal_hi), "senza": rate(nominal_lo)}
    for lo, hi in ((0, 15), (15, 25), (25, 35), (35, 50), (50, 500)):
        rows = [r for r in sent_rows if lo <= r["n"] < hi]
        out["sentence_length_bins"][f"{lo}-{hi}"] = rate(rows)
    clean = [r for r in sent_rows if r["share"] == 0 and r["n"] >= 12]
    dirty = [r for r in sent_rows if r["share"] >= 0.95 and r["n"] >= 12]
    out["examples"]["frasi_pulite"] = [r["text"] for r in clean[:12]]
    out["examples"]["frasi_sottolineate"] = [r["text"] for r in dirty[:12]]
    out["counts"] = {"sentences": len(sent_rows), "clean": len(clean), "fully_flagged": len(dirty)}
    return out


if __name__ == "__main__":
    lines_path, report_path, out_path = sys.argv[1:4]
    report = json.load(open(report_path))
    titles = [s["title"] for s in report["sections"]]
    result = analyze(lines_path, titles)
    json.dump(result, open(out_path, "w"), ensure_ascii=False, indent=1)
    print(result["file"], "sections", len(result["per_section"]), "share", result["ai_share_in_sections"])
    print(" positions:", result["paragraph_position"])
    for k, v in result["sentence_features"].items():
        print(f"  {k:42s} con={v['con']}  senza={v['senza']}")
    print(" length bins:", result["sentence_length_bins"])
    print(" per section:", {k[:28]: v["ai_share"] for k, v in result["per_section"].items()})
