"""S5: bibliography from used, verified identities; resolve citations before DOCX."""

import re

from app.services.ai_pipeline.citation_formatter import (
    CitationFormatter,
    CitationStyle,
    SourceDocument,
)
from app.services.ai_pipeline.rag_retriever import SourceDoc
from app.services.source_evidence import evidence_text

from .sections import MARKER
from .sources import verify


def sentence_at(text, marker):
    return next(
        (s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if marker in s), marker
    )


async def resolve_references(ctx, sections, pack):
    known = {s.citation_key: s.source for s in pack.sources if evidence_text(s.source)}
    for row in ctx.inputs["library"]:
        if row.get("verification_status") == "verified":
            source = SourceDoc(**row["source"])
            source.canonical_metadata = {
                **(source.canonical_metadata or {}),
                "verification_provider": row["verification_provider"],
                "origin": "library",
            }
            known.setdefault(row["key"], source)
    bibliography = {}
    style = CitationStyle(ctx.inputs["brief"]["citation_style"])
    for section in sections:
        text = section["content"]
        for proposal in section["proposed_references"]:
            if (
                not isinstance(proposal, dict)
                or not proposal.get("title")
                or not isinstance(proposal.get("id"), str)
            ):
                continue
            key = "STD:" + proposal["id"]
            if key not in MARKER.findall(text) or key in known:
                continue
            try:
                metadata = await verify(proposal)
            except Exception:
                metadata = {"status": "unresolvable"}
            if metadata.get("status") == "verified":
                source = SourceDoc(
                    title=metadata["title"],
                    authors=metadata.get("authors") or [],
                    year=metadata.get("year"),
                    doi=metadata.get("doi"),
                    provider=metadata["provider"],
                    verification_status="verified",
                    canonical_metadata={
                        **metadata,
                        "verification_provider": metadata["provider"],
                        "origin": "model_proposal",
                    },
                )
                known[key] = source
        for key in dict.fromkeys(MARKER.findall(text)):
            source = known.get(key)
            marker = f"[{key}]"
            if source is None:
                await ctx.warn(
                    "reference_replaced",
                    section_index=section["section_index"],
                    detail=f"{key}: {sentence_at(text, marker)}",
                )
                text = text.replace(marker, "")
                continue
            meta = source.canonical_metadata or {}
            formatted = CitationFormatter.format_reference(
                SourceDocument(
                    title=source.title,
                    authors=source.authors or [source.title],
                    year=source.year,
                    journal=source.venue,
                    doi=source.doi,
                    url=source.url,
                ),
                style=style,
            )
            citation = CitationFormatter.format_intext(
                source.authors or [source.title], source.year, style=style
            )
            text = text.replace(marker, citation)
            bibliography[key] = {
                "key": key,
                "formatted": formatted,
                "verified": True,
                "verification_provider": meta["verification_provider"],
                "origin": meta.get("origin", "pack"),
            }
            if meta.get("origin") == "library" and key not in pack.keys():
                await ctx.warn(
                    "standard_reference_used",
                    section_index=section["section_index"],
                    detail=key,
                )
        section["content"], section["word_count"] = text, len(text.split())
        section["bibliography"] = [
            r["formatted"]
            for key, r in bibliography.items()
            if key in MARKER.findall(section["raw_content"])
        ]
        await ctx.save_section(section)
    await ctx.emit("executor_bibliography", {"entries": list(bibliography.values())})
    return list(bibliography.values())
