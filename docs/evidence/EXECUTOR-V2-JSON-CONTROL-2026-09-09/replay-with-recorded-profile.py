"""Invoke the unchanged replay runner with the recorded legacy profile setting.

The stock CLI restores a settings prefix allowlist which omits PARTIAL_COMPLETION_ENABLED.
This verification harness configures that recorded boolean before calling the same runner.
No executable repository or server files are modified; network and provider fallback remain blocked.
"""
import argparse,asyncio,gzip,json,os,sys
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('recording',type=Path);p.add_argument('output',type=Path);args=p.parse_args()
args.job_id=14;args.worker_attempt=None;args.allow_request_changes=False
args.output=args.output.resolve();args.output.mkdir(parents=True,exist_ok=False)
raw=args.recording.read_bytes();data=json.loads(gzip.decompress(raw) if args.recording.suffix=='.gz' else raw)
snapshots=[e['payload'] for e in data['document_provenance'] if e['event_type']=='generation_replay_inputs' and e['payload']['job_id']==14];assert len(snapshots)==1
flag=snapshots[0]['profile']['settings']['PARTIAL_COMPLETION_ENABLED'];assert isinstance(flag,bool)
os.environ.clear();os.environ.update({'ENV_FILE':'/dev/null','ENVIRONMENT':'test','DEBUG':'true','DATABASE_URL':f"sqlite+aiosqlite:///{args.output / 'replay.db'}",'SECRET_KEY':'offline-replay-only-secret-never-an-account','JWT_SECRET':'offline-replay-only-secret-never-an-account'})
api=Path('/Users/maxmaxvel/AI TESI/.scratch/executor-v2-20260909/apps/api');sys.path.insert(0,str(api))
from app.core.config import settings
settings.PARTIAL_COMPLETION_ENABLED=flag
from scripts.replay_generation import run
report=asyncio.run(run(args));report['additional_recorded_setting']={'PARTIAL_COMPLETION_ENABLED':flag}
(args.output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False,indent=2))
raise SystemExit(0 if report['status']=='completed' else 2)
