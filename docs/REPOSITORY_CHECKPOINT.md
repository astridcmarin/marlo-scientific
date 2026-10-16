# Repository checkpoint — 16 October 2026

Verified tree: `main` at `edcac12` plus PR #25 (`f8379cd`). Machine-readable record: [`verification/repository_checkpoint_2026-10-16.json`](verification/repository_checkpoint_2026-10-16.json). The previous checkpoint (13 October) is in [`history/`](history/REPOSITORY_CHECKPOINT_2026-10-13.md).

This is a software and repository verification. It does not validate any model scientifically and is not a clinical-readiness review.

## What was delivered since 13 October

| Capability | Versions | Scope |
|---|---|---|
| Lenalidomide, Kim 2026 second model (2.1) | `kim_model.py`, `kim_2026_model_extract_v1.json`, `kim_pk_run` table | Renal-impairment PK on the unbound scale; renal-group check; saved runs |
| Lenalidomide reference exposure and dose proportionality (2.1) | `lenalidomide_reference_exposure_v1.json`, `lenalidomide_dose_proportionality_evidence_v1.json` | Measured normal-group AUC; EMA dose-proportionality range |
| Bortezomib platelet model (Simulation 3.0a–d) | `bortezomib_pk.py`, `bortezomib_platelets.py`, plan `bortezomib_platelet_check_plan_v1.json` | Lignet 2022, two variants; locked reading check against its fitting data |
| Patient-state schema v2 and platelet curve for a patient (2.2) | `synthetic-patient-state-v2`, `bortezomib_patient_platelets.py` | Baseline platelets; typical curve in absolute counts; CTC v2.0 and CTCAE v5.0 grading |
| Run record and banner (2.0f) | `patient-lab-run-record-v1`, `model_evidence_status_v2.json` | One provenance panel on every Patient Lab result page |
| Outside-data search for the platelet model (3.0e, PR #25) | `model_evidence_status_v2.json` (v1.1) | No usable data found; sources and reasons recorded |
| Knowledge layer | `drug_aliases.py` v1.2, `drug_knowledge.py` v1.1 | 966 reviewed mappings no longer shown as unmapped |
| Repository | `.gitignore` | Source articles ignored as `[Aa]rticles/` |

## Checks

| Check | Result |
|---|---|
| Unit tests | **Pass.** 655 tests (Python 3.13 here; CI uses 3.12 and passed on `main` and on PR #25). |
| Compile all modules | **Pass.** |
| Migration chain | **Pass.** 9 revisions, one root, one head (`585bc7cb8d18`). |
| Pinned data | **Pass, with one finding** (below). 36 of 61 data files are pinned by a matching file checksum; every checksum constant in code matches a file or is a tested canonical-content pin. |
| Validation flags | **Pass.** No file sets `clinical_prediction_validated` or `ready_for_patient_simulation` to true. |
| Page smoke test | **Pass.** 61 pages requested: 50 returned 200; 6 returned 400 because they need a `cohort_id`; 5 returned 404 because the fixture has no saved Hughes run. No server errors. |
| Repository hygiene | **Pass.** No source articles tracked; the only PDF is the public EMA assessment report; no credentials or instance data. |

## Findings to fix

Findings 1 and 2 were fixed after this checkpoint (branch `checkpoint-fixes-pins-inventory`):

1. **Reference files without a checksum pin — fixed.** Eight loaders now refuse a file whose SHA-256 differs from its pin: `drug_aliases_v1`, `formatting_group_mappings_v1`, `drug_annotations_v1`, `drug_safety_v1`, `drug_interactions_v1`, `patient_scenarios_v1`, `lenalidomide_assay_extraction_v1` and `lenalidomide_mechanism_evidence_plan_v1`. `tests/test_reference_pins.py` checks every pin and the refusal of a changed file.
   - **Corrected finding:** `bortezomib_observation_template_v1` is not a reference file. It is the default example input to the observation-intake reviewer, whose job is to check whatever document it is given, so it is deliberately not pinned.
   - **Tests realigned:** tests that write deliberately invalid files now pin each altered file, so they still test their content rule rather than passing on the checksum.
2. **Library undercount — fixed (inventory method v1.2).**
   - **Exposure models:** Kim 2026 is registered as a second educational exposure model for lenalidomide, which now counts 2.
   - **Bortezomib PK engine:** listed as a research component, used only by the platelet tool and not offered as patient PK.
   - **Research tools:** counts include every registered kind, so the platelet tool (`drug_effect_timecourse`) is counted.
   - **Failure handling:** a contract failure withholds only the affected model and names it in the warning.
3. **Housekeeping.** Seven feature branches whose work is already on `main` remain on GitHub. `patient-lab-2.2b-patient-platelets` shows one unmerged commit, but its content reached `main` as a cherry-pick in #23.

## Scientific state (from `model_evidence_status_v2.json`)

| Model | Software | Transcription | Reproduction | External consistency |
|---|---|---|---|---|
| Hughes 2019 | done | partial | not done | exploratory, group means: mild consistent; moderate and severe under-predicted |
| Kim 2026 | done | done; CL/F form unconfirmed | done | exploratory, group means: mild and moderate consistent; severe under-predicted |
| Lignet 2022 platelets | done | partial | done (fitting data) | not done; searched, no usable data |
| Lignet 2022 PK component (added 16 October, 3.0f) | done | partial | not done | exploratory (Ogawa 2008): day 11 consistent; day 1 over-predicted 2.9-fold; accumulation under-predicted |

No model is validated for clinical prediction. Efficacy and toxicity models: none registered.

## Remaining gates

- **Hughes:** independent transcription review and the Cockcroft–Gault weight basis (author confirmation).
- **Kim:** the CL/F equation form (author confirmation).
- **Bortezomib:**
  - independent review of the platelet extract;
  - outside data, through a sponsor data request;
  - PK model with time-dependent clearance (the Ogawa 2008 check, 3.0f, found the single clearance fits repeat-dose but not first-dose exposure).
- **Round 9 alias review** is awaiting completion.
- **Platform:** broader disease and drug coverage, accounts, billing and deployment remain future work. The locally reported 4,037-study cohort is not in the repository and was not verified here.

Step numbers identify historical deliveries, not a unique sequence; use module and schema versions (see the previous checkpoint for the step-number mapping).
