"""Calibration at $0 on the four recordings: how would phrase-preserving topic anchors change
(a) the document gate (share of windows with an anchor) for every fetched full text,
(b) the S2 on-topic filter for the pack rows, (c) the section exam's shared-word count.
Variants: B = current anchors (word starts); P = phrases of the topic segments + every non-structural
node's terms (multi-word terms as ordered phrases, single terms >= 4 letters); C = topic phrases +
chapter nodes' multi-word terms only."""
import gzip, json, os, sys, re
from types import SimpleNamespace
os.environ.update({"ENV_FILE": "/dev/null", "ENVIRONMENT": "test", "DEBUG": "true", "DATABASE_URL": "sqlite+aiosqlite:///:memory:", "SECRET_KEY": "offline-anchor-variants-secret-never-an-account", "JWT_SECRET": "offline-anchor-variants-secret-never-an-account"})
sys.path.insert(0, "/Users/maxmaxvel/AI TESI/apps/api")
from app.services.executor_v2.scopes import flatten
from app.services.full_text_sources import document_windows, topic_pattern
from app.services.material_fit import document_topic_share, section_fit, about_section, document_text, normalize, node_terms, MIN_SHARED_TERMS
from app.services.search_queries import GENERIC, STOPWORDS, content_tokens, tokens, is_structural, on_topic, walk

PREFIX = 6
def stem(w):
    return re.escape(w[:PREFIX]) + r"\w*" if len(w) >= PREFIX else re.escape(w) + r"\b"
def phrase_regex(words):
    return r"\b" + r"\s+".join(stem(w) for w in words)
def segments(topic):
    t = normalize(topic)
    parts = re.split(r"[:;,()]|\s+(?:e|ed|and|o|or|vs)\s+", t)
    return [p for p in parts if p and p.strip()]
def topic_anchors(topic):
    out = []
    for seg in segments(topic):
        ws = [w for w in tokens(seg) if len(w) >= 4 and w not in GENERIC]
        if len(ws) == 1: out.append((ws[0],))
        else: out += [tuple(ws[i:i+2]) for i in range(len(ws) - 1)]
    return out
def term_anchor(term):
    ws = [w for w in tokens(normalize(term)) if len(w) >= 3 and w not in GENERIC]
    if not ws: return None
    if len(ws) == 1: return (ws[0],) if len(ws[0]) >= 4 else None
    return tuple(ws)
def build(anchor_tuples):
    seen = {}
    for a in anchor_tuples:
        if a: seen[a] = phrase_regex(a)
    return seen
def strip_text(text):
    return " ".join(tokens(normalize(text)))
def matches(patterns, text):
    t = strip_text(text)
    return {a for a, rx in patterns.items() if re.search(rx, t)}
def share(patterns, windows):
    return sum(1 for w in windows if matches(patterns, w)) / len(windows) if windows else 0.0
def ontopic_v(patterns, row):
    title, abstract = row.get("title") or "", row.get("abstract") or ""
    if not title: return False
    found = matches(patterns, f"{title} {abstract}")
    return len(found) >= 2 or (not abstract and bool(matches(patterns, title)))

