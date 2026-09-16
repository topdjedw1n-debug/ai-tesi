"""S4: one writer call per section; only truncation permits continuation."""

import json
import re
from types import SimpleNamespace

from app.services import section_material as material
from app.services import writer_rules as rules
from app.services.academic_context import academic_directive
from app.services.ai_pipeline.citation_keys import split_group_markers
from app.services.full_text_sources import section_evidence

from .budgets import POLICY, model_call, output_budget
from .warnings import unusable

MARKER = re.compile(r"\[(STD:[^\[\]\n]+|[\w:./-]+)\]", re.UNICODE)
STANDARD_BLOCK = re.compile(
    r"<STANDARD_REFERENCES_JSON>(.*?)</STANDARD_REFERENCES_JSON>", re.S
)
S4_INSTRUCTION, FULL_TEXT_RULE = rules.S4_INSTRUCTION, rules.FULL_TEXT_RULE
complete_prefix = material.complete_prefix


async def write_sections(ctx, outline, pack):
    result = []
    allowed = material.citable_keys(pack, ctx.inputs["library"])
    document = SimpleNamespace(**ctx.inputs["brief"])
    commentary = material.commentary_budget(outline)
    for section in material.writing_order(outline):
        index = section["section_index"]
        ctx.section_index = index
        words = section["target_words"]
        low, high = POLICY["short_ratio"] * words, POLICY["long_ratio"] * words
        frame = material.is_frame(section)
        evidence, selection = section_evidence(
            pack, section, getattr(ctx, "scopes", []), commentary=commentary
        )
        await ctx.emit(
            "executor_section_evidence", {"section_index": index, "evidence": selection}
        )
        windowed = any(r["windows"] for r in selection)
        if not frame and not windowed:
            await ctx.warn(
                "section_without_documents",
                section_index=index,
                detail=section["title"],
            )
        prompt = (
            academic_directive(document)
            + S4_INSTRUCTION
            + (material.frame_rule(section) if frame else "")
            + (FULL_TEXT_RULE if windowed else "")
            + json.dumps(
                {
                    "forbidden_placeholders": POLICY["placeholder_phrases"],
                    "requirements": ctx.inputs["requirements"],
                    "section": section,
                    "target_words_range": [words, int(high - 1)],
                    "evidence": evidence,
                    "previous_summaries": (
                        []
                        if frame
                        else material.summaries(result, POLICY["summary_chars"])
                    ),
                    **({"findings": material.findings(result)} if frame else {}),
                },
                ensure_ascii=False,
            )
        )
        before = ctx.usage.total_tokens
        budget = output_budget("S4", words, document.language)

        async def call(suffix="", scale=1, prompt=prompt, budget=budget, index=index):
            return await model_call(
                ctx,
                prompt + suffix,
                budget=budget * scale,
                purpose="S4",
                section_index=index,
            )

        text, truncated = await call()
        if truncated:
            continuation, truncated = await call(
                "\nCONTINUE from the exact ending below, without repeating it:\n"
                + text,
                POLICY["truncation_multiplier"],
            )
            text += "\n" + continuation
            if truncated:
                text = material.complete_prefix(text)
                if len(text.split()) < POLICY["min_kept_words"]:
                    raise unusable("Модель двічі обірвала текст розділу.")
                await ctx.warn("output_truncated_kept", section_index=index)
            else:
                await ctx.warn("output_truncated_retried", section_index=index)
        if frame and material.frame_violations(text):
            text, truncated = await call(material.FRAME_RETRY)
            await ctx.warn("frame_rewritten", section_index=index)
        proposed = []
        block = STANDARD_BLOCK.search(text)
        if block:
            try:
                parsed = json.loads(block[1])
                proposed = parsed if isinstance(parsed, list) else []
            except ValueError:
                pass
            text = STANDARD_BLOCK.sub("", text).strip()
        text = split_group_markers(text)
        raw = text
        pending = {
            "STD:" + r["id"]
            for r in proposed
            if isinstance(r, dict) and isinstance(r.get("id"), str)
        }
        for key in set(MARKER.findall(text)) - allowed - pending:
            text = text.replace(f"[{key}]", "")
            await ctx.warn("citation_unresolved", section_index=index, detail=key)
        word_count = len(text.split())
        if not low <= word_count <= high:
            await ctx.warn(
                "length_off_target",
                section_index=index,
                detail=f"{word_count} / {words}",
            )
        row = {
            **section,
            "content": text,
            "raw_content": raw,
            "proposed_references": proposed,
            "word_count": word_count,
            "pack_keys_used": sorted(set(MARKER.findall(text)) & allowed),
            "tokens_used": ctx.usage.total_tokens - before,
        }
        await ctx.save_section(row)
        await ctx.emit("executor_section", row)
        result.append(row)
    ctx.section_index = None
    return sorted(result, key=lambda s: s["section_index"])
