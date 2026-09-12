# Крок 1 — здійсненність контракту кабінету й виконавця

09.09.2026. Перевірено [контракт Fable](../plans/CONTRACT-CABINET-EXECUTOR-2026-09-09.md),
код `main` (`cf863e9`) і метадані живої PostgreSQL через `BEGIN READ ONLY`.
Перевірена копія: `/Users/maxmaxvel/AI TESI/.scratch/rebuild-step0-20260909/main`.

**Напрямок відповідає погодженому плану. Контракт здійсненний без нових
таблиць і без обов’язкової міграції, якщо історію розділів зберігати
JSON-знімками.** Чинний код ще не виконує весь контракт.

**Наявна БД**

- `ai_generation_jobs.request_payload` — JSONB: вміщує stage, stop,
  лічильники, повідомлення, версію контракту й підсумок результату.
- `document_provenance.payload` — JSON: попередження, бібліографія,
  походження джерел, записи викликів і replay. `generation_warnings` —
  обчислюване поле API; JSON-колонки у `production_cases` немає.
- Статуси — `varchar(50)` без обмежувального CHECK/ENUM. Є токени/центи,
  шлях/SHA документа, порядок/текст/кількість слів секцій. Розмір береться
  зі сховища; оцінку сторінок можна додати в JSON-результат.
- Частковий UNIQUE `(document_id, job_type)` уже захищає активний запуск.
  Зберегти `job_type=full_document`; новий контракт позначати в JSON.

**Що неможливо без міграції**

Зберігати секції різних job **окремими рядками під тим самим document_id**:
у `document_sections` немає job_id, а UNIQUE `(document_id, section_index)`
забороняє два розділи №1. Потрібні nullable job_id/FK та окремі індекси
для нових секцій за job і старих рядків без job_id; нова таблиця не потрібна.

Рекомендоване уточнення §7 без міграції: перед новою спробою атомарно
зберігати повний незмінний знімок попередніх секцій і джерел у provenance
з previous_job_id та можливістю прочитати його через справу/журнал.
**Зараз цього немає:** `generate.py:564` видаляє попередні секції,
джерела, план і артефакти; generation_replacement зберігає лише метадані.

**Уточнення перед погодженням; усі вирішуються кодом без міграції**

1. Підтвердження завдання зараз пропускається за наявності методички
   (`task_contract.py:209`). §1.2 вимагає підтвердження і в цьому випадку.
2. Повторний запуск повертає **200 із наявним job**, а не 409
   (`generate.py:839`). Визначити 409 також для повтору того самого intent.
3. Нова спроба зараз потребує mode=new_version і підтвердження заміни;
   `/resume` переактивує старий job. Для v2 термінальний job незмінний,
   повтор створює новий. attempt_count — захоплення worker, не нові роботи.
4. Скасування зараз залишає документ failed; справа називає активний стан
   running, а не generating. Нові проєкції застосовувати лише до v2,
   без переписування старих станів. UI зараз поєднує WebSocket із GET
   і перекладає коди сам: це змінити відповідно до §8.
5. Вказати точні маршрути §7, усі з `/api/v1`: справи зареєстровані під
   **`/admin/production-cases`** (`main.py:217`), включно з detector-reports
   і release. До видачі DOCX доступний через **POST /admin/documents/{document_id}/download**
   із виробничим доступом. Звичайний export вимагає release.
   detector-reports завантажує файл; числові similarity/AI записує
   **POST /admin/production-cases/{id}/release-gates/{gate_key}/detector-result**.
6. Стандартні посилання зараз неперевірені. Формат БД достатній, але їхня
   перевірка/заміна до DOCX — реалізація кроку 4. Для completed потрібно
   зібрати весь результат §6 та ідентифікатор повного запису.
7. Окремий heartbeat/відкликання lease є; ≤60 с треба перевірити на v2.
   Під час недоступної БД неможливо гарантувати запис stop/cancelled у неї:
   UI показує недоступність, запис — після відновлення. Міграція цього не
   вирішує; локальне скасування не гарантує зупинки виклику у провайдера.

**Файли, які зачіпає контракт**

Шляхи відносні до перевіреної копії вище. Короткі назви в одному рядку
належать до тієї самої папки.

| Частина | Файли для зміни |
|---|---|
| Схеми | `apps/api/app/schemas/document.py`, `production.py`, `provenance.py` |
| API запуску/статусу/справи | `apps/api/app/api/v1/endpoints/generate.py`, `jobs.py`, `production_cases.py`; за розширенням читання — `documents.py` |
| Стани, підтвердження, повтор, попередження | `apps/api/app/services/task_contract.py`, `generation_worker.py`, `generation_recovery.py`, `generation_outcomes.py`, `production_case_service.py` |
| Підключення виконавця | `apps/api/app/services/background_jobs.py`; новий модуль v2 визначить специфікація кроку 2 |
| Усі посилання | `apps/api/app/services/citation_verifier.py`, `source_verification_stage.py`, `standard_references.py` |
| Типи/повідомлення UI | `apps/web/lib/api/admin.ts`; `apps/web/lib/generation-status.ts`, `production-status.ts` |
| Прогрес/нова спроба/список | `apps/web/components/GenerationProgress.tsx`; `apps/web/components/dashboard/TaskContractPanel.tsx`, `DocumentsList.tsx`; `apps/web/app/dashboard/documents/[id]/page.tsx` |
| Справи | `apps/web/app/admin/production-cases/page.tsx`, `apps/web/app/admin/production-cases/[id]/page.tsx`; менеджерські сторінки вже імпортують їх |
| Лише для секцій-рядків за job | `apps/api/app/models/document.py` і нова SQL-міграція в `apps/api/migrations/` |

Повторно використовуються, без обов’язкового переписування:
`apps/api/app/services/generation_operations.py`, `model_recording.py`,
`replay_snapshot.py`, `document_service.py`, `docx_export.py`, `storage_service.py`;
`apps/api/app/api/v1/endpoints/admin_documents.py` — внутрішнє завантаження.
Правила видачі та Compilatio зберігаються.

Створено лише цю записку. Код і контракт не змінювалися; генерації,
тестів старого виконавця, платних звернень, міграцій чи встановлень не було.
