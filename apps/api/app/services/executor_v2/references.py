"""S5: bibliography from used, verified identities; resolve citations before DOCX."""

from app.services.ai_pipeline.citation_formatter import CitationStyle
from app.services.ai_pipeline.rag_retriever import SourceDoc
from app.services.citation_render import (
    library_sources,
    page_counts,
    pages_out_of_range,
    quoted_share,
    quotes_without_page,
    render_citations,
    suspect_entries,
)
from app.services.source_evidence import evidence_text

from .sections import MARKER
from .sources import verify

QUOTE_SHARE_LIMIT = 0.15


async def resolve_references(ctx, sections, pack):
    known = {s.citation_key: s.source for s in pack.sources if evidence_text(s.source)}
    known = {**library_sources(ctx.inputs["library"]), **known}
    pages = page_counts(pack)
    bibliography, unpaged, quoted = {}, [], []
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
        if (share := quoted_share(text)) > QUOTE_SHARE_LIMIT:
            quoted.append(f"§{section['section_index']}: {round(100 * share)} %")
        if bad := pages_out_of_range(section["raw_content"], MARKER, pages):
            await ctx.warn(
                "page_out_of_range",
                section_index=section["section_index"],
                detail="; ".join(bad),
            )
        section["content"], section["word_count"] = text, len(text.split())
        section["bibliography"] = [
            r["formatted"]
            for key, r in bibliography.items()
            if key in MARKER.findall(section["raw_content"])
        ]
        await ctx.save_section(section)
    year = int(str(ctx.inputs["exported_at"])[:4])
    if suspects := suspect_entries(bibliography, known, year):
        await ctx.warn("bibliography_suspect", detail="; ".join(suspects))
    if unpaged:
        await ctx.warn("quote_without_page", detail="; ".join(unpaged))
    if quoted:
        await ctx.warn("quote_share_high", detail="; ".join(quoted))
    await ctx.emit("executor_bibliography", {"entries": list(bibliography.values())})
    return list(bibliography.values())
