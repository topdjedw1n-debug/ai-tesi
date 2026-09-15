# Consultation #5 — Thesica (thesis-writing platform), reading of the three-discipline run and the next step

You are consulted as an independent reviewer. Answer in this order: (1) DIRECTION — is my proposed next step the right one now, or should the approach change / be postponed; challenge the framing, assumptions and scope, not only the technique; (2) TECHNICAL CORRECTNESS of what I propose, separately; (3) the SMALLEST SUFFICIENT next step and how to verify it. You may object to everything, including the goal reading. Facts first, my proposal is marked as a proposal at the end.

## Goal and stage (canon)

- Product: managers of a thesis agency enter requirements, the system finds sources and writes the thesis (Italian), managers deliver a DOCX. Acceptance for delivery: Compilatio on the exact final DOCX with similarity ≤ 10 % AND AI-detection ≤ 10 %, no human rewriting of content.
- Founder's priority since 09.09.2026: a working platform first (generation completes to DOCX); the 10/10 bar is the goal, not the current gate. Reviewers judge direction before patch correctness.
- Stage goal agreed at consultation #4 (yesterday, you both took part): confirm on three disciplines (law B with 14 manager PDFs, economics A auto-search only, informatics C auto-search only) that the writing rules developed on B carry over; gate: no full texts in subject sections → do not run/scan; failure rules: intro/conclusions ≥ 35 % AI, law similarity ≥ 20 %, quotes > 12 % or unquoted flagged sentences > 20 %, fabrications/bare keys/wrong years; not a failure: file 11–15 % with body < 10 %; two levels: 15/14 (continue a short series) and 10/10 (delivery); 3/3 → short series, 2/3 → stop and analyse.

## What was done tonight (facts)

Release with all rules (primary evidence per discipline in the plan; ≤ 3 excerpt windows per legal document; "state what the norm provides in your own words and own order, never follow the source's sentence order"; quotes ≤ 1 per paragraph, < 20 words, quoted words < 10 % of the section; conclusions written before the introduction; introduction opens on a fact and cites ≥ 4 findings, shorter than conclusions; S5 flags bare keys / decision-year mismatch / pages out of range) was activated on the production server. Three works were created and started through the manager cabinet, run one after another by the server queue.

### B — law, 30 pages, magistrale, 14 manager PDFs (statute art. 4/8, d.lgs. 151/2015, Codice privacy art. 114, GDPR articles, 4 Cassazione decisions, 2 Garante provisions, 2 ECtHR judgments, 1 doctrinal article)
- $2.80, 21 sections, 11,959 words, quotes 0.6 % of words. Pack: 14 PDFs + 15 OpenAlex + 11 Crossref; 5 open-access full texts fetched. Every section got 3–4 full-text documents (8–23 windows); writing order body → conclusions → introduction worked; intro opens on a fact; no warnings for pages/years/quotes; no fabricated decisions (all numbers from the PDFs; two precedent numbers quoted from inside Cassazione texts).
- Compilatio (founder uploaded the file as .txt, 12,685 words): **similarity 16 %, AI 17 %, quoted < 1 %.**
- Per section (AI % / similarity %): intro **0.0** / 0.0; §2 original art. 4 10.9 / 17.7; §3 23.6 / 19.2; §4 Jobs Act 39.8 / 16.2; §5 26.3 / 22.0; §6 EU framework 26.3 / 2.0; §7 GDPR principles 40.9 / 17.8; §8 legal bases 13.8 / 10.5; §9 roles (titolare/responsabile/DPO) **66.4** / 0.0; §10 GDPR–Codice coordination 0.0 / 19.8; §11 work tools vs control tools 27.2 / 20.8; §12 video surveillance 10.9 / 25.6; §13 internet/e-mail 0.0 / 29.0; §14 GPS 0.0 / 20.1; §15 smart working 0.0 / 6.5; §16 DPIA 13.1 / 4.1; §17 Cassazione 0.0 / 12.0; §18 ECtHR 22.5 / 0.0; §19 Garante provisions 11.7 / **37.3**; §20 guidelines 21.7 / 19.6; conclusions 13.8 / 10.3.
- Body (19 sections): AI 18.1 % (median 13.8), similarity 16.3 %. "Cases and acts" sections (7): AI 9.8 %; "system/explanatory" sections (12): 23.6 %. 18.2 % of sentences flagged (almost no quotes, so this is the unquoted rate). Similarity comes from 12+ web sources at 2–3 % each (theses, sites paraphrasing Garante/Jobs Act) — close paraphrase of norms and Garante acts, not copying from one source.
- Reading by the consult-4 rules: no failure rule fires (tail 0/14 < 35; similarity 16 < 20; quotes 0.5 < 12; unquoted 18 < 20; no fabrications). Level 15/14 not reached (17/16). 10/10 not reached.

### The same B in four versions (same brief and PDFs)

| version | sim | AI | quotes | body AI | intro | concl | systems / cases |
|---|---|---|---|---|---|---|---|
| recipe 14.09 (cabinet, 4 docs per section, no quote budget) | 20 | 22 | 21 % | 18.5 | 40.7 | 28.7 | — |
| rules-B 15.09 (lab, plan + writer rules, no quote budget) | 24 | 12 | 33 % | 8.3 | 26 | 12 | 9.6 / 7.5 |
| rules2-B 15.09 (lab, + quote budget ≤ 10 %/section) | 17 | 11 | 5 % | 7.8 | 34 | 20 | 14.0 / 4.2 |
| cabinet 15.09 (tonight: + ≤3 windows per legal doc, norm in own words, discipline plan, live S2) | 16 | 17 | 0.5 % | 18.1 | 0 | 13.8 | 23.6 / 9.8 |

