# AI-generated methods review (ChatGPT), not an independent review

## The two blind eligibility results (v1.1 and Track C)

| | |
|---|---|
| Date | 13 November 2026 |
| Reviewer | ChatGPT (OpenAI), prompted by the platform owner |
| Repository read | `astridcmarin/marlo-scientific`, branch `batch-11`, commit `b55ff5e` (the reviewer's statement) |

The review is reproduced as received, then how each finding was handled.

---

Reviewed `batch-11` at commit `b55ff5e`. The largest weakness is the reference-review design, rather than the stopped runs.

1. **Medium — Wording is mostly supported, but shared errors receive a one-sided interpretation.**  
   **Files/sections:** [ELIGIBILITY_LLM_EXTRACTOR.md — Result](https://github.com/astridcmarin/marlo-scientific/blob/b55ff5e/docs/ELIGIBILITY_LLM_EXTRACTOR.md#result-13-november-2026); [STATUS_BY_DRUG.md — Protocol benchmarking](https://github.com/astridcmarin/marlo-scientific/blob/b55ff5e/docs/STATUS_BY_DRUG.md#protocol-benchmarking-not-a-drug).

   The failure conclusions and descriptive comparisons are supported. However, “Errors two different methods share may come from the reference rather than from either method” privileges annotation error without evidence. Replace with: **“Shared disagreements may reflect annotation errors, ambiguous text, differences between the prompt and guide, or errors common to both extractors; their frequency does not distinguish these explanations.”**

   STATUS says: “Both extractors are wrong on the same 13-33 trials per type; an error review comes before any conclusion”. Replace with: **“Both extractors disagree with the reference on 13–33 trial-and-type pairs per type. Neither passes the original rule; reference review will support a separately reported sensitivity analysis.”**

   Also name the **prespecified pair-based measures** in STATUS: these are not conventional threshold-level precision and recall. The existing failed-test conclusion does not need to await review.

2. **Medium — Retry handling is defensible for extraction performance conditional on completion; operational reliability remains separate.**  
   **Files/sections:** `docs/development/eligibility_llm_c1_run_attempts.json`, attempts 1–3; `ELIGIBILITY_LLM_EXTRACTOR.md`, Run procedure §3–4.

   Fresh sessions, identical inputs, retention of partial outputs, and scoring the first complete output are reasonable **provided technical failure was identified independently of answer quality**. Retaining completed sessions 2–4 while rerunning only interrupted sessions 1 and 5 avoids unnecessary selection.

   Bias remains possible if completion depends on difficult inputs, available reasoning time, or changing backend conditions. The records describe account-wide usage limits, which reduces—but does not eliminate—that concern. Report completion failures and retry burden separately; do not interpret the completed-output result as first-attempt reliability. The public attempt record also lacks the full transcripts and transcript hashes promised by §3, so isolation and absence of coaching are not independently verifiable from these files. Preserve or publish a redacted audit bundle, including the recorded folder-isolation breach.

3. **High — Reviewing only shared failures can preferentially improve both scores.**  
   **Files/sections:** `intelligence_store/eligibility_shared_errors.py`, `build()` and `validate_record()`; `ELIGIBILITY_LLM_EXTRACTOR.md`, Shared errors.

   These 166 pairs were selected using both systems’ outcomes, and the review displays both outputs. Owner corrections therefore constitute **unblinded, outcome-selected reference revision**. Versioning alone does not remove that bias.

   Before further decisions, commit a dated reporting plan fixing: review scope; correction criteria under the existing guide; required source-text evidence; treatment of ambiguity; adjudication; and reporting of every correction and exclusion. Do not retrospectively change guide conventions to match predictions. Keep the original analysis primary and unchanged; label rescoring **post hoc corrected-reference sensitivity analysis**, applying the same frozen outputs, scorer and pass thresholds to both systems. Show original and corrected results side by side, including denominator changes and pass/fail transitions. Any review already completed must be disclosed as preceding this plan.

4. **Medium — Repeatability is meaningful, but incompletely reported and narrower than “answers” suggests.**  
   **Files/sections:** `docs/verification/eligibility_validation_llm_c1.json`, `run_to_run_agreement`; `intelligence_store/eligibility_validation_llm.py`, `_key()` and `agreement()`.

   I recalculated from the pinned outputs using the implemented agreement definition:

   | Subset | Agreement |
   |---|---:|
   | All pairs | 1,596/1,600 = **99.75%** |
   | Annotated stated/multiple | 658/661 = **99.55%** |
   | Annotated not stated | 932/933 = **99.89%** |
   | Either run returned a threshold | 684/688 = **99.42%** |

   Thus, empty answers inflate the headline, but do **not** explain away the high agreement. Publish these strata, per-type counts and all four disagreements—the positive-case analysis was explicitly promised. Clarify that agreement covers status/comparator/value/unit, excluding evidence, qualifiers and cohort links. One disagreement is equivalent ECOG notation (`<3` versus `≤2`). Two runs demonstrate limited repeatability, not accuracy or robustness across model versions.

5. **High — The next experiment should be independent annotation, before extractor revision.**  
   **Files/sections:** `eligibility_shared_errors.py`, review design; earlier Track C review, finding 7.

   Obtain a second qualified annotator’s independent reading of the frozen texts, blinded to owner labels, extractor outputs and error-selection status. Ideally cover all 200 trials; otherwise use a prespecified random sample plus separately reported difficult strata, including cases where both systems currently agree with the owner. Adjudicate disagreements only after independent labels are locked.

   This can reveal both false accusations against the extractors and errors all three currently share. Revising prompts or rules first would optimize against an uncertain reference and consume this dataset as development material; subsequent validation would then require a new holdout.

---

## Handling (13 November 2026, main session)

| # | Checked | Handling |
|---|---|---|
| 1 | Agreed. | The reviewer's wording is adopted in `docs/ELIGIBILITY_LLM_EXTRACTOR.md` (shared disagreements) and `docs/STATUS_BY_DRUG.md` (sensitivity analysis; pair-based measures named). The findings line `eligibility_llm_c1` (pinned, findings v6) carries the older wording until its next version; reworded in findings v7 (13 November 2026). |
| 2 | Agreed: failures were account-wide usage limits, not tied to trials; transcripts and their checksums were promised but not published. | `docs/development/eligibility_llm_c1_audit_v1.json` records the SHA-256 of all 22 session transcripts and of the bundle. The transcripts themselves are kept privately by the owner, because the session context in them includes personal contact details; they can be shown redacted on request. Completion is reported separately: 12 of 22 launched sessions stopped first; results are conditional on completion. |
| 3 | Agreed; the most important finding. | The owner's review of the 166 shared pairs is **paused** until a reporting plan is committed. Any decisions made before the plan will be disclosed as preceding it. The plan is drafted for the owner's approval. |
| 4 | **Confirmed exactly** by recomputing from the pinned outputs: 1,596/1,600; positive 658/661; not stated 932/933; either returned 684/688; four disagreements, one an equivalent ECOG notation. | Strata, per-type counts and the four disagreements are in the audit supplement; the Result section reports them and says what agreement compares. |
| 5 | Agreed. | Recorded as the recommended next experiment, before any prompt or rule revision: an independent second annotator, blind to the owner's labels, both outputs and the error selection. Who that can be is the owner's decision. |
