# AI-generated methods review (ChatGPT), not an independent review

## Track C: the language-model eligibility extractor, locked plan v3

| | |
|---|---|
| Date | 12 November 2026 |
| Reviewer | ChatGPT (OpenAI), prompted by the platform owner with `chatgpt_track_c_review_prompt` (main session scratch; the questions are in the review's own numbering) |
| Repository read | `astridcmarin/marlo-scientific`, commit `8643929` (the reviewer's statement) |
| Blind data | The reviewer was told not to ask for or look for the 200-trial annotation or sample, and states it did not access them. |

The review is reproduced as received, then how each finding was handled.

---

I reviewed the specified files and scorer dependencies at commit [`8643929`](https://github.com/astridcmarin/marlo-scientific/tree/864392903f7a8de90253ababfbc8bc2788fab0d7), without accessing the blind sample or annotations. **I found no demonstrated leakage, but several weaknesses limit what a passing result would establish.** “Invalidates” below distinguishes loss of blindness from limits on interpretation.

1. **High — Blindness depends on an undocumented information barrier.**  
   **Files/sections:** `eligibility_validation_plan_v3.json`, `prespecification_note`, `order_of_events`, `extractor.session_rules`.  
   The prompt was frozen after 46 trials had been annotated. That is compatible with blind development **if nobody developing it received those trials, annotations, error patterns or informal feedback**. The development record and public lock commit support the stated sequence; they cannot verify private workspace history. Running and scoring v1.1 before the LLM also creates an avoidable opportunity for results to reach the LLM operator.  
   **Suggestion:** Retain a dated statement identifying who saw what; keep rule-based results inaccessible to LLM sessions and operators until both outputs are pinned. Verify workspace memory, project files and inherited instructions are absent. **Actual test-informed prompt changes, output selection or coaching would invalidate the blind comparison. The event order alone does not.**

2. **Medium — Development is plausible, but not independently auditable from scores alone.**  
   **Files/sections:** `docs/development/eligibility_llm_c1_development.json`, `revisions`; plan v3, `development`.  
   Two revisions, stored output hashes and an explicit already-seen dataset make the account credible as a documented claim. They do not establish that these were the only attempts or that sessions lacked other context. The development labels also follow guide v1, whose comparator conventions differ from the test target. High direction-free scores cannot demonstrate correct eligible-side interpretation.  
   **Suggestion:** Preserve complete development transcripts, attempted revisions and selection rationale. Treat direction-free scores strictly as diagnostics. **Not independently invalidating.**

3. **Medium — Fair comparison of frozen systems, not equal training conditions.**  
   **Files/sections:** plan v2, `procedure.development`; plan v3, `development` and `comparison_with_v1_1`.  
   v1.1 used both development datasets; the LLM prompt used the 120-trial set, but the underlying model may have encountered registry texts during training. Trial-level separation also does not exclude near-identical eligibility templates across development and test trials. Neither advantage can be quantified here.  
   **Suggestion:** Describe this as a comparison of two particular frozen extraction workflows. For a later test, audit template overlap and include a temporal holdout of newly published or revised criteria. **These limitations do not invalidate the present operational comparison; they preclude claims about unseen-text generalisation or inherent superiority of either method.**

4. **High — The reported “precision” is an unusual hybrid metric.**  
   **Files/sections:** plan v2, `scoring`; `eligibility_validation_v2.py::score_pair`; `eligibility_validation.py::summarise`.  
   Suppose gold contains two thresholds and the extractor returns one correctly. The pair contributes **FN only**, with neither TP nor FP. Its prediction therefore disappears from the precision denominator. Returning both gold thresholds plus one extra instead contributes **FP only**. This is neither conventional threshold-level precision/recall nor conventional pair-level classification precision/recall. It can favour different omission and over-extraction behaviours.  
   **Suggestion:** Keep the locked calculation, but label it explicitly as the prespecified pair-based metric. In a later version add threshold-level matching and exact-set accuracy with transparent denominators. **This does not invalidate execution of the locked test; interpreting its precision as the fraction of extracted thresholds that are correct would be invalid.**

5. **High — Matching does not establish preservation of eligibility meaning.**  
   **Files/sections:** `eligibility_validation_v2.py::score_pair`; prompt, “Status” and “Leave out”.  
   Matching ignores cohort assignment, qualifiers, AND/OR relationships, source sentence and kidney equation. It also does not require the extracted `stated`/`multiple` status to agree with gold. Correct numbers can therefore pass despite being assigned to the wrong cohort or losing an exception. The two-way `any` matching also permits duplicate values without penalty.  
   **Suggestion:** Limit current claims to comparator/value/unit extraction under this simplified target. Later, score cohort–threshold links, exception handling, logical alternatives and source support separately. **Not invalid for the narrow target; insufficient for claims of faithful eligibility interpretation.**

6. **Medium — The pass rule is a release gate, not evidence of comparative superiority.**  
   **Files/sections:** plan v2, `decision_rule`; plan v3, `comparison_with_v1_1`; `eligibility_validation_llm.py::paired`.  
   Thirty annotated-positive pairs is a floor, not assurance of precise estimates. Wilson intervals assume independent observations; shared trial templates can weaken that assumption. Eight separate type decisions also do not constitute simultaneous 95% assurance. Agreement between discordant-pair counts and pass decisions is not a statistical superiority test.  
   **Suggestion:** Report all counts, intervals and metric differences. For later confirmatory comparisons, prespecify a meaningful improvement margin and paired uncertainty analysis, accounting for trial/template dependence and multiple types. **Not invalidating, provided superiority remains unclaimed.**

7. **High — One annotator leaves reference error unresolved.**  
   **Files/sections:** plan v2, `procedure.annotation` and `second_annotation`; annotation guide, disease definitions, exceptions and `unclear`.  
   Self-review cannot measure reproducibility. The hardest distinctions—diagnostic versus entry thresholds, exceptions versus cohorts, and negation—are also places where one reader’s convention could systematically favour an extractor. Excluding `unclear` cases further limits conclusions about difficult text.  
   **Suggestion:** Preserve the original locked reference and report exclusions by type. For a later version, independently double-annotate a random subset plus difficult strata, report status and threshold agreement, and adjudicate without extractor identities. Add error categories for direction, number, unit, omission, hallucination, cohort, exception and disease-definition errors. **The current test remains valid against this annotator’s reading, not an established gold standard.**

8. **High — Two chat runs measure limited repeatability, not reproducibility.**  
   **Files/sections:** plan v3, `extractor`, `run_to_run_agreement`; `eligibility_validation_llm.py::agreement` and `run_check`.  
   A model’s self-reported identifier does not verify its backend version. Fresh sessions may still inherit workspace context. Forty trials per session introduce position and context-length effects. Agreement can also be high because both runs say `not_stated`, including shared invalid-output fallbacks.  
   **Suggestion:** Record complete transcripts, operator instructions, visible model selection, timestamps, workspace/memory/tool settings, input hashes and order, raw outputs, truncations, retries and every manual intervention. Report positive-case agreement and invalid-output rates separately. **Two runs suffice for a limited repeatability check. Hidden context, selective retries or edited answers would invalidate the claimed frozen workflow.**

9. **Medium — The prompt is not fully equivalent to the guide.**  
   **Files/sections:** prompt, “Report every threshold”, “Status”, “Leave out”, “Output”; guide, “Units” and “Common situations”.  
   Concrete discrepancies or ambiguities:
   - The prompt extends unnumbered “within normal limits” → `≤ 1 × ULN` to **creatinine and AST/ALT**; the guide explicitly provides that convention only for bilirubin.
   - “Report every threshold” conflicts with the three-value cap; no selection rule handles four or more.
   - Disease-defining thresholds versus thresholds required for entry remain difficult to distinguish operationally.
   - “One threshold applies to all” conflicts literally with the exception rule.
   - “With ‘or’ … report each” appears under **Leave out**.
   - The prompt requests a bare eight-key object, while ingestion expects `{nct_id, answer}` JSONL records; the wrapping instruction is outside the frozen prompt.
   
   **Suggestion:** Preserve these behaviours for this test and disclose them. Harmonise examples, truncation rules and the complete output contract in a later version. **They limit target consistency but do not alone invalidate the current test.**

10. **Medium — Failure handling is incompletely implemented and can conceal failures.**  
    **Files/sections:** `eligibility_extractor_llm.py::load_outputs`, `parse_record`, `check_entry`; `eligibility_validation_llm.py::score_run`.  
    Malformed outer JSONL raises an exception rather than becoming the promised no-answer record. One invalid type discards all eight types; on gold-negative types that fallback earns TN credit. Source segments may be absent and are not checked against input. The LLM error report stores outcome flags without the annotated/extracted values needed to diagnose errors directly.  
    **Suggestion:** Retain untouched outputs and separately report transport, formatting and extraction failures. Any necessary execution repair should be documented as a deviation, without changing substantive answers or selecting retries. Improve validation and error records in the next version. **Undisclosed manual repair or outcome-dependent rerunning would invalidate the affected result.**

A **meaningful result** would be a practically substantial improvement on the same blinded reference, with transparent paired errors, acceptable absolute performance, similar behaviour across both runs, and fewer important direction/unit/cohort mistakes. A pass/fail difference alone, high overall agreement, or direction-free development scores would be **over-interpreted** as evidence of superiority, generalisation beyond these multiple-myeloma registry texts, or clinical suitability.

---

## Handling (12 November 2026, approved by the platform owner)

Each claim about code was checked in the main session against `intelligence_store/eligibility_validation_v2.py`, `eligibility_validation.py`, `eligibility_extractor_llm.py`, the frozen prompt and guide v2.

| # | Checked | Handling |
|---|---|---|
| 1 | The order of events is as described: extractor v1.1 is scored before the language-model runs (plan v3, `order_of_events`). The sessions receive only the prompt and an input file of trial texts. | A written run procedure, committed before any run (`docs/ELIGIBILITY_LLM_EXTRACTOR.md`, "Run procedure"): isolated folder, one fixed launch message, no other operator messages, v1.1 results never placed where a session can read them. Plan unchanged. |
| 2 | Correct: the development record shows two revisions and stored output hashes; it cannot prove there were no other attempts. | Stated in the report. Development transcripts are not available for revisions 1-2; from now on transcripts are kept (run procedure). |
| 3 | Correct. | The report describes a comparison of two frozen workflows on these registry texts; no claim of generalisation or superiority. Template overlap and a temporal holdout go to plan v4. |
| 4 | **Confirmed** in `score_pair`: a pair with gold {a, b} and extraction {a} is FN only (no TP, no FP), so the correct value does not enter precision; {a, b, c} is FP only. The same rule scores extractor v1.1, so the comparison is like for like. | The report calls it "the prespecified pair-based precision and recall" and says what it is not (the share of extracted thresholds that are correct). Threshold-level and exact-set measures go to plan v4. |
| 5 | **Confirmed**: matching uses comparator, value and unit only; status (`stated` against `multiple`), cohort, qualifier and source sentence are not compared. | Claims are limited to comparator, value and unit extraction. Cohort links and exception handling go to plan v4. |
| 6 | Correct. | All counts, intervals and differences are reported; no superiority is claimed from pass/fail differences. A prespecified margin and paired analysis go to plan v4. |
| 7 | Correct: one annotator, self-review only. | The report says results are agreement with the owner's reading. Independent double annotation of a random subset and hard strata goes to plan v4. |
| 8 | Correct. | Run procedure records, for every session: transcript, its SHA-256, launch time, the identifier the session reports, input file hash, raw output, invalid-output count, and any retry with its reason. Agreement is reported on positive cases separately. |
| 9 | **Confirmed** for the first point: the prompt (line 27) applies "within normal limits" = `<=` 1 × ULN to bilirubin, creatinine and AST/ALT; guide v2 states it for bilirubin only. The other points (the three-value cap against "report every threshold"; "or" under "Leave out"; the bare object against the `{nct_id, answer}` line) are also as described. | Prompt frozen; not changed. The report names the "within normal limits" difference as a possible source of disagreement on creatinine and AST/ALT that comes from the prompt, not the reading. The prompt is brought in line with the guide in plan v4. |
| 10 | **Confirmed**: `load_outputs` calls `json.loads` on each line, so a malformed line stops the scoring; `parse_record` turns any invalid type into "no answer" for all eight types. True negatives do not enter the pass rule; on positive types the fallback counts as misses. | Run procedure: output files are kept untouched; if a line is malformed, the trial is recorded as no answer and the handling is reported as a deviation, with no answer edited and no rerun chosen by outcome. Separate transport, format and extraction failure counts go into the report. Fixed in plan v4's runner. |

**Invalidating?** None of the findings, as checked, invalidates the locked test. What would: a prompt change informed by test results, coaching of a session, selective reruns or edited answers. The run procedure rules these out in writing.
