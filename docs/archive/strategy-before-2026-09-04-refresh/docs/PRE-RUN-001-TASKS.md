# PRE-RUN-001 — покроковий таск до першого пілота

**Дата:** 2026-08-24
**Джерело:** аудит 6 агентів по HEAD `8cf379d` (кожна підсистема протрасована по коду, read-only).
**Підпорядкування:** виконує чергу [AGENT_SYNC.md](./AGENT_SYNC.md) (§7, уточнення 24.08) і lock §13. Якщо розходиться з AGENT_SYNC — перемагає AGENT_SYNC.
**Ролі:** Codex — виконання кодових блоків 1–4; Claude — рев'ю планів і верифікація; фаундер — блок 0, блок 5 (сервер), «так» на платні блоки 6–7.

**Вердикт аудиту одним рядком:** ядро (preflight, strict-цитати, fail-closed release, resume, облік €) інженерно готове і зроблене добре, але *вимкнене або недоступне з UI*; до RUN-001 треба: зібрати релізний профіль (Блок 1), закрити продуктові баги (Блок 2), доробити 3 екрани (Блок 3), залатати деплой-процедуру (Блок 4), задеплоїти і перевірити живі змінні (Блок 5), зняти короткий Compilatio-замір (Блок 6) — і лише тоді RUN-001 (Блок 7).

Пріоритети: **P0** — блокер RUN-001; **P1** — треба, але не блокує; **P2** — після пілота.

---

## Хотфікс 03.09 — створення роботи на проді (P0, виконується першим, поза чергою блоків)

**Дата:** 2026-09-03. **Симптом:** менеджерка тисне «Згенерувати роботу» → `Failed to fetch`. У базі проду 0 робіт; у логах API за 12 днів жоден `POST /api/v1/documents` не дійшов до хендлера — лише 307. Через сайт на цьому проді робота ще ніколи не створювалась. Файл менеджерки ні до чого.

**Причина (підтверджено на проді 03.09):** форма б'є в `/api/v1/documents` (без слеша), роутер оголошений як `@router.post("/")` → Starlette відповідає 307 на `http://app.thesica.co/api/v1/documents/`, бо uvicorn 0.24 довіряє `X-Forwarded-Proto` лише з 127.0.0.1, а Caddy приходить з 172.18.0.1 (шлюз docker-мережі). CSP сайту `connect-src 'self' https://app.thesica.co` блокує http-стрибок → `TypeError: Failed to fetch`. Локально непомітно (все по http). Той самий корінь: список робіт (`DOCUMENTS.LIST`) не вантажиться; усі менеджери для API = одна IP `172.18.0.1` → спільний lockout після 5 невдалих паролів (`RATE_LIMIT_AUTH_LOCKOUT_THRESHOLD=5`, зараз ніхто не заблокований).

**Докази:** `curl -sD - -o /dev/null -X POST -H 'Authorization: Bearer x' https://app.thesica.co/api/v1/documents` → `HTTP/2 307`, `location: http://app.thesica.co/api/v1/documents/`. У браузері на сайті: `fetch('/api/v1/documents')` → `Failed to fetch` + консоль «Connecting to 'http://…' violates connect-src»; `fetch('/api/v1/documents/')` → 401 (доходить).

### H.1. Код — локально, один коміт лише з переліченими файлами (консолідація доків у робочому дереві ще не закомічена → `git add <файли>`, не `-A`)

| # | Що | Де | Перевірка |
|---|---|---|---|
| H.1.1 | `DOCUMENTS.CREATE` і `DOCUMENTS.LIST` → `'/api/v1/documents/'` — форма й список більше не залежать від редиректу | `apps/web/lib/api.ts:322-323` | оновити асерти: `lib/__tests__/api.test.ts:43-44`, `__tests__/components/dashboard/CreateDocumentForm.test.tsx:34,100`, `__tests__/components/dashboard/DocumentsList.test.tsx:18,217`, `__tests__/e2e/document-creation-flow.test.tsx:27`; `npm test` зелений |
| H.1.2 | uvicorn довіряє проксі: `CMD ["uvicorn","main:app","--host","0.0.0.0","--port","8000","--proxy-headers","--forwarded-allow-ips","*"]` — будь-який редирект лишається https, API бачить реальні IP (lockout/rate-limit знову per-user) | `apps/api/Dockerfile:43` | dev-compose збирає той самий Dockerfile без override `command`: `docker compose -f infra/docker/docker-compose.yml build api && up -d api`; `curl -sD - -o /dev/null -X POST -H 'Authorization: Bearer x' -H 'X-Forwarded-Proto: https' http://localhost:8000/api/v1/documents` → `location: https://localhost:8000/api/v1/documents/` |
| H.1.3 | Порти лише на localhost — **обов'язково разом із H.1.2**: `*` при відкритому :8000 дозволяє підробити `X-Forwarded-For` з інтернету (сканери зараз б'ють у :8000 напряму ~700 раз/добу, ufw Docker не тримає). Закриває 4.7 | `infra/docker/docker-compose.prod.yml:132` → `"127.0.0.1:8000:8000"`, `:164` → `"127.0.0.1:3000:3000"` | після деплою `ss -ltnp \| grep -E ':(8000\|3000) '` — тільки `127.0.0.1`; Caddy (`reverse_proxy 127.0.0.1:…`) і healthcheck deploy.sh (`127.0.0.1:8000/health`) не зачеплені |
| H.1.4 | Canary відтворює реальний запит | `infra/deploy.sh`, крок 6/6 | (a) `POST /api/v1/documents/` з `Authorization: Bearer x` → **401** (не 307, не 403 — без bearer CSRF дає 403); (b) `POST /api/v1/documents` без слеша → 307 і `location:` починається з `https://app.thesica.co/` |
| H.1.5 (опційно; рекомендовано в той самий деплой) | CSP пускає фірмові шрифти: зараз Literata / Source Sans 3 / JetBrains Mono заблоковані → менеджери бачать системні шрифти; DESIGN.md:40 прописує саме Google Fonts | `apps/web/next.config.js:25` `style-src` + `https://fonts.googleapis.com`; `:27` `font-src` + `https://fonts.gstatic.com` | у браузері на проді немає CSP-помилки про fonts.googleapis; `getComputedStyle(document.querySelector('h1')).fontFamily` містить `Literata` |

