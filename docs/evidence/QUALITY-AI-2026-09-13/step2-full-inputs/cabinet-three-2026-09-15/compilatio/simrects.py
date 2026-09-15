"""Similarity per section from the pastel line-height highlight rectangles of a Compilatio report."""
import json, re, sys
from collections import defaultdict
import pymupdf
sys.path.insert(0, 'scan2')
from persection2 import norm, strip_num, NUMERIC
CYAN=(0.0,0.75,1.0); BROWN=(0.63,0.43,0.42)
def pastel(fill):
    c=tuple(round(x,2) for x in fill)
    if c in (CYAN, BROWN) or c==(1.0,1.0,1.0): return False
    return min(c)>=0.7 and max(c)-min(c)>=0.08   # light, tinted (not grey)
def extract(path):
    doc=pymupdf.open(path)
    start=next(i for i in range(len(doc)) if "sezione 3/3" in doc[i].get_text("text"))
    records=[]
    for pno in range(start,len(doc)):
        page=doc[pno]; words=page.get_text("words"); lines=defaultdict(list)
        for w in words: lines[(w[5],w[6])].append(w)
        rects=[d["rect"] for d in page.get_drawings() if d.get("fill") is not None and 4<=d["rect"].height<=16 and d["rect"].width>=5 and pastel(d["fill"])]
        for key in sorted(lines, key=lambda k:(min(w[1] for w in lines[k]))):
            ws=sorted(lines[key], key=lambda w:w[0]); flags=[]
            for w in ws:
                cx=(w[0]+w[2])/2; cy=(w[1]+w[3])/2
                flags.append(1 if any(r.x0<=cx<=r.x1 and r.y0-1<=cy<=r.y1+1 for r in rects) else 0)
            records.append({"page":pno+1,"text":" ".join(w[4] for w in ws),"words":len(ws),"sim_flags":flags})
    return records
def per_section(records, titles):
    tset={norm(t):t for t in titles+["Bibliografia","Normativa e giurisprudenza","Indice"]}
    out={}; sec=None; i=0
    while i<len(records):
        matched=None
        for k in (1,2,3):
            if i+k>len(records): break
            joined=" ".join(x["text"] for x in records[i:i+k])
            if norm(strip_num(joined)) in tset: matched=(tset[norm(strip_num(joined))],k)
        if matched: sec=matched[0]; out.setdefault(sec,{"words":0,"sim":0}); i+=matched[1]; continue
        l=records[i]; i+=1
        if sec is None: continue
        if l["words"]<=2 and NUMERIC.match(l["text"].replace("‎","")): continue
        if "Punti di interesse" in l["text"]: continue
        out[sec]["words"]+=l["words"]; out[sec]["sim"]+=sum(l["sim_flags"])
    return out
if __name__=="__main__":
    recs=extract(sys.argv[1]); total=sum(r["words"] for r in recs); flagged=sum(sum(r["sim_flags"]) for r in recs)
    print("words", total, "similarity-highlighted", flagged, round(100*flagged/total,1), "%")
    d=json.load(open(sys.argv[2])); outline=[e['payload'] for e in d['events'] if e['event_type']=='executor_outline'][-1]['sections']
    titles=[s['title'] for s in outline]; chapters=[n['title'] for n in [e['payload'] for e in d['events'] if e['event_type']=='executor_scopes'][-1]['nodes'] if n.get('children')]
    ps=per_section(recs, titles+chapters); rows=[]
    for i,t in enumerate(titles,1):
        o=ps.get(t)
        if o and o["words"]: rows.append({"index":i,"title":t,"words":o["words"],"sim_pct":round(100*o["sim"]/o["words"],1)}); print(f"{i:>2} {t[:44]:44s} {o['words']:>5} sim {rows[-1]['sim_pct']:>5}")
    json.dump({"total_words":total,"flagged":flagged,"rows":rows}, open(sys.argv[3],"w"), ensure_ascii=False, indent=1)
    body=[r for r in rows if r["index"] not in (1,len(titles))]; w=sum(r["words"] for r in body)
    print("body sim", round(sum(r["sim_pct"]*r["words"] for r in body)/w,1), "| top:", sorted(((r["sim_pct"],r["index"]) for r in rows), reverse=True)[:6])
