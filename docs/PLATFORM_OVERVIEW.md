# Platform overview

**Purpose.** One living document for reviewing and tracking Marlo Scientific: what the platform has, how it is laid out, what has been done (the owner's work before AI sessions joined, and the work since), and what is planned. It is updated with every batch; the "Updates" section at the end records each change.

**As of 23 November 2026**, from a review of every tracked file (1,113 on `batch-26` before this document was added, 1,117 with it; listed one by one in [PLATFORM_FILES.md](PLATFORM_FILES.md), generated from the files themselves) and the full git history (491 commits on `main`, from 5 October 2026).

**How it is kept current.**
- Facts here come from the files and the history. Anything that cannot be tied to a file or a commit is marked *unverified*.
- Each batch that changes what the platform has, what was done or what is planned updates the relevant section and adds a line under "Updates".
- `python3 scripts/platform_files_index.py` regenerates the file list; a test fails if it is out of date, so no file can be left out.
- Detail stays in the documents this one links to; this page is the map, not a copy.

Nothing on the platform is validated for clinical prediction, prescribing or treatment selection.

---

## What Marlo Scientific is

Marlo Scientific is a research and educational software platform for pharmaceutical and clinical-research work. It brings together, in one place, the evidence a drug-development question draws on and the models that try to explain it:

- **Clinical trial intelligence:** complete, frozen cohorts of ClinicalTrials.gov records, classified and summarised (recruitment, phases, sponsors, sites, stopping reasons, eligibility).
- **Drug, label and regulatory evidence:** drug identities, mechanisms, label text, special populations (kidney and liver impairment, sex), interactions and regulatory documents, each linked to its source.
- **Computational pharmacology:** published pharmacokinetic and pharmacodynamic models and the platform's own, run on synthetic patients in the Patient Lab and the Simulation Lab, with a 3D body map for lenalidomide.

It is for pharmaceutical and regulatory scientists, clinical researchers, pharmacologists and drug-development teams.

**What sets it apart is how it treats its own claims.** Every value carries its source and method. Every model check is locked by commit before it is computed, and its result is published whether it passes or fails; a dataset ledger records what each model has already seen, so a blind check can be told from one that is not. AI-assisted extraction is reviewed against the source by the owner, and each value shows its review state. Software tests and scientific validation are kept apart: passing tests does not make a model predictive.

**What it is not.** It is not a medical device or a clinical decision tool. Nothing on it is validated for clinical prediction, prescribing, dosing or treatment selection; patients are synthetic, and a real patient could enter only as a banded profile computed in the browser and never stored (decision 0008).

**Where it is now.** Pre-release, built by its owner from 5 October 2026, with AI coding sessions working under the owner's direction since 13 October; the owner is the only human reviewer. The science so far centres on multiple myeloma drugs. The first release will lead with sourced evidence, covering the label of every US prescription drug (decision 0007), with the models shown behind their check records.

---

## 1. At a glance

| | |
|---|---|
| Files tracked | 1,113 (after the clean-up of 23 November) |
| Commits on `main` | 491 (5 October to 20 November 2026) |
| Python modules in `intelligence_store/` | 174 |
| Pinned data files (`intelligence_store/data/`) | 258 JSON, plus one compressed file and one note |
| Page modules (`landscape_ui/`, `app/`) and templates | 54 page modules, 112 workspace templates; at least 112 route definitions |
| Tests | 197 files, 1,641 test functions (about 300 need the database and run in CI) |
| Database migrations | 9 |
| Documentation | 167 files, including 9 decision records and 9 AI review records |
| Locked model checks | 37 (3 passed, 2 consistent, 11 mixed, 7 disagree, 9 failed, 3 inconclusive, 2 not adopted) |
| Drugs with a drug page and catalogue entry | 10 |
| Validation flags set to true | none |

---

## 2. Structure

| Area | What lives there | Files |
|---|---|---|
| `app/` | The Flask entry point (`app.py`), the landing page and the public model pages (`/models/...`: findings, credibility records, scopes, extraction review, eligibility, evidence index) | 23 |
| `landscape_ui/` | The research workspace under `/landscape/`: page modules, templates, CSS and JavaScript for trials, drugs, Patient Lab, Simulation Lab, benchmarking and the body map | 207 |
| `intelligence_store/` | All scientific and knowledge code (models, checks, extractors, evidence logic) and `data/`, the SHA-256-pinned reference data, plans, reports and review records | 450 |
| `intelligence_migrations/` | Alembic migrations for the database tables (trial evidence, cohorts, workspaces, watchlists, patient states, educational PK runs) | 13 |
| `scripts/` | Command-line builders and checks (data index, extraction builders, review pages, smoke tests) | 48 |
| `tests/` | `unittest` tests, run in CI on every pull request | 197 |
| `examples/` | A synthetic numerical case plan | 1 |
| `docs/` | Roadmap, handoff, checkpoints, design plans, decision records, verification reports, AI reviews, history | 167 |

Outside the repository, on the owner's iMac (git-ignored, never committed): source PDFs, labels, registry records, correspondence and the 3D Atlas files in `supplemental-information/`, and the owner's annotation files in `instance/`.

---

## 3. What the platform has

Each area: what it does, where it is, its state, and whose work it started as. "Owner (Oct 5–12)" means it was in the repository before the first AI-session commit on 13 October.

### 3.1 Clinical trial intelligence — *owner (Oct 5–12), extended since*
- **What:** retrieves complete ClinicalTrials.gov cohorts with per-run evidence and completeness checks; freezes snapshots before any formatting; normalises trial fields; summarises recruitment, phases, sponsors, sites, stopping reasons, eligibility age and sex fields, safety and interaction references; watchlists and saved intelligence briefs (with PDF export).
- **Where:** `cohorts.py`, `snapshots.py`, `normalization.py`, `summaries.py`, `stopping.py`, `trial_criteria.py`, `site_feasibility.py`, `watchlists.py`, `workspaces.py`, `brief_pdf.py`; pages under `/landscape/` (trials, sites, stopped, safety, interactions, protocols, regulatory, diseases, workspace).
- **State:** in use; a frozen myeloma cohort of more than 4,000 trial records (project description, *unverified here*). Trials outside myeloma will link to a live registry search, labelled as unfrozen (decision 0007).

### 3.2 Drug, label and regulatory knowledge — *owner (Oct 5–12) foundation, mostly built since*
- **What:** drug identity and aliases from frozen evidence; mechanisms; safety and interaction label references; regulatory fields from registry records; a catalogue of 10 drugs (lenalidomide, bortezomib, daratumumab, pomalidomide, carfilzomib, dexamethasone, cyclophosphamide, melphalan, fludarabine, ixazomib); pinned label extracts (REVLIMID, NINLARO, VELCADE special populations; carfilzomib, selinexor, thalidomide, isatuximab, elotuzumab); special-population evidence for 6 drugs; drug pages with sources held, their review state and regulatory documents.
- **Where:** `drug_aliases.py`, `drug_knowledge.py`, `mechanisms.py`, `safety.py`, `interactions.py`, `regulatory.py` (owner); `drug_holdings.py`, `special_populations.py`, `*_label.py`, `drug_label_extracts.py`, `landscape_ui/drug_hub.py` (since).
- **State:** the evidence layer for the first release. Catalogue item 8 (growth) is next; the ixazomib catalogue summaries await owner review.

### 3.3 Evidence and review machinery — *built since 13 October*
- **What:** every locked check in one list with failures shown (`/models/findings`); the dataset ledger of what each model was built from, tuned on or checked against, and whether a check was blind; evidence states for pinned values (owner-reviewed, agreed by two extractions, extracted); owner review rounds of AI extractions; model scorecards, capability levels, enforceable model scopes; ICH M15-structured credibility records and analysis reports; an evidence index; source notes.
- **Where:** `check_findings.py`, `dataset_ledger.py`, `evidence_states.py`, `extraction_review.py`, `double_extraction.py`, `model_scorecards.py`, `capability_levels.py`, `model_scope.py`, `scope_registry.py`, `credibility_records.py`, `model_analysis_report.py`, `evidence_index.py`, `source_notes.py`.
- **State:** 37 locked checks; ledger v22 (40 datasets, 13 still unseen); review rounds 1–4 closed. No independent human reviewer yet.

### 3.4 Patient Lab (synthetic patients) — *owner (Oct 5–12), extended since*
- **What (owner):** versioned synthetic patient states with append-only revisions; saved scenarios and comparisons; treatment requests; educational PK runs that are immutable and audited, with sensitivity, metrics, comparisons and HTML/PDF views; model inputs, coverage and binding reviews; a validation-gap register and draft intended use.
- **What (since):** covariate estimation and typical-value PK from published models (Hughes 2019 and Kim 2026 lenalidomide), between-subject variability bands, run records, reference-exposure ratios, kidney-pathway view, ixazomib exposure within scope, the bortezomib platelet model in a patient's own counts, and the record results view.
- **Where:** `patient_state*.py`, `educational_pk*.py`, `saved_scenarios.py` (owner); `covariate_estimation.py`, `estimated_pk.py`, `population_pk.py`, `run_record.py`, `kim_*.py`, `reference_exposure.py`, `patient_*` pages (since). Design: [PATIENT_LAB_2_0.md](PATIENT_LAB_2_0.md).
- **State:** synthetic inputs only; real patients only as a banded profile computed in the browser, never stored (decision 0008; amendment for blood-count bands pending).

### 3.5 Simulation Lab and models — *owner (Oct 5–12) generic tools, drug models since*
- **What (owner):** generic, invented-input teaching mathematics: target occupancy, binding kinetics and pulses, binding–turnover coupling, protein turnover, transit chains and regimens, site exposure–response, a PK compartment timeline, a mechanism map; bortezomib proteasome and time-course research components with evidence, figure, assumption and observation-intake reviews.
- **What (since), by drug:**
  - *Lenalidomide:* Hughes 2019 and Kim 2026 population PK; the platform's kidney-pathway model (2.0a–e); ESRD and dialysis; relative odds of grade 3/4 cytopenia (4.0a); dose view. Checked against CC-5013-PK-001 and Bridoux 2016; mixed results.
  - *Bortezomib:* Lignet 2022 exposure and platelet models; checks against Ogawa, CAN-1004, MMY-3021, Reece; three candidate fixes failed (Kuan, falling clearance, Iwasaki); first blind check (NCT01801436) under-predicts day 11. Closed with the gap shown.
  - *Ixazomib:* Gupta 2017 against the renal and hepatic studies. *Daratumumab:* Luo 2021 against GEN501 and SIRIUS (two checks).
  - *Label-based exposure:* pomalidomide, dexamethasone (with an outside check against NEOFORDEX), melphalan; carfilzomib not eligible.
- **Where:** `intelligence_store/` model and `*_check.py` modules; design and results in `docs/SIMULATION_*.md`, `docs/LABEL_EXPOSURE_ENGINE.md`, `docs/STATUS_BY_DRUG.md`.
- **State:** research tools behind their records; no model is validated.

### 3.6 Digital human (body map) — *built since 31 October*
- **What:** a 3D lenalidomide elimination body map with pinned assets and flow paths, observed-data context, and drug movement over time with its locked check (peak concentration known to be too low).
- **Where:** `body_map*.py`, `glb_mesh.py`, `reference_physiology.py`, `landscape_ui/body_map_pages.py`; design in `docs/DIGITAL_HUMAN_1_*.md`. Organ-level model: lumped first (decision 0005), evidence steps first.

### 3.7 Eligibility extraction and protocol benchmarking — *built since 21 October*
- **What:** an eligibility corpus from a frozen cohort; rule-based extractors v1 and v1.1 and a language-model extractor (Track C); locked accuracy checks (v1 failed); the owner's 200-trial reference annotation (blind data); a second, independent annotation (round two met the 0.90 bar on 19 November); adjudication tooling.
- **Where:** `eligibility_*.py`, `landscape_ui/eligibility_*_pages.py`; [PROTOCOL_BENCHMARKING.md](PROTOCOL_BENCHMARKING.md), [ELIGIBILITY_LLM_EXTRACTOR.md](ELIGIBILITY_LLM_EXTRACTOR.md).
- **State:** next is an adjudicated two-reader reference, then an extractor revision tested only on trials posted after the cohort freeze.

### 3.8 First-release label pipeline — *in progress (20–23 November)*
- **What:** every US prescription label, verbatim, one page per active ingredient, with its review state (decision 0007, the owner's choices of 20 November); storage in insert-only tables rebuilt from DailyMed files listed in a pinned manifest (decision 0009).
- **Where:** `spl_labels.py`, `label_store.py`, `label_pilot.py`, `data/label_ingestion_pilot_plan_v1.json` (draft).
- **State:** reader and tables built and tested (one real label: 97 sections, identical rebuild). The pilot plan was locked on 23 November, with the candidate list from openFDA's Human NDC Directory (56,809 prescription product records with a set ID). Next: the draw, the downloads, the build and the review.

---

## 4. What has been done

### 4.1 The owner's work before AI sessions joined (5–12 October 2026)
Eight commits by the owner built the platform's foundation: 417 files at 12 October.
- **5 October:** the evidence storage foundation (v2 database), application assets, and complete trial-cohort retrieval with evidence provenance.
- **9 October:** the integrated educational Patient Lab milestone (309 files): synthetic patient states, scenarios, educational PK with audits, the Simulation Lab's generic tools, the bortezomib research components, the trial intelligence pages, and their tests.
- **12 October:** a platform checkpoint (101 files), clean-up of files that should not be tracked, and documentation (validation protocol drafts, data-access assessment, source-equation and numerical verification records, the first roadmap).
- Of those 417 files, 379 are still at their original paths (23 November). The others were moved (the step-numbered bortezomib documents into `docs/bortezomib/`, the step 65 and 66 validation records into `docs/patient_lab/`, the patient-state schema into `docs/`), folded into page modules (the install scripts) or removed (loose root files such as `tests.zip`; on 23 November a check script that always failed and three example files nothing used).

### 4.2 The owner's work since (13 October onward)
- Continuous integration (13 October), the research-tool registry consolidation, and the first repository checkpoint.
- Every merge: 134 merge commits, each batch reviewed and merged by the owner.
- Every human review of a value: extraction review rounds 1–4 (including all 166 values that feed calculations), the FDA guidance corrections, Track B disagreements.
- The 200-trial eligibility reference annotation and its re-reading, the adjudication, and recruiting the second annotator.
- Every source obtained (articles, labels, registry records, regulatory reviews) and the author correspondence (Iwasaki answered).
- Every scope decision: evidence first (18 November), every US prescription label (decision 0007 and its four choices), patient profiles not records (0008), storage (0009).

### 4.3 Work with AI sessions (13 October to 23 November)
339 commits (346 with merges), by stream (dates are each stream's first commit):

| From | Stream |
|---|---|
| 13 Oct | Patient Lab 2.0: covariate estimation, published lenalidomide models (Hughes 2019, Kim 2026), variability bands, run records |
| 14 Oct | Simulation 3.0: bortezomib exposure and platelets; label-based exposure engine (3.1) |
| 16 Oct | Simulation 2.0: lenalidomide kidney pathways; Simulation 4.0: relative odds of cytopenia |
| 19 Oct | Phase 1: model scorecards, capability levels, the findings page |
| 21 Oct | Phase 4.1: eligibility corpus, extractors and benchmarking |
| 28–31 Oct | Special populations, dose view, guided path, credibility records (ICH M15), model scope, ixazomib and daratumumab models, the body map |
| 3–4 Nov | Digital human 1.1 (flow and time); dataset ledger; five label extracts |
| 10–13 Nov | AI reviews and their handling; acceptance rule v2; evidence states; Tracks B and C; eligibility round two |
| 18–20 Nov | Evidence first; carfilzomib label check; NCT01801436 blind check; regroup and housekeeping; decisions 0007–0009 |
| 20–23 Nov | Label ingestion pilot tooling |

Process records: [REPOSITORY_CHECKPOINT.md](REPOSITORY_CHECKPOINT.md) (latest verification), [history/](history/) (earlier checkpoints, handoffs, roadmaps), [reviews/](reviews/) (AI reviews), [decisions/](decisions/).

---

## 5. What is planned

The order proposed on 20 November ([roadmap "Now"](PRODUCT_AND_SCIENCE_ROADMAP.md), [REGROUP_2026-11-20.md](REGROUP_2026-11-20.md)); the owner has decided item 1's choices and storage.

1. **Release pipeline:** the pilot plan is locked (23 November); draw and download 50 labels; build, measure, review 80 sections; then plan the full prescription ingest and the drug pages.
2. **Eligibility:** the adjudicated two-reader reference, then the extractor revision on post-freeze trials.
3. **Catalogue growth:** selinexor, thalidomide, isatuximab, elotuzumab first.
4. **An independent reviewer** for the lenalidomide model.
5. **Models (lower priority):** selinexor and thalidomide label-consistency plans; carfilzomib reading plan for the FDA and PMDA reviews, then a model to test blind against Badros and Quach.
6. **Organ-level model:** evidence steps first (decision 0005).
7. **Later:** decision 0008's blood-count bands; going online (Phase 7).

Long-term directions (README): integrated physiology across organ systems, disease progression, combination therapy, and the digital human from body to molecular target.

**Waiting on the owner:** downloading the 50 drawn labels; review of the ixazomib catalogue summaries; deleting the temporary files noted on 18–20 November; an independent reviewer.

---

## 6. Known gaps and risks

- **Models do not hold up against outside data:** of 37 checks, 5 passed or were consistent. Models stay behind their records; no new model page before a model passes a blind check.
- **One human reviewer:** the owner. No independent review yet.
- **Two sessions on one repository:** happened on 20 November; the fetch-and-check rule is in `CLAUDE.md`.
- **Release scale:** the full prescription set is about 55,000 labels; an early estimate puts the manifest near 65 MB, which would trigger the owner's rule to store it elsewhere.
- **Database-backed tests** (about 300) do not run in cloud sessions; CI and the iMac decide them.

---

## Updates

- **23 November 2026:** created from a review of all 1,113 tracked files and the full history (491 commits). Adds `docs/PLATFORM_FILES.md` (every file, generated) and its test.
- **23 November 2026:** the label ingestion pilot plan locked (section 3.8, section 5).
- **23 November 2026:** added "What Marlo Scientific is", at the owner's request.
- **23 November 2026:** clean-up at the owner's request: removed `scripts/check_bortezomib_observation_intake.py` (it always failed: it expected 12 tests, 11 exist) and three unused example files; moved the step 65 and 66 records into `docs/patient_lab/`; corrected out-of-date status lines in five documents; replaced the README's October file tree with a pointer here. The four other unreferenced October scripts run and stay. Fourteen merged GitHub branches and `remove-github-button` are to be deleted by the owner (this session cannot delete branches); `landing-reorg` (an unmerged "About the developer" section, 19 October) is kept.
