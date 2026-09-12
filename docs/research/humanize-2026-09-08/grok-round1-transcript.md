## User

# Humanize research consultation — 2026-09-08

The founder explicitly asks Codex (orchestrator), Fable and Grok to research together, delegate bounded subagents, challenge each other, establish why Humanize failed and how it should be implemented. This task authorizes research and consultation. Produce a research/design result; do not change runtime, code, thresholds, jobs, provider keys, git state, or production data. Do not launch thesis generation or detector submissions. Do not read .env, secrets or private customer content. Read-only repository files and public web research are allowed. Return the report in your response, not by writing files. You may delegate at most two independent read-only research subtasks if your toolset supports it; report actual delegation, never simulate collaborators.

Read /Users/maxmaxvel/.codex/skills/karpathy-guidelines/SKILL.md and docs/AGENT_SYNC.md first. The current request explicitly reopens research on Humanize despite the older disabled policy. It does not enable the production flag. Other agents are implementing M0-12 and M1-Q01 in this dirty checkout. Do not interfere.

Known repository snapshot: #7 is an Italian academic work; saved Compilatio similarity 3%, AI 47%; missing content/source acceptance and no-rewrite. Final acceptance requires <=10% similarity AND <=10% AI on identical final DOCX plus content/source quality, rendered pages, and no human content rewriting. No test or local detector proves that gate. Humanizer is disabled in the release profile and current day's recorded live settings.

Questions to resolve:
1. Distinguish source similarity, actual plagiarism, and AI classification. What can a legitimate academic editor fix in each? How to handle matching quotations, bibliography, standard phrases, genuine copied paraphrases, source synthesis and self-matches on repeated submissions?
2. Which AI signals are actually documented (perplexity, distribution, syntax, rhythm, repetition, stylometry)? Which are folklore? Give primary research and official detector sources with exact direct URLs. Assess Italian-language external validity and changes across detector versions. Do not claim secret Compilatio features are known.
3. Audit the existing apps/api/app/services/ai_pipeline/humanizer.py and related prompt_builder, quality_checker, orchestrator, stylometrics and historical docs/phase1-runs/HUMANIZATION-RESEARCH.md. Is there historical same-final-artifact PASS? What failed technically, what failed empirically, what is simply unknown?
4. Critically fact-check old claims: 'detector-in-loop is the winning method', 'universal transfer removes Compilatio risk', 'AuthorMist arXiv 2503.08716', and '87.9% reduction across eight detectors'. Check actual paper metadata and experiment conditions. A low GPTZero score cannot certify Compilatio.
5. Propose the smallest implementable evidence-preserving editor: immutable input, protected citations/quotes/numbers, verified source facts, targeted section revision, semantic and provenance revalidation, no regressions in academic quality, complete variant history, frozen DOCX and a fresh Compilatio report for that exact output. Discuss optional detector feedback as an experimental variable with bounded attempts, not the sole objective. Reject fake errors, invisible characters, transliteration tricks and fabricated facts/methods.
6. Give a controlled experiment separating improved writing prompts/model changes from editor effects, held-out topics, length/source parity, paired before/after full document reports, costs and stop criteria. Quantify how success is accepted without promising a score.

Output in Ukrainian, evidence-bounded and practical: confirmed / hypothesis / unknown; prioritized design; disagreements and what test resolves them. References inline. Clearly say which web pages you actually checked and which are unverified. No moralizing and no marketing claims. You are an independent reviewer: challenge the other proposed assumptions rather than agreeing automatically.

## Assistant

Починаю з обов’язкових документів і знімку репозиторію, далі перевірю код Humanize та первинні джерела без змін у runtime.

## Tools

- Read: /Users/maxmaxvel/.codex/skills/karpathy-guidelines/SKILL.md
- Read: /Users/maxmaxvel/AI TESI/docs/AGENT_SYNC.md
- Read: /Users/maxmaxvel/.grok/bundled/skills/long-running-background-tasks/SKILL.md

## Assistant

Читаю код Humanize і історичні документи, паралельно запускаю два незалежні read-only дослідження: аудит репозиторію та перевірку зовнішніх джерел.

## User

Продовжи дослідження і поверни завершений звіт за попереднім брифом. Перший запуск зупинився зі stopReason=cancelled після 2 turns; готового висновку немає. Використовуй лише доступні read-only та web tools. Якщо subagent недоступний, виконай незалежне дослідження сам, не зупиняйся. Не редагуй файлів. Власні нові знахідки Codex: old best-of-N оптимізує GPTZero, Compilatio не доведений; GPTZero офіційний FAQ каже, що perplexity/burstiness не використовує з осені 2023. Перевір і оскарж ці висновки за першоджерелами.

## Assistant

Продовжую самостійно: спочатку код і історичні документи, паралельно перевіряю першоджерела щодо GPTZero, AuthorMist і Compilatio.

## Tools

- Search: humanizer|HUMANIZER|humanize
- ListDir: apps/api/app/services/ai_pipeline
- ListDir: docs/phase1-runs
- WebFetch: https://arxiv.org/abs/2503.08716
- WebFetch: https://gptzero.me/faq

