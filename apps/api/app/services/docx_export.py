"""Small Markdown-to-Word adapter for the markup emitted by the writer."""

from __future__ import annotations

import re
from typing import Any

from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor
from markdown_it import MarkdownIt

_PARSER = MarkdownIt("commonmark", {"html": False})
DEFAULT_DOCX_PROFILE = {
    "version": "academic-docx-v1",
    "basis": "system_default",
    "page_size": "A4",
    "font": "Times New Roman",
    "font_size_pt": 12,
    "line_spacing": 1.5,
    "margins_cm": 2.5,
}


def _heading_identity(value: str) -> str:
    value = re.sub(r"^\s*#{1,6}\s+", "", value).strip()
    value = re.sub(r"\s+#+\s*$", "", value)
    return " ".join(value.strip("*_ ").split()).replace("’", "'").casefold()


def assemble_section(title: str, content: str | None) -> str:
    """Remove only repeated title lines at the beginning; preserve body headings."""
    lines = str(content or "").strip().splitlines()
    while lines and _heading_identity(lines[0]) == _heading_identity(title):
        lines.pop(0)
        while lines and not lines[0].strip():
            lines.pop(0)
    body = "\n".join(lines)
    return f"# {title}\n\n{body}".rstrip()


def apply_academic_profile(docx: Any) -> None:
    """Explicit neutral profile; never change type or spacing to hit page count."""
    for section in docx.sections:
        section.page_width, section.page_height = Cm(21), Cm(29.7)
        section.top_margin = section.bottom_margin = Cm(2.5)
        section.left_margin = section.right_margin = Cm(2.5)
    for name in (
        "Normal",
        "Title",
        "Heading 1",
        "Heading 2",
        "Heading 3",
        "List Bullet",
        "List Number",
    ):
        style = docx.styles[name]
        style.font.name = "Times New Roman"
        fonts = style.element.rPr.rFonts
        for attr in list(fonts.attrib):
            if "theme" in attr.casefold():
                del fonts.attrib[attr]
        fonts.set(qn("w:eastAsia"), "Times New Roman")
        fonts.set(qn("w:cs"), "Times New Roman")
        for border in style.element.xpath("./w:pPr/w:pBdr"):
            border.getparent().remove(border)
        style.font.color.rgb = RGBColor(0, 0, 0)
        style.font.size = Pt(
            16 if name == "Title" else 14 if name == "Heading 1" else 12
        )
        style.paragraph_format.line_spacing = 1.5
        style.paragraph_format.space_after = Pt(6)
        if name.startswith("Heading"):
            style.font.bold = True
            style.paragraph_format.keep_with_next = True
    docx.styles["Normal"].paragraph_format.widow_control = True


def append_markdown(docx: Any, text: str) -> None:
    """Render CommonMark headings, emphasis and lists without losing visible text."""
    paragraph = None
    lists: list[str] = []
    bold = italic = 0
    link_href = ""
    link_label = ""
    for token in _PARSER.parse(text):
        if token.type in {"bullet_list_open", "ordered_list_open"}:
            lists.append(
                "List Bullet" if token.type == "bullet_list_open" else "List Number"
            )
        elif token.type in {"bullet_list_close", "ordered_list_close"}:
            lists.pop()
        elif token.type == "heading_open":
            paragraph = docx.add_paragraph(
                style=f"Heading {min(int(token.tag[1:]), 3)}"
            )
        elif token.type == "paragraph_open":
            paragraph = docx.add_paragraph(style=lists[-1] if lists else "Normal")
        elif token.type == "inline" and paragraph is not None:
            for child in token.children or []:
                if child.type == "strong_open":
                    bold += 1
                elif child.type == "strong_close":
                    bold -= 1
                elif child.type == "em_open":
                    italic += 1
                elif child.type == "em_close":
                    italic -= 1
                elif child.type in {"text", "code_inline", "html_inline", "image"}:
                    if link_href:
                        link_label += child.content
                    run = paragraph.add_run(child.content)
                    run.bold = True if bold else None
                    run.italic = True if italic else None
                elif child.type == "softbreak":
                    paragraph.add_run(" ")
                elif child.type == "hardbreak":
                    paragraph.add_run().add_break()
                elif child.type == "link_open":
                    link_href = str(child.attrGet("href") or "")
                    link_label = ""
                elif child.type == "link_close":
                    if link_href and link_label != link_href:
                        paragraph.add_run(f" ({link_href})")
                    link_href = ""
        elif token.type in {"fence", "code_block"}:
            docx.add_paragraph(token.content.rstrip())


def canonical_docx_bytes(data: bytes) -> bytes:
    """Remove ZIP container clock noise; the document's own metadata is retained."""
    from io import BytesIO
    from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

    output = BytesIO()
    with (
        ZipFile(BytesIO(data)) as archive,
        ZipFile(output, "w", ZIP_DEFLATED) as target,
    ):
        for name in sorted(archive.namelist()):
            info = ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            target.writestr(info, archive.read(name))
    return output.getvalue()
