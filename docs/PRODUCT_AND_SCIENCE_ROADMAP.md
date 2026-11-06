# Product and science roadmap

Direction recorded 19 October 2026; shortened and verified against the repository on 5 November 2026. Owner: Astrid Marin. Each phase gives its goal, where it stands, what comes next and where the detail lives. The dated log of every step is in the drug and topic documents (index: [README.md](README.md)) and in the archived full roadmap, [history/PRODUCT_AND_SCIENCE_ROADMAP_2026-11-05.md](history/PRODUCT_AND_SCIENCE_ROADMAP_2026-11-05.md); the 10 October version is also in [history/](history/). Per-drug status in plain language: [STATUS_BY_DRUG.md](STATUS_BY_DRUG.md). Latest software verification: [REPOSITORY_CHECKPOINT.md](REPOSITORY_CHECKPOINT.md).

## Positioning

**Marlo Scientific is the evidence reference for people designing and running drug development.** Search what has been done, see what the evidence supports, and trace every number to its source.

In one line: *drug development evidence you can trace, reproduce and trust — every number sourced, every model checked, every limitation shown.*

- **It is** a clinical *research* reference: trials, drug and regulatory evidence, and transparent pharmacology models, for research, trial design and education.
- **It is not** a clinical *care* reference. It does not inform the treatment of individual patients, and it is not a medical device ([intended use](../app/templates/intended_use.html), served at `/intended-use`).
- **The long-term vision stays:** a computational human where a drug can be followed from body to organ, tissue, cell and target. The near-term product earns the credibility that vision needs.

## Who it is for

| User | Question they bring | What the platform answers with |
|---|---|---|
| Clinical trial designers and clinical operations | What have similar trials done? | Trial landscape, eligibility comparisons, designs, sites |
| Clinical pharmacologists and pharmacometricians | What does the evidence say about this drug's exposure, and how credible is this model? | Special-population and exposure evidence, models with credibility records |
| Regulatory affairs and medical writers | How do I justify this dose or population, and what did regulators say about similar drugs? | Sourced evidence summaries, regulatory context |
| Educators and students | How does pharmacology actually behave? | Safe, synthetic, explained simulations |

Primary users first: trial designers, clinical pharmacologists and regulatory professionals. Education is a secondary use of the same tools.

## What makes it different

| Differentiator | Status |
|---|---|
| **Shows its work.** Every value carries its source; every model shows what has and has not been checked, including failures. | In place: run records, scorecards at `/models`, a capability level on every drug. |
| **Checks planned before they run.** | 27 checks, each locked by commit before computation, all at `/models/findings`. Only 3 were blind (dataset ledger). |
| **A regulatory reviewer's structure.** | Partly: for lenalidomide, 21 of 29 reviewer questions answered, 6 partly, 2 gaps ([REVIEWER_CHECKLIST.md](REVIEWER_CHECKLIST.md)). |
| **The whole chain in one place.** Trial → drug → evidence → exposure → regulatory context. | Partly: a guided path exists for lenalidomide only. |
| **Reproducible snapshots.** Frozen cohorts; checksum-pinned, versioned data. | In place. |
| **AI that cites and is checked.** | In place for the 166 values that feed calculations (owner-reviewed, not independent). The 74 values of the 4 November labels are not reviewed. |
| **Built for the individual expert.** | Product decision; pricing not set. |

Not differentiating on their own, so not the lead message: trial search, dashboards, "AI-powered" claims, and the digital human while it is still distant.

## Phases at a glance (5 November 2026)

| Phase | Goal | Status |
|---|---|---|
| 1. Provenance visible | Any visitor sees what each model checked and failed | **Done** |
| 2. Fix what is known wrong | Bortezomib exposure model | **Closed with the gap shown;** reopens with new data |
| 3. Any drug, at an honest level | Label-based curves for most small molecules | **Early:** 2 drugs shown |
| 4. Trial-design support | Benchmark eligibility; dose evidence | **Partly:** benchmarking waits for the annotation |
| 5. AI that cites and is checked | Every extracted value reviewed against its source | **Partly:** 166 reviewed, 74 not |
| 6. Credibility records (ICH M15) | An exportable record per model | **Done** (8 records); analysis reports to add |
| 7. Going online | Invited users with private workspaces | **Not started** |
| Digital human | Body map built on checked models | 1.0–1.1d done; 1.1e paused |

The phases overlap. Every step keeps the rules at the end of this page.

## Phase 1 — Make the provenance visible: done

**Goal:** any visitor can see, for every model, what was checked and what failed, without opening a JSON file.

**Done (19 October – 4 November):** model scorecards (`/models`), capability levels per drug, run records, what the checks found (`/models/findings`), and the dataset ledger ([DATASET_LEDGER.md](DATASET_LEDGER.md)).

