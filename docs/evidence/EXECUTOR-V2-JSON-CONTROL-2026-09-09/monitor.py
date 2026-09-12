import asyncio,datetime,json
from sqlalchemy import select,func
from app.core import database
from app.models.document import Document,AIGenerationJob,DocumentProvenance,DocumentSection
from app.services.generation_operations import journal_usage
async def main():
 async with database.AsyncSessionLocal() as db:
  d=await db.get(Document,12)
  jobs=(await db.scalars(select(AIGenerationJob).where(AIGenerationJob.document_id==12).order_by(AIGenerationJob.id))).all()
  out={'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'document_status':d.status,'docx_path':d.docx_path,'docx_sha256':d.docx_sha256,'jobs':[]}
  for j in jobs:
   usage,unknown=await journal_usage(db,12,j.id)
   out['jobs'].append({'id':j.id,'status':j.status,'progress':j.progress,'model':j.ai_model,'executor_version':(j.request_payload or {}).get('executor_version'),'execution':(j.request_payload or {}).get('execution'),'started_at':str(j.started_at),'completed_at':str(j.completed_at),'confirmed_cost_cents':usage.cost_usd_cents(),'confirmed_tokens':usage.total_tokens,'unknown_provider_attempts':unknown,'error':j.error_message})
  out['events']={k:v for k,v in (await db.execute(select(DocumentProvenance.event_type,func.count()).where(DocumentProvenance.document_id==12).group_by(DocumentProvenance.event_type))).all()}
  out['sections']=[{'index':s.section_index,'title':s.title,'status':s.status,'words':s.word_count} for s in (await db.scalars(select(DocumentSection).where(DocumentSection.document_id==12).order_by(DocumentSection.section_index))).all()]
  print(json.dumps(out,ensure_ascii=False,default=str,indent=2))
asyncio.run(main())
