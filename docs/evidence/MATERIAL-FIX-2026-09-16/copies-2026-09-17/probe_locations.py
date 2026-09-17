"""$0 probe: for every pack record with a DOI, ask OpenAlex for all its locations and try each
open-access PDF link (repositories first) with the production fetcher's headers. Reports which
records gain readable pages that the run did not have. Nothing is written to the server."""
import asyncio, json, sys, time, re
import httpx, pymupdf
USER_AGENT = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36 Thesica/1.0")
ACCEPT = "application/pdf,text/html;q=0.9,*/*;q=0.8"
META = re.compile(r"<meta[^>]+?(?:name|property)=[\"']citation_pdf_url[\"'][^>]*?content=[\"']([^\"']+)[\"']|<meta[^>]+?content=[\"']([^\"']+)[\"'][^>]*?(?:name|property)=[\"']citation_pdf_url[\"']", re.I)
MAX_PER_RECORD = 3
rows = json.load(open(sys.argv[1])); out_path = sys.argv[2]

def pdf_pages(data):
    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
        return sum(1 for p in doc if len(p.get_text("text").strip()) > 200), len(doc)
    except Exception:
        return 0, 0

async def fetch(client, url):
    try:
        r = await client.get(url)
    except Exception as e:
        return {"url": url, "status": None, "reason": f"error:{type(e).__name__}"}
    ct = r.headers.get("content-type", "")
    body = r.content
    if r.status_code != 200:
        return {"url": url, "status": r.status_code, "reason": f"http_{r.status_code}", "final": str(r.url)}
    if body[:5] == b"%PDF-" or "pdf" in ct:
        text_pages, pages = pdf_pages(body)
        return {"url": url, "status": 200, "reason": None if text_pages else "no_text_layer", "pages": text_pages, "total_pages": pages, "final": str(r.url), "bytes": len(body)}
    if b"citation_pdf_url" in body:
        m = META.search(body.decode("utf-8", "ignore"))
        link = next((g for g in (m.groups() if m else ()) if g), None)
        if link:
            link = str(httpx.URL(str(r.url)).join(link))
            sub = await fetch(client, link)
            sub["via_landing"] = url
            return sub
    return {"url": url, "status": 200, "reason": "not_pdf", "content_type": ct[:40], "final": str(r.url)}

async def main():
    results = []
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True, headers={"User-Agent": USER_AGENT, "Accept": ACCEPT}) as client:
        for row in rows:
            doi = row.get("doi")
            rec = {"key": row["key"], "title": row["title"][:70], "doi": doi, "run_url": row.get("oa_url"), "run_pages": row.get("pages"), "run_reason": row.get("reason"), "candidates": [], "tries": []}
            results.append(rec)
            if not doi:
                rec["note"] = "no doi"; continue
            try:
                r = await client.get(f"https://api.openalex.org/works/https://doi.org/{doi}", params={"select": "id,title,open_access,best_oa_location,locations"})
                if r.status_code != 200:
                    rec["note"] = f"openalex_{r.status_code}"; await asyncio.sleep(0.3); continue
                work = r.json()
            except Exception as e:
                rec["note"] = f"openalex_error:{type(e).__name__}"; continue
            cands = []
            for loc in work.get("locations") or []:
                if not loc.get("is_oa"): continue
                src = loc.get("source") or {}
                for u in (loc.get("pdf_url"), loc.get("landing_page_url")):
                    if u and u.startswith("http") and u not in [c["url"] for c in cands]:
                        cands.append({"url": u, "kind": src.get("type") or "?", "host": src.get("display_name") or "", "is_pdf_field": u == loc.get("pdf_url")})
            # repositories first, pdf fields before landing pages, then the rest; skip the url the run already tried
            cands.sort(key=lambda c: (0 if c["kind"] == "repository" else 1, 0 if c["is_pdf_field"] else 1))
            cands = [c for c in cands if c["url"] != row.get("oa_url")]
            rec["candidates"] = cands
            for c in cands[:MAX_PER_RECORD]:
                res = await fetch(client, c["url"]); res["kind"] = c["kind"]; res["host"] = c["host"]
                rec["tries"].append(res)
                await asyncio.sleep(0.5)
                if res.get("pages"): break
            await asyncio.sleep(0.3)
    json.dump(results, open(out_path, "w"), ensure_ascii=False, indent=1)
    gained = [r for r in results if not r["run_pages"] and any(t.get("pages") for t in r["tries"])]
    print(f"records: {len(results)} | with candidates: {sum(1 for r in results if r['candidates'])} | tries: {sum(len(r['tries']) for r in results)} | GAINED readable pages: {len(gained)}")
    print(f"\n{'key':14} {'run':9} {'cands':>5}  outcome")
    for r in results:
        best = next((t for t in r["tries"] if t.get("pages")), None)
        outcome = f"GAIN {best['pages']}/{best['total_pages']} p via {best['kind']} {best['host'][:28]} {best['url'][:60]}" if best else ("run had pages" if r["run_pages"] else (r.get("note") or ("; ".join(f"{t['kind']}:{t.get('reason')}" for t in r["tries"]) if r["tries"] else "no alternative")))
        print(f"{r['key']:14} {str(r['run_reason'] or ('pages' if r['run_pages'] else 'no url')):9} {len(r['candidates']):5d}  {outcome}")
asyncio.run(main())
