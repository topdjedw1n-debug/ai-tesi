"""Cut sections out of a generated DOCX into small DOCX files (for section-level scans).

Usage: python scripts/docx_sections.py IN.docx OUT_DIR SPEC
SPEC: name=Title1|Title2,... where each name becomes OUT_DIR/name.docx containing the
named sections (heading + paragraphs up to the next heading). Headings are matched by
exact paragraph text. Prints word counts. No bibliography is included.
"""

import sys
from pathlib import Path

from docx import Document


def main():
    src, out_dir, spec = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
    out_dir.mkdir(parents=True, exist_ok=True)
    doc = Document(str(src))
    paras = list(doc.paragraphs)
    level1 = {
        p.text.strip(): i for i, p in enumerate(paras) if p.style.name == "Heading 1"
    }
    for part in spec.split(","):
        name, titles = part.split("=", 1)
        wanted = titles.split("|")
        new = Document()
        words = 0
        for title in wanted:
            start = level1.get(title.strip())
            if start is None:
                raise SystemExit(
                    f"heading not found: {title!r}; available: {list(level1)[:30]}"
                )
            end = min([i for i in level1.values() if i > start] + [len(paras)])
            new.add_heading(paras[start].text, level=1)
            for p in paras[start + 1 : end]:
                if not p.text.strip():
                    continue
                if p.style.name.startswith("Heading"):
                    new.add_heading(p.text, level=2)
                else:
                    new.add_paragraph(p.text)
                    words += len(p.text.split())
        path = out_dir / f"{name}.docx"
        new.save(str(path))
        print(name, words, "words ->", path)


if __name__ == "__main__":
    main()