What changed between rules2-B and tonight: (1) ≤ 3 windows per legal document and "norm in own words, own order" (quotes 5 → 0.5 %); (2) plan rules per discipline, 21 sections instead of 18; (3) live source search (different pack, 5 OA texts, catalogue 429s) instead of the recorded pack; (4) another run (detector noise on identical text was ±10 points in earlier calibration). My reading: the frame is fixed (intro 0, conclusions 14 — both new rules worked), but the body went back to 18 % through the explanatory sections (§9 66, §7 41, §4 40): restating a norm in one's own words yields exactly the explanatory genre the detector flags, and similarity did not drop (Garante 37, e-mail 29, video 26) — close paraphrase stays close paraphrase. The version with short norm quotations (rules2-B, 5 % quotes) had body 7.8 %. Astra objected yesterday to MAX_LEGAL_WINDOWS = 3; I kept it.

### A — economics, 20 pages, triennale, no manager PDFs (auto-search only)
- $1.81, 14 sections, 6,996 words, quotes 0.5 %. Pack: 40 sources (20 Crossref, 20 OpenAlex, 0 Semantic Scholar — 65 search queries to Semantic Scholar ended in HTTP 429 after retries); 11 open-access full texts. The pack is mostly off-topic: "Valutazione della ricerca", "Lessico: insegnarlo e impararlo", "Tortura e razzismo", "Copper complexes of synthetic peptides", "Repertori dei movimenti ecclesiali", six records titled "Introduzione", "Obiettivi e metodi della ricerca"…
- Root cause visible in S1/S2: the scope tree's search terms for structural nodes are topic-less ("introduzione", "obiettivi della ricerca", "metodologia", "selezione dei casi", "evidenze empiriche", "discussione dei risultati", "bibliografia", "riferimenti APA") and sub-node terms lack the topic ("engagement", "best practice", "case selection"); S2 sends each node's terms_local, terms_en and title as three queries to Semantic Scholar, Crossref and OpenAlex as they are, including intro/conclusions/bibliography nodes. Crossref's query.bibliographic on such phrases returns anything.
- What the sections actually used: the only relevant full text ("PMI Marketing: business model for a digital-marketing startup for Tuscan tourism SMEs", 113 pp.) in §2–§6; §7 and §13 no documents; §8 an education paper on "tone analysis"; §9–§12 corporate museums, travel-agency websites, "support teachers", "contratto di rete". The intro starts with tourism; §8 retells a Spanish master's thesis on BSH white goods with Spanish words leaking. Gate failed (7 of 12 subject sections without relevant full text) → not scanned.

### C — informatics, 25 pages, triennale, no manager PDFs
- Pack: 40 sources, all Crossref; OpenAlex answered 429 on 274 of 274 calls that hour, Semantic Scholar 56 final failures, arXiv 81 timeouts; zero full texts; titles include "Eschilo e Pindaro", "insonnia", "sistemi arborei da frutto", "Introduzione", "6 Conclusioni"; ≈ 8 relevant abstracts. Gate failed → generation cancelled through the cabinet after the plan ($0.33).

### Catalogue throttling (all day, one server IP)
Yesterday three parallel works produced thousands of 429 retries; today a process-wide shared limiter was active (Crossref 5 rps, OpenAlex 5 rps, Semantic Scholar 1 rps with API key, arXiv 0.33 rps) and works ran one at a time, yet: Crossref 429 on a share of calls (the verifier sent no mailto → anonymous pool; fixed in a local commit, not deployed), Semantic Scholar 429 on roughly a third of search queries even at 1 rps with a key, OpenAlex 429 on 100 % of calls in the evening (daily quota or IP block?). Manager PDFs made B immune to this; A and C were not.

Money tonight: $4.94 of ≈ $8 authorised; one scan of three.

## What I conclude (my reading, open to objection)

1. The writing-rule work has reached the point where the frame is solved and the body of a law thesis sits at 8–18 % depending on how norms are handled; the last change (≤3 windows + own words) looks like a step back on AI for explanatory sections with no similarity gain, but it is confounded by a different pack and detector noise.
2. Transfer to other disciplines was not tested at all, because auto-search without manager PDFs fails before writing: topic-less queries + structural nodes searched + catalogue throttling. This is upstream of every writing rule and blocks the "working platform" goal more than the 10/10 bar does: a manager who does not upload PDFs gets an off-topic thesis.

## My proposal (a proposal, not a decision)

A. Stop scanning B variants for now. Fix source provisioning first (S1/S2, $0 model cost, offline-testable on recorded scope trees): do not search structural nodes (introduction, conclusions, bibliography, methodology, discussion); anchor every query to the topic core (topic terms + node terms); require a topic-relevance match on title/abstract before verification; keep manager PDFs as the primary evidence when present. Deploy the polite-pool mailto; lower Semantic Scholar to 0.5 rps and OpenAlex to 2 rps in the server environment; consider an OpenAlex API key and a pause between works.
B. On the writer: revert only the "norm in own words, never follow the source order" sentence to the rules2-B regime (short quotations of the operative words of a norm allowed within the ≤ 10 % quote budget), keep ≤3 windows per legal document and everything else. Verify on the recorded cabinet pack of B in the lab (same pack, same plan, one scan, ≈ $2.7) only after A is done, so that the next three-discipline run tests both.
C. Until S2 is fixed, tell managers that PDFs of the primary sources are required for every discipline (not optional), because the platform cannot yet find them reliably.

Questions: Is A the right first move given "working platform first", or should the writer regression (B) be settled first since law with PDFs is the only path that currently produces deliverable text? Is the reading of the B regression (own-words rule → explanatory genre) sound or is it noise? What is the smallest verification for the S2 fix that does not need paid generations (I can replay recorded scope trees against the live catalogues at $0)? Anything in the proposal that is premature or unnecessary?
