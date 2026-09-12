# Humanize: source-grounded editor and similarity repair

Date: 2026-09-08. Author: Codex research subagent `similarity_design`.
Status: RESEARCH / PROPOSED DESIGN; no implementation, production changes, paid generations, or Compilatio submissions performed by this subagent.

## Decision

Keep the existing `HUMANIZER_ENABLED=False`. A useful experiment is a small automatic academic editing stage that fixes identified writing or source-use defects, preserves evidence, and is evaluated against the unchanged writer output. Re-enabling the existing detector-score rescue is not a sufficient implementation.

For the current document №7, the locally recorded result is **3% similarity and 47% AI**, with 15 insufficiently supported claims and no accepted content/no-rewrite review. A high plagiarism percentage is not the observed issue in that case. These facts were read in `docs/AGENT_SYNC.md` §19 and `THESICA-PLAN.md`; this subagent did not independently read the live database or authenticate the original Compilatio report.

The current user request authorizes renewed investigation of Humanize. This report evaluates that request; it does not silently change the older disabled-by-default policy, final thresholds, or the production state. The engineering experiment should retain the product requirement: Compilatio similarity ≤10% and AI ≤10% on the exact final DOCX, accepted academic quality, and no human content rewriting.

## 1. What high similarity actually means

Compilatio measures matching content, including potentially legitimate quotations and references; a human must determine the nature of the match. Its score is not independently a finding of plagiarism. [Compilatio: correctly cited sources](https://support.compilatio.net/hc/en-us/articles/115005919629-Why-does-a-correctly-cited-source-appear-in-the-analysis-report), [Compilatio: similarity interpretation](https://support.compilatio.net/hc/en-us/articles/115005893725-How-to-interpret-the-similarity-score-colour-and-percentage-of-an-analysed-document).

Therefore a high number must first be classified. The action depends on the source and the passage, not simply on the percentage.

| Match class | Correct action | What an editor must preserve |
|---|---|---|
| Same work's earlier checked draft | Confirm the source's document name/code and version lineage; handle the verified self-match under a recorded evaluation policy. Do not rewrite an otherwise acceptable passage to disguise the duplicate. | Original report, matching source ID, prior artifact hash, exclusion reason, before/after report settings. |
| Bibliography, required title, named instrument, technical term, prescribed template | Check whether the institution's/report's preset legitimately excludes it. Keep necessary scholarly information. | Exact titles, authors, identifiers, references, instrument names. |
| Exact quotation with correct attribution | Keep it if the exact wording matters. Otherwise choose an accurately attributed summary as an editorial decision. | Exact quoted words, quotation boundaries, locator and source association. |
| Exact or near-copy with absent/wrong attribution | Identify the actual source and whether the claim is needed; add valid attribution and either quote accurately or write an independently structured, source-grounded explanation. | Meaning, ownership of the idea, scope, numerical facts, uncertainty. |
| Patchwriting: source sentence order and structure with synonym substitutions | Rebuild the paragraph from the research question and evidence notes; compare sources where they actually offer comparable evidence. | What each source actually says, agreement/disagreement and limitations. |
| Translated borrowing | Treat the original-language source as a source, verify it, and attribute it. | Meaning and attribution across languages. |
| False association or inaccessible matching source | Review context and secondary sources; mark unresolved rather than invent a citation or claim the match is harmless. | Uncertainty and access limitation. |

Compilatio explicitly documents that an already analyzed document can produce a 100% match. Its procedure is to inspect the primary source name/code to identify a previous version; a confirmed source belonging to that same work can then be ignored in the analysis. This is a measurement correction with a visible reason, not a text improvement. The FAQ does not justify ignoring somebody else's work or unrelated earlier work. [Compilatio: 100% similarity](https://support.compilatio.net/hc/fr/articles/360000415509-Quand-obtient-on-un-taux-de-similitudes-de-100).

Indexing settings also matter. Magister/Magister+ use reference libraries containing submitted documents; their database inclusion is configurable. Studium and Magister compare against different collections, so their results are not interchangeable baselines. [Compilatio: document database](https://support.compilatio.net/hc/en-us/articles/360000736009-Add-or-Not-My-Documents-to-the-Compilatio-Magister-Database), [Compilatio: product differences](https://support.compilatio.net/hc/en-us/articles/360009829177-Why-do-the-similarities-differ-between-Studium-and-Magister-for-the-same-document).

**Proposed measurement rule:** store the original score, evaluated score, included comparison sources, and every exclusion. Preset exclusions must be identical in baseline and candidate. Never exclude sources automatically until a target percentage is reached. `AGENT_SYNC` specifies ≤10%, but does not yet define a sufficiently detailed raw-versus-adjusted report policy; this is an explicit unresolved protocol choice, not permission to reinterpret a failed result.

## 2. Why sentence paraphrasing alone is inadequate

Changing wording can reduce literal overlap while retaining an unsupported argument or hiding the origin of an idea. Correct paraphrasing still needs attribution. Source material should serve the paper's own question and argument; summaries should represent the source accurately and not merely reproduce every point in its order. [Harvard: summarizing, paraphrasing, quoting](https://usingsources.fas.harvard.edu/summarizing-paraphrasing-and-quoting).

The useful unit is usually the **paragraph's claim and evidence**, not each individual sentence. A synthesis should explain how relevant sources relate to a question, including their differences, evidence strength, and limits. Do not force two citations into every paragraph: a definition or a specific study result can correctly depend on one source. Distinguish the document's analysis from borrowed findings. [Harvard: integrating sources](https://usingsources.fas.harvard.edu/integrating-sources-0), [Harvard: integrating source material into the argument](https://usingsources.fas.harvard.edu/nuts-bolts-integrating-0).

In a proposed editor, sensible repairs include reducing empty transitions, repeated claims, inflated phrasing, unsupported generalizations, and paragraphs that list sources without explaining their relevance. None of these is a verified universal signal of AI authorship. They are quality defects that can be assessed directly. Their effect on Compilatio AI scores remains a hypothesis to test.

Compilatio's documented advanced comparison can identify paraphrasing and translations for user-added sources, including Italian. Ordinary rewriting is therefore not a guarantee of lower similarity. [Compilatio: source comparison](https://support.compilatio.net/hc/en-us/articles/115005903225-What-do-the-detected-sources-mean-primary-accidental-ignored).

## 3. Existing Thesica contract and the insertion point

Read-only code findings from the current working tree:

- `apps/api/tests/release_profile.py`: strict citation verification, blocking claim verification, citation freezing, and disabled humanizer are explicit profile values.
- `apps/api/app/services/ai_pipeline/generator.py`: the optional humanizer operates on section content. Canonical source markers already exist; reuse this source identity system rather than invent another citation format.
- `apps/api/app/services/ai_pipeline/citation_freezer.py`: citations and quotes of at least ten words are replaced with placeholders. `all_present()` checks existence only, not duplicate count, unknown placeholders, or whether a citation still supports the adjoining claim. Short direct quotes are unprotected.
- `apps/api/app/services/ai_pipeline/humanizer.py`: `humanize_multi_pass()` ranks candidates by the AI checker's score; `humanize()` can return the original text on an exception or preservation failure. A caller must distinguish unchanged/rejected/unavailable from an applied successful edit.
- `apps/api/app/services/claim_verification_stage.py`: `verify_section_claims()` checks candidate section text. `run_claim_verification_stage()` then **aggregates previously accepted section verdicts without a new LLM pass**. Editing after that accepted section check makes the old verdict stale.
- `apps/api/app/services/release_policy.py`: the policy is `agency-docx-2026-09-04`, detector is Compilatio, threshold is 10.0, and required artifact format is DOCX. Missing or incomplete evidence stays `no_data`; a manual `passed` does not override >10%.
- `apps/api/app/services/production_case_service.py`: `_artifact_binding()` uses document ID, format, storage path, completion timestamp, and exact artifact SHA-256; changed evidence revokes release. Both external results and the content review must concern the same current artifact. A recorded human rewrite cannot be erased by later accepting that generation.

**Insertion:** edit the source-grounded draft **before** its final grammar, citation, claim, and academic-quality checks, and before final DOCX export/freeze. If an edit happens after any such check, invalidate that check and run it again on the edited content. Existing aggregate-only verification is not a substitute.

Keep generation jobs, usage accounting, storage, citation keys, evidence ledger, and release/download logic. The first experiment needs no new microservice, external humanizer vendor, automatic Compilatio integration, or manager workflow redesign.

## 4. Minimal proposed pipeline

### Step A — Pin the inputs and assess the defect

Pin the task/outline contract, source-pack digest, draft hash, writer model and prompt version, and any supplied source passages. Assign stable section/paragraph IDs for a candidate diff.

Create a concise defect list: paragraph ID, defect class, evidence, and intended outcome. A missing research method or a weak master's-level discussion belongs to the writer/requirements fix (M1-Q01); a cosmetic editor cannot supply a research method that was never performed. An empty defect list means an explicit `unchanged` result and no paid editing call.

For similarity remediation, attach the actual matching passage and matching source identity. A document-level percentage without matched spans is insufficient for targeted similarity repair.

### Step B — Build the paragraph evidence packet

Use existing source IDs and retrieved evidence. For each edited factual assertion retain:

```text
claim_id, paragraph_id, source_key, source_excerpt_or_locator,
source_evidence_digest, population/context, numbers/units/dates,
direction_of_effect, certainty/limitations, quote_if_any
```

Not every field must become a new database column; a versioned provenance payload can carry the first experimental contract. If only an abstract is available, do not pretend to have checked a detailed full-text finding or page-specific quote. Narrow the claim to what is supported, obtain suitable evidence through the existing source workflow, or stop that repair as `insufficient_evidence`.

### Step C — One scoped editorial pass

Give the model the paragraph purpose, relevant evidence packet, adjacent context, and only the identified changes. Permit a reorganized explanation or synthesis when warranted. Keep the required outline and academic register.

Protect exact quotations of **all lengths**, references, citation identities, technical names, numbers, dates, units, and evidence limitations. Preserving a factual item means preserving its meaning and relation to its source, not merely preserving a token somewhere in the result. If the original fact is wrong, route it to an explicit evidence correction with a documented old/new claim; do not silently edit it as style.

Return one candidate plus a structured change list and remaining unresolved defects. No invented results, fake first-person experience, random errors, character substitutions, translation loops, or added padding. These operations do not solve an academic-quality defect and can corrupt the artifact.

Use one explicit editor model/version and record actual usage. Do not silently replace the writer. Start with one attempt per selected paragraph/section and no recursive detector-score search. A rejected candidate leaves the original intact and records why.

### Step D — Validate before accepting the candidate

Deterministic checks:

1. Every protected item has the expected multiplicity; no missing, duplicated, unknown, or leaked placeholder.
2. Direct quotes match their source passages exactly; quote attribution and locator survive.
3. No new unresolvable source keys; bibliography membership corresponds to citations actually used.
4. Numbers, units, named entities, dates, and negation/qualifier changes are detected for semantic review.
5. Target language, section structure, completeness, and reasonable length are preserved; truncation is a hard failure.

Semantic checks against the source packet, with an independent reviewer where available:

1. The changed claim is supported by its cited source, with the original population, strength, and limitations intact.
2. Citation anchors refer to the intended claims. A marker's presence alone is not sufficient.
3. The candidate fixes the declared defect and does not create factual, logical, citation, or academic-level regressions.
4. The passage remains useful in the full section; removed repetition does not remove a necessary distinction or limitation.

Re-run the existing grammar, citation, claim, and academic-quality checks on the actual accepted candidate. Bind each stored verdict to at least the generation ID and verified content digest. Record `applied`, `unchanged`, `rejected`, `insufficient_evidence`, and provider failures distinctly. Do not record an applied success when the helper returned its original input.

### Step E — Export and use the unchanged final gate

Export the entire work to DOCX, inspect the rendered pages and extracted text, and freeze its exact bytes. Only then attach the full-document Compilatio reports and manager review to that hash. Preserve the existing ≤10/≤10 rule and no-human-rewrite requirement.

If a later Compilatio report identifies a real fixable defect, preserve that original failed artifact and report. A new machine-edited candidate is a distinct recorded version with its own checks, DOCX hash, and release decision. Reuse existing durable job/storage/version mechanisms where sufficient; do not overwrite the historical failure. A first experiment can do this offline without creating a new product workflow.

## 5. Stop criteria

Stop and retain the failure when any of the following holds:

- No actual source evidence supports the intended repair, or a material source is inaccessible.
- Attribution, quote fidelity, factual meaning, or academic completeness becomes worse.
- The model drops/duplicates content, introduces unsupported claims, or changes language.
- The declared quality defect is not improved by the one allowed candidate. Do not repeat the same input automatically.
- A required provider/check is unavailable or its result cannot be bound to the candidate bytes.
- The final Compilatio score is >10 in either dimension, its report is missing/mismatched, or the manager rejects the content/no-rewrite review.
- High similarity is dominated by correctly required quotations or fixed material that cannot be reduced without harming the task; report the conflict rather than weakening the gate or distorting the work.

An AI score dropping while similarity rises above 10 is a failure. Both scores dropping while evidence or readable academic quality degrades is also a failure. Humanize cannot be called successful merely because text changed, a model call completed, or a local proxy score fell.

## 6. Meaningful verification and comparison

### Offline engineering fixtures — no paid providers

Use fixed source packets and mocked editor outputs. Test the result, not just the implementation's chosen thresholds:

| Mutation or scenario | Required result |
|---|---|
| Citation retained but moved from claim A to unrelated claim B | Reject by claim/source verification. |
| Duplicate known placeholder, unknown placeholder, or leftover sentinel | Reject before restore/export. |
| Seven-word direct quote changes one word | Reject exact-quote mismatch. |
| `associated with` becomes `causes`; `not significant` loses negation | Reject unsupported strengthening. |
| Sample/population, 12%/21%, date, dose/unit or CI bounds change | Flag and reject unless explicit source-grounded correction is separately approved by the verifier. |
| Two studies with different designs become a fabricated pooled result | Reject; synthesis cannot invent an analysis. |
| Claim needs full-text evidence but only an abstract is provided | `insufficient_evidence`; no fabricated supporting quote. |
| Provider error or discarded candidate returns the original | Record failure/unchanged appropriately; no false `applied`. |
| High match comes from an authenticated earlier draft | Classify self-match and record provenance; no prose mutation. |
| Baseline report differs in product, exclusions, or comparison sources | Refuse a claimed paired improvement. |
| Text edit occurs after an accepted section verdict | Old grammar/claim/quality proof is invalid; export waits for candidate checks. |
| DOCX changes after 10/10 reports and accepted review | Existing release revoked; historical reports cannot authorize new bytes. |

Pure local overlap checks (for example, unquoted matching spans against available source passages) can flag copied prose. They cannot reproduce Compilatio's corpus, AI model, or final score. Test this distinction in the report labels.

### Small paid experiment — proposed only

First fix the already diagnosed DOCX/academic-level defects (M0-12 and M1-Q01), so the comparison does not reward hiding a weak base document. Then compare:

- **A:** the fixed writer with the same frozen brief and source pack, no editor.
- **B:** exactly A's draft plus the one-pass editor described above.

Use three different Italian 10–20-page tasks as a first internal feasibility check, including source synthesis and genuine quotations. This is a small pilot, not statistical proof. Historical Humanize artifacts can form a failure reference set; the old pipeline need not incur fresh paid runs merely to reproduce known defects. A diagnostic existing №7 pair can precede the three tasks, but cannot by itself prove all supported task types or master's-level completeness.

For each pair record both complete candidate files, hashes, source/brief versions, every attempt and rejection, model/prompt/usage, whole-document word and rendered-page counts, full source checks, blinded academic-quality review, human intervention, and both Compilatio scores. Keep failed and unchanged candidates in the denominator.

Primary decision: whether the editor produces more **fully accepted works without human rewriting** and fixes the predeclared defects without evidence/quality regressions. Report cost per accepted work including failed attempts and manager handling effort. A lower AI median is a secondary observation, not the sole objective.

Compilatio states that even the same document's AI result can vary because of file extraction, probabilistic analysis, and detector updates. Freeze file format, product, settings, and the compared source collection; record scan date/version if available. Any repeated scans must be specified before looking at results, applied symmetrically, and all reported. Never select the lowest repeated score as the official outcome. [Compilatio: AI result variability](https://support.compilatio.net/hc/en-us/articles/37785891417105-Why-Do-AI-Results-Vary-Between-Analyses).

Engineering advancement requires the mutation and artifact-binding tests to pass. Production activation additionally needs observed full-document passes and an independent review of the change. The existing M1 requirement remains three consecutive complete passes on different tasks; a research score or a short paragraph comparison does not satisfy it.

## 7. Open evidence gaps and concrete next step

Unknown from this subtask: original №7 Compilatio full report and highlighted spans; actual Compilatio product, exclusion/indexing settings, detector version; current live runtime state; how much each proposed quality edit changes Italian detector outcomes. No source establishes that a general Humanize pass will reliably reach ≤10% AI on Thesica's long documents.

Prepare the existing №7 artifact/report pair as the first diagnostic bundle, classify its highlighted spans and the 15 unsupported claims, and finish the already diagnosed M0-12/M1-Q01 defects. In parallel, implement only the offline editor contract/negative fixtures as an isolated experimental harness. The reviewable result should be a paired candidate and complete evidence, followed by a decision on any paid full-document experiment and eventual activation under the user's existing authorization.

No production setting was changed in this research. Only this report was created by `similarity_design`.