## Phase 2 — Fix what is known to be wrong: closed with the gap shown

**Goal:** the bortezomib platelet course rests on an exposure model not contradicted by outside data, *or* the gap is documented and shown.

**Where it stands:** the second outcome. The constant-clearance model cannot reproduce the rise in exposure from day 1 to day 11 in any study tested (Ogawa 2008, CAN-1004, MMY-3021, and its own reproduction study, Reece 2011). Three candidate fixes failed under locked plans (Kuan 2012, an empirical falling clearance, Iwasaki 2020). The scorecards and the platelet page show this.

**Reopens when:** individual concentration data, or a published mechanism that changes clearance between doses, becomes available.

**Also here (Phase 2.5, model scope):** what each model may be run on is an enforced rule set; requests beyond a model's data are refused ([MODEL_SCOPE.md](MODEL_SCOPE.md)).

**Detail:** [SIMULATION_3_BORTEZOMIB_PLATELETS.md](SIMULATION_3_BORTEZOMIB_PLATELETS.md).

## Phase 3 — Any drug, at an honest level

**Goal:** a user can open most approved small-molecule drugs and see at least a sourced, label-based exposure curve with its capability level.

**Where it stands:**
- Label-based exposure engine built. Pomalidomide and dexamethasone are shown, each after a locked label check and an outside check; melphalan is not eligible (one compartment cannot reproduce its distribution phase).
- Published population models checked against outside data: lenalidomide (Hughes 2019, Kim 2026), ixazomib (Gupta 2017) and daratumumab (Luo 2021), each used only within its scope.
- Five labels extracted by hand (3.2d, 4 November; 74 values, nothing computed).

**Next:** label-consistency plans for selinexor, carfilzomib and thalidomide, after extraction review round 3. Then catalog growth from public sources (openFDA, RxNorm, ChEMBL), and published models beyond myeloma where outside data exist.

**Detail:** [LABEL_EXPOSURE_ENGINE.md](LABEL_EXPOSURE_ENGINE.md), [SIMULATION_3_2_IXAZOMIB.md](SIMULATION_3_2_IXAZOMIB.md), [SIMULATION_3_2B_DARATUMUMAB.md](SIMULATION_3_2B_DARATUMUMAB.md), [PATIENT_LAB_2_0.md](PATIENT_LAB_2_0.md), [SIMULATION_2_RENAL_PATHWAYS.md](SIMULATION_2_RENAL_PATHWAYS.md).

## Phase 4 — Trial design support (oncology, starting with multiple myeloma)

**Goal:** a trial designer can benchmark a draft protocol's eligibility criteria and see the exposure evidence for a dose choice in one session.

**Where it stands:**
- **Protocol benchmarking:** extractor v1 failed its locked check (all eight criterion types). v2 is locked with 200 new trials and a pass rule sized to the sample. **The owner's annotation is the platform's only unseen dataset**, so the extractor must not be run on it before the check.
- **Special populations** for six drugs, and the **dose view** and **guided path** for lenalidomide: built.

**Next:** the annotation, the locked v2 check, then the benchmarking page with passing criterion types only.

**Detail:** [PROTOCOL_BENCHMARKING.md](PROTOCOL_BENCHMARKING.md), [SPECIAL_POPULATIONS.md](SPECIAL_POPULATIONS.md), [DOSE_OPTIMISATION.md](DOSE_OPTIMISATION.md).

## Phase 5 — AI that cites and is checked

**Goal:** extraction speeds up curation measurably, and no unsourced statement reaches a user.

**Where it stands:** every extracted value links to its source page; unreviewed values never feed a model. Owner review rounds 1–2 cover all 166 values that feed calculations (all match).

**Next:** review round 3 (the 74 label values and the rest of the REVLIMID section 12.3); an independent reviewer. Later: plain-language questions answered only from platform data, and cited summaries.

**Detail:** [EXTRACTION_REVIEW.md](EXTRACTION_REVIEW.md).

## Phase 6 — Model credibility records (ICH M15): done, one addition

**Goal:** each platform model has an exportable credibility record that a reviewer can read without the code.

**Done:** eight records (six registered models, two label curves) at `/models/credibility`, each downloadable with its checksum.

**Next:** one readable model analysis report per model, in ICH M15's section order, generated from the pinned plans and reports (reviewer's checklist M3). Later: teams document their own models in the same structure.

**Detail:** [CREDIBILITY_RECORDS.md](CREDIBILITY_RECORDS.md).

## Phase 7 — Going online

**Goal:** invited users can use the platform online with their own private workspace.

**Steps:** production server, hosted database, secrets, backups and monitoring; accounts and access control before any public write access; privacy, security and intended-use review by a qualified person before charging; pricing for individual experts and small teams. **Not started.**

## Digital human track

