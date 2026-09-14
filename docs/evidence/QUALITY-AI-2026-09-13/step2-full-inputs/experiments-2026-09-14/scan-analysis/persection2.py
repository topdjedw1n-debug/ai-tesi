"""Line-based per-section shares: every text line belongs to the current section; headings matched
against plan titles (numbering stripped, up to 3 wrapped lines); 1-2 word numeric lines (margin source
numbers, page numbers) excluded. Old and new reports are computed with the same rule."""
import json, re, sys, difflib
from collections import OrderedDict
def norm(s): return re.sub(r"\W+"," ",s.replace("‎","")).strip().lower()
def strip_num(s): return re.sub(r"^\s*\d+(?:\.\d+)*[.)]?\s+","",s.replace("‎","").strip())
NUMERIC=re.compile(r"^[\d\s,.\-–/]+$")
def canon(t): return re.sub(r"\s+"," ",t.replace("’","'").replace("«",'"').replace("»",'"').replace("–","-").replace("—","-").replace("‎","")).strip()
def sections(lines_path, titles):
    L=json.load(open(lines_path))["lines"]
    tset={norm(t):t for t in titles+["Bibliografia","Normativa e giurisprudenza","Indice"]}
    out=OrderedDict(); sec=None; i=0
    while i<len(L):
        matched=None
        for k in (1,2,3):
            if i+k>len(L): break
            joined=" ".join(x["text"] for x in L[i:i+k])
            if norm(strip_num(joined)) in tset: matched=(tset[norm(strip_num(joined))],k)
        if matched:
            sec=matched[0]; out.setdefault(sec,{"words":0,"ai":0,"sim":0,"text":[]}); i+=matched[1]; continue
        l=L[i]; i+=1
        if sec is None: continue
        if l["words"]<=2 and NUMERIC.match(l["text"].replace("‎","")): continue
        if "Punti di interesse" in l["text"]: continue
        o=out[sec]; o["words"]+=l["words"]; o["ai"]+=sum(l["ai_flags"]); o["sim"]+=sum(l["sim_flags"]); o["text"].append(l["text"])
    for o in out.values():
        o["ai_pct"]=round(100*o["ai"]/o["words"],1) if o["words"] else None
        o["sim_pct"]=round(100*o["sim"]/o["words"],1) if o["words"] else None
    return out
if __name__=="__main__":
    sp=sys.argv[1]; E="docs/evidence/QUALITY-AI-2026-09-13/step2-full-inputs"; res={}
    for work,fix in (("A","fix-A"),("B","fix-B-v1")):
        rep=json.load(open(f"{E}/experiments-2026-09-14/{fix}/lab-report.json")); titles=[s["title"] for s in rep["sections"]]; live=rep["live_sections"]
        new=sections(f"{sp}/{work}-fix.lines2.json",titles); old=sections(f"{sp}/{work}-old.lines2.json",titles)
        print(f"\n=== {work}: rewritten sections {live}")
        print(f"{'#':>3} {'section':38s} {'old AI':>7} {'new AI':>7} {'dAI':>6} {'old sim':>8} {'new sim':>8} {'words o/n':>10} text_ratio")
        rows=[]
        for idx,t in enumerate(titles+["Bibliografia","Normativa e giurisprudenza"],1):
            o=old.get(t); n=new.get(t)
            if not o and not n: continue
            ratio=round(difflib.SequenceMatcher(None,canon(" ".join(o["text"])).split(),canon(" ".join(n["text"])).split()).ratio(),3) if (o and n and o["words"] and n["words"]) else None
            oa=o["ai_pct"] if o else None; na=n["ai_pct"] if n else None; d=(na-oa) if (oa is not None and na is not None) else None
            print(f"{idx:>2}{'*' if idx in live else ' '} {t[:38]:38s} {str(oa):>7} {str(na):>7} {('%+.1f'%d) if d is not None else '':>6} {str(o['sim_pct'] if o else None):>8} {str(n['sim_pct'] if n else None):>8} {str(o['words'] if o else 0)+'/'+str(n['words'] if n else 0):>10} {ratio}")
            rows.append({"index":idx,"title":t,"live":idx in live,"old":{k:v for k,v in (o or {}).items() if k!="text"},"new":{k:v for k,v in (n or {}).items() if k!="text"},"text_ratio":ratio})
        def agg(rs,which,key):
            w=sum(r[which]["words"] for r in rs if r[which]); return round(100*sum(r[which][key] for r in rs if r[which])/w,1) if w else None
        un=[r for r in rows if not r["live"] and r["old"] and r["new"] and r["index"]<=len(titles)]; lv=[r for r in rows if r["live"]]
        print(f" unchanged {len(un)} sections: AI old {agg(un,'old','ai')} -> new {agg(un,'new','ai')} | sim old {agg(un,'old','sim')} -> new {agg(un,'new','sim')}")
        print(f" rewritten sections: AI old {agg(lv,'old','ai')} -> new {agg(lv,'new','ai')} | sim old {agg(lv,'old','sim')} -> new {agg(lv,'new','sim')}")
        al=[r for r in rows]; print(f" all mapped words old {sum(r['old']['words'] for r in al if r['old'])} new {sum(r['new']['words'] for r in al if r['new'])}: AI old {agg(al,'old','ai')} -> new {agg(al,'new','ai')} | sim old {agg(al,'old','sim')} -> new {agg(al,'new','sim')}")
        res[work]={"rewritten":live,"rows":rows}
    json.dump(res,open(f"{sp}/persection2.json","w"),ensure_ascii=False,indent=1)