def run(rec, job, label):
    data = json.loads(gzip.decompress(open(rec, "rb").read()))
    events = [e for e in data["document_provenance"] if (e.get("payload") or {}).get("job_id", job) == job]
    def last(kind):
        rows = [e["payload"] for e in events if e.get("event_type") == kind]; return rows[-1]
    inputs = last("generation_replay_inputs")["executor_inputs"]; tree = last("executor_scopes")["nodes"]; nodes = flatten(tree)
    topic = inputs["brief"]["topic"]
    base = topic_pattern(SimpleNamespace(topic=topic), nodes)
    chapters = [n for n in tree if not is_structural(n)]
    P = build(topic_anchors(topic) + [term_anchor(t) for n in nodes if not is_structural(n) for t in node_terms(n)])
    C = build(topic_anchors(topic) + [a for n in chapters for t in node_terms(n) if (a := term_anchor(t)) and len(a) >= 2])
    print(f"\n######## {label}: {topic[:80]}")
    print("topic anchors:", [" ".join(a) for a in topic_anchors(topic)])
    print(f"P anchors: {len(P)}; C anchors: {len(C)}: {[' '.join(a) for a in C][:14]}")
    deps = [e["payload"] for e in events if e.get("event_type") == "generation_dependency"]
    pages_by_url = {d["request"]["url"]: (d.get("response") or {}).get("pages") or [] for d in deps if d.get("kind") == "executor_full_text"}
    pack = last("executor_source_pack")["sources"]; outline = last("executor_outline")["sections"]
    print(f"\n{'B share':>7} {'P share':>7} {'C share':>7}  windows  title")
    full = []
    for r in pack:
        src = r["source"]; url = (src.get("canonical_metadata") or {}).get("open_access_url"); pages = pages_by_url.get(url) if url else None
        if not pages: continue
        wins = [w.text for w in document_windows(r["citation_key"], url, pages)]
        b = document_topic_share(wins, base); p = share(P, wins); c = share(C, wins)
        full.append((r["citation_key"], src, wins))
        print(f"{b:7.2f} {p:7.2f} {c:7.2f}  {len(wins):7d}  {src['title'][:75]}")
    kept = {"B": 0, "P": 0, "C": 0}; dropped = {"P": [], "C": []}
    for r in pack:
        src = r["source"]
        if on_topic(src, base): kept["B"] += 1
        for name, pats in (("P", P), ("C", C)):
            if ontopic_v(pats, src): kept[name] += 1
            else: dropped[name].append(src["title"][:60])
    print(f"\npack rows on topic: B {kept['B']}/{len(pack)}  P {kept['P']}  C {kept['C']}")
    for name in ("P", "C"): print(f"  dropped by {name} ({len(dropped[name])}): {dropped[name][:12]}")
    # section exam: shared words without the topic's own tokens
    topic_tokens = set(content_tokens(normalize(topic)))
    ev = {int(e["payload"]["section_index"]): e["payload"]["evidence"] for e in events if e.get("event_type") == "executor_section_evidence"}
    by_key = {k: src for k, src, _ in full}
    print("\nsection exam on full texts that got pages (own/shared -> shared without topic words):")
    for s in outline:
        i = int(s["section_index"]); rows = [r for r in ev.get(i, []) if r["key"] in by_key and r["windows"]]
        if not rows: continue
        cells = []
        for r in rows:
            src = by_key[r["key"]]; own, sh = section_fit(s, nodes, document_text(src))
            wording_tokens = set(content_tokens(" ".join(str(x) for x in [s.get("title"), s.get("purpose"), s.get("question"), *(s.get("main_points") or [])] if x)))
            doc_tokens = set(content_tokens(normalize(document_text(src))))
            sh2 = len((wording_tokens & doc_tokens) - topic_tokens)
            verdict_new = own >= 1 or sh2 >= MIN_SHARED_TERMS
            cells.append(f"{src['title'][:22]}[{own}/{sh}->{sh2}{'*' if verdict_new else '-'}]")
        print(f" §{i:>2} {s['title'][:30]:30} " + " ; ".join(cells))

for rec, job, label in (("doc23-recording.json.gz", 26, "A2 economia-1 (digital marketing PMI)"), ("doc24-recording.json.gz", 27, "E2 economia-2 (fintech/credito PMI)"), ("doc25-recording.json.gz", 28, "BIO antibiotici"), ("doc26-recording.json.gz", 29, "PSY social media adolescenti")):
    run(f"/private/tmp/claude-502/-Users-maxmaxvel-AI-TESI/69ef12c9-520b-4201-b801-1de8fefcf12f/scratchpad/recordings/{rec}", job, label)
