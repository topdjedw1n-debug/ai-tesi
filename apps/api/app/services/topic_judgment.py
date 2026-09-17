"""Is a fetched full text about this work? One recorded model call per document
in the uncertain band of the deterministic gate.

Calibrated 17.09.2026 (consultation #9, 41 documents of four recorded runs):
no fixed lexical rule separates a same-field text on another question (a
review on healthcare workers' mental health for a work on adolescents' social
media use; a sex-education thesis) from a text on the topic, while a small
model does, judging by the phenomenon and the questions the document studies,
not by its field or its sample. The call is bounded: only documents whose
topic share lies in ``JUDGE_BAND`` are judged, the lowest shares first, at
most ``MAX_JUDGMENTS`` per run; a rejected document keeps its abstract and
hands no pages; an uncertain or unreadable answer changes nothing.
"""

from __future__ import annotations

import json
import re
from typing import Any

from app.services.material_fit import document_topic_share
from app.services.search_queries import is_structural
from app.services.source_evidence import freeze_evidence

JUDGE_MODEL = "claude-haiku-4-5-20251001"
JUDGE_BAND = (0.5, 0.9)
# Calibrated with eight; the copies of 17.09 tripled the fetched texts of a
# run (23 of 36), so the cap follows: cheap calls, outside the call ceiling.
MAX_JUDGMENTS = 12
JUDGE_MAX_TOKENS = 400
EXCERPT_CHARS = 1300
PURPOSE = "S2_judge"

PROMPT = """You check whether a fetched document may serve as FULL-TEXT material (pages the writer cites with page numbers) for one thesis. Decide by the PHENOMENON and the QUESTIONS the document studies, not by its field. Two different things must not be confused:
- Another PHENOMENON or another set of questions (a review on the mental health of healthcare workers in a pandemic, a thesis on sex education, a meta-analysis on children's food consumption for a thesis on adolescents' social media use; a cyber-risk regulation book for a thesis on SME credit access) -> "reject": such pages must not lead sections, even when the field, the population or single words match.
- The SAME phenomenon and questions studied on a different sample, sector or country (university students instead of adolescents; construction SMEs instead of Italian SMEs; Pseudomonas instead of bacteria in general) -> "allow", with "population_match": false: its pages teach the mechanisms, the definitions and the findings, and the writer states the sample.
"uncertain" only when the excerpts do not show what the document studies.

THESIS TOPIC: {topic}
REQUIREMENTS (manager intake): {requirements}
PLAN NODES (id, title, terms):
{nodes}

DOCUMENT
Title: {title} ({year}, {venue})
Abstract: {abstract}
Excerpts ({n_windows} windows in the document; three shown with locators):
{windows}

Answer with one JSON object only:
{{"verdict": "allow" | "reject" | "uncertain", "population_match": true | false, "scope_ids": ["scope-…", …], "reason": "one sentence naming the excerpt(s) that decide"}}
scope_ids = the nodes whose own question the pages genuinely address (empty for reject)."""


