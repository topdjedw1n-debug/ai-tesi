import json, sys, statistics
sys.path.insert(0, 'scan2')
from persection2 import sections
d = json.load(open('three/B-doc20.json'))
outline = [e['payload'] for e in d['events'] if e['event_type'] == 'executor_outline'][-1]['sections']
titles = [s['title'] for s in outline]
scopes = [e['payload'] for e in d['events'] if e['event_type'] == 'executor_scopes'][-1]['nodes']
chapters = [n['title'] for n in scopes if n.get('children')]
res = sections('scan6/B-cabinet.lines2.json', titles + chapters)
rows = []
print(f"{'#':>2} {'section':44s} {'words':>5} {'AI%':>6} {'sim%':>6}")
for i, t in enumerate(titles, 1):
    o = res.get(t)
    if not o: print(f"{i:>2} {t[:44]:44s}   -- not mapped"); continue
    rows.append({'index': i, 'title': t, 'words': o['words'], 'ai_pct': o['ai_pct'], 'sim_pct': o['sim_pct']})
    print(f"{i:>2} {t[:44]:44s} {o['words']:>5} {o['ai_pct']:>6} {o['sim_pct']:>6}")
for t in chapters + ['Bibliografia', 'Normativa e giurisprudenza']:
    o = res.get(t)
    if o and o["words"]: print(f"   {t[:44]:44s} {o['words']:>5} {o['ai_pct']:>6} {o['sim_pct']:>6}")
def agg(rs, key):
    w = sum(r['words'] for r in rs); return round(sum(r[key] * r['words'] / 100 for r in rs) / w * 100, 1) if w else None
body = [r for r in rows if r['index'] not in (1, len(titles))]
intro = [r for r in rows if r['index'] == 1]; concl = [r for r in rows if r['index'] == len(titles)]
print(f"\nbody ({len(body)} sections): AI {agg(body,'ai_pct')} % (median {statistics.median(r['ai_pct'] for r in body)}), sim {agg(body,'sim_pct')} %")
print(f"intro: AI {intro[0]['ai_pct']} sim {intro[0]['sim_pct']} | conclusions: AI {concl[0]['ai_pct']} sim {concl[0]['sim_pct']}")
allr = rows; print(f"all mapped: {sum(r['words'] for r in allr)} words, AI {agg(allr,'ai_pct')} %, sim {agg(allr,'sim_pct')} %")
cases = [r for r in body if any(k in r['title'].lower() for k in ('giurisprudenza', 'videosorveglianza', 'geolocalizzazione', 'monitoraggio', 'provvedimenti', 'linee guida'))]
systems = [r for r in body if r not in cases]
print(f"cases/acts ({len(cases)}): AI {agg(cases,'ai_pct')} | systems ({len(systems)}): AI {agg(systems,'ai_pct')}")
print("top AI:", sorted(((r['ai_pct'], r['index'], r['title'][:30]) for r in rows), reverse=True)[:6])
print("top sim:", sorted(((r['sim_pct'], r['index'], r['title'][:30]) for r in rows), reverse=True)[:6])
json.dump({'rows': rows, 'body_ai': agg(body,'ai_pct'), 'body_sim': agg(body,'sim_pct'), 'intro': intro[0], 'conclusions': concl[0]}, open('scan6/persection-cabinet.json', 'w'), ensure_ascii=False, indent=1)
