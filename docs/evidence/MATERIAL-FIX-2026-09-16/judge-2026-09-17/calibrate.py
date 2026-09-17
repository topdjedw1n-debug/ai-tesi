"""Calibration pass of the document judgment (consultation #9, founder's yes on 17.09):
for every fetched full text of the four recordings plus the eight psychology copies, one model call
with the topic, the requirements, the plan nodes, the document's title/abstract and three excerpts with
locators -> {"verdict": allow|reject|uncertain, "scope_ids": [...], "reason": "..."}. Compared with the
labels (OFF = known off-topic). Cost-capped. Prompts and answers are written to a JSON file.
Usage: calibrate.py OUT.json MODEL [MAX_USD]"""
import asyncio, glob, gzip, json, os, re, sys, time
from types import SimpleNamespace
os.environ.update({"ENV_FILE": "/dev/null", "ENVIRONMENT": "test", "DEBUG": "true", "DATABASE_URL": "sqlite+aiosqlite:///:memory:", "SECRET_KEY": "offline-judge-secret-never-an-account", "JWT_SECRET": "offline-judge-secret-never-an-account"})
sys.path.insert(0, "/Users/maxmaxvel/AI TESI/apps/api")
import anthropic
from app.services.executor_v2.scopes import flatten
from app.services.full_text_sources import document_windows, topic_pattern
from app.services.search_queries import is_structural

SP = "/private/tmp/claude-502/-Users-maxmaxvel-AI-TESI/69ef12c9-520b-4201-b801-1de8fefcf12f/scratchpad"
RUNS = (("doc23-recording.json.gz", 26, "A2"), ("doc24-recording.json.gz", 27, "E2"), ("doc25-recording.json.gz", 28, "BIO"), ("doc26-recording.json.gz", 29, "PSY"))
OFF = ["cibernetico", "Migrazioni", "Islamic Finance", "Understanding Financial Crises", "Integrasi di HIV", "ialuronico", "sessualit", "COVID-19 on the mental health of healthcare", "food consumption", "school disaffection", "synthetic drugs"]
PRICE = {"claude-haiku-4-5-20251001": (1.0, 5.0), "claude-sonnet-5": (3.0, 15.0)}  # USD per 1M tokens (in, out)
WINDOW_CHARS = 1300

def api_key():
    for line in open("/Users/maxmaxvel/AI TESI/apps/api/.env"):
        if line.startswith("ANTHROPIC_API_KEY="):
            return line.split("=", 1)[1].strip().strip("'\"")
    raise SystemExit("no key")

