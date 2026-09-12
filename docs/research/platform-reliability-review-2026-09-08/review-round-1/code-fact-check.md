# Додаткова перевірка зауважень у коді

Код 067e90c; читання, без реалізації.


## apps/api/app/services/generation_worker.py


```text
875: async def release_generation_lease_for_shutdown(
876:     db: AsyncSession,
877:     *,
878:     job_id: int,
879:     worker_id: str,
880:     lease_token: str,
881:     now: datetime | None = None,
882: ) -> bool:
883:     """Immediately requeue a gracefully cancelled attempt without consuming it."""
884:     released_at = now or utc_now()
885:     result = await db.execute(
886:         update(AIGenerationJob)
887:         .where(
888:             AIGenerationJob.id == job_id,
889:             AIGenerationJob.status == "running",
890:             AIGenerationJob.lease_owner == worker_id,
891:             AIGenerationJob.lease_token == lease_token,
892:         )
893:         .values(
894:             status="queued",
895:             available_at=released_at,
896:             heartbeat_at=released_at,
897:             lease_owner=None,
898:             lease_token=None,
899:             lease_expires_at=None,
900:             # A controlled deploy/restart is not a failed execution attempt.
901:             attempt_count=case(
902:                 (AIGenerationJob.attempt_count > 0, AIGenerationJob.attempt_count - 1),
903:                 else_=0,
904:             ),
905:         )
906:         .returning(AIGenerationJob.id)
907:     )
908:     released = result.scalar_one_or_none() is not None
909:     await db.commit()
910:     return released
911:
912:
913: async def enqueue_artifact_deletions(
```


## apps/api/tests/test_generation_worker.py


```text
292: async def test_graceful_shutdown_requeues_without_consuming_attempt(db_session):
293:     _, job = await _seed_job(db_session, email="worker-shutdown@example.com")
294:     claimed = await claim_next_generation_job(
295:         db_session, worker_id="worker-a", now=utc_now()
296:     )
297:     assert claimed is not None
298:
299:     released = await release_generation_lease_for_shutdown(
300:         db_session,
301:         job_id=job.id,
302:         worker_id="worker-a",
303:         lease_token=claimed.lease_token,
304:         now=utc_now(),
305:     )
306:     await db_session.refresh(job)
307:
308:     assert released is True
309:     assert job.status == "queued"
310:     assert job.lease_owner is None
311:     assert job.lease_expires_at is None
312:     assert job.attempt_count == 0
313:
314:
```


## apps/api/app/services/academic_review.py


```text
303:     if not method.get("retrieval_trace"):
304:         problems.append("Немає фактичного запису пошуку для методики огляду.")
305:     prompt, reviewed = review_prompt(
306:         document,
307:         pack,
308:         method,
309:         kind=kind,
310:         run_requirements=(getattr(job, "request_payload", None) or {}).get(
311:             "additional_requirements"
312:         ),
313:     )
314:     if problems:
315:         outcome = {**base, "status": "failed", "reason": " ".join(map(str, problems))}
316:     elif len(prompt) > REVIEW_MAX_CHARS or not reviewed.strip():
317:         outcome = {
318:             **base,
319:             "status": "unchecked",
320:             "reason": "Повний текст перевищує місткість перевірки або відсутній; скорочений текст не перевірявся.",
321:         }
322:     else:
323:         await append_review_event(
324:             db, document.id, event_type + "_started", {**base, "status": "pending"}
325:         )
326:         try:
327:             service = ai_service or AIService(
328:                 db, usage_tracker=usage_tracker, max_retries=0
329:             )
330:             # One configured model and no provider/application fallback.
331:             timeout = min(90, max(1, settings.GENERATION_JOB_LEASE_SECONDS - 15))
332:             response = await asyncio.wait_for(
333:                 service.call_with_fallback(
334:                     prompt,
335:                     purpose=event_type,
336:                     chain_override=settings.AI_FALLBACK_CHAIN_LIST[:1],
337:                 ),
338:                 timeout=timeout,
339:             )
340:             outcome = {
341:                 **base,
342:                 **validate_review(
343:                     response, reviewed, len(document.outline["sections"]), keys
344:                 ),
345:             }
346:         except Exception as error:
347:             outcome = {
348:                 **base,
349:                 "status": "unchecked",
350:                 "reason": f"Академічна перевірка не завершена ({type(error).__name__}).",
351:             }
352:     await append_review_event(db, document.id, event_type, outcome)
353:     return outcome
```


## apps/api/app/services/background_jobs.py


