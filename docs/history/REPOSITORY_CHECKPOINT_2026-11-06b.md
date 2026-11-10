# Repository checkpoint — 6 November 2026 (b), end of batch 3

**Verified tree:** branch `batch-3` at `7172b2e`, 5 commits on top of `main` after PR #114. Applied on the owner's iMac from `batch-3-backup-1.bundle`. CI runs when the pull request is opened.
**Machine-readable record:** [`verification/repository_checkpoint_2026-11-06b.json`](verification/repository_checkpoint_2026-11-06b.json).
**Previous checkpoint:** 6 November, end of batch 2, in [`history/`](history/REPOSITORY_CHECKPOINT_2026-11-06.md). Its unrecorded test count is now known: CI on PR #114 ran 1,310 tests, all passing (5 skipped).

**New machine.** The project moved from the owner's MacBook to an iMac on 6 November: code from GitHub, `supplemental-information/` (174 files) and `instance/` copied by hand, Python 3.14 in a new environment. All tests passed there before this batch.

This is a software and repository verification. It does not validate any model scientifically, and it is not a clinical-readiness review.

## What was delivered (batch 3)

| Area | What | Main files |
|---|---|---|
| One instance folder | Database, workspace key and annotations all in `instance/`; an annotation file left in `app/instance/` is carried over without losing saved trials | `app/app.py`, `eligibility_annotations.resolve_store` |
| Model analysis reports (M3) | Hughes 2019 and Kim 2026, one result table per locked check | `model_analysis_report.py`, two narrative files |
| Dialysis (R7) | Paired on/off dialysis data, removal per session, myeloma patients on the label dose; not modelled | `dialysis_evidence.py`, `dialysis_panel.html` |
| Assays (O8) | The bioanalytical method behind each kidney dataset, quoted and checked against the PDFs | `lenalidomide_bioanalytical_methods_v1.json`, `assay_panel.html` |
| Interval on ratios (R5) | Approximate 90% intervals for the Bridoux ratios, derived and labelled | `renal_dose_exposure.ratio_interval` |

## Checks

| Check | Result |
|---|---|
| Unit tests | **Pass.** On the owner's iMac at this tree: 1,330 tests ran in 173 s; all passed, 2 skipped. |
| Compile all modules | **Pass.** |
| Migration chain | **Unchanged.** 9 revisions. |
| Pinned data | **Pass.** 177 data files outside `curation/`; 176 pinned (the observation template is unpinned by design). |
| Locked checks | **Unchanged.** 27, 3 blind. |
| Validation flags | **Pass.** None set to true. |
| Repository hygiene | **Pass.** No source PDFs or private files tracked; `instance/` (annotations, database) is outside git and must be backed up by hand. |

## Findings

1. **Two instance folders.** Flask's default put annotations in `app/instance/` while the database used `instance/`. The owner's copy of the annotation file went to the wrong one and the page showed 0 of 200; nothing was lost. Fixed in the first update of this batch.
2. **Drafting errors caught before commit.** The Hughes narrative first said four checks (there are three), and the Kim narrative said severe was under-predicted "throughout" (one sensitivity scenario was consistent). Both were found by comparing the text with the reports.
3. **Round 3 has grown to 117 entries.** Three queue versions were made before any review began; v1 and v2 are kept unchanged.

## Scientific state

- Reviewer's checklist for lenalidomide: 21 of 29 answered, 6 partly, 2 gaps (O7 exposure–efficacy, M8 independent review).
- 27 locked checks, 3 blind. No model is validated for clinical prediction.

## Remaining gates

- **This batch:** push `batch-3`, one pull request, CI; the owner merges with "Create a merge commit".
- **Owner work:** review round 3 (117 entries); the eligibility annotation (38 of 200).
- **Independent review:** none yet. **Authors:** Hughes, Kim, Iwasaki. **Platform:** accounts and deployment.