**Не робимо:** не вимикаємо `redirect_slashes`, не переписуємо роутер, не чіпаємо Caddyfile, не змінюємо генерацію/профіль (§13), не деплоїмо разом з блоками 1–4.

### H.2. Рев'ю (Claude)

Diff проти таблиці H.1; `npm test` (web), `pytest` (api — зміни його не зачіпають, ганяємо як регрес). Dockerfile/compose тестами не покриті — доказ = H.1.2 локально + canary H.1.4.

### H.3. Деплой — тільки після «так» фаундера

1. Копія коду на сервері перед rsync (як 21.08): `ssh thesica 'tar czf /opt/thesica/backups/pre-code-$(date +%Y%m%d-%H%M%S).tar.gz -C /opt/thesica apps infra'`.
2. Канонічна доставка (закриває 4.6; dry-run 03.09: сервер = локальне дерево, відрізняються лише кеші/логи/`.env.local`):
   `rsync -rlc --exclude='.env*' --exclude='node_modules' --exclude='.next' --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' --exclude='venv' --exclude='.venv' --exclude='qa_venv' --exclude='.ruff_cache' --exclude='.pytest_cache' --exclude='.mypy_cache' --exclude='.coverage' --exclude='htmlcov' --exclude='logs' apps infra thesica:/opt/thesica/`
   Без `--delete`. `.env*` обов'язково: локальний `apps/web/.env.local` і `infra/docker/.env` з `ENVIRONMENT=development` не мають потрапити на прод.
3. `ssh thesica 'bash /opt/thesica/infra/deploy.sh'` — бекап бази → rollback-теги → міграції 024–027 (ідемпотентні, повтор безпечний) → build → up → canary (вже з H.1.4).
4. Відкат, якщо canary впав: команди, які друкує deploy.sh (`rollback-<STAMP>` теги); нові порти в compose сумісні зі старими образами, базу не чіпати.

### H.4. Верифікація на проді (Claude, без логіна менеджера)

- `curl -sD - -o /dev/null -X POST -H 'Authorization: Bearer x' https://app.thesica.co/api/v1/documents` → `location: https://…`; те саме зі слешем → 401.
- У браузері на `https://app.thesica.co`: `fetch('/api/v1/documents')` → 401 (редирект пройшов по https), консоль без CSP-помилок.
- `ss -ltnp` — 8000/3000 лише на 127.0.0.1; у `docker logs ai-thesis-api` нові запити з реальних IP, не `172.18.0.1`.
- Менеджерка відправляє **ту саму** заявку (Document 1.docx міняти не треба). Увага: успішна відправка одразу запускає реальну генерацію — це вже витрати за прогін.

### H.5. DoD

Заявка менеджерки створена і видна в списку робіт; у логах немає 307 на створення; canary зелений; 8000/3000 закриті ззовні; (опц.) на проді шрифти Scholarly Press.

---

## Хотфікс 03.09 №2 — генерація на проді падає до першого запиту в модель (P0, після №1)

**Дата:** 2026-09-03, ~16:25. **Контекст:** хотфікс №1 задеплоєно (f412e91) і верифіковано; менеджерка створила роботу (doc 1, user 1): create → upload методички → `POST /generate/full-document` = 200. Генерація впала за 2 хв зі статусом `failed` («Не пройшла перевірку»), job 1 `attempt 3/3`, **cost 0 ¢, жодного успішного виклику моделі** — грошей не витрачено.

**Причина (підтверджено в контейнері):** `apps/api/requirements.txt` пінить `anthropic==0.7.8` (листопад 2023, без Messages API) і `openai==1.3.7`; образ збирається з нього (`Dockerfile:21-25`). У локальному venv, проти якого проходять 1015 тестів і всі прогони doc 1→9, стоять `anthropic 0.76.0`, `openai 2.15.0`, `anyio 4.12.1` — це всі три розбіжності між пінами і venv. У контейнері `AsyncAnthropic(...)` не має `.messages` → `AttributeError` у `ai_service.py:568` на кожному виклику (pack_translation, outline; 4 ретраї × circuit breaker). OpenAI-шлях у тому ж образі не приймає `max_completion_tokens` (gpt-5-гілка `ai_service.py:515-519`). CI ставить залежності з `requirements.txt`, але тести мокають SDK — тому зелені. Через сайт на проді генерація ще ніколи не запускалась, тож дрейф нікому не показувався.

### H2.1. Код — локально, один коміт

| # | Що | Де | Перевірка |
|---|---|---|---|
| H2.1.1 | Піни: `anthropic==0.76.0`, `openai==2.15.0`. **`anyio` лишається 3.7.1** — `fastapi==0.104.1` декларує `anyio<4`, з 4.12.1 образ не збирається (локальний venv у цьому місці неконсистентний: anyio 4 туди заїхав повз обмеження fastapi); anthropic 0.76 і openai 2.15 приймають anyio ≥3.5 (уточнення 03.09 після виконання) | `apps/api/requirements.txt:5`, `:80`, рядок `anyio` | `docker build -t thesica-api-local apps/api` проходить; `docker run --rm thesica-api-local python -c "from anthropic import AsyncAnthropic; import inspect, openai; from openai.resources.chat.completions import AsyncCompletions; assert hasattr(AsyncAnthropic(api_key='x'),'messages'); assert 'max_completion_tokens' in inspect.signature(AsyncCompletions.create).parameters; print('sdk ok', openai.__version__)"` → `sdk ok 2.15.0` |
| H2.1.2 | Контракт залежностей у тестах **без моків**: клієнт Anthropic має `.messages`; `AsyncCompletions.create` приймає `max_completion_tokens`; мінімальні версії `anthropic>=0.76`, `openai>=2.15`. Живе в CI (`.github/workflows/ci.yml:102` ставить `requirements.txt`) → дрейф пінів = червоний CI, а не мовчазний прод | новий `apps/api/tests/test_dependency_contract.py` | локально `pytest tests/test_dependency_contract.py` зелений; той самий тест на старому образі (rollback-тег) — червоний (доказ, що ловить) |
| H2.1.3 | Pre-flight у деплої **на щойно зібраному образі, до перезапуску** (без даунтайму): після `build`, перед `up` — `docker compose -f $COMPOSE_FILE run --rm --no-deps --entrypoint python api -c "<та сама перевірка з H2.1.1>"`; фейл = `exit 1` з підказкою, старі контейнери працюють далі | `infra/deploy.sh`, між кроками 4/6 і 5/6 | прогін deploy.sh на сервері друкує `OK: SDK контракт`; вручну підмінити піни назад локально → крок падає |

