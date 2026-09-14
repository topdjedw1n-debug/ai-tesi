"""Compilatio underline extraction with per-colour flags (AI = cyan, similarity = brown)."""
import json, sys
from collections import Counter, defaultdict
import pymupdf
CYAN=(0.0,0.75,1.0); BROWN=(0.63,0.43,0.42)
def ck(fill): return tuple(round(c,2) for c in fill)
def extract(path):
    doc=pymupdf.open(path)
    start=next(i for i in range(len(doc)) if "sezione 3/3" in doc[i].get_text("text") or "section 3/3" in doc[i].get_text("text"))
    records=[]; colours=Counter(); total=0
    for pno in range(start,len(doc)):
        page=doc[pno]; words=page.get_text("words"); lines=defaultdict(list)
        for w in words: lines[(w[5],w[6])].append(w)
        uls=[d for d in page.get_drawings() if d.get("fill") is not None and d["rect"].height<=3 and d["rect"].width>=5]
        for key in lines:
            ws=sorted(lines[key], key=lambda w:w[0])
            x0,y0=min(w[0] for w in ws),min(w[1] for w in ws); x1,y1=max(w[2] for w in ws),max(w[3] for w in ws)
            flagged={}
            for d in uls:
                r=d["rect"]
                if y1-1.5<=r.y0<=y1+4.5 and r.x1>x0 and r.x0<x1:
                    c=ck(d["fill"])
                    for w in ws:
                        if w[2]>r.x0 and w[0]<r.x1: flagged[w[7]]=c
            for c in set(flagged.values()): colours[c]+=sum(1 for w in ws if flagged.get(w[7])==c)
            total+=len(ws)
            records.append({"page":pno+1,"block":key[0],"y":round(y0,1),"text":" ".join(w[4] for w in ws),"words":len(ws),
                "ai_flags":[1 if flagged.get(w[7])==CYAN else 0 for w in ws],"sim_flags":[1 if flagged.get(w[7])==BROWN else 0 for w in ws]})
    return {"file":path,"total_words":total,"shares":{str(k):round(v/total,4) for k,v in colours.items()},"lines":records}
out=extract(sys.argv[1]); json.dump(out,open(sys.argv[2],"w"),ensure_ascii=False,indent=1); print(out["total_words"],out["shares"])
