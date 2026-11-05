# Repository checkpoint — 5 November 2026

**Verified tree:** branch `batch-1` at `c481e40` ("Label pharmacokinetics and drug interactions…"), 6 commits on top of `main` at `cf18a32` (PR #112). Applied on the owner's Mac from the git bundle `batch-1-backup-2026-11-05f.bundle`. Not yet pushed; CI runs when the batch's pull request is opened.
**Machine-readable record:** [`verification/repository_checkpoint_2026-11-05.json`](verification/repository_checkpoint_2026-11-05.json).
**Previous checkpoint:** 4 November, in [`history/`](history/REPOSITORY_CHECKPOINT_2026-11-04.md). Its main finding (no CI run on the offline work) was resolved on 5 November, when CI passed on PR #112 and the owner merged it.

This is a software and repository verification. It does not validate any model scientifically, and it is not a clinical-readiness review.

## What was delivered since the previous checkpoint

| Area | What | Main files |
|---|---|---|
| Simulation 2.0e | Bioavailability re-check of the kidney pathway model (plan locked first): moderate and severe bands now "depend on bioavailability" | `lenalidomide_renal_pathways_f.py`, plan v3, report v3, `lenalidomide_mass_balance_chen_2012_v1.json` |
| Repository | GitHub reconnected; PR #112 (49 commits) merged after CI; commit-count rules | `CLAUDE.md` |
| Roadmap | Verified against the repository (20 statements corrected over two passes), then shortened to goal, status, next step and link per phase; the full version archived | `PRODUCT_AND_SCIENCE_ROADMAP.md`, `history/PRODUCT_AND_SCIENCE_ROADMAP_2026-11-05.md` |
| Kidney classifications (R1, R2) | FDA 2024 Table 1 beside the study's groups and the label's dose rows; each source's kidney-function measure; where the body map's value falls in each | `kidney_function_classifications.py`, `fda_renal_impairment_guidance_2024_v1.json`, two templates |
| Label extract | The rest of REVLIMID section 12.3 and section 7: 20 quotes, each matched by script against the label file | `lenalidomide_label_2023_pk_v1.json` |
| Label pharmacokinetics and interactions (O1, O2, O5) | Quoted on the lenalidomide special-populations page; a seventh guided-path step | `lenalidomide_label.label_pk_view`, `guided_path.py`, `label_pk_panel.html` |

## Checks

| Check | Result |
|---|---|
| Unit tests | **Pass.** On the owner's Mac, at this tree: 1,283 tests ran in 264 s; all passed, 2 skipped. ResourceWarning lines were printed; no failures. |
| Compile all modules | **Pass.** `compileall` on `app`, `intelligence_store`, `landscape_ui`, `scripts` and `intelligence_migrations`. |
| Migration chain | **Unchanged.** 9 revisions; no schema change since 16 October. |
| Pinned data | **Pass.** 168 data files in `intelligence_store/data/` outside `curation/`; 167 match a checksum in a module, a test or a pinned plan that cites them. The exception is the observation template, unpinned by design. `docs/DATA_FILES.md` is current. |
| Locked plans and reports | **Pass.** No new check this period after 2.0e; 27 locked checks, all in the dataset ledger and on `/models/findings`. |
| Validation flags | **Pass.** No tracked JSON sets `clinical_prediction_validated` or `ready_for_patient_simulation` to true. |
| Repository hygiene | **Pass.** No source articles, labels, guidances or private correspondence tracked; the backup bundles stay in `supplemental-information/`, which is ignored. |

## Findings

1. **New values not yet reviewed.** The FDA guidance categories and the 20 label quotes of 5 November are on pages, marked as AI-extracted and not reviewed by the owner. Three newly answered checklist questions (O1, O2, O5) rest on them. **Gate:** extraction review round 3.
2. **A lower absorption bound in the label.** The label's 82% of a radioactive dose unchanged in urine within 24 hours implies absorption of at least about 0.82, below the 0.85 floor that Simulation 2.0e took from the renal study's normal group. The two are different studies and are not reconciled; whether it changes the 2.0e conclusions has not been checked. **Resolved 5 November, after this checkpoint:** it cannot change them. Both figures are lower bounds, so the higher (0.85) binds and the label's 82% is the weaker one ([SIMULATION_2_RENAL_PATHWAYS.md](SIMULATION_2_RENAL_PATHWAYS.md), last section).
3. **Stale statements in the roadmap.** The first verification pass missed seven of them (found on the second). The shortened roadmap moves the dated detail into the topic documents, which should make this less likely.

## Scientific state

- 27 locked checks; 3 blind (Bridoux for Hughes and Kim, NEOFORDEX for dexamethasone, eligibility sample v1). See `/models/findings`.
- Reviewer's checklist for lenalidomide: 17 of 29 answered, 9 partly, 3 gaps.
- Lenalidomide: Hughes and Kim under-predict moderate and severe kidney impairment in two studies; the pathway model's moderate and severe results depend on bioavailability. No unseen renal data remains.
- Bortezomib exposure model: contradicted by every study tested; three candidate fixes failed.
- No model is validated for clinical prediction.

## Remaining gates

- **This batch:** push `batch-1`, open one pull request, let CI run; the owner merges with "Create a merge commit".
- **Owner work:** v2 eligibility annotation (the only unseen dataset); extraction review round 3.
- **Independent review:** none yet, of extractions or of any model.
- **Authors:** Hughes (Cockcroft–Gault weight basis); Kim (CL/F equation form); Iwasaki (human data).
- **Platform:** accounts and deployment.

Step numbers identify historical deliveries, not a unique sequence; use module and schema versions.
