# Documentation index

Organised by the question you bring. Step numbers (2.0a, 3.1f, …) are historical delivery labels and are not unique across tracks; module and schema versions are the stable identifiers.

## Start here

- [Product and science roadmap](PRODUCT_AND_SCIENCE_ROADMAP.md): positioning, users, phases, status of each phase and next steps (shortened 5 November 2026; the full version with the dated log of every step, and the 10 October version, are in history/).
- [Reviewer's checklist](REVIEWER_CHECKLIST.md): the questions an FDA clinical pharmacology reviewer asks (renal 2024, hepatic draft 2026, ICH M15), scored against the lenalidomide workflow (18 answered, 9 partly, 2 gaps), with the gaps ranked.
- [Status by drug](STATUS_BY_DRUG.md): for each drug, in plain language, what the platform has, what was checked, what is known to be wrong and what is missing.
- [Repository checkpoint](REPOSITORY_CHECKPOINT.md): the latest software verification (5 November 2026: all 1,283 tests passing on the owner's Mac at the end of batch 1), findings and remaining gates. [Record](verification/repository_checkpoint_2026-11-05.json); earlier checkpoints in [history](history/).
- Conventions for working in the repository: `CLAUDE.md` at the root.

## How far can the results be trusted?

- **What the checks found:** page `/models/findings`. Every locked check in one line, failures included, and whether it was blind (`check_findings.py`, `check_findings_v3.json`).
- [Reviews](reviews/): AI reviews of the platform's work (not independent), with what was done about each finding.
- [Dataset ledger](DATASET_LEDGER.md): which data each model was built from, tuned on or checked against, and the gate that refuses a blind check on seen data.
- [Extraction review](EXTRACTION_REVIEW.md): the owner's review of the 166 extracted values that feed calculations (rounds 1–2, all match), and where the review status is shown.
- [Model scope](MODEL_SCOPE.md): each model's context of use as enforced rules, with evidence tiers.
- [Credibility records](CREDIBILITY_RECORDS.md): one record per model in the ICH M15 structure (`/models/credibility`); model scorecards at `/models`.
- [Source reconciliation](SOURCE_RECONCILIATION.md): lenalidomide renal sources compared (measured vs Cockcroft–Gault clearance; corrections to two plans).

## Lenalidomide

- [Patient Lab 2.0](PATIENT_LAB_2_0.md): the Hughes and Kim population models, their checks against CC-5013-PK-001 and Bridoux 2016 (2.0g, 2.1c, 2.1e, 2.1h), and the recorded decisions (Cockcroft–Gault weight basis, typical value vs population band).
- [Kidney pathways](SIMULATION_2_RENAL_PATHWAYS.md): filtration, secretion and non-renal clearance (2.0a), end-stage kidney disease (2.0c), the steeper-secretion test that was not adopted (2.0d), the AI review and the bioavailability re-check (2.0e).
- [Dose view](DOSE_OPTIMISATION.md): exposure and relative cytopenia odds at each model's study doses (4.3).
- Guided path: `guided_path.py`, page `/landscape/drugs/lenalidomide/guide` (4.4); seven steps since 5 November, when label pharmacokinetics and interactions were added.
- [Digital human 1.0](DIGITAL_HUMAN_1_LENALIDOMIDE_ELIMINATION.md) and [1.1](DIGITAL_HUMAN_1_1_FLOW_AND_TIME.md): the elimination body map, blood flow, per-pass extraction and the checked time course.

## Bortezomib

- [Platelet time course and exposure model](SIMULATION_3_BORTEZOMIB_PLATELETS.md): the Lignet 2022 models, the outside checks (Ogawa, CAN-1004, MMY-3021, Reece) and the three failed candidates (Kuan, falling clearance, Iwasaki).
- Research tools: [proteasome target activity](BORTEZOMIB_PROTEASOME_STEP104.md), [peak-evidence review](BORTEZOMIB_EVIDENCE_STEP105.md), [figure review](BORTEZOMIB_FIGURES_STEP106.md), [study-regimen time course](BORTEZOMIB_TIMECOURSE_STEP107.md), [elimination assumptions](BORTEZOMIB_ASSUMPTIONS_STEP108.md), [observation intake](BORTEZOMIB_OBSERVATION_INTAKE_STEPS106_108.md), [discoverable research tools](DRUG_RESEARCH_TOOLS_STEP109.md).

## Other drugs

- [Ixazomib](SIMULATION_3_2_IXAZOMIB.md): Gupta 2017 checked against the dedicated kidney and liver studies (3.2a).
- [Daratumumab](SIMULATION_3_2B_DARATUMUMAB.md): Luo 2021 checked against GEN501 and SIRIUS (3.2b–3.2c).
- [Label-based exposure engine](LABEL_EXPOSURE_ENGINE.md): pomalidomide and dexamethasone (shown), melphalan (not eligible), and the five labels extracted on 4 November 2026 (3.2d: carfilzomib, selinexor, thalidomide, isatuximab, elotuzumab).
- [Special populations](SPECIAL_POPULATIONS.md): kidney, liver, age and body size per drug, every value resolved against its pinned source (4.2).
- [Exposure–effect evidence scan](SIMULATION_4_EVIDENCE_SCAN.md): why no drug yet has a patient-dependent exposure–effect model (4.0).

## Trial design

- [Protocol benchmarking](PROTOCOL_BENCHMARKING.md): eligibility criteria across similar trials; v1 failed its locked check, v2 waits for annotation (4.1).
- Annotation guides: [v2, current](ELIGIBILITY_ANNOTATION_GUIDE_V2.md) and [v1](ELIGIBILITY_ANNOTATION_GUIDE.md).

## Data, schemas and verification foundations

- [Data files](DATA_FILES.md): every pinned JSON file by family, with the latest version and the earlier ones (generated; a test keeps it current).
- [Synthetic patient-state schema v1](PATIENT_STATE_SCHEMA.md).
- [Numerical verification summary](NUMERICAL_VERIFICATION.json) and the [RK4–analytic cross-check (Step 70)](verification/synthetic_numerical_crosscheck_step70.json).
- Check reports: `docs/verification/`. Each one is listed, with its plan and data, in the dataset ledger and on the findings page.
- Early Patient Lab records: [source-equation check (Step 65)](patient-lab-step65/SOURCE_EQUATION_CHECK.md), [data access assessment (Step 66)](patient-lab-step66/DATA_ACCESS_ASSESSMENT.md) and [original-materials checklist](patient-lab-step66/ORIGINAL_MATERIALS_CHECKLIST.md), [verification and validation protocol, draft (Step 67)](patient_lab/step67/VERIFICATION_VALIDATION_PROTOCOL.md).
- Scientific decision records kept as data, in `intelligence_store/data/`:
  - the Kim CL/F equation-form assessment;
  - the Hughes weight-basis assessment;
  - the lenalidomide assay quality review;
  - the dose-proportionality evidence;
  - the reference exposure;
  - the covariate formula registries (v2 current; v1 kept because earlier estimates cite it).

## History

- [history/](history/): earlier roadmaps and checkpoints, and the [Step 26 computational-human proposal](history/FUTURE_PATIENT_LAB_ARCHITECTURE_STEP26.md) (historical; its "Patient Lab 2.0" meant the versioned patient state, not the current plan).
- Installer scripts (`scripts/install_*.py`) from when features arrived as packages were retired on 13 October 2026; they remain in git history.
