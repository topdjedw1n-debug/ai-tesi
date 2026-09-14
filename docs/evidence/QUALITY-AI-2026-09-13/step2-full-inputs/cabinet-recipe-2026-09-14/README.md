# Три роботи новим рецептом через кабінет (14.09.2026, 18:58–20:12)

Дозвіл фаундера: «Ну давай, подивимось чи ми щось зрозуміли, в тебе так. Роби. Але роби через кабінет, а не через сервер»; реліз активовано фаундером («Готово», контейнери перезапущені, модулі рецепту на місці: `section_material.py` `508c5de1…`, `executor_v2/sections.py` `a05d0ced…`). Чернетки створено і запущено в кабінеті app.thesica.co через Chrome фаундера (сесія manager1): бриф як у контролях 12–13.09, без методички, для B — 14 PDF (10 обов'язкових, автори/роки виставлені, назви з метаданих PDF). Три генерації йшли паралельно.

| Робота | Документ / job | Розділів | Вартість | Токени | Слів | Лапки | Файл (SHA-256) |
|---|---|---|---|---|---|---|---|
| A економіка (triennale, 20 стор.) | 16 / 19 | 14 | $1,69 | 237 625 | 7 785 | 21,0 % | `A-doc16-job19-83c7c549.docx`, `83c7c549…` |
| B право (magistrale, 30 стор.) | 17 / 20 | 17 | $2,69 | 385 612 | 12 600 | 20,7 % | `B-doc17-job20-73f02528.docx`, `73f02528…` |
| C інформатика (triennale, 25 стор.) | 18 / 21 | 20 | $1,94 | 262 223 | 9 699 | 10,7 % | `C-doc18-job21-63449662.docx`, `63449662…` |

Файли взято з S3 роботи (`storage_path` у результаті job) через `StorageService.download_file` у контейнері API; SHA-256 збігаються з `result.docx.sha256`. Сесія кабінету в Chrome закінчилася під час генерації, тому завантаження через інтерфейс не було.

## Матеріал по розділах (події `executor_section_evidence`)

- **A:** документи є в 11 із 14 розділів (1–4 документи, 5–27 вікон); без документів §7 «Il concetto di fidelizzazione», §9 «Strategie di social media per la fidelizzazione nelle PMI», §12 «Evidenze empiriche» (попередження `section_without_documents` ×3); слабкі §8 (5 вікон), §11 (2). Вступ (§1) отримав 14 вікон, висновки (§14) 23 — обидва написані останніми з 12 готових розділів.
- **B:** усі 17 розділів — 2–4 документи, 22–26 вікон, 18,7–21,9 тис. символів; `section_without_documents` — 0.
- **C:** жоден із 20 розділів не отримав повнотекстових документів (2–3 анотації, 2–5 тис. символів на розділ); `section_without_documents` ×18, `source_coverage_gap` ×2. Причина: під час S2 усі каталоги (Semantic Scholar, OpenAlex, Crossref, arXiv) віддавали HTTP 429 — три роботи шукали джерела одночасно з одного IP; пакет C лишився без відкритих PDF. Це відомий стан «без матеріалу» (25–50 % AI), сканувати його — перевірка заради перевірки. Переробити після зняття обмеження або з PDF від менеджера.

## Попередження (за кодами)

A: source_no_readable_text 10, citation_unresolved 6, outline_scope_unmapped 4, section_without_documents 3, quote_without_page 1, bibliography_suspect 1, source_full_text_unavailable 1, review_note 1. B: outline_scope_unmapped 5, source_no_readable_text 5, citation_unresolved 2, review_note 1, quote_without_page 1. C: section_without_documents 18, citation_unresolved 4, outline_scope_unmapped 4, source_coverage_gap 2, bibliography_suspect 1, source_no_readable_text 1, placeholder_text 1, quote_without_page 1, review_note 1.

## Що видно в текстах ($0)

Вступ і висновки в усіх трьох починаються з питання роботи і відповіді на нього результатами глав («Il presente lavoro muove da un interrogativo preciso…», «La domanda che ha guidato l'indagine chiedeva se…»); фраз-дорожніх карт («si articola», «il primo capitolo») — 1 в A, 1 в B, 3 в C. Частка тексту в лапках A 21 %, B 20,7 % (як у ранкових A/B), C 10,7 %. Побічно: лічильник `sections_done` у статусі показує подвоєне число (28/34/40), бо розділи зберігаються двічі (S4 і S5) — косметика, виправити окремо.

## Скани

На скан — A і B (папка фаундера «Thesica-на-скан-3-2026-09-14»). Правила читання: розділи з документами ≤ 15 %; вступ і висновки окремо (нове завдання); файл A ≤ 10 %, B ≤ 20 %; similarity B ≤ 14 %; C не сканується.
