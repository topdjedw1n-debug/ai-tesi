"""Third pass: phrase anchors learned from the run's own bilingual vocabulary (topic segments + every
non-structural node term, both languages), no single words.
N1 = every ordered bigram of consecutive content words inside a term/segment (stemmed, adjacency on stopword-stripped text)
N2 = only the bigrams that occur at least twice across the vocabulary (the run's recurring phrases)
Also the on-topic filter for pack rows (title+abstract, >=1 phrase) under N1."""
import gzip, json, os, sys, re
from collections import Counter
os.environ.update({"ENV_FILE": "/dev/null", "ENVIRONMENT": "test", "DEBUG": "true", "DATABASE_URL": "sqlite+aiosqlite:///:memory:", "SECRET_KEY": "offline-anchor-variants-secret-never-an-account", "JWT_SECRET": "offline-anchor-variants-secret-never-an-account"})
sys.path.insert(0, "/Users/maxmaxvel/AI TESI/apps/api")
from app.services.executor_v2.scopes import flatten
from app.services.full_text_sources import document_windows
from app.services.material_fit import normalize, node_terms
from app.services.search_queries import GENERIC, tokens, is_structural
OFF = ["cibernetico", "Migrazioni", "Islamic Finance", "Understanding Financial Crises", "Integrasi di HIV", "ialuronico", "sessualit", "COVID-19 on the mental health of healthcare", "food consumption", "school disaffection", "synthetic drugs"]
PREFIX = 6
def stem(w): return re.escape(w[:PREFIX]) + r"\w*" if len(w) >= PREFIX else re.escape(w) + r"\b"
def words(text): return [w for w in tokens(normalize(text)) if len(w) >= 3 and w not in GENERIC]
def grams(text): ws = words(text); return [tuple(ws[i:i+2]) for i in range(len(ws) - 1)]
def vocabulary(topic, nodes):
    segs = [p for p in re.split(r"[:;,()]|\s+(?:e|ed|and|o|or|vs)\s+", topic) if p.strip()]
    terms = segs + [t for n in nodes if not is_structural(n) for t in node_terms(n)]
    c = Counter(g for t in terms for g in set(grams(t)))
    return c
def strip_text(t): return " ".join(tokens(normalize(t)))
def run(rec, job, label):
    data = json.loads(gzip.decompress(open(rec, "rb").read()))
    events = [e for e in data["document_provenance"] if (e.get("payload") or {}).get("job_id", job) == job]
    def last(kind):
        rows = [e["payload"] for e in events if e.get("event_type") == kind]; return rows[-1]
    inputs = last("generation_replay_inputs")["executor_inputs"]; tree = last("executor_scopes")["nodes"]; nodes = flatten(tree)
    topic = inputs["brief"]["topic"]; c = vocabulary(topic, nodes)
    N1 = {g: r"\b" + r"\s+".join(stem(w) for w in g) for g in c}
    N2 = {g: rx for g, rx in N1.items() if c[g] >= 2}
    print(f"\n######## {label}: N1 {len(N1)} phrases, N2 {len(N2)}: {[' '.join(g) for g in N2][:20]}")
    deps = [e["payload"] for e in events if e.get("event_type") == "generation_dependency"]
    pages_by_url = {d["request"]["url"]: (d.get("response") or {}).get("pages") or [] for d in deps if d.get("kind") == "executor_full_text"}
    pack = last("executor_source_pack")["sources"]
    out = []
    print(f"  {'lab':3} {'N1':>5} {'N2':>5}  win  title")
    for r in pack:
        src = r["source"]; url = (src.get("canonical_metadata") or {}).get("open_access_url"); pages = pages_by_url.get(url) if url else None
        if not pages: continue
        wins = [strip_text(w.text) for w in document_windows(r["citation_key"], url, pages)]
        lab = "OFF" if any(k.casefold() in src["title"].casefold() for k in OFF) else "ON"
        n1 = sum(1 for w in wins if any(re.search(rx, w) for rx in N1.values())) / len(wins)
        n2 = sum(1 for w in wins if any(re.search(rx, w) for rx in N2.values())) / len(wins)
        out.append((lab, (n1, n2), src["title"])); print(f"  {lab:3} {n1:5.2f} {n2:5.2f}  {len(wins):4d}  {src['title'][:60]}")
    kept = sum(1 for r in pack if any(re.search(rx, strip_text((r['source'].get('title') or '') + ' ' + (r['source'].get('abstract') or ''))) for rx in N1.values()))
    dropped = [r["source"]["title"][:50] for r in pack if not any(re.search(rx, strip_text((r['source'].get('title') or '') + ' ' + (r['source'].get('abstract') or ''))) for rx in N1.values())]
    print(f"  pack rows with >=1 N1 phrase in title+abstract: {kept}/{len(pack)}; dropped: {dropped[:10]}")
    return out
allrows = []
for rec, job, label in (("doc23-recording.json.gz", 26, "A2"), ("doc24-recording.json.gz", 27, "E2"), ("doc25-recording.json.gz", 28, "BIO"), ("doc26-recording.json.gz", 29, "PSY")):
    allrows += run(f"/private/tmp/claude-502/-Users-maxmaxvel-AI-TESI/69ef12c9-520b-4201-b801-1de8fefcf12f/scratchpad/recordings/{rec}", job, label)
print("\n=== separation:")
for i, name in enumerate(("N1", "N2")):
    on = sorted(r[1][i] for r in allrows if r[0] == "ON"); off = sorted((r[1][i] for r in allrows if r[0] == "OFF"), reverse=True)
    print(f"  {name}: ON lowest {[round(x,2) for x in on[:4]]} | OFF highest {[round(x,2) for x in off[:4]]}")
