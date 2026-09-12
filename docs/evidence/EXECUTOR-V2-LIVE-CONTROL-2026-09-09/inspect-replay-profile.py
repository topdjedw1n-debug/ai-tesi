import os,json,gzip,sys
from pathlib import Path
from types import SimpleNamespace
out=Path('/Users/maxmaxvel/AI TESI/docs/evidence/EXECUTOR-V2-LIVE-CONTROL-2026-09-09')
data=json.loads(gzip.decompress((out/'document12-job13-recording.json.gz').read_bytes()));snap=next(e['payload'] for e in data['document_provenance'] if e['event_type']=='generation_replay_inputs')
os.environ.clear();os.environ.update({'ENV_FILE':'/dev/null','ENVIRONMENT':'test','DEBUG':'true','DATABASE_URL':'sqlite+aiosqlite:///:memory:','SECRET_KEY':'offline-diagnostic-only-secret-not-an-account','JWT_SECRET':'offline-diagnostic-only-secret-not-an-account'})
sys.path.insert(0,'/Users/maxmaxvel/AI TESI/.scratch/executor-v2-20260909/apps/api')
from app.core.config import settings
from app.services.replay_snapshot import REPLAY_SETTING_NAMES
from app.services.generation_profile import generation_profile
for k,v in snap['replay_settings'].items():
 if k in REPLAY_SETTING_NAMES:setattr(settings,k,v)
for k,present in snap['provider_presence'].items():
 if k in type(settings).model_fields and (k.endswith('_API_KEY') or k=='COPYSCAPE_USERNAME'):setattr(settings,k,'offline-placeholder' if present else None)
settings.UNLIMITED_GENERATION_USER_IDS=[snap['job']['user_id']] if snap['profile'].get('unlimited_claim_checks') else []
actual=generation_profile(SimpleNamespace(**snap['document']),snap['job']['user_id'])
def diff(a,b,p=''):
 if isinstance(a,dict) and isinstance(b,dict):return [x for k in a.keys()|b.keys() for x in diff(a.get(k),b.get(k),p+'.'+k)]
 return [] if a==b else [{'field':p.lstrip('.'),'live':a,'replay':b}]
d=diff(snap['profile'],actual);(out/'replay-profile-difference.json').write_text(json.dumps(d,indent=2));print(json.dumps(d,indent=2))
