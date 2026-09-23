"""S2: bilingual coverage, verified identities and frozen evidence, without a quota gate."""

import asyncio
from dataclasses import asdict

from app.services.academic_context import digest
from app.services.ai_pipeline.rag_retriever import RAGRetriever, SourceDoc
from app.services.ai_pipeline.source_identity import sources_equivalent
from app.services.ai_pipeline.source_pack import PackedSource, SourcePack
from app.services.citation_verifier import CitationVerifier, SourceInput
from app.services.full_text_sources import (
    attach_full_text,
    links_metadata,
    open_access_link,
    topic_pattern,
)
from app.services.generation_policy import RecordingPersistenceError
from app.services.model_recording import ReplayIncomplete
from app.services.pack_seats import scope_metadata, seat
from app.services.replay_dependencies import recorded_dependency
from app.services.search_queries import is_structural, on_topic, plan
from app.services.source_evidence import evidence_text, freeze_evidence
from app.services.topic_judgment import judge_and_report
from app.services.uploaded_sources import SourcePassage

from .budgets import POLICY, model_call
from .scopes import flatten

PROVIDERS = ("semantic_scholar", "crossref", "openalex")


@recorded_dependency("executor_search")
async def search(provider, query):
    # A catalogue failure is raised and recorded; an empty answer is a result.
    retriever = RAGRetriever()
    rows = await getattr(retriever, f"search_{provider}")(query, raise_on_error=True)
    return [asdict(row) for row in rows]


@recorded_dependency("executor_verify")
async def verify(candidate):
    source = SourceInput(
        title=candidate["title"],
        authors=candidate.get("authors") or [],
        year=candidate.get("year"),
        doi=candidate.get("doi"),
        source_type=candidate.get("source_type") or candidate.get("type"),
        url=candidate.get("url"),
    )
    result = (await CitationVerifier(cache_enabled=False).verify_sources([source]))[0]
    return result.to_dict()


async def build_sources(ctx, scopes):
    nodes = flatten(scopes)
    semaphore = asyncio.Semaphore(POLICY["search_concurrency"])
    topic = ctx.inputs["brief"]["topic"]

    async def fetch(scope_id, provider, query):
        async with semaphore:
            try:
                return scope_id, provider, await search(provider, query)
            except (RecordingPersistenceError, ReplayIncomplete):
                raise
            except Exception:
                return scope_id, provider, None

    queries, parents, anchors = plan(topic, scopes)
    found = await asyncio.gather(
        *[fetch(s, p, q) for s, q in queries for p in PROVIDERS]
    )
    for provider in PROVIDERS:
        tries = [r for r in found if r[1] == provider]
        if tries and sum(r[2] is None for r in tries) >= 0.8 * len(tries):
            await ctx.warn("catalogue_unavailable", detail=provider)
    candidates = {}
    for scope_id, _, rows in found:
        for row in rows or []:
            if not on_topic(row, anchors):
                continue
            identity = (row.get("doi") or row["title"]).strip().lower()
            if identity not in candidates:
                candidates[identity] = {"source": row, "scopes": set()}
            candidates[identity]["scopes"].update({scope_id, parents.get(scope_id)})
            first = candidates[identity]["source"]
            if not first.get("abstract") and row.get("abstract"):
                first["abstract"] = row["abstract"]
            if not open_access_link(first) and open_access_link(row):
                first["canonical_metadata"] = links_metadata(row)

    async def checked(item):
        async with semaphore:
            try:
                metadata = await verify(item["source"])
            except (RecordingPersistenceError, ReplayIncomplete):
                raise
            except Exception:
                return None
        if metadata["status"] != "verified":
            return None
        row = {
            **item["source"],
            **{
                k: metadata[k]
                for k in ("title", "authors", "year", "doi", "venue")
                if metadata.get(k)
            },
        }
        row["abstract"] = metadata.get("abstract") or row.get("abstract")
        source = SourceDoc(**row)
        source.verification_status = "verified"
        source.canonical_metadata = {
            **metadata,
            "origin": "pack",
            "verification_provider": metadata["provider"],
            # The query that found the record is history, not coverage.
            "query_scope_ids": sorted(filter(None, item["scopes"])),
            **scope_metadata(source, nodes, parents),
        }
        source.canonical_metadata.update(links_metadata(item["source"]))
        key = (
            "K"
            + digest({"doi": source.doi, "title": source.title, "year": source.year})[
                :12
            ]
        )
        freeze_evidence(source, [], key)
        source.canonical_metadata["evidence_level"] = (
            "abstract" if evidence_text(source) else "none"
        )
        return PackedSource(source, key, 1.0)

    checked_rows = [
        r for r in await asyncio.gather(*map(checked, candidates.values())) if r
    ]
    passages = [SourcePassage(**p) for p in ctx.inputs["passages"]]
    for row in ctx.inputs["uploaded_sources"] + ctx.inputs["library"]:
        if row.get("verification_status") != "verified":
            continue
        source = SourceDoc(**row["source"])
        source.verification_status = "verified"
        key = row["key"]
        source.canonical_metadata = {
            **(source.canonical_metadata or {}),
            "origin": row["origin"],
            "verification_provider": row["verification_provider"],
        }
        freeze_evidence(source, passages, key, query=topic)
        # Only relevant local matches contribute to a node's coverage.
        source.canonical_metadata.update(
            scope_metadata(
                source,
                nodes,
                parents,
                source.title + " " + (evidence_text(source) or ""),
            )
        )
        source.canonical_metadata["evidence_level"] = (
            row["origin"] if evidence_text(source) else "none"
        )
        checked_rows.insert(0, PackedSource(source, key, 1.0))
    # A found record of an uploaded work would add a second key and entry.
    uploads = [r for r in checked_rows if r.source.provider == "uploaded"]
    checked_rows = [
        r
        for r in checked_rows
        if r in uploads
        or not any(sources_equivalent(u.source, r.source) for u in uploads)
    ]
    # Reserved seats per node go to records with the node's own terms first.
    selected, coverage = seat(
        checked_rows,
        nodes,
        minimum=POLICY["minimum_evidence_sources"],
        max_sources=POLICY["max_sources"],
    )
    summary, unavailable = await attach_full_text(selected, passages, semaphore, topic)
    if summary:
        await ctx.emit("executor_full_text", {"sources": summary})
    for detail in unavailable:  # "title — link": the manager can fetch it by hand
        await ctx.warn("source_full_text_unavailable", detail=detail)
    pack = SourcePack(
        ctx.job.document_id, topic, sources=selected, bilingual=True, passages=passages
    )
    await judge_and_report(
        ctx, pack, nodes, topic_pattern(pack, nodes), call=model_call
    )
    for node in nodes:
        count = coverage.get(node["scope_id"], 0)
        if (
            node["required"]
            and not is_structural(node)
            and count < POLICY["minimum_evidence_sources"]
        ):
            await ctx.warn("source_coverage_gap", detail=f'{node["title"]}: {count}')
    for row in selected:
        if not evidence_text(row.source):
            await ctx.warn("source_no_readable_text", detail=row.citation_key)
        if row.source.canonical_metadata["origin"] == "library":
            await ctx.warn("standard_reference_used", detail=row.citation_key)
    await ctx.save_pack(pack)
    await ctx.emit(
        "executor_source_pack",
        {
            "sha256": pack.sha256(),
            "sources": [asdict(s) for s in selected],
            "coverage": coverage,
        },
    )
    return pack
