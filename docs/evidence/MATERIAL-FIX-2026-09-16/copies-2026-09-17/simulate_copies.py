"""Offline ($0): the psychology run replayed through the current material code with the eight
repository copies added as full texts. Prints, per section, which documents hand pages BEFORE
(recorded) and AFTER (recorded pack + new pages), and the plan-check warnings."""
import gzip, json, os, sys, glob
os.environ.update({"ENV_FILE": "/dev/null", "ENVIRONMENT": "test", "DEBUG": "true", "DATABASE_URL": "sqlite+aiosqlite:///:memory:", "SECRET_KEY": "offline-copies-secret-never-an-account", "JWT_SECRET": "offline-copies-secret-never-an-account"})
sys.path.insert(0, "/Users/maxmaxvel/AI TESI/apps/api")
from app.services.ai_pipeline.rag_retriever import SourceDoc
from app.services.ai_pipeline.source_pack import PackedSource, SourcePack
from app.services.executor_v2.scopes import flatten
from app.services.full_text_sources import document_windows, section_evidence
from app.services.plan_check import review
from app.services.source_evidence import freeze_evidence
from app.services.uploaded_sources import SourcePassage
sp = "/private/tmp/claude-502/-Users-maxmaxvel-AI-TESI/69ef12c9-520b-4201-b801-1de8fefcf12f/scratchpad"
job = 29
data = json.loads(gzip.decompress(open(f"{sp}/recordings/doc26-recording.json.gz", "rb").read()))
events = [e for e in data["document_provenance"] if (e.get("payload") or {}).get("job_id", job) == job]
def last(kind):
    rows = [e["payload"] for e in events if e.get("event_type") == kind]; return rows[-1]
inputs = last("generation_replay_inputs")["executor_inputs"]; tree = last("executor_scopes")["nodes"]; nodes = flatten(tree)
topic = inputs["brief"]["topic"]
deps = [e["payload"] for e in events if e.get("event_type") == "generation_dependency"]
pages_by_url = {d["request"]["url"]: (d.get("response") or {}).get("pages") or [] for d in deps if d.get("kind") == "executor_full_text"}
new_pages = {}
for f in glob.glob(f"{sp}/copies/pages/*.json"):
    d = json.load(open(f)); new_pages[d["key"]] = (d["url"], d["pages"])
recorded = last("executor_source_pack")["sources"]; outline = last("executor_outline")["sections"]
rec_ev = {int(e["payload"]["section_index"]): e["payload"]["evidence"] for e in events if e.get("event_type") == "executor_section_evidence"}
def build(with_copies):
    selected, passages = [], [SourcePassage(**p) for p in inputs.get("passages") or []]
    for r in recorded:
        src = SourceDoc(**r["source"]); key = r["citation_key"]
        cm = src.canonical_metadata or {}; url = cm.get("open_access_url"); pages = pages_by_url.get(url) if url else None
        if not pages and with_copies and key in new_pages:
            url, pages = new_pages[key]
        if pages:
            wins = document_windows(key, url, pages); passages.extend(wins)
            freeze_evidence(src, passages, key, query=topic); cm["evidence_level"] = "pdf"
        src.canonical_metadata = cm
        selected.append(PackedSource(src, key, r.get("on_topic_score", 1.0)))
    return SourcePack(0, topic, sources=selected, passages=passages)
title = {r["citation_key"]: r["source"]["title"][:30] for r in recorded}
for label, with_copies in (("BEFORE (recorded pages)", False), ("AFTER (+8 repository copies)", True)):
    pack = build(with_copies)
    print(f"\n===== {label}: full texts {sum(1 for p in pack.sources if (p.source.canonical_metadata or {}).get('evidence_level') == 'pdf')}")
    sections = [dict(s) for s in outline]
    warnings = review(sections, pack, nodes)
    for s in sections:
        items, selection = section_evidence(pack, s, nodes)
        rows = [f"{title[x['key']]}[{x['reason']},w={x['windows']}]" for x in selection if x.get("windows") or x.get("chars")]
        print(f" §{s['section_index']:>2} {s['title'][:34]:34} | " + " ; ".join(rows))
    print(" plan warnings:", [w.get("detail", w) if isinstance(w, dict) else w for w in warnings][:8])