def pick_windows(wins, pattern):
    """Three distinct excerpts: the first with a topic anchor (subject/sample), the one with the most
    distinct anchors (best match), one from the last third (results/conclusions)."""
    def anchors(w):
        return len({m.group(0) for m in pattern.finditer(w.text.casefold())}) if pattern else 0
    if not wins: return []
    first = next((w for w in wins if anchors(w)), wins[0])
    best = max(wins, key=lambda w: (anchors(w), -wins.index(w)))
    tail = wins[len(wins) * 2 // 3:] or wins
    last = max(tail, key=lambda w: (anchors(w), -tail.index(w)))
    out = []
    for w in (first, best, last):
        if w not in out: out.append(w)
    return out

def locator(w):
    for attr in ("page", "page_start", "pages", "page_number"):
        if hasattr(w, attr): return f"{attr}={getattr(w, attr)}"
    return "?"

def load_runs():
    docs = []
    for rec, job, label in RUNS:
        data = json.loads(gzip.decompress(open(f"{SP}/recordings/{rec}", "rb").read()))
        events = [e for e in data["document_provenance"] if (e.get("payload") or {}).get("job_id", job) == job]
        def last(kind):
            rows = [e["payload"] for e in events if e.get("event_type") == kind]; return rows[-1]
        inputs = last("generation_replay_inputs")["executor_inputs"]; tree = last("executor_scopes")["nodes"]; nodes = flatten(tree)
        topic = inputs["brief"]["topic"]; requirements = inputs["brief"].get("additional_requirements") or ""
        pattern = topic_pattern(SimpleNamespace(topic=topic), nodes)
        deps = [e["payload"] for e in events if e.get("event_type") == "generation_dependency"]
        pages_by_url = {d["request"]["url"]: (d.get("response") or {}).get("pages") or [] for d in deps if d.get("kind") == "executor_full_text"}
        pack = last("executor_source_pack")["sources"]
        subject_nodes = [{"scope_id": n["scope_id"], "title": n.get("title", ""), "terms_local": n.get("terms_local", [])[:6], "terms_en": n.get("terms_en", [])[:6]} for n in nodes if not is_structural(n)]
        for r in pack:
            src = r["source"]; url = (src.get("canonical_metadata") or {}).get("open_access_url"); pages = pages_by_url.get(url) if url else None
            copy = None
            if not pages and label == "PSY":
                f = f"{SP}/copies/pages/{r['citation_key']}.json"
                if os.path.exists(f):
                    d = json.load(open(f)); pages = d["pages"]; url = d["url"]; copy = True
            if not pages: continue
            wins = document_windows(r["citation_key"], url, pages)
            docs.append({"run": label, "key": r["citation_key"], "title": src.get("title") or "", "year": src.get("year"), "venue": src.get("venue") or "", "abstract": (src.get("abstract") or "")[:1500], "label": "OFF" if any(k.casefold() in (src.get("title") or "").casefold() for k in OFF) else ("ON-copy" if copy else "ON"), "topic": topic, "requirements": requirements[:900], "nodes": subject_nodes, "windows": [{"locator": locator(w), "text": w.text[:WINDOW_CHARS]} for w in pick_windows(wins, pattern)], "n_windows": len(wins)})
    return docs

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

async def main():
    out_path, model = sys.argv[1], sys.argv[2]; cap = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0
    docs = load_runs()
    print(f"documents: {len(docs)} (ON {sum(d['label']=='ON' for d in docs)}, ON-copy {sum(d['label']=='ON-copy' for d in docs)}, OFF {sum(d['label']=='OFF' for d in docs)}) | model {model} | cap ${cap}")
    client = anthropic.AsyncAnthropic(api_key=api_key())
    price_in, price_out = PRICE[model]; spent = 0.0; results = []
    for d in docs:
        nodes = "\n".join(f"- {n['scope_id']}: {n['title']} | {', '.join(n['terms_local'])} | {', '.join(n['terms_en'])}" for n in d["nodes"])
        windows = "\n\n".join(f"[{w['locator']}] {w['text']}" for w in d["windows"])
        prompt = PROMPT.format(topic=d["topic"], requirements=d["requirements"], nodes=nodes, title=d["title"], year=d["year"], venue=d["venue"], abstract=d["abstract"] or "(none)", n_windows=d["n_windows"], windows=windows)
        if spent >= cap:
            results.append({**{k: d[k] for k in ("run", "key", "title", "label")}, "verdict": "skipped_cap"}); continue
        t0 = time.time()
        try:
            resp = await client.messages.create(model=model, max_tokens=300, messages=[{"role": "user", "content": prompt}])
            text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text").strip()
            usage = {"in": resp.usage.input_tokens, "out": resp.usage.output_tokens}
        except Exception as e:
            results.append({**{k: d[k] for k in ("run", "key", "title", "label")}, "verdict": f"error:{type(e).__name__}", "error": str(e)[:200]}); continue
        cost = usage["in"] / 1e6 * price_in + usage["out"] / 1e6 * price_out; spent += cost
        m = re.search(r"\{.*\}", text, re.S)
        try: parsed = json.loads(m.group(0)) if m else {}
        except Exception: parsed = {}
        row = {**{k: d[k] for k in ("run", "key", "title", "label")}, "verdict": parsed.get("verdict", "unparsed"), "population_match": parsed.get("population_match"), "scope_ids": parsed.get("scope_ids", []), "reason": parsed.get("reason", text[:200]), "usage": usage, "cost_usd": round(cost, 5), "seconds": round(time.time() - t0, 1), "prompt": prompt, "response": text}
        results.append(row)
        print(f"  {d['run']:3} {d['label']:7} -> {row['verdict']:9} pop={str(row['population_match']):5} {str(row['scope_ids'])[:30]:30} ${cost:.4f}  {d['title'][:46]}")
        await asyncio.sleep(0.3)
    json.dump({"model": model, "spent_usd": round(spent, 4), "results": results}, open(out_path, "w"), ensure_ascii=False, indent=1)
    print(f"\nspent ${spent:.3f}")
    from collections import Counter
    for lab in ("ON", "ON-copy", "OFF"):
        c = Counter(r["verdict"] for r in results if r["label"] == lab); print(f"  {lab:7}: {dict(c)}")
asyncio.run(main())
