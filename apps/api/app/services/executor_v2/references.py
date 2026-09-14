"""S5: bibliography from used, verified identities; resolve citations before DOCX."""

from app.services.ai_pipeline.citation_formatter import CitationStyle
from app.services.ai_pipeline.rag_retriever import SourceDoc
from app.services.citation_render import (
    quotes_without_page,
    render_citations,
    suspect_metadata,
)
from app.services.source_evidence import evidence_text

from .sections import MARKER
from .sources import verify


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
    bibliography, unpaged = {}, []
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
        text, entries, missing = render_citations(text, known, style, MARKER)
        for key, sentence in missing:
            await ctx.warn(
                "reference_replaced",
                section_index=section["section_index"],
                detail=f"{key}: {sentence}",
            )
        for key, entry in entries.items():
            bibliography.setdefault(key, entry)
            if entry["origin"] == "library" and key not in pack.keys():
                await ctx.warn(
                    "standard_reference_used",
                    section_index=section["section_index"],
                    detail=key,
                )
        if count := quotes_without_page(text):
            unpaged.append(f"§{section['section_index']}: {count}")
        section["content"], section["word_count"] = text, len(text.split())
        section["bibliography"] = [
            r["formatted"]
            for key, r in bibliography.items()
            if key in MARKER.findall(section["raw_content"])
        ]
        await ctx.save_section(section)
    year = int(str(ctx.inputs["exported_at"])[:4])
    suspects = [
        f"{key}: {', '.join(reasons)}"
        for key in bibliography
        if (reasons := suspect_metadata(known[key], year))
    ]
    if suspects:
        await ctx.warn("bibliography_suspect", detail="; ".join(suspects))
    if unpaged:
        await ctx.warn("quote_without_page", detail="; ".join(unpaged))
    await ctx.emit("executor_bibliography", {"entries": list(bibliography.values())})
    return list(bibliography.values())
