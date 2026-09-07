const q=require('./api-control.cjs');const fs=require('fs');const assert=require('assert/strict');
(async()=>{
 q.control({mode:'success',hold:'upload'});const offset=fs.readFileSync('provider-calls.jsonl','utf8').length;
 const id=await q.create('cancel during storage upload');const started=await q.start(id);assert.equal(started.status,200);
 let entry;const end=Date.now()+45000;
 while(Date.now()<end){entry=fs.readFileSync('provider-calls.jsonl','utf8').slice(offset).trim().split('\n').filter(Boolean).map(l=>JSON.parse(l)).find(r=>r.stage==='upload_entered');if(entry)break;await q.delay(300)}
 assert.ok(entry,'upload not reached');const cancelled=await q.api(`/generate/full-document/${id}/cancel`,'POST',{});assert.equal(cancelled.status,200,JSON.stringify(cancelled));
 const health=await fetch('http://localhost:8320/health',{signal:AbortSignal.timeout(2000)});assert.equal(health.status,200);
 await q.delay(4000);q.control({mode:'success',hold:null});await q.delay(4500);
 const doc={data:JSON.parse(q.sql(`select json_build_object('status',status,'docx_path',docx_path) from documents where id=${Number(id)}`))};assert.equal(doc.data.docx_path,null);assert.equal(doc.data.status,'failed');
 const terminal=await q.until(id,j=>j.status==='cancelled');
 const {execFileSync}=require('child_process');
 const objects=JSON.parse(execFileSync('docker',['exec','thesica-resilience-api-1','python','-c',`import json;from app.services.storage_service import StorageService;from app.core.config import settings;print(json.dumps([o.object_name for o in StorageService().client.list_objects(settings.MINIO_BUCKET,recursive=True) if o.object_name==${JSON.stringify(entry.object_name)}]))`],{encoding:'utf8'}));
 assert.deepEqual(objects,[]);fs.writeFileSync('cancel-upload.json',JSON.stringify({id,job:started.data.job_id,cancelled:cancelled.data,terminal,document_status:doc.data.status,docx_path:doc.data.docx_path,uploaded_object:entry.object_name,remaining_objects:objects,health:health.status},null,2));console.log('cancel during upload: passed');
})().catch(e=>{q.control({mode:'success',hold:null});console.error(e);process.exit(1)});
