# Consultation #10 — Thesica: the same psychology brief went from 6/20 to 7/14 on the copies-and-judgment version. What now, before touching anything frozen?

You are an independent reviewer (Astra and Grok are asked in parallel; you do not see each other's answer). The founder's instruction after the second scan: "Давай консультуйся" — consult before any change to the frozen writer/frame/plan rules or to the judgment. Answer in the order of the questions at the end. Facts first, Fable's reading marked separately; challenge the framing if you think it is wrong.

## Goal and constraints (canon, unchanged)
- `docs/AGENT_SYNC.md`, block `founder-priority-2026-09-09`: platform first (a manager alone reaches a DOCX); delivery bar similarity ≤ 10 % AND AI ≤ 10 % on the exact final DOCX, no human rewriting, content accepted after an editor's reading; 15 % AI / 14 % similarity = "continue the series"; a failure means analysis of the recording, not an automatic paid retry.
- Frozen: S4 rules2-B text, plan v2, frame (body → conclusions → introduction, `FRAME_RULE` in `writer_rules.py`), plan check, quote budget. Consultations #6–#9: no new writer or plan rule sentences, no model change, no mandatory PDFs, no browser/TLS workarounds, no stop after S2.
- Delivered 17.09 (consultation #9 → commits 2–3 + three hotfixes, server `99d6aee`): copies of the same record (all OpenAlex locations, `works/doi:` for Crossref records, tries in order until a text layer); frame titles with a comma; the section exam ignores the topic's own words; **the document judgment** (`app/services/topic_judgment.py`): fetched full texts whose topic share lies in [0.5, 0.9) are judged once by Haiku 4.5 (lowest first, ≤ 12 per run, not counted against the call ceiling): `allow` / `reject` / `uncertain` with `population_match` and `scope_ids`; `reject` → the document keeps its abstract and hands no pages on any path; anything else changes nothing. Calibrated on 41 documents ($0.75): every known off-topic text rejected; same-field texts on another question rejected with editor-like reasons (`docs/evidence/MATERIAL-FIX-2026-09-16/judge-2026-09-17/README.md`).

## The two files of the same brief (psychology, master's, 20 pages, no manager PDFs)
| | doc26 (morning, `90a678f`) | doc30 (evening, `99d6aee`) |
|---|---|---|
| Full texts with pages | 8 of 22 links | **15 of 36** (copies) |
| Judgment | — | 8 judged, **4 rejected** (child sexual exploitation, psychological ownership, youth radicalisation, cyberbullying prevention at school); none handed pages |
| Loosely admitted | — | "Salute mentale e Brain-Mind Capital" (35 p, `allow`, `scope-2, scope-5`, reason: "defines psychological well-being according to WHO and discusses measurement dimensions") → pages in **6 sections**; "Social media use, loneliness and psychological distress in emerging adults" (43 p, share ≥ 0.9, not judged) → 5 sections |
| Sections on abstracts only | 1.3, 4.1 | only 5 (Discussione) |
| Frame | intro last; conclusions with a comma **not** frame | intro last; "Conclusioni" frame |
| **Scan** | similarity 6 / **AI 20** | similarity 7 / **AI 14**, quotes < 1 % |
| Body (subsections) | 22.6 % | **12.6 %** |
| Intro / discussion / conclusions | 0 / 22 / 48 | 24 / 29 / 42 |

Per section, AI % doc26 → doc30 and what handed pages in doc30 (`docs/evidence/CABINET-PSICOLOGIA-2-2026-09-17/README.md`, `PSY2-doc30-material-analysis.txt`):
- 2.1 Confronto sociale **49 → 0** (Self-comparison with influencers 6 w, Valkenburg 6 w, Cureus review, loneliness paper; clean lines cite Moreno-Padilla ×9, Tiggemann ×4)
- 2.3 Autostima **63 → 0** (Valkenburg 6 w first, PSMU survey, Cureus; clean lines cite Valkenburg ×11)
- 3.3 Sonno **14 → 0** (nighttime-use review 18 w) · 4.4 Famiglia **18 → 0** (Genitori in corso 9 w, EU Kids Online, transmedia literacy) · 3.2 PSMU 0 → 0 · 4.1 Regolazione 0 → 0
- 3.1 FoMO 35 → 14 (nighttime review 4 w, loneliness paper 10 w, Brain-Mind Capital 12 w by wording; the FoMO papers stay abstracts — SSRN 403) · 4.2 Fattori protettivi 34 → 16 · 4.3 Scuola 29 → 13
- **1.3 Misure del benessere 0 → 44** (Brain-Mind Capital 14 w as `support`, Genitori in corso 8 w; flagged lines cite Brogonzoli: "la salute mentale non è la mera assenza di disturbi, ma un «equilibrio dinamico»…"; clean lines cite Businaro, an abstract-only Italian source)
- **1.2 Modelli teorici 14 → 34** (Brain-Mind Capital 17 w, EU Kids Online 4 w; flagged lines carry no citations: generic construct prose about SMUM motives)
- **2.2 Immagine corporea 30 → 31** despite Self-comparison 18 w as the only full text; flagged lines cite abstract-only sources (Nerini 2009 SATAQ-3 subscales, Gesto), clean lines cite Stefanile/Gesto abstracts too
- Intro 0 → 24: both intros received ~22 document windows (tier `windows`); doc30's flagged lines paraphrase the Cureus review (Khalaf: "undici studi… associazione modesta ma significativa… causalità incerta")
- Conclusioni 48 → 42 although now a frame section written from the body's findings: flagged lines = "relazione mediata e moderata, non un effetto diretto", "il 92 % dei teenager si connette ogni giorno" (Scolari), limits and future research
- 5 Discussione 22 → 29: no full-text documents (abstract excerpts only), flagged lines summarise conditional effects

Other facts: quotes 0 %; top source 12 % of citations (the sleep review); S6 review PASS with citation-rendering glitches ("in (Autore, anno) (p. N)" ×5, "p. 3); p. 9"); three failed attempts before the successful run were all defects of the new code caught only live (unregistered warning code; judge calls exhausting the pre-outline call ceiling; PDF parsing on the event loop starving the heartbeat) — fixed with tests (`9a70eec`, `99c18b2`, `99d6aee`), ≈ $0.18.

## Fable's reading (not established)
1. Second confirmation on six sections: pages about the section's own question → 0 %; pages about an adjacent question → 30–44 %. The judgment removed the foreign texts but **admitted an adjacent one "for definitions"**, and that text fed six sections; the two sections where it led rose to 34–44 %.
2. Prose written from abstracts of several sources (dense summaries) is flagged even when pages of the specific source exist (2.2); prose with page-level specifics from one or two sources is not.
3. The frame parts and the discussion (≈ 1 500 words at ~30 %) now weigh ≈ 6 of the 14.7 points. The comma fix was a defect but not the cause of the conclusions' AI (E2 and biology conclusions scored 0 with the same rule); the introduction's 24 % appeared when it paraphrased a review's findings instead of the body's.
4. Stability is not proven: one file per version, no repeat scan; the judgment is a model call and differs between runs (cyberbullying-at-school: allow in calibration, reject live).

## Candidates on the table (none implemented; all touch the judgment or the frozen frame/evidence path)
A. **Judgment stricter on "adjacent, admitted for definitions"**: e.g., `allow` with `population_match: false` and no node of the section in `scope_ids` → the document's pages do not reach subject sections (only sections whose node it names), or a fourth verdict "definitions only" → abstract/excerpt only. Deterministic use of the verdict already recorded.
B. **Introduction without document windows**: the frame writes the introduction last from the findings; today it also receives ~22 windows of documents (tier `windows`, by wording) and in doc30 paraphrased a review instead. Remove windows for frame sections (evidence path, not the rule text) — or keep them.
C. **Conclusions/discussion meta prose** (42–48 % conclusions in both psychology files; discussion 22–29 %): any change is a change to the frozen frame or plan; alternatives: accept as the master's genre and let the editor judge; or a narrowly scoped evidence-side change (e.g., the discussion receives the body's page-cited facts instead of abstract excerpts).
D. **Abstract excerpts beside pages**: when a section has enough page windows, keep the abstract excerpts of other planned sources for citation only (shorter) so that the writer builds facts from pages (2.2 case). Evidence composition, not a rule sentence.
E. Do nothing more on the frozen parts; run the series on real orders on the current version and gather two or three more files before any change.

## Questions (answer in this order)
1. **Direction.** Given 6/20 → 7/14 on the same brief, is continuing on this version the right call, and which of A–E (or none) is the single most needed change now? What would you explicitly not do? Is the reading (pages about the section's question protect; adjacent pages and abstract-built prose are flagged; frame/discussion ≈ 6 points) supported by the two files, or over-read?
2. **Judgment (A).** Is admitting adjacent texts "for definitions" a defect of the prompt, of the verdict use, or acceptable? If you change it: exact rule, $0 proof on the recorded verdicts of doc30 and the 41 calibration documents, risk to biology/economics recipes (calibration: Haiku rejected 4 tangential economics-1 texts and 1 biology text in the band).
3. **Frame (B, C).** Is B a rule change or an evidence-path change? Would you do it now, and how to prove it at $0 on the recordings (the introduction's prompt is recorded)? For C: change, accept, or wait for more files — and what evidence would settle it?
4. **Abstracts beside pages (D).** Worth testing? The smallest deterministic rule and its $0 proof.
5. **Confirmation and the live-order rule.** After the chosen change: rerun this brief once more, or move to real orders? And what does Tanya's manager do with a psychology-like order on the current version (7/14)?

Be concrete; name files or stages only if you know them. No new writer or plan rule sentences, no model change, no browser/TLS workarounds, no lab runs of the old works.

## Files you may read (repository root, read-only)
- `docs/evidence/CABINET-PSICOLOGIA-2-2026-09-17/README.md` (doc30: run, material, scan per section), `PSY2-doc30-material-analysis.txt`, `persection-PSY2.json`; `docs/evidence/CABINET-PSICOLOGIA-2026-09-17/README.md` (doc26).
- `docs/evidence/MATERIAL-FIX-2026-09-16/judge-2026-09-17/README.md` (calibration), `docs/evidence/QUALITY-AI-2026-09-13/step2-full-inputs/consult9-2026-09-17/README.md`, `docs/plans/MATERIAL-FIX-2026-09-16.md`.
- Code: `apps/api/app/services/topic_judgment.py`, `apps/api/app/services/full_text_sources.py` (`section_evidence`, tiers `support`/`windows`, budgets), `apps/api/app/services/section_material.py` (frame, `writing_order`, `frame_rule`), `apps/api/app/services/executor_v2/sections.py` (what a frame section receives), `apps/api/app/services/writer_rules.py` (read the frame rule; do not propose changing its text), `apps/api/app/services/plan_check.py`.
- Canon: `docs/AGENT_SYNC.md` (state paragraph of 16–17.09).
