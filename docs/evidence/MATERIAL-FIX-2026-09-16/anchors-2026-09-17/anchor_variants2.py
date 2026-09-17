"""Second calibration pass: window-level rules on the current word anchors and on topic-only anchors.
B  = current (>=1 anchor per window, anchors = topic words + english core of the nodes)
B2 = >=2 distinct anchors per window
Bt = topic-derived anchors only (no english core), >=1
Bt2 = topic-derived only, >=2 distinct
H  = phrase-preserving head anchors: bigrams of the topic segments + the English node terms paired with a local term containing such a bigram, >=1 per window
HB = window passes H, or carries >=2 distinct B anchors of which one is topic-derived
Labels: OFF = known off-topic full texts (manual), ON = the rest."""
import gzip, json, os, sys, re
from types import SimpleNamespace
os.environ.update({"ENV_FILE": "/dev/null", "ENVIRONMENT": "test", "DEBUG": "true", "DATABASE_URL": "sqlite+aiosqlite:///:memory:", "SECRET_KEY": "offline-anchor-variants-secret-never-an-account", "JWT_SECRET": "offline-anchor-variants-secret-never-an-account"})
sys.path.insert(0, "/Users/maxmaxvel/AI TESI/apps/api")
from app.services.executor_v2.scopes import flatten
from app.services.full_text_sources import document_windows
from app.services.material_fit import normalize
from app.services.search_queries import GENERIC, content_tokens, tokens, is_structural, anchors, english_core, walk

OFF = ["cibernetico", "Migrazioni", "Islamic Finance", "Understanding Financial Crises", "Integrasi di HIV", "ialuronico", "sessualit", "COVID-19 on the mental health of healthcare", "food consumption", "school disaffection", "synthetic drugs"]
PREFIX = 6
def stem(w): return re.escape(w[:PREFIX]) + r"\w*" if len(w) >= PREFIX else re.escape(w) + r"\b"
def segments(topic): return [p for p in re.split(r"[:;,()]|\s+(?:e|ed|and|o|or|vs)\s+", normalize(topic)) if p and p.strip()]
def bigrams(seg):
    ws = [w for w in tokens(seg) if len(w) >= 4 and w not in GENERIC]
    return [tuple(ws)] if len(ws) == 1 else [tuple(ws[i:i+2]) for i in range(len(ws) - 1)]
def head_anchors(topic, nodes):
    grams = [g for seg in segments(topic) for g in bigrams(seg)]
    out = {g: r"\b" + r"\s+".join(stem(w) for w in g) for g in grams}
    for n in nodes:
        if is_structural(n): continue
        loc, en = list(n.get("terms_local") or []), list(n.get("terms_en") or [])
        for i, lt in enumerate(loc):
            lt_n = " ".join(tokens(normalize(lt)))
            if any(len(g) >= 2 and re.search(out[g], lt_n) for g in grams) and i < len(en):
                ws = [w for w in tokens(normalize(en[i])) if len(w) >= 3 and w not in GENERIC]
                if len(ws) >= 2: out[tuple(ws)] = r"\b" + r"\s+".join(stem(w) for w in ws)
    return out
def strip_text(t): return " ".join(tokens(normalize(t)))
def distinct(pattern, text): return {m.group(0) for m in pattern.finditer(text.casefold())} if pattern else set()

def run(rec, job, label):
    data = json.loads(gzip.decompress(open(rec, "rb").read()))
    events = [e for e in data["document_provenance"] if (e.get("payload") or {}).get("job_id", job) == job]
    def last(kind):
        rows = [e["payload"] for e in events if e.get("event_type") == kind]; return rows[-1]
    inputs = last("generation_replay_inputs")["executor_inputs"]; tree = last("executor_scopes")["nodes"]; nodes = flatten(tree)
    topic = inputs["brief"]["topic"]
    B = anchors(topic, english_core(nodes, 8)); Bt = anchors(topic)
    H = head_anchors(topic, nodes)
    print(f"\n######## {label}")
    print("  Bt anchors:", Bt.pattern[:160]); print("  H anchors:", [" ".join(g) for g in H][:16])
    deps = [e["payload"] for e in events if e.get("event_type") == "generation_dependency"]
    pages_by_url = {d["request"]["url"]: (d.get("response") or {}).get("pages") or [] for d in deps if d.get("kind") == "executor_full_text"}
    pack = last("executor_source_pack")["sources"]
    print(f"  {'lab':3} {'B':>5} {'B2':>5} {'Bt':>5} {'Bt2':>5} {'H':>5} {'HB':>5}  win  title")
    rows = []
    for r in pack:
        src = r["source"]; url = (src.get("canonical_metadata") or {}).get("open_access_url"); pages = pages_by_url.get(url) if url else None
        if not pages: continue
        wins = [w.text for w in document_windows(r["citation_key"], url, pages)]
        n = len(wins); lab = "OFF" if any(k.casefold() in src["title"].casefold() for k in OFF) else "ON"
        b = b2 = bt = bt2 = h = hb = 0
        for w in wins:
            db = distinct(B, w); dt = distinct(Bt, w); sw = strip_text(w); dh = {g for g, rx in H.items() if re.search(rx, sw)}
            b += bool(db); b2 += len(db) >= 2; bt += bool(dt); bt2 += len(dt) >= 2; h += bool(dh); hb += bool(dh) or (len(db) >= 2 and bool(dt))
        vals = [x / n for x in (b, b2, bt, bt2, h, hb)]
        rows.append((lab, vals, src["title"]))
        print(f"  {lab:3} " + " ".join(f"{v:5.2f}" for v in vals) + f"  {n:4d}  {src['title'][:60]}")
    return rows

allrows = []
for rec, job, label in (("doc23-recording.json.gz", 26, "A2"), ("doc24-recording.json.gz", 27, "E2"), ("doc25-recording.json.gz", 28, "BIO"), ("doc26-recording.json.gz", 29, "PSY")):
    allrows += run(f"/private/tmp/claude-502/-Users-maxmaxvel-AI-TESI/69ef12c9-520b-4201-b801-1de8fefcf12f/scratchpad/recordings/{rec}", job, label)
print("\n=== separation over all four recordings (min share of ON docs vs max share of OFF docs):")
for i, name in enumerate(("B", "B2", "Bt", "Bt2", "H", "HB")):
    on = [r[1][i] for r in allrows if r[0] == "ON"]; off = [r[1][i] for r in allrows if r[0] == "OFF"]
    on_s = sorted(on); off_s = sorted(off, reverse=True)
    print(f"  {name:3} ON min {min(on):.2f} (lowest three {[round(x,2) for x in on_s[:3]]}) | OFF max {max(off):.2f} (highest three {[round(x,2) for x in off_s[:3]]}) | ON<0.5: {sum(1 for x in on if x<0.5)}/{len(on)}  OFF>=0.5: {sum(1 for x in off if x>=0.5)}/{len(off)}")
