import asyncio,datetime,gzip,json,sys
from sqlalchemy import text
from app.core import database
from app.services.generation_operations import journal_usage
async def main():
 out={'origin':'live-cabinet-document12-job14-executor-v2-61a4912','exported_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'revision':'61a4912f53a55850fcc2fa9666f785bbe9090757','document_id':12,'job_id':14}
 async with database.AsyncSessionLocal() as db:
  await db.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY'))
  for table,condition in [('documents','id=12'),('ai_generation_jobs','document_id=12'),('document_sections','document_id=12'),('document_sources','document_id=12'),('document_source_files','document_id=12'),('document_provenance','document_id=12'),('production_cases','document_id=12')]:
   rows=(await db.execute(text(f'SELECT row_to_json(t) FROM {table} t WHERE {condition} ORDER BY id'))).scalars().all()
   if table=='ai_generation_jobs':
    for row in rows:row.pop('lease_token',None);row.pop('lease_owner',None)
   out[table]=rows
  jobs=[j for j in out['ai_generation_jobs'] if j['id']==14];assert len(jobs)==1 and jobs[0]['request_payload']['executor_version']==2
  assert jobs[0]['status'] in ('completed','failed','cancelled'),'Not terminal yet'
  usage,unknown=await journal_usage(db,12,14)
  out['journal_usage']={'confirmed_tokens':usage.total_tokens,'confirmed_cost_cents':usage.cost_usd_cents(),'unknown_provider_attempts':unknown}
  await db.rollback()
 sys.stdout.buffer.write(gzip.compress(json.dumps(out,ensure_ascii=False,default=str).encode(),mtime=0))
asyncio.run(main())
