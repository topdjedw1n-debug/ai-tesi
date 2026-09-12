# Докази та межі дослідження

## Джерела

| ID | Джерело | Що використано |
|---|---|---|
| E01 | [AGENT_SYNC](../../AGENT_SYNC.md), [THESICA-PLAN](../../../THESICA-PLAN.md), [PRE-RUN](../../PRE-RUN-001-TASKS.md) | Внутрішній продукт; ролі; чинні вимоги приймання; M1/M2/M3; останній контроль №8 |
| E02 | [Контроль №8](../../evidence/WORK-008-CONTROL-2026-09-08.md) | Непогоджені ключі після остаточного відбору джерел; конфлікти/обмеження; зупинка до писаря й семантичного рецензента |
| E03 | [Відгук №7](../../evidence/WORK-007-MANAGER-FEEDBACK-2026-09-08.md), [M0-12/M1-Q01](../../evidence/M0-12-M1-Q01-2026-09-08.md), AGENT_SYNC | Технічний DOCX не означає академічне приймання; 3% similarity, 47% AI за зафіксованими даними; поліпшення верстки на offline-файлі |
| E04 | [M0-09](../../evidence/M0-09-2026-09-07.md), [M0-08 QA](../../evidence/m0-08-qa/README.md), [M0-09 QA](../../evidence/m0-09-qa/README.md) | Історичні ін'єкції збоїв і перевірки відновлення; ручні умови відтворення стендів; межі технічного доказу |
| E05 | [Fable/Grok](../stability-consultation-2026-09-08/README.md) та сирі відповіді поруч | Обидва рекомендували зберегти основу, узгодити план і докази та не перетворювати кожний збій на новий безмежний проєкт |
| E06 | Код `generation_worker.py`, `models/document.py` | Збережені jobs, leases, CAS, контроль stale owner, checkpoint, обмежені спроби й deletion outbox |
| E07 | Код `api/v1/endpoints/generate.py` | Блокування й повторний запит; `_invalidate_previous_generation_evidence` очищає попередній результат при новому запуску |
| E08 | Код `background_jobs.py`, `academic_review.py` | Межа між попереднім планом/остаточними джерелами; `conflicts` як блокувальна проблема; оркестрація в одній великій функції |
| E09 | Код `apps/web/lib/generation-status.ts` | Інструкції менеджеру через regex тексту помилки; загальний маршрут до відповідального за систему |
| E10 | Код `generation_contract.py`, `infra/deploy.sh` | Хеш входів не містить версії pipeline/prompt; у переглянутому deploy-шляху не встановлено перевірку сумісності продовження активної задачі |
| E11 | `tests/conftest.py`, `test_release_evidence_postgres.py`, `.github/workflows/ci.yml` | Типові локальні SQLite/профілі; PostgreSQL race test потребує спеціального URL; межі звичайної CI-перевірки |
| E12 | `apps/api/main.py`, `core/monitoring.py`, compose | Статичний health; HTTP/Sentry інструментування; залежності на одному хості; повнота зовнішнього моніторингу/позахостового відновлення не встановлена |
| E13 | [Свіжі цільові тести](focused-tests.txt) | 52 passed, 6 warnings; перевірені worker/cancel/single-owner/review-retry/storage та вузький academic pipeline |
| E14 | `ai_service.py` та оркестрація провайдерних викликів | Облік отриманої відповіді не доводить відсутність витрат після timeout; повну наскрізну ідемпотентність зовнішнього провайдера не встановлено |
| E15 | [Незалежні рев'ю](REVIEW_DECISIONS.md), [receipt](review-round-1/consultations.json) | Завершені відповіді Fable і Grok на спільному повному пакеті; рекомендації перевірені й прийняті частково |
| E16 | [Додаткова перевірка коду](review-round-1/code-fact-check.md) | Timeout планового рецензента → terminal quality failure; кабінетний retry → новий POST; штатний shutdown уже повертає спробу; один документ на справу; межа PostgreSQL fixtures |

## Версії

Прочитаний робочий каталог:
`/Users/maxmaxvel/AI TESI/.scratch/m0-12-m1-q01-20260908/worktree`.
HEAD `27f80da9101d4faa3c71122105ed6d387cd65655`; код `apps` без відмінностей від `067e90cab8f9dc8f5720cfc6ff3fb948be11b8f9`, який зазначений у останньому записі релізу. Корінь репозиторію має іншу старішу гілку та сторонні зміни, тому його робочий код не використаний як доказ deployed-реалізації.

[Маніфест](source-manifest.json) містить SHA-256 основних прочитаних файлів. Наприкінці дослідження хеші повторно зіставлені. Код не змінювали. Безпосередньо поточний стан production, його логи, облікові записи й рахунки у цьому дослідженні не перевіряли.

Орієнтири коду (рядки у зазначеному worktree):

- `generation_worker.py`: claim 171–306, source pack 544, sections 474, claim budget 583, artifact 699, shutdown 875, cleanup 913, cancel 1050, reschedule 1131.
- `generate.py`: invalidation 550–634, durable start/duplicate protection 720–920.
- `background_jobs.py`: outline 1664, final source preflight 1780–1907, academic outline 2015–2035. Головна `generate_full_document` містить приблизно 2639 рядків; сам розмір не доводить конкретної помилки.
- `academic_review.py`: структурні проблеми 43–67; перевірка до виклику моделі 314–315.
- `test_release_evidence_postgres.py`: спеціальний URL/skip 27–33.
- `main.py`: статичний `/health` 176–184.

## Свіжа перевірка

Виконано в ізольованому тестовому профілі, без завантаження production `.env`, із тестовими ключами та підмінами зовнішніх викликів:

```text
python -m pytest -o asyncio_mode=auto -p no:cacheprovider \
  tests/test_generation_worker.py \
  tests/test_generation_cancel.py \
  tests/test_generation_job_single_owner.py \
  tests/test_academic_quality_pipeline.py \
  tests/test_academic_review_retry.py \
  tests/test_storage_resilience_regression.py -q

52 passed, 6 warnings in 10.04s
```

Тести використовують наявний Python environment та SQLite. Вони не перевіряють весь production-стек або реальні блокування PostgreSQL. `test_academic_quality_pipeline` починається з узгоджених даних і не відтворює відбракування джерел після попереднього плану у №8. Показник coverage в сирому журналі стосується лише вибраних файлів тестів; це не оцінка повноти тестів усієї системи.

## Межі висновків

Це системний огляд із цільовою перевіркою ключових механізмів, а не повний аудит кожного рядка чи експериментальна перевірка всього реєстру ризиків. «Не встановлено» означає прогалину в наданому доказі, а не доведену відсутність механізму. Не встановлені частоти відмов, середні витрати на прийняту роботу, production SLO, допустимий час відновлення після втрати хоста або повний актуальний CI.

Нові платні генерації, Compilatio, зміни коду, даних, налаштувань чи деплой не виконувалися. Збережені лише матеріали дослідження й результати локальних тестів. Реєстр ризиків є проєктом перевірок, а не свідченням, що всі перелічені збої вже траплялися.
