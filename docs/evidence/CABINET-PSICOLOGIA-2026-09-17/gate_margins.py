"""Offline: why did the eight full texts of doc 26 pass the document gate and the section exam? Prints the topic anchors, the per-document topic share, and per section x document (own, shared) with the verdict."""
import gzip, json, os, sys, re
from types import SimpleNamespace
os.environ.update({"ENV_FILE": "/dev/null", "ENVIRONMENT": "test", "DEBUG": "true", "DATABASE_URL": "sqlite+aiosqlite:///:memory:", "SECRET_KEY": "offline-gate-margins-secret-never-an-account", "JWT_SECRET": "offline-gate-margins-secret-never-an-account"})
sys.path.insert(0, "/Users/maxmaxvel/AI TESI/apps/api")
from app.services.executor_v2.scopes import flatten
from app.services.full_text_sources import document_windows, topic_pattern, MIN_RELEVANCE, MIN_MATCHED_TERMS
from app.services.material_fit import document_topic_share, section_fit, about_section, document_text, MIN_DOCUMENT_TOPIC_SHARE, MIN_SHARED_TERMS, node_terms, covers
from app.services.search_queries import plan, on_topic

rec, job = sys.argv[1], int(sys.argv[2])
data = json.loads(gzip.decompress(open(rec, "rb").read()))
events = [e for e in data["document_provenance"] if (e.get("payload") or {}).get("job_id", job) == job]
def last(kind):
    rows = [e["payload"] for e in events if e.get("event_type") == kind]; return rows[-1]
inputs = last("generation_replay_inputs")["executor_inputs"]
tree = last("executor_scopes")["nodes"]; nodes = flatten(tree)
topic = inputs["brief"]["topic"]
queries, parents, anchors_ = plan(topic, tree)
pattern = topic_pattern(SimpleNamespace(topic=topic), nodes)
print("TOPIC:", topic)
print("TOPIC ANCHORS (S2 on-topic pattern):", pattern.pattern if pattern else None)
print("NODES:")
for n in nodes:
    print(f"  {n['scope_id']:9} req={n.get('required')} {n.get('title','')[:60]} | terms: {node_terms(n)[:8]}")
deps = [e["payload"] for e in events if e.get("event_type") == "generation_dependency"]
pages_by_url = {d["request"]["url"]: (d.get("response") or {}).get("pages") or [] for d in deps if d.get("kind") == "executor_full_text"}
pack = last("executor_source_pack")["sources"]
outline = last("executor_outline")["sections"]
full = []
for r in pack:
    src = r["source"]; url = (src.get("canonical_metadata") or {}).get("open_access_url")
    pages = pages_by_url.get(url) if url else None
    if pages:
        windows = document_windows(r["citation_key"], url, pages)
        texts = [w.text for w in windows]
        share = document_topic_share(texts, pattern)
        full.append((r["citation_key"], src, share, len(texts)))
print(f"\nDOCUMENT GATE (share of windows with a topic anchor, threshold {MIN_DOCUMENT_TOPIC_SHARE}):")
for k, src, share, n in sorted(full, key=lambda x: -x[2]):
    print(f"  {share:.2f}  {n:4d} windows  {src['title'][:70]}")
print(f"\nSECTION EXAM per document (own>=1 or shared>={MIN_SHARED_TERMS}); cells = own/shared, * = passes")
docs = [(k, src) for k, src, _, _ in full]
print("     " + " ".join(f"{src['title'][:10]:>10}" for _, src in docs))
for s in outline:
    cells = []
    for k, src in docs:
        own, shared = section_fit(s, nodes, document_text(src))
        cells.append(f"{own}/{shared}{'*' if about_section(s, nodes, src) else ' '}")
    print(f"§{s['section_index']:>2} {s['title'][:28]:28} " + " ".join(f"{c:>10}" for c in cells))
print("\nWHY the abstract-only foreign rows are on topic (anchors matched in title+abstract):")
for r in pack:
    src = r["source"]; t = document_text(src).casefold()
    if re.search(r"cardiovasc|synthetic drugs|overweight|food consumption|sessualit|healthcare workers|substance|dificultad|dropout", t):
        found = sorted(set(m.group(0) for m in pattern.finditer(t))) if pattern else []
        print(f"  {src['title'][:60]:60} -> {found[:8]}")
