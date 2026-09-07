const fs=require('fs');const path=require('path');const {execFileSync}=require('child_process');
const token=fs.readFileSync(path.join(__dirname,'qa-token'),'utf8').trim();
async function api(url,method='GET',data){
 const r=await fetch('http://localhost:8330/api/v1'+url,{method,headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},body:data?JSON.stringify(data):undefined});
 const body=await r.text();let result;try{result=JSON.parse(body)}catch{result=body}
 return {status:r.status,data:result};
}
const delay=ms=>new Promise(r=>setTimeout(r,ms));
function control(values){fs.writeFileSync(path.join(__dirname,'control.json'),JSON.stringify(values))}
function sql(query){return execFileSync('docker',['exec','thesica-completion-postgres-1','psql','-U','resilience','-d','resilience','-At','-c',query],{encoding:'utf8'}).trim()}
async function create(name,overrides={}){
 let r=await api('/documents/','POST',{title:'QA '+name,topic:'QA assistenza infermieristica perinatale '+name,target_pages:18,language:'it',work_type:'tesi_triennale',citation_style:'apa',additional_requirements:'Synthetic technical QA; no primary data.',...overrides});
 if(r.status!==200)throw new Error('create '+JSON.stringify(r));
 return r.data.id;
}
async function start(id){let c=await api(`/documents/${id}/task-contract/confirm`,'POST',{});if(c.status!==200)throw new Error('confirm '+JSON.stringify(c));return api('/generate/full-document','POST',{document_id:id});}
async function until(id,predicate,timeout=60000){
 const end=Date.now()+timeout;let r;
 while(Date.now()<end){try{r=await api(`/jobs/document/${id}/status`);if(predicate(r.data))return r.data;}catch{}await delay(500);}
 throw new Error('wait '+id+' last='+JSON.stringify(r));
}
module.exports={api,delay,control,sql,create,start,until};