```text
2001:                 academic_job = await db.get(AIGenerationJob, job_id) if job_id else None
2002:                 if fenced_execution and not durable_completed_indices:
2003:                     assert (
2004:                         job_id is not None
2005:                         and lease_owner is not None
2006:                         and lease_token is not None
2007:                     )
2008:                     try:
2009:                         async with hold_generation_job_lease(
2010:                             job_id=job_id,
2011:                             worker_id=lease_owner,
2012:                             lease_token=lease_token,
2013:                             document_id=document_id,
2014:                         ):
2015:                             outline_review = await run_academic_review(
2016:                                 db,
2017:                                 document,
2018:                                 academic_job,
2019:                                 source_pack,
2020:                                 kind="outline",
2021:                                 usage_tracker=usage,
2022:                             )
2023:                         if outline_review["status"] != "passed":
2024:                             await update_generation_document(
2025:                                 db,
2026:                                 job_id=job_id,
2027:                                 worker_id=lease_owner,
2028:                                 lease_token=lease_token,
2029:                                 document_id=document_id,
2030:                                 values={"status": "failed_quality"},
2031:                             )
2032:                             raise QualityThresholdNotMetError(
2033:                                 detail=outline_review.get("reason")
2034:                                 or "Академічний план або покриття джерелами не пройшли перевірку. Перегляньте зауваження до плану."
2035:                             )
2036:                     finally:
2037:                         await write_job_usage(db)
2038:                 if expected_source_pack_sha:
2039:                     method_events = (
2040:                         (
```


```text
3958:                 logger.warning("Stopped stale generation executor for job %s", job_id)
3959:                 raise
3960:             except Exception as error:
3961:                 await db.rollback()
3962:                 terminal = isinstance(
3963:                     error, CitationIntegrityError | QualityThresholdNotMetError
3964:                 ) or is_permanent_provider_error(error)
3965:                 decision = await reschedule_or_fail_generation_job(
3966:                     db,
3967:                     job_id=job_id,
```


## apps/web/components/dashboard/TaskContractPanel.tsx


```text
192:   const handleConfirmAndStart = async () => {
193:     if (!contract || !acknowledged || isStarting || (retry && !causeResolved)) return
194:     setIsStarting(true)
195:     let confirmed = contract.confirmed
196:     try {
197:       if (!confirmed) {
198:         await apiClient.post(
199:           API_ENDPOINTS.DOCUMENTS.CONFIRM_TASK_CONTRACT(documentId)
200:         )
201:         confirmed = true
202:         setContract((current) =>
203:           current ? { ...current, confirmed: true } : current
204:         )
205:       }
206:       await apiClient.post(API_ENDPOINTS.GENERATE.FULL, {
207:         document_id: documentId,
208:       })
209:       toast.success('Умови підтверджено — написання почалось')
210:       onGenerationStarted?.()
211:     } catch (error: any) {
```


## apps/api/app/models/document.py


```text
442: class ProductionCase(Base):
443:     """Internal production case wrapping a document for Phase 2 operations."""
444:
445:     __tablename__ = "production_cases"
446:     __table_args__ = (
447:         Index("ix_production_cases_document_id", "document_id"),
448:         Index("ix_production_cases_client_user_id", "client_user_id"),
449:         Index("ix_production_cases_manager_id", "manager_id"),
450:         Index("ix_production_cases_editor_id", "editor_id"),
451:         Index("ix_production_cases_release_status", "release_status"),
452:         UniqueConstraint("document_id", name="uq_production_cases_document_id"),
453:     )
454:
455:     id = Column(Integer, primary_key=True, index=True)
456:     document_id = Column(
457:         Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
458:     )
459:     client_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
460:     manager_id = Column(Integer, ForeignKey("users.id"), nullable=True)
461:     editor_id = Column(Integer, ForeignKey("users.id"), nullable=True)
462:
```


## apps/api/tests/conftest.py


```text
100:     so all test files used to share ./test.db — any row left behind by one file
101:     (e.g. users created through the app's get_db without a drop_all teardown)
102:     broke unrelated files later in the run. A per-module engine on a fresh tmp
103:     file makes each file start exactly like a standalone run.
104:
105:     NullPool: pooled aiosqlite connections must not be reused across the
106:     function-scoped event loops pytest-asyncio creates per test.
107:     """
108:     db_path = tmp_path_factory.mktemp("db") / "test.db"
109:     engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", poolclass=NullPool)
110:     _database._engine = engine
111:     # Every consumer (tests and app code alike) holds the same sessionmaker
112:     # object created via the module __getattr__ — rebind it to the new engine.
```


## apps/api/tests/test_release_evidence_postgres.py


```text
25:
26: @pytest.fixture
27: async def postgres():
28:     url = os.environ.get("M0_03_TEST_DATABASE_URL")
29:     if not url:
30:         pytest.skip(
31:             "An isolated PostgreSQL database is required for the row-lock races"
32:         )
33:     schema = f"m003_{uuid4().hex}"
34:     bootstrap = create_async_engine(url)
35:     async with bootstrap.begin() as connection:
```


## apps/api/app/services/ai_service.py


```text
551:             nonlocal total_tokens
552:             import openai
553:
554:             if not settings.OPENAI_API_KEY:
555:                 raise AIProviderError("OpenAI API key not configured")
556:
557:             client = openai.AsyncOpenAI(
558:                 api_key=settings.OPENAI_API_KEY, timeout=600.0, max_retries=0
559:             )
560:
```


```text
619:             import anthropic
620:
621:             if not settings.ANTHROPIC_API_KEY:
622:                 raise AIProviderError("Anthropic API key not configured")
623:
624:             client = anthropic.AsyncAnthropic(
625:                 api_key=settings.ANTHROPIC_API_KEY, timeout=600.0, max_retries=0
626:             )
627:
```