def pick_windows(windows: list[Any], pattern: re.Pattern[str] | None) -> list[Any]:
    """Three distinct excerpts, reproducibly: the first window with a topic
    anchor (the subject and the sample), the window with the most distinct
    anchors (the best match), the best window of the last third (results or
    conclusions)."""
    if not windows:
        return []

    def anchors(window: Any) -> int:
        if pattern is None:
            return 0
        return len({m.group(0) for m in pattern.finditer(window.text.casefold())})

    first = next((w for w in windows if anchors(w)), windows[0])
    best = max(windows, key=lambda w: (anchors(w), -windows.index(w)))
    tail = windows[len(windows) * 2 // 3 :] or windows
    last = max(tail, key=lambda w: (anchors(w), -tail.index(w)))
    chosen: list[Any] = []
    for window in (first, best, last):
        if window not in chosen:
            chosen.append(window)
    return chosen


def locator(window: Any) -> str:
    for attr in ("page", "page_start", "page_number"):
        value = getattr(window, attr, None)
        if value:
            return f"p. {value}"
    return "p. ?"


def judgment_prompt(
    topic: str,
    requirements: str,
    nodes: list[dict[str, Any]],
    source: Any,
    windows: list[Any],
    total_windows: int,
) -> str:
    node_lines = "\n".join(
        f"- {n['scope_id']}: {n.get('title', '')} | "
        f"{', '.join(list(n.get('terms_local') or [])[:6])} | "
        f"{', '.join(list(n.get('terms_en') or [])[:6])}"
        for n in nodes
        if not is_structural(n)
    )
    excerpts = "\n\n".join(f"[{locator(w)}] {w.text[:EXCERPT_CHARS]}" for w in windows)
    return PROMPT.format(
        topic=topic,
        requirements=(requirements or "")[:900],
        nodes=node_lines,
        title=getattr(source, "title", ""),
        year=getattr(source, "year", ""),
        venue=getattr(source, "venue", "") or "",
        abstract=(getattr(source, "abstract", "") or "")[:1500] or "(none)",
        n_windows=total_windows,
        windows=excerpts,
    )


def parse_verdict(text: str) -> dict[str, Any] | None:
    """The model's JSON, or None when it cannot be read (nothing changes then)."""
    match = re.search(r"\{.*\}", text or "", re.S)
    parsed: Any = {}
    if match:
        try:
            parsed = json.loads(match.group(0))
        except (json.JSONDecodeError, TypeError):
            parsed = {}
    verdict = parsed.get("verdict") if isinstance(parsed, dict) else None
    if verdict not in ("allow", "reject", "uncertain"):
        # A cut answer still names its verdict before the rest.
        found = re.search(r'"verdict"\s*:\s*"(allow|reject|uncertain)"', text or "")
        if not found:
            return None
        verdict = found.group(1)
        parsed = {"verdict": verdict}
    scope_ids = parsed.get("scope_ids") if isinstance(parsed, dict) else None
    return {
        "verdict": verdict,
        "population_match": parsed.get("population_match"),
        "scope_ids": [s for s in (scope_ids or []) if isinstance(s, str)],
        "reason": str(parsed.get("reason") or "")[:300],
    }


def candidates(pack: Any, pattern: re.Pattern[str] | None) -> list[tuple[float, Any]]:
    """Fetched documents whose topic share lies in the band, lowest first."""
    rows = []
    for packed in pack.sources:
        metadata = packed.source.canonical_metadata or {}
        if metadata.get("evidence_level") != "pdf":
            continue
        if getattr(packed.source, "provider", "") == "uploaded":
            continue  # the manager's own PDFs are never judged
        windows = [
            p.text
            for p in getattr(pack, "passages", None) or []
            if p.citation_key == packed.citation_key
        ]
        if not windows:
            continue
        share = document_topic_share(windows, pattern)
        if JUDGE_BAND[0] <= share < JUDGE_BAND[1]:
            rows.append((share, packed))
    rows.sort(key=lambda r: (r[0], r[1].citation_key))
    return rows[:MAX_JUDGMENTS]


def apply_rejection(pack: Any, packed: Any) -> None:
    """A rejected document hands no pages: its stored excerpt is rebuilt from
    the abstract alone (the frozen excerpt already carried page material) and
    its level goes back to the abstract; the fetch stays on record."""
    freeze_evidence(packed.source, [], packed.citation_key)
    metadata = packed.source.canonical_metadata
    metadata["evidence_level"] = (
        "abstract" if metadata.get("evidence_level") else "none"
    )


async def judge_documents(
    ctx: Any,
    pack: Any,
    nodes: list[dict[str, Any]],
    pattern: re.Pattern[str] | None,
    *,
    call: Any,
) -> list[dict[str, Any]]:
    """Judge the fetched documents in the band; returns the per-document
    record (share, verdict, reason) for the recording. ``call`` is the bounded
    model call ``(ctx, prompt, budget, purpose, model, counted) -> (text,
    truncated)``; the judgment's calls are not counted against the ceiling."""
    topic = str(getattr(pack, "topic", "") or "")
    requirements = str(
        (ctx.inputs.get("brief") or {}).get("additional_requirements") or ""
    )
    results: list[dict[str, Any]] = []
    for share, packed in candidates(pack, pattern):
        windows = [
            p for p in pack.passages or [] if p.citation_key == packed.citation_key
        ]
        prompt = judgment_prompt(
            topic,
            requirements,
            nodes,
            packed.source,
            pick_windows(windows, pattern),
            len(windows),
        )
        record: dict[str, Any] = {
            "key": packed.citation_key,
            "share": round(share, 3),
            "model": JUDGE_MODEL,
        }
        try:
            text, _ = await call(
                ctx,
                prompt,
                budget=JUDGE_MAX_TOKENS,
                purpose=PURPOSE,
                model=JUDGE_MODEL,
                counted=False,
            )
            verdict = parse_verdict(text)
        except Exception as error:  # the provider's failure never blocks S2
            verdict = None
            record["error"] = type(error).__name__
        if verdict is None:
            record["verdict"] = "unreadable"
        else:
            record.update(verdict)
            if verdict["verdict"] == "reject":
                apply_rejection(pack, packed)
        packed.source.canonical_metadata["topic_judgment"] = {
            k: v for k, v in record.items() if k != "key"
        }
        results.append(record)
    return results


async def judge_and_report(
    ctx: Any, pack: Any, nodes: list[dict[str, Any]], pattern: Any, *, call: Any
) -> list[dict[str, Any]]:
    """Judge, record the verdicts as an event and warn about every rejected
    document in words the manager reads on the work page."""
    judgments = await judge_documents(ctx, pack, nodes, pattern, call=call)
    if judgments:
        await ctx.emit("executor_topic_judgment", {"documents": judgments})
    for row in judgments:
        if row.get("verdict") == "reject":
            await ctx.warn(
                "source_full_text_off_topic",
                detail=f'{row["key"]}: повний текст не про тему роботи, лишається анотація',
            )
    return judgments
