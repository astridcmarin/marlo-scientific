# Documentation index

Start with the roadmap and the current Patient Lab plan. Step numbers are historical delivery labels and are not unique; module and schema versions are the stable identifiers (see the repository checkpoint).

Several step documents describe installer scripts (`scripts/install_*.py`) from when features arrived as packages. Those features are integrated into the code, and the installers were retired on 13 October 2026; they remain in git history.

## Current direction

- [Product and science roadmap](PRODUCT_AND_SCIENCE_ROADMAP.md) — product goal, development phases, capability representation.
- [Patient Lab 2.0](PATIENT_LAB_2_0.md) — current computational-pharmacology work: scope, non-goals, architecture, step status, and the recorded scientific decisions (Hughes 2019 lenalidomide model, Cockcroft–Gault weight basis, typical value vs population band).
- [Repository checkpoint](REPOSITORY_CHECKPOINT.md) — what is integrated, step-number history, outstanding scientific work.

## Patient Lab foundations

- [Synthetic patient-state schema v1](PATIENT_STATE_SCHEMA.md) — fields, units, provenance and preview contract.
- [Step 65 — source-equation check](patient-lab-step65/SOURCE_EQUATION_CHECK.md) and [source assessment data](patient-lab-step65/hughes_source_assessment.json).
- [Step 66 — data access assessment](patient-lab-step66/DATA_ACCESS_ASSESSMENT.md), [original-materials checklist](patient-lab-step66/ORIGINAL_MATERIALS_CHECKLIST.md) and [inventory](patient-lab-step66/data_access_inventory.json). The checklist includes the open question on the Hughes `CRCL2` covariate.
- [Step 67 — verification and validation protocol (draft)](patient_lab/step67/VERIFICATION_VALIDATION_PROTOCOL.md) and [protocol data](patient_lab/step67/validation_protocol_draft.json).

## Verification records

- [Numerical verification summary](NUMERICAL_VERIFICATION.json).
- [Synthetic RK4–analytic cross-check (Step 70)](verification/synthetic_numerical_crosscheck_step70.json) — output of `scripts/pk_numerical_crosscheck.py`.
- [Hughes renal-group consistency check (2.0g)](verification/hughes_renal_group_check_v1.json) — exploratory check against study CC-5013-PK-001; plan locked in `intelligence_store/data/hughes_renal_group_check_plan_v1.json`. Finding recorded in `intelligence_store/data/hughes_applicability_findings_v1.json`.
- [Kim renal-group consistency check (2.1c)](verification/kim_renal_group_check_v1.json) — the same study and design for the Kim 2026 model, with eGFR built from assumed demographics; plan locked in `intelligence_store/data/kim_renal_group_check_plan_v1.json`. Finding recorded in `intelligence_store/data/kim_applicability_findings_v1.json`.
- Lenalidomide reference exposure — `intelligence_store/data/lenalidomide_reference_exposure_v1.json` (measured 25 mg AUC, normal renal function; context ratio only).
- Lenalidomide dose proportionality — `intelligence_store/data/lenalidomide_dose_proportionality_evidence_v1.json` (EMA assessment p.20, checked against the pinned PDF).

## Scientific decision records kept as data

- Kim 2026 model extract and CL/F equation-form assessment — `intelligence_store/data/kim_2026_model_extract_v1.json`, `kim_cl_equation_form_assessment_v1.json` (see Patient Lab 2.0, section 2.1).
- Covariate formula registries — `covariate_formula_registry_v2.json` is current; `v1` is kept because estimates made before v2 cite it.

- Lenalidomide assay quality review — `intelligence_store/data/lenalidomide_assay_quality_review_v1.json`: the Lu Fig. 2D assay is retained as qualitative evidence and not used for quantitative calibration.
- Hughes Cockcroft–Gault weight-basis assessment — `intelligence_store/data/hughes_weight_basis_assessment_v1.json` (see Patient Lab 2.0).

## Bortezomib research tools

- [Step 104 — proteasome target activity](BORTEZOMIB_PROTEASOME_STEP104.md)
- [Step 105 — peak-evidence review](BORTEZOMIB_EVIDENCE_STEP105.md)
- [Step 106 — provisional figure review](BORTEZOMIB_FIGURES_STEP106.md)
- [Step 107 — study-regimen time course](BORTEZOMIB_TIMECOURSE_STEP107.md)
- [Step 108 — elimination-assumption comparison](BORTEZOMIB_ASSUMPTIONS_STEP108.md)
- [Observation intake v1](BORTEZOMIB_OBSERVATION_INTAKE_STEPS106_108.md) — separate workflow that reused the numbers 106–108.
- [Simulation 3.0 — bortezomib platelet time course](SIMULATION_3_BORTEZOMIB_PLATELETS.md): Lignet 2022 model transcription, open questions and Lonial 2005 observed values (`intelligence_store/data/bortezomib_platelet_*_v1.json`). PK engine and label comparison: `bortezomib_pk.py`, `bortezomib_label_pk_v1.json`.
- [Step 109 — discoverable drug research tools](DRUG_RESEARCH_TOOLS_STEP109.md)

## History

- [Computational human direction — Step 26 proposal](history/FUTURE_PATIENT_LAB_ARCHITECTURE_STEP26.md). Historical; its "Patient Lab 2.0" meant the versioned patient state, not the current plan.
