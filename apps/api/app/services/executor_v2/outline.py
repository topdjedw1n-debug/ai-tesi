"""S3: one plan, one truncation retry, server-owned section identities."""

import json

from .budgets import POLICY, model_call, output_budget, sparse_json
from .scopes import flatten
from .warnings import ExecutionStop


async def build_outline(ctx, scopes, pack):
    nodes = flatten(scopes)
    prompt = """Build a plan for this academic brief, preserving the required supervisor chapter names and order.
Return ONLY {"sections":[{"title":"...","purpose":"...","main_points":["..."],"scope_ids":["scope-1"],"evidence_keys":["K..."],"target_words":1000}]}.
Do not return section IDs or indexes. Include each required scope. Use ONLY evidence keys with readable text from the frozen pack.
The target_words values must sum exactly to the brief target_words. No bibliography section: the server builds it separately.
""" + json.dumps(
        {
            "brief": ctx.inputs["brief"],
            "requirements": ctx.inputs["requirements"],
            "scopes": scopes,
            "pack": [
                {
                    "key": p.citation_key,
                    "title": p.source.title,
                    "evidence": (p.source.canonical_metadata or {}).get(
                        "academic_evidence"
                    ),
                }
                for p in pack.sources
            ],
        },
        ensure_ascii=False,
    )
    budget = output_budget("S3", len(nodes))
    text, truncated = await model_call(ctx, prompt, budget=budget, purpose="S3")
    if truncated:
        text, truncated = await model_call(
            ctx, prompt, budget=budget * POLICY["truncation_multiplier"], purpose="S3"
        )
        if truncated:
            raise ExecutionStop(
                "provider_unusable_response", "Модель двічі обірвала план роботи."
            )
        await ctx.warn("output_truncated_retried")
    sections = sparse_json(text).get("sections")
    if not isinstance(sections, list) or not sections:
        raise ExecutionStop(
            "provider_unusable_response", "Модель не повернула розділи плану."
        )
    covered = set()
    for i, section in enumerate(sections, 1):
        if (
            not isinstance(section, dict)
            or not isinstance(section.get("title"), str)
            or not section["title"].strip()
            or not isinstance(section.get("target_words"), int)
            or section["target_words"] <= 0
        ):
            raise ExecutionStop(
                "provider_unusable_response", "Розділи плану мають непридатний формат."
            )
        for key in ("scope_ids", "evidence_keys", "main_points"):
            if not isinstance(section.get(key), list) or not all(
                isinstance(x, str) for x in section[key]
            ):
                raise ExecutionStop(
                    "provider_unusable_response", "Поля плану мають непридатний формат."
                )
        covered.update(section["scope_ids"])
        unknown = set(section["evidence_keys"]) - set(pack.keys())
        if unknown:
            await ctx.emit(
                "executor_outline_keys_removed",
                {"section_index": i, "keys": sorted(unknown)},
            )
        section["evidence_keys"] = [
            k
            for k in section["evidence_keys"]
            if k in pack.keys()
            and (pack.by_key(k).source.canonical_metadata or {}).get("evidence_level")
            != "none"
        ]
        section.pop("id", None)
        section["section_index"] = i
    for node in nodes:
        if node["required"] and node["scope_id"] not in covered:
            await ctx.warn("outline_scope_unmapped", detail=node["title"])
    total = sum(s["target_words"] for s in sections)
    target = ctx.inputs["brief"]["target_words"]
    # A scale mismatch is corrected locally, never sent through a quality loop.
    if len(sections) > target:
        raise ExecutionStop(
            "provider_unusable_response",
            "План містить більше розділів, ніж слів у завданні.",
        )
    remaining = target - len(sections)
    weights = [s["target_words"] * remaining / total for s in sections]
    allocations = [int(w) + 1 for w in weights]
    for i in sorted(range(len(sections)), key=lambda i: weights[i] % 1, reverse=True)[
        : target - sum(allocations)
    ]:
        allocations[i] += 1
    for section, words in zip(sections, allocations, strict=False):
        section["target_words"] = words
    await ctx.save_outline(sections)
    await ctx.emit(
        "executor_outline", {"sections": sections, "source_pack_sha256": pack.sha256()}
    )
    return sections
