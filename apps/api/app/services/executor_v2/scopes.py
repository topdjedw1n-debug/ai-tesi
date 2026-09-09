"""S1: parse requirements once; preserve the supervisor's exact index."""

import json
import re

from .budgets import model_call, output_budget, sparse_json
from .warnings import ExecutionStop


def flatten(nodes):
    return [
        item for node in nodes for item in [node, *flatten(node.get("children", []))]
    ]


def fixed_index(requirements):
    # Numbered lines are authoritative; prose outside the index remains in the brief.
    lines = [
        re.sub(r"^\s*[*•-]\s*", "", line).strip() for line in requirements.splitlines()
    ]
    pattern = r"^(?:(?:CAPITOLO|CHAPTER|РОЗДІЛ)\s+)?\d+(?:\.\d+)*[.)]?\s+\S"
    numbered = [line for line in lines if re.match(pattern, line, re.I)]
    structural = any(
        re.match(r"^\d+\.\d+\s", line)
        or re.match(r"^(?:CAPITOLO|CHAPTER|РОЗДІЛ)\s+\d", line, re.I)
        for line in numbered
    )
    labelled = bool(
        re.search(
            r"(?im)^\s*(?:indice|index|зміст|індекс|структура|chapters|capitoli)\b",
            requirements,
        )
    )
    return list(dict.fromkeys(numbered)) if structural or labelled else []


def title_identity(title):
    title = re.sub(
        r"^(?:(?:CAPITOLO|CHAPTER|РОЗДІЛ)\s+)?\d[\d.]*[.)]?\s*", "", title, flags=re.I
    )
    return title.replace("’", "'").strip().casefold()


async def build_scopes(ctx):
    index = fixed_index(ctx.inputs["requirements"])
    prompt = (
        """Parse the academic brief into chapters -> subsections -> concepts. Return only sparse JSON:
{"nodes":[{"title":"exact title", "required":true, "terms_local":["term"], "terms_en":["term"], "children":[]}]}
No IDs. Keep ALL supervisor index wording, hierarchy and order unchanged. Concepts may have no children.
Terms must name the actual subject in the work language and English. Do not invent fieldwork or required topics.
BRIEF:\n"""
        + json.dumps(ctx.inputs["brief"], ensure_ascii=False)
        + "\nREQUIREMENTS:\n"
        + ctx.inputs["requirements"]
    )
    text, truncated = await model_call(
        ctx, prompt, budget=output_budget("S1", max(1, len(index))), purpose="S1"
    )
    if truncated:
        raise ExecutionStop(
            "provider_unusable_response", "Модель не завершила структуру вимог."
        )
    nodes = sparse_json(text).get("nodes")

    def validate(items):
        if not isinstance(items, list) or not items:
            raise ExecutionStop(
                "provider_unusable_response", "Модель не повернула структуру вимог."
            )
        for node in items:
            if (
                not isinstance(node, dict)
                or not isinstance(node.get("title"), str)
                or not node["title"].strip()
                or not isinstance(node.get("required"), bool)
            ):
                raise ExecutionStop(
                    "provider_unusable_response",
                    "Структура вимог має непридатний формат.",
                )
            for name in ("terms_local", "terms_en"):
                if (
                    not isinstance(node.get(name), list)
                    or not node[name]
                    or not all(isinstance(x, str) and x.strip() for x in node[name])
                ):
                    raise ExecutionStop(
                        "provider_unusable_response",
                        "У структурі відсутні двомовні терміни.",
                    )
            node["children"] = node.get("children") or []
            if node["children"]:
                validate(node["children"])
            node.pop("id", None)

    validate(nodes)
    if index:
        # Restore fixed titles deterministically; unmatched nodes retain their terms as concepts.
        all_nodes = flatten(nodes)
        nodes = []
        parents = {}
        indexed_titles = {title_identity(line) for line in index}
        for line in index:
            number = re.search(r"\d+(?:\.\d+)*", line)[0]
            match = next(
                (
                    n
                    for n in all_nodes
                    if title_identity(n["title"]) == title_identity(line)
                ),
                None,
            )
            node = {
                **(
                    match
                    or {
                        "terms_local": [line],
                        "terms_en": list(
                            dict.fromkeys(t for n in all_nodes for t in n["terms_en"])
                        )[:3],
                    }
                ),
                "title": line,
                "required": True,
                "children": [
                    child
                    for child in (match or {}).get("children", [])
                    if title_identity(child["title"]) not in indexed_titles
                ],
            }
            parent = parents.get(number.rsplit(".", 1)[0]) if "." in number else None
            (parent["children"] if parent else nodes).append(node)
            parents[number] = node
    for i, node in enumerate(flatten(nodes), 1):
        node["scope_id"] = f"scope-{i}"
    await ctx.emit("executor_scopes", {"nodes": nodes, "supervisor_index": index})
    return nodes
