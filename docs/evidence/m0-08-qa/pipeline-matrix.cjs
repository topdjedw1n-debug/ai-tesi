const q=require('./api-control.cjs');const fs=require('fs');const assert=require('assert/strict');const {execFileSync}=require('child_process');
const results=[];const mode=process.argv[2]||'providers';
const log=(name,evidence)=>{results.push({name,status:'passed',evidence});fs.writeFileSync('matrix-'+mode+'.json',JSON.stringify(results,null,2));console.log(name+': passed '+JSON.stringify(evidence));};
const docker=(...args)=>execFileSync('docker',args,{encoding:'utf8'}).trim();
const snapshot=id=>JSON.parse(q.sql(`select json_build_object('id',d.id,'status',d.status,'has_docx',d.docx_path is not null,'sections',(select count(*) from document_sections s where s.document_id=d.id),'words',(select sum(word_count) from document_sections s where s.document_id=d.id)) from documents d where id=${Number(id)}`));
const sections=id=>q.sql(`select coalesce(json_agg(json_build_object('id',id,'index',section_index,'hash',md5(content)) order by section_index)::text,'[]') from document_sections where document_id=${Number(id)} and status='completed'`);
async function launch(name,control){q.control(control);const id=await q.create(name);const r=await q.start(id);assert.equal(r.status,200,JSON.stringify(r));return {id,job:r.data.job_id};}
async function terminal(id){return q.until(id,j=>['completed','failed','cancelled'].includes(j.status),90000);}
(async()=>{
 if(mode==='providers'){
  for(const name of ['source_insufficient','source_outage','writer_timeout','writer_429','malformed_outline','malformed_writer']){
   const {id,job}=await launch(name,{mode:name,hold:null});const state=await terminal(id);assert.equal(state.status,'failed');assert.ok(state.attempt_count<=3);assert.equal(snapshot(id).has_docx,false);log(name,{id,job,state,document:snapshot(id)});
  }
 }
 if(mode==='recovery'){
  for(const action of ['restart','kill']){
   const {id,job}=await launch(action+' recovery',{mode:'success',hold:'writer_2'});
   const end=Date.now()+20000;while(Date.now()<end&&JSON.parse(sections(id)).length<1)await q.delay(300);
   const before=JSON.parse(sections(id));assert.equal(before.length,1);assert.equal((await q.api('/documents/'+id)).data.status,'generating');
   if(action==='restart')docker('restart','-t','10','thesica-resilience-api-1');
   else{docker('kill','--signal=KILL','thesica-resilience-api-1');docker('start','thesica-resilience-api-1');}
   q.control({mode:'success',hold:null});let state=await terminal(id);assert.equal(state.status,'completed',JSON.stringify(state));
   const after=JSON.parse(sections(id));assert.equal(after.length,4);assert.deepEqual(after[0],before[0]);assert.equal(new Set(after.map(s=>s.index)).size,4);assert.equal(state.job_id,job);
   log(action+'_resume_without_rewriting',{id,job,state,firstSection:before[0],document:snapshot(id)});
  }
 }
 if(mode==='redis'){
  const {id,job}=await launch('redis interruption',{mode:'success',hold:'writer_2'});
  const end=Date.now()+20000;while(Date.now()<end&&JSON.parse(sections(id)).length<1)await q.delay(300);
  const before=JSON.parse(sections(id));assert.equal(before.length,1);docker('stop','-t','2','thesica-resilience-redis-1');
  q.control({mode:'success',hold:null});let state;
  try{state=await terminal(id);assert.equal(state.status,'completed',JSON.stringify(state));}finally{docker('start','thesica-resilience-redis-1')}
  assert.deepEqual(JSON.parse(sections(id))[0],before[0]);log('redis_unavailable_uses_postgres',{id,job,state,document:snapshot(id)});
 }
 if(mode==='database'){
  const {id,job}=await launch('database interruption',{mode:'success',hold:'writer_2'});
  const end=Date.now()+20000;while(Date.now()<end&&JSON.parse(sections(id)).length<1)await q.delay(300);
  const before=JSON.parse(sections(id));assert.equal(before.length,1);docker('stop','-t','2','thesica-resilience-postgres-1');
  await q.delay(6500);docker('start','thesica-resilience-postgres-1');q.control({mode:'success',hold:null});const state=await terminal(id);
  assert.equal(state.status,'completed',JSON.stringify(state));assert.deepEqual(JSON.parse(sections(id))[0],before[0]);log('database_restart_resume',{id,job,state,document:snapshot(id)});
 }
 if(mode==='storage'){
  const {id,job}=await launch('storage interruption',{mode:'success',hold:'writer_4'});
  const end=Date.now()+20000;while(Date.now()<end&&JSON.parse(sections(id)).length<3)await q.delay(300);
  assert.equal(JSON.parse(sections(id)).length,3);docker('stop','-t','2','thesica-resilience-minio-1');q.control({mode:'success',hold:null});await q.delay(1200);
  const started=Date.now();let health;try{const r=await fetch('http://localhost:8320/health',{signal:AbortSignal.timeout(3000)});health={status:r.status,ms:Date.now()-started};}catch(e){health={error:e.name,ms:Date.now()-started}}
  fs.writeFileSync('storage-health.json',JSON.stringify({id,job,health,document:snapshot(id)},null,2));console.log('storage interruption health '+JSON.stringify(health));
  docker('start','thesica-resilience-minio-1');const state=await terminal(id);log('storage_recovery',{id,job,health,state,document:snapshot(id)});
 }
})().catch(e=>{fs.writeFileSync('matrix-'+mode+'-failure.txt',String(e.stack));console.error(e);process.exit(1)});
