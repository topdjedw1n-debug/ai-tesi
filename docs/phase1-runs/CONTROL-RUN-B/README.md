# Контрольний прогін B — ті самі параметри + методичка UNIBO (11.07.2026)

Документ 62, job 51, той самий користувач і вхід, що в прогоні A, плюс
`docs/methodiche/UNIBO-linee-guida-tesi-magistrale.pdf` (21 522 байти, текст 21 608 символів витягнуто і персистовано).
**Результат: FAILED на strict-гейті цитат** — 3/3 розділи згенеровано і пройшли посекційні гейти, але одне процитоване джерело з автопакета не підтвердилось у жодній бібліографічній базі → CitationIntegrityError, видача чесно заблокована (DOCX не створено). 0 ретраїв, 0 ручних втручань, збій не виправлявся (за інструкцією).

- Контракт: basis `university_methodology`, **всі правила explicit** (структура = explicit/methodology), припущень 0, підтвердження не потрібне (sha `65247a…`).
- Час: 12:50:31 → 12:53:56 UTC = **3 хв 25 с** (до стадії цитат; аудит тверджень і експорт не виконувались — fail-closed). Вартість: **€0.55** (55 cost_cents), 93 644 токени.
- Гейти: grounding — без фейлів; граматика 100/90/85; плагіат 0%; AI-детекція failed 73.4/85.4/80.0 % (неблокуюча); панель 88.5×3; **цитати strict: 21 verified + 1 not_found з 22 процитованих → FAILED**.
- Джерело-провальник: «Industria 4.0, digitalizzazione e organizzazione aziendale: il contributo dei sistemi CRM e il caso Salesforce» (ABITABILE, R., 2025) — **прийшло з самого автопакета** (is_in_upfront_pack=true, paper_id openalex.org/W7113394431, ETD-репозиторій Пізи = студентська теза, індексована OpenAlex). Письменник нічого не вигадував; пост-верифікація його не знайшла → strict-політика зупинила роботу.

## Файли

| Файл | Що це |
|---|---|
| task-contract-pre.json | контракт після завантаження методички |
| task-contract-provenance.json | подія task_contract з провенансу (basis=university_methodology) |
| methodology-upload-response.json | відповідь upload методички |
| outline.json | план (3 розділи UNIBO-подібної структури) |
| final-text.md | текст розділів з БД (робота не видана — тексти лишились у БД) |
| sources.json | document_sources: 40 записів (24 у пакеті; 21 verified / 1 not_found / 18 unverified) |
| sections-meta.json | бали гейтів по розділах |
| provenance-events.json | повний ledger (25 подій, включно з integrity_gate_failed) |
| job.json, production-case.json, document.json | стан job/кейса/документа (generation failed, release blocked, DOCX нема) |

Помічені дефекти (нічого не виправлялось): 2 сирі маркери `[EnriPeiró2025]`; цитата з автором-ініціалом «(N. et al., 2026)» (битий author-запис у пакеті); CAPS-прізвище «ABITABILE»; у §3.1–3.2 дужкові цитати вжиті як підмет речення («(Neri et al., 2023) documenta…») — стилістичний збій APA-прози.
