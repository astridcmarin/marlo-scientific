# Repository checkpoint — 31 October 2026

**Verified tree:** `main` at `7b4bda4` (after PR #95).
**Machine-readable record:** [`verification/repository_checkpoint_2026-10-31.json`](verification/repository_checkpoint_2026-10-31.json).
**Previous checkpoint:** 30 October (second), in [`history/`](history/REPOSITORY_CHECKPOINT_2026-10-30b.md).

This is a software and repository verification. It does not validate any model scientifically, and it is not a clinical-readiness review.

## What was delivered since the previous checkpoint (PRs #82–#95)

| Area | What | Main files |
|---|---|---|
| Checkpoint (#82) | 30 October verification (second) | `docs/history/REPOSITORY_CHECKPOINT_2026-10-30b.md` |
| Dose optimisation (Phase 4.3, #83) | Lenalidomide dose-optimisation view (v1) | `dose_optimisation.py` |
| Lenalidomide label (#84) | REVLIMID label, revision 3/2023: special-population summary v2 and the dose page | `lenalidomide_label_2023_v1.json` |
| Renal source reconciliation (#85, #88, #90) | Label history, the conference abstract and the Chen 2007 publication reconciled against the EMA table; evidence status v8–v9 | `lenalidomide_renal_source_reconciliation_v1–v3.json` |
| Extraction review (#86) | Owner review of the 166 AI-extracted values that feed calculations | `extraction_review.py`, `/models/extraction-review` |
| Guided path (Phase 4.4, #87) | Lenalidomide guided path; landing page brought up to date | `guided_path.py` |
| Ixazomib label (#89) | Label revision 7/2024: special-population summary v2 | `ixazomib_label.py` |
| Bortezomib PK (Simulation 3.0m–3.0n, #91–#92) | MMY-3021 day 11 check; Reece 2011 reproduction check: first-dose exposure about 2-fold too high, rise over doses too small | `bortezomib_pk_mmy3021_check.py`, `bortezomib_pk_reece_reproduction.py` |
| Lenalidomide renal recheck (2.1e, #93) | Both models against CC-5013-PK-001 with study-matched virtual subjects; Kim moderate changes to under-predicts | `renal_group_recheck.py` |
| Kim moderate warning (2.1f, #94) | Findings v2 (warning for eGFR 30–50); Kim scope v2 flags that band | `kim_applicability_findings_v2.json` |
| Renal study population (2.1g, #95) | CC-5013-PK-001 recorded as non-malignant renal impairment with healthy controls; renal evidence v2, Hughes scope v2, Kim scope v3, lenalidomide summary v3 | `renal_pk_group_evidence_v2.json` |

## Checks

| Check | Result |
|---|---|
| Unit tests | **Pass.** CI (Python 3.12, `python -m unittest discover -s tests`) passed on `7b4bda4`. The suite defines 1,040 test methods (static count). |
| Compile all modules | **Pass.** `compileall` on `app`, `intelligence_store`, `landscape_ui`, `scripts` and `intelligence_migrations`. |
| Migration chain | **Pass.** 9 revisions; one root (`3538c7d69211`) and one head (`585bc7cb8d18`). No schema change since 16 October. |
| Pinned data | **Pass.** 128 tracked data files in `intelligence_store/data/` outside `curation/`; 126 match a checksum in code. The other two are known: the observation template (unpinned by design) and the eligibility corpus (pinned by its decompressed content). Of 125 named checksum constants in code, 121 match a tracked file. The other four are known: the corpus content pin; two canonical-content pins in `scripts/`; and the Hughes source article's checksum, whose file stays on the owner's computer. |
| Locked plans and reports | **Pass.** All 23 check reports in `docs/verification/` were regenerated for this checkpoint and are byte-identical to the committed files, including the three slow ones not regenerated in the unit tests: Iwasaki (`529772d9…`), daratumumab v1 (`ac3369f7…`) and v2 (`24b12ab8…`). The other five files there are checkpoint records. |
| Validation flags | **Pass.** No tracked JSON sets `clinical_prediction_validated` or `ready_for_patient_simulation` to true. |
| Page smoke test | **Not run here; covered by CI.** The cloud workspace cannot install packages, so the app could not be started against a database. The page tests in the CI suite request every route family touched since the last checkpoint and passed. The next checkpoint run with the database available should repeat the full smoke test. |
| Repository hygiene | **Pass.** No source articles or private correspondence tracked; no database or `instance/` files. The only PDF is the public EMA lenalidomide report. The only email addresses are in the font licence. |

**How the checks were run.** The database layer was stubbed so that every non-database module and report could be imported and run. Every database-backed test ran in CI.

## Findings

1. **A stale claim was shown to users — fixed in PR #96.**
   - **What it said.** The bortezomib platelet tool's limitations, and the drug-capability assumption, said the PK model "overstates first-dose exposure about 7-fold".
   - **Where the figure came from.** It is the ratio of the label's first-dose clearance to the model's clearance, not measured exposure.
   - **What the outside data show.** Measured first-dose AUC is 2–3-fold too high in two studies and consistent in a third.
2. **The bortezomib platelet model had no scope — fixed in PR #96.**
   - It was the only computed model without one.
   - Baselines below every entry threshold of its source study were computed with a warning, against the 30 October policy of refusing beyond a model's data.
3. **Stacked pull requests close when their base branch is deleted.**
   - On 31 October, #94 closed automatically when #93's branch was deleted after merging. It was reopened and merged; nothing was lost.
   - **Rule:** retarget a stacked PR to `main` before deleting the branch it sits on.
4. **Housekeeping.** Merged branches on GitHub can be deleted.

## Scientific state

| Model | Outside data | Platform scope |
|---|---|---|
| Hughes 2019 (lenalidomide) | Mild consistent; moderate and severe under-predicted about 2–2.5-fold (confirmed by the 2.1e recheck) | CrCl 50–211 checked; 36–50 flagged; below 36 refused |
| Kim 2026 (lenalidomide) | Mild consistent; moderate and severe under-predicted about 1.3-fold (2.1e; moderate was consistent in the first check) | eGFR 50–94.7 checked; 11.1–50 flagged (moderate added 31 October); outside refused |
| Renal study behind both checks | CC-5013-PK-001 enrolled people with non-malignant renal impairment and healthy controls, not myeloma patients; one possible contributor to the disagreements, untested | — |
| Lenalidomide kidney pathways 2026 | Calibrated on normal kidney function | — |
| Lenalidomide exposure–safety 2016 | Not done (no independent data) | — |
| Lignet 2022 bortezomib PK | Disagrees with outside data: first dose too high (Ogawa, Reece), rise too small (every study sampling both days); three candidate fixes failed | Not offered as patient PK |
| Lignet 2022 bortezomib platelets | Reproduced against fitting data; no outside platelet data; inherits the PK component's disagreements | Scope proposed in PR #96: baseline 30 or more; below 30 refused |
| Gupta 2017 (ixazomib) | Consistent in MM with normal renal function; solid tumours under-predicted; peaks 2–4-fold low | MM, oral 1.5–4 mg, CrCl 30–297, bilirubin ≤ 1.5 × ULN; AUC only |
| Luo 2021 (daratumumab) | Peaks consistent; 16 mg/kg first-week AUC over-predicted | Defined, not run on any page |
| Label-based exposure | Pomalidomide and dexamethasone shown; melphalan not eligible | — |
| Eligibility extractor | v1.0 failed every type; v1.1 awaits the v2 annotation (200 trials, in progress) | — |

No model is validated for clinical prediction.

## Remaining gates

- **Owner work in progress:**
  - v2 eligibility annotation (then pin, run the locked check, and show the passing types);
  - round 1 of the extraction review (then validate and pin the record).
- **Independent review** of the AI-assisted extractions: none yet. The owner's review is not independent.
- **A second renal dataset:** an independent lenalidomide renal-impairment study in myeloma patients, to separate model error from the population difference.
- **Authors:** Hughes (Cockcroft–Gault weight basis); Kim (CL/F equation form); Iwasaki (the human data used to evaluate the model).
- **Kim protein binding:** the label gives about 30% binding (unbound fraction about 0.7) against Kim's estimated 0.614. Not yet assessed.
- **Bortezomib PK:** individual concentration data, or a mechanism that changes clearance between doses.
- **Drug catalog growth:** needs the DailyMed label files.
- **Platform:** accounts and deployment.

Step numbers identify historical deliveries, not a unique sequence; use module and schema versions.