## Assistant

FAQ GPTZero не містить заяви про perplexity на цій сторінці — перевіряю інші офіційні URL і паралельно читаю humanizer.

## Tools

- Read: /Users/maxmaxvel/AI TESI/apps/api/app/services/ai_pipeline/humanizer.py
- Read: /Users/maxmaxvel/AI TESI/docs/phase1-runs/HUMANIZATION-RESEARCH.md
- Read: /Users/maxmaxvel/AI TESI/apps/api/app/services/ai_pipeline/stylometrics.py
- WebFetch: https://gptzero.me/news/perplexity-and-burstiness-in-ai-detection
- WebFetch: https://arxiv.org/pdf/2503.08716

## Assistant

У старій замітці вже є змішування AuthorMist і Adversarial Paraphrasing — зараз звіряю PDF, промпти, детектор і офіційні сторінки.

## Tools

- Read: /Users/maxmaxvel/.grok/sessions/%2FUsers%2Fmaxmaxvel%2FAI%20TESI/01a0814b-11b4-78c3-ad0b-e426e40224fd/downloads/1.pdf
- Search: build_humanization_prompt|humanize_multi_pass|HUMANIZER_ENABLED|GPTZero|ai_probability
- WebFetch: https://arxiv.org/abs/2506.07001
- WebFetch: https://compilatio.net/en/ai-detector
- WebFetch: https://gptzero.me/technology
- Read: /Users/maxmaxvel/.grok/sessions/%2FUsers%2Fmaxmaxvel%2FAI%20TESI/01a0814b-11b4-78c3-ad0b-e426e40224fd/downloads/1.pdf
- Read: /Users/maxmaxvel/AI TESI/docs/phase1-runs/MODEL-MATRIX-EXPERIMENT.md (361-450)
- Search: def build_humanization_prompt
- WebFetch: https://www.compilatio.net/en/ai-detector
- WebFetch: https://support.gptzero.me/hc/en-us/articles/15180402124791-What-is-perplexity-and-burstiness-and-how-does-GPTZero-use-them

## Assistant

Шукаю офіційну заяву GPTZero про perplexity і Compilatio щодо цитат, плюс проводжу аудит промпта та оркестратора.

## Tools

- WebFetch: https://gptzero.me/blog/perplexity-and-burstiness-what-is-it
- WebFetch: https://support.compilatio.net/hc/en-us/articles/17408769118993
- WebFetch: https://www.compilatio.net/en/similarities-detection-info
- Read: /Users/maxmaxvel/AI TESI/apps/api/app/services/ai_pipeline/prompt_builder.py (209-274)
- Read: /Users/maxmaxvel/AI TESI/apps/api/app/services/background_jobs.py (741-800)
- ListDir: docs/research/humanize-2026-09-08
- WebFetch: https://arxiv.org/abs/2602.13042
- WebFetch: https://support.compilatio.net/hc/en-us/articles/17407151992465-Does-the-Compilatio-AI-detector-detect-AI-corrected-and-reformulated-texts
- WebFetch: https://support.compilatio.net/hc/en-us/articles/115005893725
- WebFetch: https://arxiv.org/html/2506.07001v2
- Read: /Users/maxmaxvel/AI TESI/apps/api/app/core/config.py (81-130)
- Read: /Users/maxmaxvel/AI TESI/apps/api/app/services/ai_pipeline/citation_freezer.py (1-80)
- WebFetch: https://arxiv.org/html/2602.13042v1
- WebFetch: https://support.compilatio.net/hc/en-us/articles/115005904109
- WebFetch: https://support.compilatio.net/hc/en-us/articles/17435773405329
- WebFetch: https://arxiv.org/abs/2310.13606
- Search: quality_checker|QUALITY_MAX_AI
- Read: /Users/maxmaxvel/AI TESI/infra/docker/docker-compose.prod.yml (121-140)
- WebFetch: https://web.archive.org/web/20231115000000/https://gptzero.me/faq
- WebFetch: https://support.compilatio.net/hc/en-us/articles/115005893725
- Read: /Users/maxmaxvel/AI TESI/apps/api/app/core/config.py (141-160)
- Search: HUMANIZER_ENABLED
- Read: /Users/maxmaxvel/AI TESI/docs/phase1-runs/MODEL-MATRIX-EXPERIMENT.md (2-51)
- WebFetch: https://web.archive.org/web/20230901000000/https://gptzero.me/faq
- Read: /Users/maxmaxvel/AI TESI/apps/api/app/services/background_jobs.py (2289-2318)
- Read: /Users/maxmaxvel/AI TESI/docs/research/humanize-2026-09-08/codex-audit.md (1-80)

## Assistant

Перевіряю один технічний пункт Codex про порядок перевірок, щоб не повторити його сліпо.

## Tools

- Read: /Users/maxmaxvel/AI TESI/apps/api/app/services/background_jobs.py (2361-2560)
- Read: /Users/maxmaxvel/AI TESI/docs/phase1-runs/HANDOFF-2026-07-03.md (101-220)
