# Repository checkpoint — 4 November 2026

**Verified tree:** branch `offline-work` at `91fcca0` ("What the checks found; roadmap brought up to 4 November"), 42 commits on top of `main` at `45c4afe` (after PR #110). The GitHub account has been flagged since 3 November, so these commits were delivered as patch files (0001–0040) and then as a git bundle. They have not been pushed or run in CI.
**Machine-readable record:** [`verification/repository_checkpoint_2026-11-04.json`](verification/repository_checkpoint_2026-11-04.json).
**Previous checkpoint:** 3 November, in [`history/`](history/REPOSITORY_CHECKPOINT_2026-11-03.md).

This is a software and repository verification. It does not validate any model scientifically, and it is not a clinical-readiness review.

## What was delivered since the previous checkpoint

| Area | What | Main files |
|---|---|---|
| Body map | Flows along vessel centre lines; rendering pass; navigation (pan, zoom at pointer); flow key, scale bar, selectable flows | `body_map_vessel_lines_v1.json`, `body_map_flow_paths_v2.json`, `body-map-viewer.js` |
| Digital human 1.1a–1.1c | Reference blood flow (ICRP 89), blood-to-plasma ratio (Chen 2012), per-pass extraction, blood-flow layer | `reference_physiology.py`, `body_map.py` (view v2) |
| Digital human 1.1d | Time course v1 and v2, each under a plan locked before computation; v2 not adopted | `body_map_time_course.py`, two plans, two reports |
| Bridoux 2016 (2.1h) | Two-stage blind check of Hughes and Kim; evidence status v13 | `lenalidomide_bridoux_check.py`, design and observed files |
| Simulation 2.0d | Kidney pathway v2 (secretion falls faster): plan locked, run, not adopted; myeloma comparison shown beside the warnings; evidence status v14 | `lenalidomide_renal_pathways_v2.py`, `body_map.myeloma_note` |
| Extraction review | Rounds 1 and 2 pinned (166 of 166 values match); round-2 page; review status on model, label, special-population and dose pages | `extraction_review.py`, two records |
| Dataset ledger | Which data each model was built from, tuned on or checked against; gate refusing blind checks on seen data; v2 adds five labels | `dataset_ledger.py`, `dataset_ledger_v1.json`, `_v2.json` |
| Label extracts (3.2d) | Carfilzomib, selinexor, thalidomide, isatuximab, elotuzumab: 74 quoted values | `drug_label_extracts.py`, five extracts, build script |
| What the checks found | `/models/findings`: 26 locked checks in one line each, with blindness from the ledger | `check_findings.py`, `check_findings_v1.json` |
| Other | Scroll position kept on reload; locked-report tests tolerant of last-digit differences off Linux; roadmap updated | `marlo-scroll.js`, `tests/report_reproduction.py` |

## Checks

| Check | Result |
|---|---|
| Unit tests | **Pass.** On the owner's Mac, at this tree: 1,243 tests ran in 274 s; all passed, 2 skipped. First full-suite run since the 3 November checkpoint (subsets were run after each patch). CI has not run on this tree. |
| Compile all modules | **Pass.** `compileall` on `app`, `intelligence_store`, `landscape_ui`, `scripts` and `intelligence_migrations`. |
| Migration chain | **Unchanged.** 9 revisions; no schema change since 16 October. |
| Pinned data | **Pass.** 158 data files in `intelligence_store/data/` outside `curation/`; 157 match a checksum in code. The exception is the observation template, unpinned by design. |
| Locked plans and reports | **Pass.** Every check report is listed in the dataset ledger and in the findings file with its checksum, and both are tested. New plans this period were pinned before their computation (1.1d v1 and v2, 2.0d). |
| Validation flags | **Pass.** No tracked JSON sets `clinical_prediction_validated` or `ready_for_patient_simulation` to true. |
| Repository hygiene | **Pass.** No source articles, labels or private correspondence tracked. The only PDF is the public EMA lenalidomide report. Label PDFs and articles stay in `supplemental-information/`, which is ignored. |

## Findings

1. **No CI run on 42 commits.** **Gate:** when the account is restored, push `offline-work`, let CI run, then open the pull requests.
2. **A plan rationale was wrong (2.0d).** The plan said the Bridoux check had found the pathway model's clearance too high; that check compared Hughes and Kim. The plan stays as locked; the correction is in `SIMULATION_2_RENAL_PATHWAYS.md`. The dataset ledger and findings page now make this kind of misattribution easier to catch.
3. **Delivery mishap.** One bundle re-sent under the same file name arrived as the previous copy. Bundles are now sent under a unique name and their size is checked on the owner's computer.

## Scientific state

- 26 locked checks; 3 blind (Bridoux for Hughes and Kim, NEOFORDEX for dexamethasone, eligibility sample v1). See `/models/findings`.
- Lenalidomide: Hughes and Kim under-predict moderate and severe kidney impairment in two studies; the pathway model is consistent with both myeloma studies there but not with CC-5013-PK-001. No unseen renal data remains.
- Bortezomib exposure model: contradicted by every study tested; three candidate fixes failed.
- No model is validated for clinical prediction.

## Remaining gates

- **GitHub access:** restore; push; CI; pull requests (#111 still open).
- **Owner work:** v2 eligibility annotation (the only unseen dataset); extraction review round 3 for the 74 new label values.
- **Independent review:** none yet, of extractions or of any model.
- **Authors:** Hughes (Cockcroft–Gault weight basis); Kim (CL/F equation form); Iwasaki (human data).
- **Platform:** accounts and deployment.

Step numbers identify historical deliveries, not a unique sequence; use module and schema versions.
