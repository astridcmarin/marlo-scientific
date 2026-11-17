# Repository checkpoint — 16 November 2026, end of batch 16

**Verified tree:** `main` at the merge of PR #127 (batch 16). This checkpoint covers batches 5 to 16, which were merged without one: the previous checkpoint is dated 10 November, eleven batches back, and the convention is one per batch. The gap is recorded rather than quietly closed.
**Machine-readable record:** [`verification/repository_checkpoint_2026-11-16.json`](verification/repository_checkpoint_2026-11-16.json).
**Previous checkpoint:** 10 November, end of batch 4, in [`history/`](history/REPOSITORY_CHECKPOINT_2026-11-10.md).

This is a software and repository verification. It does not validate any model scientifically, and it is not a clinical-readiness review.

## What was delivered (batches 5 to 16)

| Batch | PR | What |
|---|---|---|
| 5 | #117 | AI audit of user-facing wording; all 33 findings fixed, wording only |
| 6 | #118 | Track C and Track B plans locked; evidence index and evidence states; sex in the evidence |
| 7 | #119 | ICRP reference women and men; body-map anatomy fixes; the exposure–efficacy search (O7) |
| 8 | #120 | Body map 3D navigation and the foldable caution |
| 9 | #121 | Kidney anatomy (paths v4); Track B result; Track C review; F08 bootstrap uncertainty |
| 10 | #122 | Acceptance rule v2 (F03) and its lenalidomide result; Track B review page; handoff note |
| 11 | #123 | The two blind eligibility checks: extractor v1.1 and Track C, both failing every type |
| 12 | #124 | Eligibility reference re-reading plan, locked |
| 13 | #125 | Re-reading deviation; second-annotator plan; FDA second reading; Track G full texts; findings v7 |
| 15 | #126 | Handoff corrections; the reference re-reading result |
| 16 | #127 | Annotation guide v3; annotator B's record pinned; the second-annotation result |

Batch 14 was never pushed and is not recoverable: see "What was lost" below.

## Checks

| Check | Result |
|---|---|
| Unit tests | **Pass.** CI on PR #127: 1,450 tests. In a cloud session without the database packages, 1,430 collected and 300 database-backed errors by design. |
| Compile all modules | **Pass.** |
| Migration chain | **Unchanged.** 9 revisions. |
| Pinned data | **Pass.** 223 JSON data files in 147 families, 76 of them earlier versions kept unchanged because locked plans and reports cite them by checksum. |
| Locked checks | **32**, in findings v9. Of 60 ledger uses, 4 are blind and 2 blind with a recorded deviation. |
| Validation flags | **Pass.** No `clinical_prediction_validated` is true anywhere. |
| Repository hygiene | **Pass, with the previous checkpoint's wording corrected.** One source PDF is tracked on purpose: the EMA 2008 public assessment report, with its checksum in `landscape_ui/data/renal_pk/SHA256SUMS.json` and cited as the local copy by several pinned evidence files. No journal-article PDFs (`.gitignore` excludes one by name) and no correspondence are tracked. The 10 November line "No source PDFs … tracked" was inaccurate when written; the file predates it by many batches. |

## Findings

1. **The eligibility track reached its answer, and it is a recorded failure.** Both extractors failed their blind checks on all eight criterion types (#123). The owner's blind re-reading then corrected 108 of 215 items (#126), and an independent second reader agreed with the owner on 357 of 400 pairs, a bootstrap lower bound of 0.8475 against the plan's 0.90 bar (#127). The prespecified reading is that a one-reader reference is **not shown** adequate to judge an extractor at that bar.
2. **Anchoring was tested and not supported.** Every re-reading was locked before its own reveal, and agreement with the extractors falls across the session where drift would raise it.
3. **No learning curve in the reference.** Correction and disagreement rates are flat across the annotation order, which rules out repairing the reference by redoing the early trials.
4. **The ledger's blind gate rejected a wrong entry.** The second-annotation result was first recorded as `checked_blind`; the sample's values were seen on 12 November and the plan locked on 13 November, so the gate refused it. Reader blinding and dataset blindness are now distinguished in the use's step text.
5. **A handoff paragraph asserted work that did not exist.** `docs/HANDOFF.md` item 3 described the extended acceptance rule as locked and committed with ledger and findings updated. None of it was on `main`; the edit was made through the GitHub web editor and its commit message described work the diff did not contain (#126).
6. **Three extractor v1.1 defects are recorded with no effect on the current sample:** `/>` and `/<` read as strict comparators and five further forms dropped entirely, none of which occur in the 216 items; a bare "WNL" missed; and a true multi-cohort trial returning the first value only.

## What was lost

Batch 14 — the body-map update and the extended acceptance rule's plan and result for ixazomib and daratumumab — existed only in a cloud session's workspace and was never pushed. It is not in the owner's working copy, not in `supplemental-information/bundles/`, and not on GitHub. The narrative survives in `docs/HANDOFF.md` item 3's history, but a locked plan cannot be reconstructed from a description of its own results. The extended acceptance rule is therefore **not done** and needs a fresh locked plan.

From batch 17 a batch branch is pushed when its first commit exists, not when the batch is full, so an unpushed branch is never the only copy.

## Scientific state

- 32 locked checks: 2 passed, 2 consistent, 9 mixed, 6 disagree, 8 failed, 3 inconclusive, 2 not adopted. No model is validated for clinical prediction.
- Reviewer's checklist for lenalidomide (self-assessed): 2 gaps remain — O7 exposure–efficacy, which is a gap in the published evidence, and M8 independent review, which has never been done. AI reviews are not independent reviews.
- Of 27 datasets in the ledger, 24 have had their values seen. The three that have not are the Hughes, Gupta and Luo fitting datasets, each recorded as unavailable to the platform. **No dataset currently on the platform can support a further blind check.**

## Remaining gates

- **Eligibility (1b):** adjudicate the 43 second-annotation disagreements with annotator B, which the plan prescribes next; then a second round under guide v3 with B reading a fresh 50 of the other 150 trials.
- **Owner work:** extraction review round 3 (109 of its 121 entries); the two FDA guidance PDFs and Chen 2017.
- **Deferred review findings:** F04 (a)–(d), F17, F19, F20, F24, and F16's second half.
- **Not done, needs a fresh locked plan:** the acceptance rule extended beyond lenalidomide.
- **Independent review:** none yet. **Authors:** Hughes (weight basis, CRCL2), Kim (CL/F equation form), Iwasaki (which human data evaluated the model) — questions drafted, not sent.