**Не робимо:** не чіпаємо код викликів моделей, не міняємо моделі/профіль (§13), не робимо повний `pip freeze` (три піни рівно закривають розбіжність; решта — окремо, якщо колись знадобиться), не деплоїмо разом із блоками 1–4.

### H2.2. Рев'ю (Claude) — diff проти таблиці; `pytest` (api) повний + новий тест; образ збирається локально й проходить перевірку з H2.1.1.

### H2.3. Стоп-точка — деплой **тільки після «так» фаундера** (у мету виконавцю писати прямо: «H2.4 не виконувати без мого дозволу»).

### H2.4. Деплой і верифікація

1. Копія коду на сервері + rsync — команди з блоку №1 (H.3.1–H.3.2, `--exclude='.env*'`).
2. `ssh thesica 'bash /opt/thesica/infra/deploy.sh'` — тепер із pre-flight H2.1.3.
3. Верифікація (Claude, read-only): `docker exec ai-thesis-api python -c "import anthropic, openai; print(anthropic.__version__, openai.__version__)"` → `0.76.0 2.15.0`; canary зелений; профіль у контейнері незмінний.
4. Менеджерка створює роботу **заново** (doc 1 у стані `failed` з `attempt 3/3` перезапускається лише admin-retry; простіше нова заявка, ліміт на день дозволяє). Це вже платна генерація. Claude стежить у логах за ланцюжком: pack_translation → outline → секції; перший успішний виклик моделі = дрейф закритий.

### H2.5. DoD — у логах немає `AttributeError`, job проходить далі outline, CI має тест контракту залежностей, deploy.sh має pre-flight образу.

