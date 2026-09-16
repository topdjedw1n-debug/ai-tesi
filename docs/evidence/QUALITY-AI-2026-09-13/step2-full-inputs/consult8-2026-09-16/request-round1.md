# Consultation #8 — Thesica: the material behind the writing. Round 1: your solution first

You are an independent reviewer. The founder's instruction for this consultation: "Go to Astra and Grok with the fixes. Tell them the situation and first listen to their decisions. Then propose yours, and then find together the best and most needed solution and its implementation." This is round 1: I describe the situation and the evidence and ask what you would do. My own proposals come in round 2, after your answer, so that they do not anchor you.

## Goal and constraints (canon, 16.09.2026)
- Platform first: a manager alone reaches a DOCX; delivery bar similarity ≤ 10 % AND AI ≤ 10 % on the exact final DOCX; no human rewriting; content accepted by the agency (Tanya) after an editor's reading. Verification of sources is the system's job.
- The writer is frozen (S4 rules2-B text, plan v2, framing rules, plan check, no legal-window cap, quote budget); consultations #6–#7b: no new writer/plan rule sentences, no lab runs of the same law work, no model change, no mandatory PDFs as policy.
- Founder today: "We need to fix this [weak material], but without harming what we built in terms of AI and plagiarism, and aim for stable results." The next real order from Tanya can arrive any time; every code change must be provable at $0 on recorded runs before a paid run.

## What happened today (all on the same frozen writer, all through the cabinet, no manager PDFs)
| Work | Level | Sources with full text | Full texts on topic | Body sections written on abstracts only | Compilatio similarity / AI |
|---|---|---|---|---|---|
| Economics A2 (digital marketing, SMEs), 16.09 morning | bachelor | 9/17 | 9 | 0 | 3 % / 3 % |
| Economics E2 (SME credit and fintech), 16.09 evening | master | 6/16 | 1 | 6 of 13 | 6 % / 8 % |
| Biology (antibiotic resistance), 16.09 evening | bachelor | 10/20 | 8 | 1 of 11 | 5 % / <1 % |

Three files in a row under the bar on three disciplines. The detector is not the problem any more. The problem is what the writer is given:

1. **Full texts are refused by publishers.** Of the open-access links found by Crossref/OpenAlex, 10/16 (economics) and 9/20 (biology) answered HTTP 403: ScienceDirect (JavaScript challenge page), SSRN, MDPI, Sage, Wiley, ASM, OECD iLibrary and three Italian university repositories (handle.net → Cloudflare-style block). I re-tested from my Mac: plain browser headers → 403; a Chrome-impersonating TLS client (curl_cffi) → 0/20 PDFs (MDPI returns 200 with a 2 kB HTML stub). Unpaywall's best_oa_location points to the same publisher URLs. Alternatives checked at $0: Europe PMC has full text for 5/20 (all biology, none of economics); OpenAlex lists a repository copy with a pdf_url for 7/20 (not tested for reachability). So the system reads whatever does not block, which is not the same as what is relevant.
2. **Off-topic full texts pass into the pack and become the main material.** In E2 the only large readable text was a 348-page book on cyber-risk regulation in banking; it received 47 of 208 in-text citations, and the S6 reviewer flagged the mismatch. In biology two off-topic Italian theses (HIV integrase; a hyaluronic-acid ester) were fetched; one was offered as material in two sections (not cited in the end). The selection score of the evidence windows does not separate them: the cyber-risk book scored 0.32–1.16 across five sections, the on-topic fintech review 0.72–1.13 (score = term overlap between windows and the section's queries). The on-topic record filter passed the book because its title mentions the banking market.
3. **Sections without material are written on abstracts.** E2: P2P lending, crowdfunding, minibond, complementarity, costs, discussion — six sections; no source about crowdfunding or minibond exists in the pack at all. The detector scored those sections 0–28 % (mean 7.9 % vs 1.8 % with documents), so the price is mostly content, not AI.
4. **The master's introduction "about the work"** (research question, objectives, methodology) scored 50 % AI in E2, while the bachelor's introductions written from a fact scored 0 % (A2, biology). The frame writes the introduction last from the findings; the master's structure invites meta-text.
5. What an editor would see but the detector does not: a methodology section that describes other studies' methods (A2); 47 citations to a book off topic (E2); the same opening sentence three times (E2).

## What the system already has (so you do not propose it again)
- S2: topic-anchored queries per subject subsection (Crossref, OpenAlex, Semantic Scholar with visible failures), on-topic filter on title/abstract, verification of every candidate, full-text fetch of open-access links with a plain HTTP client, per-section evidence windows (round-robin, character budgets), warnings `section_without_documents`, `plan_material_gap`, `source_full_text_unavailable`, shown to the manager in words on the work page.
- S3 plan check: a primary document leads each subject section; case sections without a case source are flagged.
- S4 writer frozen; S5 renders and verifies citations; S6 advisory review.
- Recorded runs of all three works (packs, windows, full-text pages, section texts) — any change can be replayed at $0.

## Questions for round 1 (answer in this order)
1. **Direction.** Given the goal (stable ≤10/≤10 with content an editor accepts, without touching the writer), what is the single most needed change now, and why that one? What would you explicitly not do?
2. **Your solution** for each of the three material problems (blocked full texts; off-topic full texts dominating; sections with no material), with the mechanism, the cheapest proof at $0 on the recorded runs, and the risk to the AI/similarity results we have.
3. **The master's introduction at 50 %**: is it worth a change now, and if so where (frame, plan, or leave to the editor)?
4. **Operational rule for Tanya's real orders** meanwhile: what should the manager do when the pack shows sections without documents?

Be concrete; name files or stages only if you know them. Do not propose new writer rule sentences, model changes, or lab runs of the same works. I will send round 2 with my proposals and your answers.

## Files you may read (repository root is your working directory, read-only)
- Evidence of today's three runs: `docs/evidence/QUALITY-AI-2026-09-13/step2-full-inputs/s2-topic-anchored-2026-09-16/README.md` (economics A2), `docs/evidence/CABINET-ECONOMIA-2-2026-09-16/README.md` (E2: pack, full texts, per-section scan, the 403 diagnosis), `docs/evidence/CABINET-BIOLOGIA-2026-09-16/README.md` (biology).
- Code of the material path: `apps/api/app/services/executor_v2/sources.py` (S2), `apps/api/app/services/search_queries.py` (topic-anchored queries and the on-topic filter), `apps/api/app/services/full_text_sources.py` (open-access fetch, per-section evidence windows and their score), `apps/api/app/services/plan_check.py` (S3 plan check), `apps/api/app/services/executor_v2/sections.py` (S4 call; do not propose changing `writer_rules.py`).
- Canon: `docs/AGENT_SYNC.md` (block `founder-priority-2026-09-09`, state of 16.09), `docs/plans/IDLE-SESSION-2026-09-16.md`.