The visual layer of the long-term vision, built only on models that have passed the earlier checks.
- **Done:** 1.0, the lenalidomide elimination body map on Human Reference Atlas anatomy, with kidney-function bands carrying their check status; 1.1a–1.1d, blood flow (ICRP 89), per-pass kidney extraction, vessel-following flow paths, and a time course (v1 shown with its warnings; v2 not adopted).
- **Next, paused during consolidation:** 1.1e, the timeline and running amounts.
- **Later:** kidney-to-nephron zoom, the target explorer (cereblon), and a female reference body with hormone effects (owner's goal).

**Detail:** [DIGITAL_HUMAN_1_LENALIDOMIDE_ELIMINATION.md](DIGITAL_HUMAN_1_LENALIDOMIDE_ELIMINATION.md), [DIGITAL_HUMAN_1_1_FLOW_AND_TIME.md](DIGITAL_HUMAN_1_1_FLOW_AND_TIME.md).

## Long term — the computational human

Multi-organ physiology, disease progression, combination therapies, the body → organ → tissue → cell → target interface, and mechanistic + machine-learning hybrid models. Each builds only on models that have passed the earlier phases' checks.

## Now: consolidate before adding

Agreed with the owner on 4 November: the platform has grown faster than it has been used or checked (27 checks, 3 blind; about 165 pinned data files; 33 docs). Until user conversations are possible, work consolidates and reviews rather than adds.

**Done:** full suite on the owner's Mac and the 4 and 5 November checkpoints; docs index by question, status by drug and the data-file index; the reviewer's checklist; an AI review of the kidney pathway model and the bioavailability re-check (2.0e); this roadmap verified and shortened.

**Batch 1 (done; PR #113, merged 5 November):** commit-count rules; roadmap verified and shortened; FDA 2024 kidney categories and each model's kidney-function measure (R1, R2); the rest of REVLIMID sections 12.3 and 7, shown on the special-populations page and in the guided path (O1, O2, O5); the 5 November checkpoint. Checklist 17 answered, 9 partly, 3 gaps.

**Batch 2 (done; PR #114, merged 6 November; CI 1,310 tests):** review round 3 opened (113 entries); label kidney doses and exposure (R9); the label's 82% shown not to change 2.0e; credibility records v3; the first model analysis report (M3); liver-function classifications (H2). Checklist 19 answered, 8 partly, 2 gaps.

**Moved to the iMac, 6 November.** The project now runs on the owner's iMac (1,310 tests passing there). Moving it showed that annotations were saved in `app/instance/` while the database was in `instance/`.

**Batch 3 (in progress; one pull request):**
1. One instance folder for the database, workspace key and annotations (done).
2. Model analysis reports for Hughes 2019 and Kim 2026 (M3) (done).
3. What is known in dialysis, on the special-populations page (R7) (done).
4. Assay summary for the kidney studies (O8) (done; added to review round 3).
5. Precision of the dose-exposure ratios (R5), if the published variability supports it.
6. Checkpoint.

**Then:** the exposure–safety analysis report; label-consistency plans for selinexor, carfilzomib and thalidomide once round 3 is done.

**Owner's work:** the v2 eligibility annotation, then its locked check; extraction review round 3 when there is time.

**Paused:** special-population pages and label curves for the five new drugs (until round 3), Digital human 1.1e, and further kidney or bortezomib modelling without new data.

**Blocked or waiting:**
- **Lenalidomide kidney model:** every available renal-impairment dataset has been seen; a further check needs unseen data.
- **Bortezomib exposure:** individual concentration data or a mechanism (Phase 2).
- **Author answers:** Hughes (Cockcroft–Gault weight basis), Kim (CL/F equation form), Iwasaki (which human data evaluated the model).
- **People:** user conversations with five to ten trial designers, clinical pharmacologists or regulatory professionals, and an independent human reviewer. Postponed by the owner.

**Repository:** GitHub reconnected on 5 November; PR #112 and PR #113 merged after CI passed. Work goes in batches: one commit per update, one push and one pull request per batch (`CLAUDE.md`). No model is validated for clinical prediction.

## Rules that do not change

- Every drug may have identity, mechanism, safety and interaction references without any simulation model. These are recorded independently.
- Each new model records: drug, formulation, route, schedule and disease context; the endpoint; equations, inputs, units, source locations and versions; population, dose and sampling coverage with extrapolation limits; verification, source review, outside-data evaluation and uncertainty; and what the output supports for a synthetic profile.
- Checks follow a plan locked before computation; a blind claim must pass the dataset ledger's gate.
- A group mean is not an individual observation. Marginal covariate ranges do not establish joint coverage. A generic demonstration is never relabelled as a researched drug model.
- Software verification is kept distinct from empirical or independent scientific validation. Passing every check supports research use only.
