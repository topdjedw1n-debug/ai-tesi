# Рецепт «2–4 документи під питання розділу, рамка як інше завдання» — доказ за $0 (14.09.2026, пізній вечір)

Дозвіл фаундера: «Ну давай, подивимось чи ми щось зрозуміли, в тебе так. Роби. Але роби через кабінет, а не через сервер». Зміни описані в [S2-FULL-TEXT-EVIDENCE §15](../../../../plans/S2-FULL-TEXT-EVIDENCE-2026-09-14.md). Тут — сухий прогін нового коду на записі ранкової A з недійсним ключем: усе до першого живого виклику виконується штатно, сам виклик відхиляється (401), тобто запит складено і надіслано, грошей не витрачено.

Команда: `s4_lab.py …/A/fresh-A-fulltext-job16-recording.json.gz OUT --job-id 16 --variant dry-recipe-A --mode live --cost-cap-usd 0.5 --secrets-file bogus.env --live-sections 1 --recorded-outline --recorded-sections --allow-host '*'` → [dry-recipe-A-report.json](dry-recipe-A-report.json): `live.calls[0]` = S4 §1, `AuthenticationError 401`, витрати 0.

## Що показав прогін

1. **Порядок письма.** Розділи 2–13 (тіло) взято зі стрічки в новому порядку, потім живий §1 Introduzione; §14 Conclusioni стояв би після нього. Запит §1: `previous_summaries` порожній, `chapter_material` = 12 готових розділів (43 809 символів) у порядку плану, докази — 3 заплановані джерела (уривки), правило рамки в промпті дослівно:
   > This section frames the whole work; it is written LAST from chapter_material (the finished chapters) as an answer to the research question. State the question and answer it with the chapters' concrete findings, evidence and limits, citing the same [KEY] markers and pages the chapters cite. Do not describe the structure of the work, do not announce what each chapter does, do not summarise chapter by chapter, do not discuss the sources as a corpus.
2. **Документи під питання розділу.** Той самий пакет A (12 відкритих PDF), новий відбір: жоден предметний розділ не лишився без вікон (попередження `section_without_documents` — 0). Розділи 2, 3 і 5, які вранці писалися з анотацій (0 вікон → AI 0 / 36 / 27 %), тепер отримують 14–25 вікон із документів, що покривають їхні власні слова:

| § | Розділ | Вікна раніше (fresh-A) | AI раніше | Документи з вікнами тепер | Вікна тепер | Символи | Додані поза планом |
|---|---|---|---|---|---|---|---|
| 1 | Introduzione | 0 | 42.3 | 0 | 0 | 1657 | — |
| 2 | Quadro teorico del marketing digitale | 0 | 0.0 | 2 | 25 | 20159 | K3382bcbd, K35b7b833 |
| 3 | Evoluzione dal marketing tradizionale al | 0 | 35.9 | 1 | 14 | 12097 | K3382bcbd |
| 4 | Strumenti e canali del marketing digital | 19 | 0.0 | 3 | 26 | 20894 | K3382bcbd, Kd1a8a0c1 |
| 5 | Il marketing digitale nelle piccole e me | 0 | 27.2 | 2 | 24 | 22499 | K3382bcbd, K837f79b2 |
| 6 | Social media e customer loyalty nelle PM | 26 | 0.0 | 3 | 26 | 20825 | K3382bcbd |
| 7 | Il ruolo dei social media nelle strategi | 23 | 0.0 | 4 | 24 | 20219 | K3382bcbd, Kd1a8a0c1 |
| 8 | Concetti di fidelizzazione e customer en | 25 | 11.4 | 2 | 25 | 21106 | — |
| 9 | Social media come leva di fidelizzazione | 25 | 12.5 | 2 | 25 | 20348 | — |
| 10 | Analisi di casi ed evidenze empiriche | 24 | 0.0 | 4 | 24 | 19720 | Kd1a8a0c1, K2e093c0b |
| 11 | Metodologia di analisi | 5 | 0.0 | 3 | 10 | 8356 | K2f4230e3 |
| 12 | Casi di studio di PMI italiane | 27 | 0.0 | 4 | 27 | 19560 | Kd1a8a0c1 |
| 13 | Discussione dei risultati | 24 | 13.5 | 4 | 23 | 21046 | Kd1a8a0c1, K2f4230e3 |

   Ключі з «*» у звіті — документи поза планом S3, допущені гейтом на власних словах розділу (той самий поріг, що для завантажень).

## Межі доказу
Це доказ складання запитів і відбору, не результату: текстів новий писар тут не писав. Результат покажуть три роботи через кабінет (економіка, право, інформатика), кожна з одним сканом.
