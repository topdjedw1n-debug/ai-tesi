"""Isolated external-response fixture. Never imported by production code.

The real HTTP API, worker, leases, DB, checkpoints, gates, formatter and
MinIO run unchanged. Only external scholarly/LLM/grammar responses are
controlled. All fixture text/scores are synthetic, never academic evidence.
"""
import asyncio
import json
import os
from pathlib import Path
import re
import time

import httpx

from app.services.ai_pipeline.rag_retriever import SourceDoc
from app.services.ai_pipeline.source_pack import SourcePackBuilder, PackedSource, SourcePack
from app.services.ai_pipeline.generator import SectionGenerator
from app.services.ai_service import AIService
from app.services.citation_verifier import CitationVerifier, VerificationResult, VerificationStatus
from app.services.grammar_checker import GrammarChecker
from minio import Minio

ROOT = Path('/qa')

def control():
    return json.loads((ROOT / 'control.json').read_text())

def record(stage, **values):
    with (ROOT / 'provider-calls.jsonl').open('a') as f:
        f.write(json.dumps({'time':time.time(), 'pid':os.getpid(), 'stage':stage, **values})+'\n')

async def pause(stage):
    record(stage+'_entered')
    while control().get('hold') == stage:
        await asyncio.sleep(0.2)

async def build(self, **kwargs):
    await pause('sources')
    mode=control().get('mode')
    sources=[]
    count=1 if mode=='source_insufficient' else 24
    for n in range(count):
        surname='Rossi'+chr(65+n)
        s=SourceDoc(title=f'QA synthetic perinatal nursing study {n+1}',
                    authors=[f'Mario {surname}'],year=2023,
                    doi=f'10.9999/qa-resilience-{n+1}',
                    abstract='Synthetic fixture: 120 neonates received nursing care with systematic assessment.',
                    venue='QA fixture journal',provider='crossref',source_type='journal-article')
        sources.append(PackedSource(s,f'{surname}2023',0.9))
    return SourcePack(document_id=kwargs['document_id'], topic=kwargs['topic'],sources=sources,
                      underfilled=count<24,provider_errors=['crossref: synthetic timeout'] if mode=='source_outage' else [])

async def verify(self, source):
    if control().get('mode')=='source_outage':
        return VerificationResult(status=VerificationStatus.UNRESOLVABLE,reason='provider_errors')
    return VerificationResult(status=VerificationStatus.VERIFIED,title=source.title,
        authors=source.authors,year=source.year,doi=source.doi,provider='crossref',match_score=1.0,
        abstract='Synthetic fixture: 120 neonates received nursing care with systematic assessment.')

async def ai_response(self, provider, model, prompt):
    if self.usage_tracker is not None:
        self.usage_tracker.add(provider,model,100,100,purpose='synthetic_fixture')
    if prompt.startswith('Translate this academic thesis'):
        return {'topic':'perinatal nursing care','section_titles':[], 'tokens_used':200}
    if 'CLAIMS:\n' in prompt:
        claims=re.findall(r'^(\d+)\. \(source (S\d+):',prompt,re.M)
        record('claims', count=len(claims))
        return {'verdicts':[{'id':int(i),'source':s,'verdict':'supported','explanation':'Synthetic response for technical QA.'} for i,s in claims], 'tokens_used':200}
    if '"weakness"' in prompt:
        return {'severity':'minor','weakness':'Synthetic fixture; academic quality was not measured.','tokens_used':200}
    if '"score"' in prompt:
        return {'score':90,'remarks':[],'tokens_used':200}
    await pause('outline')
    if control().get('mode')=='malformed_outline':
        return {'content':'malformed synthetic provider response', 'tokens_used':200}
    record('outline')
    titles=['Introduzione','Assistenza infermieristica','Valutazione perinatale','Conclusioni']
    if control().get('mode')=='many_claims':titles=['Introduzione','Assistenza','Valutazione','Continuita','Supporto','Conclusioni']
    return {'sections':[{'title':t,'estimated_words':5400//len(titles),'description':'Technical QA fixture'} for t in titles], 'tokens_used':200}

async def writer(self, prompt, language='it', purpose='', preferred=None):
    match=re.search(r'Section Index: (\d+)',prompt)
    section=int(match.group(1)) if match else 0
    record('writer',section=section)
    await pause('writer')
    await pause('writer_'+str(section))
    mode=control().get('mode')
    if mode=='writer_timeout':
        raise httpx.ReadTimeout('Synthetic upstream timeout')
    if mode=='writer_429':
        raise httpx.HTTPStatusError('Synthetic upstream 429',request=httpx.Request('POST','https://fixture.invalid'),response=httpx.Response(429))
    if mode=='malformed_writer':
        return ''
    self._last_writer=preferred
    if self.usage_tracker is not None:
        self.usage_tracker.add(*(preferred or ('anthropic','claude-opus-4-8')),100,100,purpose='synthetic_writer')
    length=re.search(r'Section Length: write approximately (\d+) words',prompt)
    target=int(length.group(1)) if length else 1350
    keys=re.findall(r'\[(Rossi[A-X]2023)\]',prompt)
    keys=list(dict.fromkeys(keys))
    if not keys:
        raise RuntimeError('Fixture expected source markers in the real writer prompt')
    count=9 if mode=='many_claims' else 6
    offset=(max(section-1,0)*count)%len(keys)
    chosen=(keys+keys)[offset:offset+count] or keys[:count]
    paragraphs=[]
    for k in chosen:
        prefix=f'Nel campione di 120 neonati viene documentata la valutazione infermieristica [{k}]. '
        filler='Questo testo sintetico serve alla verifica tecnica della piattaforma e non costituisce una valutazione scientifica. '
        words=(prefix+(filler*(target//60+2))).split()[:target//len(chosen)]
        paragraphs.append(' '.join(words)+'.')
    return '\n\n'.join(paragraphs)

async def grammar(self, text, language='it'):
    return {'checked':True,'total_errors':0,'matches':[],'language':language,'error_types':{},'text_length':len(text),'qa_synthetic':True}

_http = httpx.AsyncHTTPTransport.handle_async_request
async def local_http(self, request):
    if request.url.host not in {'localhost','127.0.0.1','api','minio','redis','postgres'}:
        record('blocked_external_http', host=request.url.host)
        raise httpx.ConnectError('External HTTP disabled in isolated QA',request=request)
    return await _http(self, request)

_put_object = Minio.put_object

def upload(self, bucket_name, object_name, *args, **kwargs):
    record('upload_entered', object_name=object_name)
    while control().get('hold') == 'upload':
        time.sleep(0.1)
    result = _put_object(self, bucket_name, object_name, *args, **kwargs)
    record('upload_completed', object_name=object_name)
    return result

Minio.put_object=upload

SourcePackBuilder.build=build
CitationVerifier.verify_source=verify
AIService._call_ai_provider=ai_response
SectionGenerator._call_ai_with_fallback=writer
GrammarChecker.check_text=grammar
httpx.AsyncHTTPTransport.handle_async_request=local_http

from main import app  # noqa: E402,F401
