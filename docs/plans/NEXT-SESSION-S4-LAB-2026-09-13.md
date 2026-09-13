# Промпт для нової сесії Fable — лабораторія S4

13.09.2026. Фаундер: у Codex мало лімітів, крок 1 етапу якості виконує Fable у новій сесії Claude Code в папці проєкту. Нижче текст для вставки першим повідомленням.

---

Ти Fable, у цій сесії виконавець, не лише рецензент: Codex зараз без лімітів, тому лабораторію S4 будуєш ти. Прецедент є — правка бюджетів 3892cac 11.09 теж була твоя.

Спершу прочитай у такому порядку і лише це: docs/plans/CODEX-S4-LAB-2026-09-13.md (доручення; адресоване Codex, виконуєш ти), docs/plans/QUALITY-AI-ROUND1-2026-09-13.md (§3–4), docs/evidence/QUALITY-AI-2026-09-13/README.md і codex-astra/answer.md (поправки Astra до лабораторії), docs/plans/SPEC-EXECUTOR-V2-2026-09-09.md §5 (запис і відтворення). Старі плани — історія, не читай.

Рішення фаундера 13.09: «так» на лабораторію; дозволені витрати лише один живий smoke-розділ роботи A, разом не більше $0.50; Compilatio не робити; на сервер нічого не ставити; дослід на B (4 файли) — лише після окремого «так». Вичитку якості редактори зроблять пізніше.

Стан репозиторію: main = 1f2df27, сервер на 3892cac. У робочій копії лежать незакомічені документи (docs/AGENT_SYNC.md, docs/PRE-RUN-001-TASKS.md, docs/plans/*, docs/evidence/QUALITY-AI-2026-09-13, docs/evidence/EXECUTOR-V2-THREE-CONTROLS-2026-09-12/compilatio і README). Перший крок: закоміть їх на main одним комітом «docs: …» (лише docs/, код не чіпати; великі .json.gz і теки replay-job*/ у git не додавати, вони в .gitignore або поза git). Далі працюй у гілці fable/s4-lab.

Що будуєш: apps/api/scripts/s4_lab.py поруч зі штатним apps/api/scripts/replay_generation.py, за §2 доручення. Ключові місця коду: replay_generation.py (свіжа SQLite, знімок generation_replay_inputs, ReplayTape.from_events, блокування мережі), app/services/model_recording.py (ReplayTape, active_replay, replay_models), app/services/replay_dependencies.py (recorded_dependency, recorded_http), app/services/executor_v2/run.py (Context, prepare → S1–S3, execute → S4 write_sections → S5 → S6; Context.provider = AsyncAnthropic; ctx.model), executor_v2/sections.py (write_sections; текст інструкції S4 зараз inline у промпті, previous_summaries — останні 1 200 символів попередніх розділів), executor_v2/budgets.py (POLICY, model_call через recorded_provider_call, output_budget), executor_v2/references.py (S5, verify для нових [STD:…]), executor_v2/assemble.py (S6, огляд моделлю і DOCX). Виробничі таблиці тарифів app/services/cost_estimator.py і валідатор моделей app/schemas/document.py не чіпати: для моделей поза таблицями лабораторія має власну таблицю.

Єдина зміна виробничого коду: винести текст інструкції S4 у константу модуля sections.py без зміни поведінки; пакет executor_v2 має лишитися ≤1 500 рядків і без перемикачів (є тести-запобіжники).

Записи для доказу лежать локально поза git: docs/evidence/EXECUTOR-V2-THREE-CONTROLS-2026-09-12/A/document13-job16-recording.json.gz, B/document14-job17-recording.json.gz, C/document15-job18-recording.json.gz, а також docs/evidence/EXECUTOR-V2-LIVE-3892cac-2026-09-12/document12-job15-recording.json.gz. Очікувані SHA-256 DOCX у режимі exact: A 08e203b54283619dcb245e75a679844b3d83d4132187ae756b10d4d0c1cb426f, B 69c1bd760520ece7f226209edda4808c93f8865fba49b7541529fed243e77792, C d0bf1da2f6f6ee43d9c22f0498616ef1b4eba7214893d2dcf92ae3c01190b68b, job15 a4e217c052a13ddb117809cc897705fd31c738d23880006d23d2a6fc9fbe9fdd. Кожен запуск — у нову порожню теку (штатне правило replay).

Приймання (§4 доручення): 1) exact на job16/17/18 дає ті самі DOCX побайтово; 2) exact з підставленою іншою інструкцією зупиняється з поясненням, а не бере старий текст; 3) smoke: один найкоротший розділ A живо з виробничою інструкцією й моделлю, з cost-cap $0.50, далі S5–S6 до DOCX, усе записано; 4) повні сукупності тестів API і web зелені, у звіті лише повні числа; 5) окремим файлом проєкт переглянутої інструкції S4 за дев'ятьма правками з QUALITY-AI-ROUND1 §4 (виробничий текст не змінювати).

Звіт: docs/evidence/QUALITY-AI-2026-09-13/s4-lab/README.md (команди, SHA до/після, підсумок smoke з вартістю, повні числа тестів, посилання на файл варіанта інструкції), коміт у гілці. Потім звіт фаундеру простою мовою: що працює → що блокує → що потрібно → наступні кроки; наступний крок — його окреме «так» на дослід на B (4 файли ≈ $10 генерації + 4 перевірки Compilatio за кредити).

Не робити: повних генерацій, Compilatio, змін POLICY/переліку моделей/сервера/бази, нових гейтів або перемикачів, «покращень» replay поза потребою лабораторії. Якщо щось із доручення виявиться нездійсненним у коді, спершу поясни фаундеру, не обходь мовчки.

---
