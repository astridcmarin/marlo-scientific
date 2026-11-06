# Repository checkpoint — 6 November 2026

**Verified tree:** branch `batch-2` at `fa73bfd`, 6 commits on top of `main` after PR #113. Applied on the owner's Mac from the git bundle `batch-2-backup-3.bundle`. CI runs when the batch's pull request is opened.
**Machine-readable record:** [`verification/repository_checkpoint_2026-11-06.json`](../verification/repository_checkpoint_2026-11-06.json).
**Previous checkpoint:** 5 November, in [`history/`](REPOSITORY_CHECKPOINT_2026-11-05.md) (batch 1: 1,283 tests passing; CI passed on PR #113, which the owner merged).

This is a software and repository verification. It does not validate any model scientifically, and it is not a clinical-readiness review.

## What was delivered since the previous checkpoint (batch 2)

| Area | What | Main files |
|---|---|---|
| Extraction review round 3 | 113 entries in a queue of their own, at `/models/extraction-review/round-3`; pages read the review status | `extraction_review_queue_round3_v2.json`, `scripts/build_review_round_3.py`, `extraction_review.round_3_view` |
| Label kidney doses and exposure (R9) | Exposure on each band's reduced dose relative to the reference, from Bridoux 2016, CC-5013-PK-001 (scaled by dose) and the sponsor's simulation; descriptive | `renal_dose_exposure.py`, `renal_dose_exposure_panel.html` |
| The label's 82% | Shown to be a weaker lower bound than the 85% 2.0e uses; planned re-check dropped | `SIMULATION_2_RENAL_PATHWAYS.md` |
| Credibility records | Context v3: pathway model after 2.0e, bortezomib disagreements; plan lists completed from the dataset ledger | `model_credibility_context_v3.json`, `credibility_records.plan_files` |
| Model analysis report (M3) | First report in ICH M15 Appendix 2 order: the kidney pathway model | `model_analysis_report.py`, `/models/lenalidomide_renal_pathways_2026/report` |
| Liver-function classifications (H2) | FDA September 2026 draft hepatic guidance (NCI ODWG, Child–Pugh) beside the label's definitions | `hepatic_classifications.py`, `fda_hepatic_impairment_guidance_2026_draft_v1.json` |

## Checks

| Check | Result |
|---|---|
| Unit tests | **Pass,** as reported by the owner on the Mac at this tree ("all good"); the count was not pasted. The suite defines 1,310 test methods. CI will give the count on the pull request. |
| Compile all modules | **Pass.** |
| Migration chain | **Unchanged.** 9 revisions. |
| Pinned data | **Pass.** 173 data files outside `curation/`; 172 match a checksum in a module, test or pinned plan. The exception is the observation template, unpinned by design. `docs/DATA_FILES.md` is current. |
| Locked plans and reports | **Pass.** No new check in batch 2; 27 locked checks. |
| Validation flags | **Pass.** None set to true. |
| Repository hygiene | **Pass.** No source PDFs, guidances or correspondence tracked. |

## Findings

1. **A stale credibility record.** The kidney pathway model's record still stated that renal elimination falls faster than in proportion to kidney function, which 2.0e had shown is not established, and listed two of its four plans. The bortezomib records understated their disagreements. All were corrected in context v3. Plan lists now come partly from the dataset ledger, so a new check's plan cannot be left out again.
2. **The 82% question is closed without a check.** Both figures are lower bounds on absorption, so the higher one binds.
3. **The guidance extracts came from web text.** Both FDA guidances (renal 2024, hepatic draft 2026) were read from text returned by a web-fetch tool, not from PDFs in the owner's folder; the hepatic tables came back flattened and their reading is marked as the assistant's. **Gate:** round 3, with the PDFs saved locally.

## Scientific state

- 27 locked checks, 3 blind. Reviewer's checklist for lenalidomide: 19 of 29 answered, 8 partly, 2 gaps (O7 exposure–efficacy, M8 independent review).
- Lenalidomide: Hughes and Kim under-predict moderate and severe kidney impairment in two studies; the pathway model's moderate and severe results depend on bioavailability. On the label's reduced doses, observed myeloma exposure is about 1.0 to 1.3 times the normal-function reference (Bridoux 2016; descriptive).
- No model is validated for clinical prediction.

## Remaining gates

- **This batch:** push `batch-2`, open one pull request, let CI run; the owner merges with "Create a merge commit".
- **Owner work:** extraction review round 3 (113 entries); the v2 eligibility annotation.
- **Independent review:** none yet.
- **Authors:** Hughes, Kim, Iwasaki (unchanged).
- **Platform:** accounts and deployment.
