"""$0 proof of change B on five recordings: BEFORE = the recorded prompts of the framing sections
(findings rows, document windows in evidence, where the cited keys came from); AFTER = the new
findings() on the recorded finished sections (rows, size) and, by construction, no evidence."""
import gzip, json, os, re, sys
os.environ.update({"ENV_FILE": "/dev/null", "ENVIRONMENT": "test", "DEBUG": "true", "DATABASE_URL": "sqlite+aiosqlite:///:memory:", "SECRET_KEY": "offline-frame-proof-secret-never-an-account", "JWT_SECRET": "offline-frame-proof-secret-never-an-account"})
sys.path.insert(0, "/Users/maxmaxvel/AI TESI/apps/api")
from app.services.section_material import findings, is_frame, writing_order
PAGE = re.compile(r"\[page \d+\]"); KEY = re.compile(r"K[0-9a-f]{12}"); CITED = re.compile(r"\[(K[0-9a-f]{12})\]")
def run(path, job, label):
    data = json.loads(gzip.decompress(open(path, "rb").read()))
    prov = [e["payload"] for e in data["document_provenance"] if e["event_type"] == "generation_provider_attempt" and e["payload"].get("job_id") == job and e["payload"].get("stage") == "S4"]
    outline = [e["payload"] for e in data["document_provenance"] if e["event_type"] == "executor_outline" and e["payload"].get("job_id") == job][-1]["sections"]
    secs = {s["section_index"]: s for s in (data.get("document_sections") or [])}
    by_idx = {s["section_index"]: s for s in outline}
    frames = [s for s in outline if is_frame(s)]
    order = [s["section_index"] for s in writing_order(outline)]
    print(f"\n######## {label}: sections {len(outline)}, frames {[ (s['section_index'], s['title'][:20]) for s in frames]}, writing order {order}")
    for fr in sorted(frames, key=lambda s: order.index(s["section_index"])):
        idx = fr["section_index"]
        started = next((r for r in prov if r.get("section_index") == idx and r.get("outcome") == "started"), None)
        received = next((r for r in prov if r.get("section_index") == idx and r.get("outcome") == "received"), None)
        before = "no recorded prompt"
        if started and received:
            req = started["request"]; msgs = req.get("messages") if isinstance(req, dict) else None
            text = msgs[0]["content"] if msgs else json.dumps(req, ensure_ascii=False)
            text = text if isinstance(text, str) else json.dumps(text, ensure_ascii=False)
            k = text.find('{"forbidden_placeholders"'); obj = json.loads(text[k:]) if k >= 0 else {}
            f = obj.get("findings") or []; ev = obj.get("evidence") or []
            resp = received["response"]; rt = resp if isinstance(resp, str) else json.dumps(resp, ensure_ascii=False)
            cited = sorted(set(CITED.findall(rt))); fk = set(KEY.findall(json.dumps(f, ensure_ascii=False))); ek = set(KEY.findall(json.dumps(ev, ensure_ascii=False)))
            frame_flag = "frame" if "findings" in obj else "NOT frame"
            before = f"{frame_flag}; findings rows {len(f)}; evidence docs {len(ev)}, windows {len(PAGE.findall(json.dumps(ev, ensure_ascii=False)))}; cited {len(cited)}: from findings {len([c for c in cited if c in fk])}, from evidence only {len([c for c in cited if c in ek and c not in fk])}"
        # AFTER: the sections finished before this frame, in writing order, with the recorded content and the plan's question/conclusion
        finished_idx = order[: order.index(idx)]
        written = [{**by_idx[i], "content": (secs.get(i) or {}).get("content") or ""} for i in finished_idx]
        after = findings(written)
        size = len(json.dumps(after, ensure_ascii=False))
        print(f"  §{idx} {fr['title'][:28]:28} BEFORE: {before}")
        print(f"      AFTER : findings rows {len(after)}/{len(written)} (all finished sections), size {size} chars, facts {sum(len(r['facts']) for r in after)}; evidence: none by construction; last row = {after[-1]['title'][:28] if after else None}")
for path, job, label in ((f"{sys.argv[1]}/doc23-recording.json.gz", 26, "A2"), (f"{sys.argv[1]}/doc24-recording.json.gz", 27, "E2"), (f"{sys.argv[1]}/doc25-recording.json.gz", 28, "BIO"), (f"{sys.argv[1]}/doc26-recording.json.gz", 29, "PSY doc26"), (f"{sys.argv[2]}/doc30-recording.json.gz", 33, "PSY doc30")):
    run(path, job, label)