**Статус 03.09 ~17:30:** H2.1–H2.3 ✅ (коміт `bbe7953`, 3 файли, рев'ю Claude: BLOCKER/HIGH — немає; повний pytest усередині нового образу 1003 passed / 7 skipped). H2.4.1–H2.4.3 ✅ — задеплоєно GPT/Codex через deploy.sh з pre-flight; у live-контейнері `anthropic 0.76.0 / openai 2.15.0 / anyio 3.7.1`, профіль генерації незмінний, порти 127.0.0.1, `.env` цілий, canary зелений, бекап `pre-deploy-20260903-142426.sql` + `pre-code-20260903-142255.tar.gz`, rollback-теги `rollback-20260903-142426`, коміт запушено. **H2.4.4 виконано 03.09 17:36–17:40 (doc 2, job 2): інфраструктурно ланцюжок пройшов повністю** — create → методичка → task contract (з листа професора) → автопакет джерел → outline (Opus, без fallback) → section writer (Opus, `fallback_used: false`). **Робота впала на grounding-гейті секції 1 після 3 спроб** (rate 0.23 / 0.20 / 0.29 < 0.80), €0.47 (42.5k токенів). Обидва хотфікси доведені реальним замовленням; далі — продуктова черга блоків 1–3, не хотфікси.

**Чому впала (не баг хотфіксів, а відомі дірки плану):**
- автопакет для теми слабкий: 18 → 24 джерела, `mean_on_topic_score` 0.452 → 0.216, `underfilled: true`, `passages: 0` (без повнотекстових уривків); builder послабив поріг релевантності до 0.17, щоб добрати пакет (`source_pack.py`: «Source pack underfilled … relaxed threshold 0.17»);
- гейт рахує цитату grounded лише якщо ключ є в пакеті **і** `on_topic_score >= 0.35` (`grounding_gate.py:evaluate_grounding`). Письменник цитує тільки пакет, а більшість пакета нижче 0.35 → секція приречена ще до письма; 3 ретраї Opus спалюють гроші на гарантований фейл;
- `SOURCE_PACK_PREFLIGHT_ENABLED` на проді не задано (дефолт False; compose не містить) — preflight зупинив би прогін **до** письма й витрат. Це рівно Блок 1.2 + рішення 11.07 «верифікація пакета ДО письма»;
- менеджерка не може дати реальні PDF-джерела: UI завантаження джерел відсутній (Блок 3.1), форма стартує генерацію одразу (Блок 3.3).

**Наслідок для менеджерів:** повторна відправка тієї ж заявки без нових джерел = той самий фейл і ~€0.5 за спробу. Тестування генерації ставимо на паузу до Блоків 1–3; створення заявки/інтейк тестувати можна (безкоштовно, генерацію не запускати).

**Додано в Блок 2 (див. 2.х нижче):** узгодити пороги builder ↔ gate. **P2 UI:** «Докази якості» для failed-роботи показують «невідома модель (невідомий провайдер)», хоча provenance має `section_writer` з моделлю (`DocumentQualityEvidence.tsx:218-220`).

**Побічно помічено в логах після рестарту (P2, не блокує):** websocket прогресу `apps/api/app/api/v1/endpoints/jobs.py:140` при простроченому JWT (`ExpiredSignatureError`) закриває сокет двічі → `RuntimeError: Unexpected ASGI message 'websocket.close', after sending 'websocket.close'`. Виникає, коли вкладка кабінету висить відкритою довше за життя токена; браузер перепідключається сам, шкоди немає. Полагодити: після першого `close` у гілці помилки аутентифікації не закривати повторно.

---

## Виконання блоків 1–3 — черга, цілі для виконавця, стоп-точки (план 03.09, після живого прогону doc 2)

**Навіщо саме так.** Живий прогін 03.09 показав: інфраструктура працює, а падає продукт — слабкий автопакет, гейт без preflight, менеджер не може дати джерела, форма стартує генерацію одразу. Тому черга = **спочатку «чесна зупинка до витрат» (Блок 1 + 2.х), потім дірки коду (Блок 2), потім три екрани (Блок 3), і один спільний деплой** — окремо деплоїти Блок 1 сенсу мало: з preflight ON і без екрана джерел (3.1) кожна складна тема зупинятиметься на старті, і менеджеру нічим це полікувати.

Ролі як у хотфіксах: **Codex/GPT виконує кожну ціль локально одним комітом і зупиняється; Claude рев'юїть diff проти таблиці + ганяє тести; деплой (G3) — лише після «так» фаундера.** Консолідація доків у робочому дереві досі не закомічена → у кожній цілі `git add <перелічені файли>`, не `-A`.

### Передумови (Блок 0) — рішення, які план бере за замовчуванням; фаундер підтверджує або змінює

| # | Рішення в плані | Стан на 03.09 |
|---|---|---|
| 0.1 | `CLAIM_VERIFICATION_BLOCKING=true` — без цього валідатор `config.py:486-499` не дає увімкнути preflight; це не опція, а умова | приймаємо |
| 0.2 | `AI_ENABLE_FALLBACK=false` у профілі: збій Opus = чесний фейл/ретрай, а не тихий gpt-4o | приймаємо (сьогоднішній прогін: `fallback_used: false`, але дефолт коду True) |
| 0.3 | Copyscape: на проді `COPYSCAPE_API_KEY` і `COPYSCAPE_USERNAME` задані | ✅ виглядає закритим; фаундер підтверджує, що ключ живий |
| 0.4 | Ліміти: 2 роботи/день/акаунт (зараз .env=20), ≤50 стор., глобальна стеля 6M токенів/день | приймаємо; після G1 значення живуть у compose, а не в .env |
| 0.5 | Ротація ключа OpenRouter — тільки фаундер | ☐ відкрито |
| 0.6 | Semantic Scholar: `SEMANTIC_SCHOLAR_API_KEY` на проді задано | ✅ виглядає закритим |

### G1 — бекенд: релізний профіль + чесна зупинка + баги коду (Блоки 1, 2.1–2.5, 2.х) — один коміт

| # | Що | Де | Перевірка |
|---|---|---|---|
| G1.1 | Дефолти коду: `METHODOLOGY_REQUIRED_FOR_GENERATION` True→False (D2), `HUMANIZER_ENABLED` True→False, `AI_ENABLE_FALLBACK` True→False | `apps/api/app/core/config.py:378, :120, :80` | перевернути асерти старого режиму в `tests/test_config_guards.py:71` (і сусідні для humanizer/fallback, якщо є); `pytest` зелений |
| G1.2 | Профіль як артефакт у compose (env-блок api): додати `SOURCE_PACK_PREFLIGHT_ENABLED=true` **разом із** `CLAIM_VERIFICATION_BLOCKING=true` (:116); `METHODOLOGY_REQUIRED_FOR_GENERATION=false` (:102); літерали без `${}`: `MVP_FREE_GENERATION_ENABLED=true`, `MVP_FREE_GENERATION_MAX_PAGES=50`, `MVP_FREE_GENERATION_DAILY_USER_LIMIT=2`; `AI_ENABLE_FALLBACK=false`; `GENERATION_WORKER_ENABLED=true`; `GLOBAL_DAILY_TOKEN_LIMIT=6000000` (G1.3) | `infra/docker/docker-compose.prod.yml` | `docker compose -f infra/docker/docker-compose.prod.yml config` без помилок; `Settings(**RELEASE_PROFILE)` конструюється (G1.5) |
| G1.3 | Глобальна стеля витрат: нова змінна `GLOBAL_DAILY_TOKEN_LIMIT` (дефолт 6_000_000) + **блокуючий** чек у `generate.py:435-477` поруч із по-юзерним (сума за добу по всіх юзерах + резервації активних джоб); `ai_service.py:85-110` лишається warning-only або читає ту ж змінну | `config.py`, `generate.py` | тест: за стелею `POST /generate/full-document` → 429/400 з людським detail; під стелею — проходить |
| G1.4 | **2.х — пороги builder ↔ gate.** (а) `build_source_pack`: при `underfilled` після одноразового послаблення джерела з `on_topic_score < SOURCE_PACK_MIN_ON_TOPIC_SCORE` **не подавати письменнику як цитовані** (лишати в пакеті як «контекст», без ключа для цитування) — тоді гейт і builder міряють одну планку; (б) якщо після цього цитованих джерел < `_UNDERFILL_FLOOR` (6) і завантажених PDF немає — **чесна зупинка до письма**: `status=failed_quality`, provenance-подія `source_pack_insufficient` з людським текстом «замало релевантних джерел, додайте PDF» (той самий шлях, яким preflight зупиняє при `not meets_minimum`, `background_jobs.py:~1648-1676`); ретраїв секції не буде | `source_pack.py:533-562`, `background_jobs.py` (місце виклику builder і гілка preflight) | тест на пакеті з 24 джерел mean 0.2: письменник отримує 0 цитованих ключів → зупинка без виклику моделі; тест на пакеті 0.45: нічого не змінюється |
| G1.5 | Тести профілю: розширити `tests/test_production_runtime_contract.py:106-122` (preflight=true, claim blocking=true, methodology=false, free-gen трійка літералами, `PUBLIC_REGISTRATION_ENABLED=false`, `AI_ENABLE_FALLBACK=false`, `GLOBAL_DAILY_TOKEN_LIMIT`); фікстура `RELEASE_PROFILE` + тест `Settings(**RELEASE_PROFILE)` без ValueError; один мокнутий e2e прогін пайплайна на повній комбінації профілю (зшити harness `test_provenance_ledger.py` + `test_source_pack_preflight_pipeline.py`) | `apps/api/tests/` | `pytest` зелений; тест e2e фейлить, якщо вимкнути будь-який прапорець профілю |
| G1.6 | 2.1 DOCX-гігієна: `core_properties` (title = назва роботи, author/last_modified_by нейтральні), прибрати англійську шапку `Topic:/Language:/Created:` з тіла tesi (`document_service.py:879-880`, PDF-гілка :992-993), додати «Sitografia» поруч із «Bibliografia» (контракт `task_contract.py:33-37`) | `apps/api/app/services/document_service.py` | тест розпаковує DOCX: `docProps/core.xml` без `python-docx`/`Word Document`; у тілі немає `Topic:`; є заголовок Sitografia |
| G1.7 | 2.2 не логувати робочий лінк входу: `auth_service.py:75-95` — у warning лишити факт «email not sent», URL прибрати | `auth_service.py` | тест: caplog не містить `/auth/verify?token=` |
| G1.8 | 2.3 `POST /auth/admin-login` (`auth.py:522`) без rate-limit/lockout → додати `@rate_limit("5/minute")` + `check_auth_lockout/record_auth_failure` як у звичайного login (`auth.py:119-175`) | `auth.py` | тест: 6-та спроба за хвилину → 429; 5 неправильних паролів → lockout |
| G1.9 | 2.4 `work_type` полем: `intake-fields.ts` має опцію `workType` лише як текст у `additional_requirements`; схема вже приймає `work_type` (`schemas/document.py:60,120-127`) і контракт читає його (`task_contract.py:76-93`). Бекенд: узгодити допустимі значення (`validate_work_type` ↔ `WORK_TYPE_STRUCTURES`) і повернути їх у помилці; фронт — у G2.4 | `schemas/document.py`, `task_contract.py` | допустимі значення вже є: `tesi_triennale`, `tesi_magistrale`, `diploma`, `essay`, `report` (дефолт `tesi_magistrale`, `task_contract.py:29-45`); тест: create з `work_type="tesi_triennale"` → контракт без «assumed magistrale» |
| G1.10 | 2.5 (P1) release-гейт `source_availability` читає подію `source_pack_preflight` (і нову `source_pack_insufficient`), а не провізорний пак | `production_case_service.py:1098-1123` | тест на кейсі з preflight-подією |
| G1.11 | 1.5 гігієна: `.env.example` — прибрати `AI_FALLBACK_CHAIN` з ретирнутими моделями (:33), `AI_ENABLE_FALLBACK=false`; у `docs/` блок «релізний профіль» = канонічний список змінних (той самий, що в compose) | `.env.example`, `docs/setup/PRODUCTION_DEPLOYMENT_PLAN.md` | — |

Не робимо в G1: 2.6, 2.7 (P2 — після пілота), зміни Caddy/портів, будь-які зміни моделей.

**Статус G1 (03.09, вечір):** виконано GPT/Codex локально, коміт `02b3037` (25 файлів, +1422/−204), не запушено, не задеплоєно. **Рев'ю Claude: BLOCKER/HIGH — немає; G1 прийнято.** Перевірено командами: повний `pytest` 1035 passed / 8 skipped; `ruff` чистий; `docker compose config` рендерить профіль літералами (preflight=true, claim blocking=true, methodology=false, free-gen 2/50, fallback=false, worker=true, GLOBAL_DAILY_TOKEN_LIMIT=6000000, registration=false); шлях insufficient-стопу стоїть до outline (`background_jobs.py:1504` < `:1539`), `CitationIntegrityError` у терміналі (`:3636`, ретраїв нема), провайдерський збій = `RuntimeError` = retryable; спільний гейт бюджету викликають усі три шляхи enqueue (`generate.py:813`, `admin_documents.py:556`, `payment.py:181`), legacy-маршрут `jobs.py` вимкнено профілем. **MEDIUM (не блокують, закрити до G3):** (1) DOCX `core_properties.created/modified` лишаються шаблонними `2013-12-23` (python-docx) — виставити поточну дату UTC + асерт у `test_bibliography_export.py`; (2) insufficient-стоп є лише на початковому пакеті; у релізному профілі пост-outline пакет іде через preflight (verified ≥18 або `failed_quality`), а legacy-гілка без preflight (`:1781`) стопу не має — лишити як є, зафіксовано; (3) advisory-lock захист від гонки бюджету — Postgres-only, у CI (SQLite) не перевіряється; прийнятно для пілота. Серверний `.env` (`AI_ENABLE_FALLBACK=true`, `DAILY_USER_LIMIT=20`) тепер інертний для цих ключів — прибрати в G3.2.

### G2 — фронт: три екрани (Блок 3.1–3.3 + дешева частина 3.4) — один коміт

| # | Що | Де | Перевірка |
|---|---|---|---|
| G2.1 | 3.1 Джерела клієнта на сторінці роботи: новий компонент `DocumentSourceFiles` (окремо від `DocumentSources`, який показує провенанс цитат): multipart upload кількох PDF → `POST /documents/{id}/sources/upload`; список `GET .../sources/files` зі статусами `parsed` / `no_text_layer` / `metadata_incomplete`; редагування `title/authors/year` і перемикач `mandatory` → `PATCH .../sources/files/{file_id}`; видалення → `DELETE`. Додати ці шляхи в `API_ENDPOINTS.DOCUMENTS` (`lib/api.ts`). Доступно лише поки робота `draft` (до старту генерації) | `apps/web/components/dashboard/DocumentSourceFiles.tsx`, `app/dashboard/documents/[id]/page.tsx`, `lib/api.ts` | jest: рендер списку зі статусами, PATCH при зміні поля, disabled після старту; ручна перевірка у браузері на dev-стенді |
| G2.2 | 3.3 Екран контракту (D2): форма більше **не стартує генерацію** (`CreateDocumentForm.tsx:167-189` → після create + upload методички лише `router.push`); методичка у формі **опційна** (`:119-121`, `required` :264 прибрати; підказка «без методички контракт буде на припущеннях»); на сторінці роботи для `draft` — панель «Контракт» з `GET /documents/{id}/task-contract` (правила: explicit vs assumed), блок «Джерела» (G2.1), «Орієнтовна вартість» з `GET /generate/estimate-cost` (3.4), кнопка **«Підтвердити і запустити»** → `POST .../task-contract/confirm` → `POST /generate/full-document`. Кнопка активна лише після підтвердження | `CreateDocumentForm.tsx`, `app/dashboard/documents/[id]/page.tsx`, новий `components/dashboard/TaskContractPanel.tsx`, `lib/api.ts` (TASK_CONTRACT, CONFIRM, ESTIMATE_COST) | jest: створення без методички проходить; після create генерація не викликається; confirm → generate у правильному порядку; оновити `__tests__/e2e/document-creation-flow.test.tsx` |
| G2.3 | 3.2 Кнопка «DOCX для Compilatio (pre-release)» на сторінці кейсу `app/admin/production-cases/[id]/page.tsx` → `POST /api/v1/admin/documents/{document_id}/download` (scope `internal_review`, `admin_documents.py:661-755`); показати sha256 файлу поруч (він же потім вписується в release decision) | `production-cases/[id]/page.tsx`, `lib/admin-api` (де живе `adminApiClient`) | jest: кнопка викликає ендпоінт і показує sha; ручна перевірка на dev-стенді |
| G2.4 | 2.4 фронт: `workType` → окреме поле `work_type` у payload (`intake-fields.ts:23-25` вже має механізм «maps to API column»), мапа UI→API: «Дипломна (бакалавр)»→`tesi_triennale`, «Магістерська»→`tesi_magistrale`, «Курсова»→`report`, «Реферат»→`essay`, «Есе»→`essay` (мапа курсової/реферату — дрібне рішення фаундера, дефолт такий); в `additional_requirements` не дублювати | `lib/intake-fields.ts`, `CreateDocumentForm.tsx` | jest: payload містить `work_type` |
| G2.5 | 3.4 дешеве: людський рендер подій `source_pack_preflight` / `source_pack_insufficient` у «Доказах якості»; для failed-роботи модель/провайдер брати з `section_writer`-подій (зараз «невідома модель», `DocumentQualityEvidence.tsx:218-220`); обробка WS `job_retrying` як статус «повторна спроба» | `DocumentQualityEvidence.tsx`, `app/dashboard/documents/[id]/page.tsx` | jest на рендер подій |

Не робимо в G2: редизайн, оплату, клієнтський фронт, € по кейсу для менеджера (P1, після пілота).

### G3 — деплой і повторний живий прогін (після «так» фаундера)

1. Рев'ю G1+G2 (Claude), CI зелений (крім хронічного mypy), локальний образ зібрано і пройшов pre-flight SDK.
2. Сервер: `.env` — прибрати/ігнорувати `MVP_FREE_GENERATION_DAILY_USER_LIMIT=20` (compose тепер літерал 2), переконатися `ENVIRONMENT=production`; Блок 4.1 (SMTP у compose) — окремо, не в цьому деплої.
3. Копія коду → rsync (`--exclude='.env*'`) → `infra/deploy.sh` → у контейнері `env | grep -E 'PREFLIGHT|CLAIM|METHODOLOGY|HUMANIZER|FREE_GEN|FALLBACK|GLOBAL_DAILY'` = профіль G1.2 → canary.
4. Живий прогін: менеджерка створює роботу **з 5–8 реальними PDF по темі** (3.1), дивиться контракт, підтверджує, запускає. Очікуване: preflight-вердикт у «Доказах якості» до письма; або чесна зупинка «замало джерел» (безкоштовно), або секції пишуться з grounding ≥0.8. Claude стежить у логах. Бюджет однієї спроби ≤ €2 (без ретраїв на приречених секціях).

### Стоп-точки (писати в мету виконавцю дослівно)
- G1 і G2: «Виконати лише перелічені файли, один коміт, без деплою, без `git add -A`. Після коміту зупинитись і віддати на рев'ю.»
- G3: «Не виконувати без мого окремого "так".»

### DoD блоків 1–3
Профіль живе в compose і захищений тестами; слабкий пакет зупиняє прогін **до** витрат з людським поясненням; менеджер із кабінету може: додати PDF-джерела → побачити контракт і ціну → підтвердити → запустити; адмін може зняти DOCX для Compilatio з sha; `work_type` доходить до контракту; DOCX без слідів генератора; лінк входу не в логах; admin-login під lockout.

---

## Блок 0 — підтвердження фаундера (без коду)

| # | Питання | Рекомендація | Статус |
|---|---|---|---|
| 0.1 | `CLAIM_VERIFICATION_BLOCKING=true` | Технічно обов'язково разом із preflight (валідатор `config.py:486-499` інакше кладе API на старті). Наслідок: непідтверджені твердження = регенерація секції, дорожчий прогін, але без «води під виглядом фактів». Вмикаємо. | ☐ |
| 0.2 | Fallback писаря на пілоті | При збої Opus секцію зараз мовчки дописує gpt-4o (слід у provenance, стопа немає). Для «писар = Opus» у RUN-001 — **вимкнути fallback у профілі** (чесний фейл + ретрай замість підміни). | ☐ |
| 0.3 | Copyscape | Ключа немає → кожен прогін дає plagiarism `UNCHECKED` → release тільки через аудитований override. Або дати ключ, або зафіксувати «override за замовчуванням до Фази 2» письмово. | ☐ |
| 0.4 | Ліміти free-генерації на проді | Free-режим лишаємо ON (це єдиний шлях менеджерів без оплати), але: 2 док/день/акаунт (на сервері зараз 20!), ≤50 стор., **глобальна стеля** ~6M токенів/день на систему (див. 1.3). | ☐ |
| 0.5 | Ротація ключа OpenRouter | Ключ світився в чатах. Живе тільки в локальному `apps/api/.env`, прод його не читає — ризик лише сам ключ. Revoke в кабінеті + заміна значення. Тільки фаундер. | ☐ |
| 0.6 | Ключ Semantic Scholar | Без нього верифікатор джерел упирається в 429 і preflight ретраїться замість чесного вердикту. Безкоштовний ключ по заявці — завести до Блоку 6. | ☐ |

---

## Блок 1 — релізний профіль: конфіг + тести (P0)

Мета (черга AGENT_SYNC §7, крок «релізний профіль»): профіль існує як **артефакт** (env-блок у compose) і **захищений тестом**, а не тримається на пам'яті.

**1.1. Дефолти коду** — `apps/api/app/core/config.py`:
- `METHODOLOGY_REQUIRED_FOR_GENERATION`: True → **False** (:378) — пряме виконання D2 «методичка = опція». Тести вже живуть у цьому світі (`conftest.py:69-70`); свідомо перевернути асерт старого режиму в `tests/test_config_guards.py:71`.
- `HUMANIZER_ENABLED`: True → **False** (:120) — зараз «чистий» запуск без env вмикає humanizer (локальний `.env` реально ганяє gpt-4o-гуманізацію, яку фаундер виключив).

**1.2. Бойовий compose** — `infra/docker/docker-compose.prod.yml`, env-блок api:
- додати `SOURCE_PACK_PREFLIGHT_ENABLED=true` **одночасно з** `CLAIM_VERIFICATION_BLOCKING=true` (:116 false → true) — нарізно API не стартує;
- `METHODOLOGY_REQUIRED_FOR_GENERATION`: захардкоджене `true` (:102) → **false**;
- явно: `MVP_FREE_GENERATION_ENABLED=true`, `MVP_FREE_GENERATION_MAX_PAGES=50` (прибрати `:-50`-двозначність; 50 покриває ціль 45 стор. RUN-001 — дефолт коду 20 прогін би заблокував), `MVP_FREE_GENERATION_DAILY_USER_LIMIT=2`;
- `AI_ENABLE_FALLBACK=false` (рішення 0.2);
- `GENERATION_WORKER_ENABLED=true` явно (зараз тримається на дефолті).

**1.3. Глобальна стеля витрат** (зараз її немає — бюджет тільки per-user `generate.py:435-477`, глобальний чек `ai_service.py:85-110` warning-only):
- нова змінна `GLOBAL_DAILY_TOKEN_LIMIT` + блокуючий чек поруч із по-юзерним (сума за добу по всіх юзерах, з резервацією активних джоб);
- P2: фантомні адмін-ліміти (`PUT /settings/limits` пише в БД, генерація не читає — `endpoints/settings.py:187-241`) — або підключити, або прибрати з UI.

**1.4. Тести профілю:**
- розширити `apps/api/tests/test_production_runtime_contract.py:106-122` асертами: preflight=true, claim blocking=true, methodology=false, free-gen трійка, `PUBLIC_REGISTRATION_ENABLED=false`, `AI_ENABLE_FALLBACK=false`;
- Settings-рівень: фікстура-словник `RELEASE_PROFILE` + тест, що `Settings(**RELEASE_PROFILE)` конструюється без ValueError і кожен прапорець має релізне значення;
- один мокнутий e2e-прогін пайплайна **на повній комбінації профілю** (зараз повну комбінацію стадій разом не ганяє жоден тест) — зшити harness `test_provenance_ledger.py` + preflight з `test_source_pack_preflight_pipeline.py`.

**1.5. Гігієна конфігів:** оновити `.env.example` (мертвий `AI_FALLBACK_CHAIN` з ретирнутими моделями — прибрати), додати у docs блок «релізний профіль» як канонічний список змінних.

---

## Блок 2 — продуктові баги до прогону (P0; за §13.1.3 «дефекти — наші баги, лікуємо в коді»)

- **2.1. Гігієна DOCX** — файл, який іде в Compilatio, зараз сам себе видає:
  - `docProps/core.xml`: `last_modified_by="python-docx"`, `title="Word Document"` — виставити нейтральні core_properties (title = назва роботи, автор/last_modified_by — порожньо або узгоджене ім'я) у `document_service.py` при збірці;
  - прибрати англійську службову шапку `Topic: … / Language: it / Created: …` з тіла італійської tesi (`document_service.py:871-884`);
  - додати розділ «Sitografia» (контракт tesi_magistrale обіцяє bibliography + sitography — `task_contract.py:33-37`, рендериться лише «Bibliografia»).
- **2.2. Не логувати робочий лінк входу** — при недоступному SMTP валідний login-URL пише warning-лог (`auth_service.py:90-93`). Прибрати URL з лога (лишити факт «email not sent»).
- **2.3. `POST /auth/admin-login` без захисту** — єдиний вхід без rate-limit/lockout (брутфорс адмінського пароля). Додати `@rate_limit` + lockout як у звичайного login, або прибрати ендпоінт.
- **2.4. `work_type` з форми не доходить** — консоль шле тип роботи текстом у вимоги, колонка `document.work_type` лишається NULL, контракт мовчки припускає магістерську (`intake-fields.ts:135-165` → `schemas/document.py:60`). Передавати полем.
- **2.5. P1:** release-гейт `source_availability` читає провізорний пак до верифікації, а подію preflight не бачить (`production_case_service.py:1098-1123`) — навчити читати `source_pack_preflight`.
- **2.6. P2:** `task_contract_sha256` не включає digest PDF всупереч власному docstring (`task_contract.py:186-205`) — вирівняти з `generation_contract_sha256`.
- **2.7. P2:** шаблон `PHASE0_READINESS_RECORD` в адмін quick setup: прибрати поля бюджету редактора/хвилин (знято `D4`), власників підставити з `D3`/`D5`. Файл руками не редагувати — правити код, що його пише.

- **2.х (з живого прогону 03.09, doc 2). Пороги builder ↔ gate неузгоджені.** Builder добирає «недозаповнений» пакет, послаблюючи поріг релевантності до 0.17 (`source_pack.py`, «relaxed threshold»), а grounding-гейт вважає цитату обґрунтованою лише при `on_topic_score >= 0.35` (`grounding_gate.py:evaluate_grounding`). Письменник може цитувати тільки пакет → секція гарантовано провалює гейт, а 3 ретраї коштують ~€0.5 без шансу пройти. Лікування: (а) preflight ON (Блок 1.2) як стоп до письма; (б) builder не послаблює поріг нижче гейтового або позначає джерела нижче 0.35 як «не для цитування» і не подає їх письменнику; (в) при `underfilled` без завантажених PDF — чесна зупинка з повідомленням менеджеру «дай джерела», а не ретраї.

---

## Блок 3 — мінімальний UI, щоб RUN-001 пройшов без curl (P0)

Зараз через UI неможливі 3 ключові кроки (бекенд для всіх трьох повний):

- **3.1. PDF-джерела клієнта** — блок на сторінці роботи: завантажити кілька PDF, бачити статуси (`no_text_layer`, metadata_incomplete), підтвердити/виправити авторів-рік, перемикач mandatory. Ендпоінти готові: `POST/GET/PATCH/DELETE /documents/{id}/sources/*` (`documents.py:921/1069/1159/1112`).
- **3.2. «DOCX для Compilatio (pre-release)»** — кнопка в адмін-кейсі, що викликає `POST /admin/documents/{id}/download` (`admin_documents.py:661-755`; internal_review-токен, аудит, sha). Без неї ланцюг «файл → Compilatio → внести результат → release» рветься на першому кроці.
- **3.3. Екран контракту (механіка D2)** — після створення робота НЕ стартує автоматично (`CreateDocumentForm.tsx:167-189`): показати контракт/припущення (`GET /documents/{id}/task-contract`), кнопка «Підтвердити і запустити» (`POST .../task-contract/confirm`). Методичку в формі зробити опційною (зараз `required` — `CreateDocumentForm.tsx:119-121, 264` — суперечить D2 і робить універсальний контур недосяжним).
- **3.4. P1:** оцінка вартості до старту (`GET /generate/estimate-cost` є); діалог підтвердження release + видимий sha256; людський рендер події preflight у «Доказах якості»; обробка WS `job_retrying`; € по кейсу видно менеджеру, не тільки в адмінці.

---

## Блок 4 — деплой-машинерія (P0/P1)

- **4.1. SMTP у контейнер** — додати `SMTP_HOST/PORT/USER/PASSWORD/TLS`, `EMAILS_FROM_EMAIL/NAME` в env-блок api (compose:80-130 — зараз жодної; вхід поштою мертвий навіть для менеджерів).
- **4.2. `restart: unless-stopped`** всім сервісам (зараз політики немає — ребут Hetzner кладе прод до ручного втручання).
- **4.3. Canary-фікс** — перевірка №4 чекає 302 від `/auth/register`; після зняття Caddy-заглушки Next віддає 307 → фальшивий фейл наступного деплою. Приймати `302|307` (`infra/deploy.sh:77-100`).
- **4.4. Бекап файлів** — pre-deploy бекап бере тільки Postgres; том MinIO (всі PDF і видані DOCX) без копії. Додати tar тому в deploy.sh поряд з дампом.
- **4.5. Робочий restore** — надрукована в deploy.sh:110 команда відновлення непрацездатна (plain-дамп поверх живої бази), `scripts/restore.sh` несумісний за форматом. Задокументувати і поправити: stop api → drop/create db → `psql < pre-deploy-*.sql` → старий образ.
- **4.6. rsync-дисципліна** — команда доставки коду ніде не зафіксована; локальний `infra/docker/.env` протухлий і містить `ENVIRONMENT=development` (на сервері такий рядок вимкнув би CSRF і прод-валідатори). Зафіксувати канонічну команду з `--exclude='.env'` у docs/скрипті.
- **4.7. Порти повз проксі** — api `8000:8000`, web `3000:3000` опубліковані на хост: пряме звернення обходить Caddy і його правила. Бінд на `127.0.0.1:8000:8000` / `127.0.0.1:3000:3000` (Caddy на хості — йому досить localhost).

---

## Блок 5 — сервер і деплой (руками, після мержа блоків 1–4; AGENT_SYNC §7 — «вирівняти прод»)

1. Перевірити серверний `.env` (`/opt/thesica/infra/docker/.env`): `ENVIRONMENT=production` (не development!), `MVP_FREE_GENERATION_DAILY_USER_LIMIT` (зараз 20 → 2), `MAX_PAGES`, SMTP-значення на місці, `DEBUG` відсутній/false.
2. Ревізія таблиці users на проді: деактивувати акаунти, створені за період відкритої самореєстрації (будь-який активний акаунт має повні права генерації — ролі «менеджер» у коді немає).
3. Ротація OpenRouter-ключа, якщо ще не зроблено (0.5).
4. Деплой: rsync (з `--exclude='.env'`) → `infra/deploy.sh` (бекап+валідація → міграції 024–027 → build → up → canary). Міграції additive і backward-сумісні: якщо canary впав — відкат **тільки коду** (rollback-теги), базу не чіпати.
5. Перевірити живі змінні в контейнері (`docker compose exec api env | grep -E 'PREFLIGHT|CLAIM|METHODOLOGY|HUMANIZER|FREE_GEN|REGISTRATION'`) — профіль має збігатися з Блоком 1.
6. Зняти Caddy-заглушку реєстрації (захист тепер у коді) → повторно прогнати canary → перевірити ззовні: реєстрація закрита, вхід менеджера паролем працює.

---

## Блок 6 — короткий prod-like прогін (замір перед RUN-001, уточнення черги 24.08) — ПЛАТНИЙ, тільки після «так» фаундера

- **6.1.** Чекліст-драйвер прогону за зразком `docs/phase1-runs/CONTROL-RUN-A/` (створити → PDF → підтвердити контракт → прогін → DOCX через адмін-кнопку → Compilatio руками → внести обидва результати в кейс → release). Артефакти: job.json, provenance-events.json, sources.json, docx-artifact, вартість €.
- **6.2.** Прогін 10–20 стор. на релізному профілі (~€0.60–1.50). **Той самий DOCX → Compilatio.** Це перший чесний замір профілю взагалі (C10: всі попередні цифри — короткі тексти без preflight) і перевірка, що preflight блокує ДО витрат, а не після (анти-«прогін B»).
- **Гейт:** якщо Compilatio прийнятний відносно планки D1 — йдемо на Блок 7. Якщо AI% високий — не маскувати: факт у звіт, ескалація фаундеру (§4).
- Ризик на довжині: LanguageTool без ключа має жорсткі публічні ліміти — на 40+ стор. стежити за grammar-стадією (P1: ключ або self-host).

## Блок 7 — RUN-001 (веде фаундер, D3)

За §7.3 AGENT_SYNC: tesi magistrale, італійська, **≥40 стор.**, APA, UniBo, Opus, humanizer off, методичка + 5–10 PDF клієнта. Preflight має пройти ДО письма. Після DOCX — той самий файл у Compilatio. Заповнити [phase1-runs/RUN-001.md](./phase1-runs/RUN-001.md): якість, вартість, токени, similarity%, AI%, pass/fail.
**Pass (§13.1.2, три блоки):** якість → ≤10/≤10 на тому самому файлі → жодного переписування змісту людиною. Fail по джерелах → лікувати пакет. Fail по AI% → не вмикати humanizer; дивитись генерацію і авторський шар.

---

## Чого НЕ робимо (§4 + §13)

Жодного detector-evasion / «щоб Compilatio не впізнав»; humanizer лишається off; жодного публічного кабінету, Stripe, трафіку до pass Фази 1; mypy-борг (357) — окрема задача після пілота; нові фічі поза цим списком — стоп.

## Definition of done цього таска

1. Профіль увімкнено і закріплено тестами (CI зелений по required-джобах).
2. Прод на HEAD, живі змінні в контейнері = профіль, заглушка знята, реєстрація закрита, менеджери входять.
3. Всі кроки прогону можливі через UI (PDF, контракт, pre-release DOCX) — нуль curl.
4. Короткий прогін пройшов повний цикл з Compilatio-звітом на тому самому файлі.
5. RUN-001 проведений і чесно заповнений — незалежно від pass/fail.
