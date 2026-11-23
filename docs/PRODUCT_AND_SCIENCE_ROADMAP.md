# Product and science roadmap

Direction recorded 19 October 2026; shortened and verified against the repository on 5 November 2026; the "Now" section rewritten after the regroup of 18 November 2026, and brought to 20 November after the regroup of that day ([REGROUP_2026-11-20.md](REGROUP_2026-11-20.md)). Owner: Astrid Marin. Each phase gives its goal, where it stands, what comes next and where the detail lives. The dated log of every step is in the drug and topic documents (index: [README.md](README.md)) and in the archived full roadmap, [history/PRODUCT_AND_SCIENCE_ROADMAP_2026-11-05.md](history/PRODUCT_AND_SCIENCE_ROADMAP_2026-11-05.md); the 10 October version is also in [history/](history/). Per-drug status in plain language: [STATUS_BY_DRUG.md](STATUS_BY_DRUG.md). Latest software verification: [REPOSITORY_CHECKPOINT.md](REPOSITORY_CHECKPOINT.md).

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
| **Checks planned before they run.** | 37 checks on 20 November, each locked by commit before computation, all at `/models/findings`. The dataset ledger records 8 blind uses, 2 with a deviation. |
| **A regulatory reviewer's structure.** | Partly: for lenalidomide, 19 of 29 reviewer questions answered, 8 partly, 2 gaps, self-scored and corrected after the AI review of 10 November ([REVIEWER_CHECKLIST.md](REVIEWER_CHECKLIST.md)). |
| **The whole chain in one place.** Trial → drug → evidence → exposure → regulatory context. | Partly: a guided path exists for lenalidomide only. |
| **Reproducible snapshots.** Frozen cohorts; checksum-pinned, versioned data. | In place. |
| **AI that cites and is checked.** | In place: the 166 values that feed calculations are owner-reviewed (not independent); review round 3 settled the rest by double extraction and the owner's review of every disagreement (19 November). |
| **Built for the individual expert.** | Product decision; pricing not set. |

Not differentiating on their own, so not the lead message: trial search, dashboards, "AI-powered" claims, and the digital human while it is still distant.

## Phases at a glance (20 November 2026)

| Phase | Goal | Status |
|---|---|---|
| 1. Provenance visible | Any visitor sees what each model checked and failed | **Done** |
| 2. Fix what is known wrong | Bortezomib exposure model | **Closed with the gap shown,** now also blind (NCT01801436); reopens with new data |
| 3. Any drug, at an honest level | Label-based curves for most small molecules | **Early:** 2 drugs shown; carfilzomib not eligible |
| 4. Trial-design support | Benchmark eligibility; dose evidence | **Partly:** the two-reader reference meets its bar; the extractor revision is next |
| 5. AI that cites and is checked | Every extracted value reviewed against its source | **Partly:** rounds 1–4 closed; no independent reviewer yet |
| 6. Credibility records (ICH M15) | An exportable record per model | **Done** (8 records); analysis reports to add |
| 7. Going online | Invited users with private workspaces | **Not started** |
| Digital human | Body map built on checked models | 1.0–1.1e done |

The phases overlap. Every step keeps the rules at the end of this page.

## Phase 1 — Make the provenance visible: done

**Goal:** any visitor can see, for every model, what was checked and what failed, without opening a JSON file.

**Done (19 October – 4 November):** model scorecards (`/models`), capability levels per drug, run records, what the checks found (`/models/findings`), and the dataset ledger ([DATASET_LEDGER.md](DATASET_LEDGER.md)).

## Phase 2 — Fix what is known to be wrong: closed with the gap shown

**Goal:** the bortezomib platelet course rests on an exposure model not contradicted by outside data, *or* the gap is documented and shown.

**Where it stands:** the second outcome. The constant-clearance model cannot reproduce the rise in exposure from day 1 to day 11 in any study tested (Ogawa 2008, CAN-1004, MMY-3021, and its own reproduction study, Reece 2011). Three candidate fixes failed under locked plans (Kuan 2012, an empirical falling clearance, Iwasaki 2020). The first blind check (3.0n, 20 November, NCT01801436) agrees: the constant-clearance and Iwasaki models both under-predict day 11 AUC0-t, and the observed day 11/day 1 rise is 3.7-fold against about 1.5 in the models. The scorecards and the platelet page show this.

**Reopens when:** individual concentration data, or a published mechanism that changes clearance between doses, becomes available.

**Also here (Phase 2.5, model scope):** what each model may be run on is an enforced rule set; requests beyond a model's data are refused ([MODEL_SCOPE.md](MODEL_SCOPE.md)).

**Detail:** [SIMULATION_3_BORTEZOMIB_PLATELETS.md](SIMULATION_3_BORTEZOMIB_PLATELETS.md).

## Phase 3 — Any drug, at an honest level

**Goal:** a user can open most approved small-molecule drugs and see at least a sourced, label-based exposure curve with its capability level.

**Where it stands:**
- Label-based exposure engine built. Pomalidomide and dexamethasone are shown, each after a locked label check and an outside check; melphalan is not eligible (one compartment cannot reproduce its distribution phase).
- Published population models checked against outside data: lenalidomide (Hughes 2019, Kim 2026), ixazomib (Gupta 2017) and daratumumab (Luo 2021), each used only within its scope.
- Five labels extracted by hand (3.2d, 4 November; 74 values), settled in review round 3 (19 November).
- Carfilzomib's label curve is not eligible (19 November): the label's exposure and stated clearance disagree about two-fold *(finding: carfilzomib_label)*.

**Next:** label-consistency plans for selinexor, carfilzomib and thalidomide, after extraction review round 3. Then catalog growth from public sources (openFDA, RxNorm, ChEMBL), and published models beyond myeloma where outside data exist.

**Detail:** [LABEL_EXPOSURE_ENGINE.md](LABEL_EXPOSURE_ENGINE.md), [SIMULATION_3_2_IXAZOMIB.md](SIMULATION_3_2_IXAZOMIB.md), [SIMULATION_3_2B_DARATUMUMAB.md](SIMULATION_3_2B_DARATUMUMAB.md), [PATIENT_LAB_2_0.md](PATIENT_LAB_2_0.md), [SIMULATION_2_RENAL_PATHWAYS.md](SIMULATION_2_RENAL_PATHWAYS.md).

## Phase 4 — Trial design support (oncology, starting with multiple myeloma)

**Goal:** a trial designer can benchmark a draft protocol's eligibility criteria and see the exposure evidence for a dose choice in one session.

**Where it stands:**
- **Protocol benchmarking:** extractor v1 failed its locked check (all eight criterion types); v2 was locked with 200 new trials and a pass rule sized to the sample.
- **18 November:** both extractors then failed every type blind (13 November), and the reference itself is not yet shown adequate (two readers agreed on 0.8925 of pairs against a 0.90 bar; adjudication found the reference wrong in at least 31 of 400). Round two under guide v3 was locked, with a miss meaning benchmarking is recorded as not validated ([decision 0006](decisions/0006-eligibility-round-two-miss-rule.md)).
- **19 November:** round two met the bar, lower bound 0.9125 against 0.90 *(finding: eligibility_second_annotation_v2)*.
- **Special populations** for six drugs, and the **dose view** and **guided path** for lenalidomide: built.

**Next:** an adjudicated two-reader reference under its own plan (round two's 22 disagreements), then an extractor revision tested only on trials posted after the cohort freeze, then the benchmarking page with passing criterion types only.

**Detail:** [PROTOCOL_BENCHMARKING.md](PROTOCOL_BENCHMARKING.md), [SPECIAL_POPULATIONS.md](SPECIAL_POPULATIONS.md), [DOSE_OPTIMISATION.md](DOSE_OPTIMISATION.md).

## Phase 5 — AI that cites and is checked

**Goal:** extraction speeds up curation measurably, and no unsourced statement reaches a user.

**Where it stands:** every extracted value links to its source page; unreviewed values never feed a model. Owner review rounds 1–2 cover all 166 values that feed calculations (all match). Round 3 closed on 19 November by double extraction: 102 match, 7 FDA guidance entries wrong and corrected, 12 agreements accepted under the plan's sampling rule (labelled as such, not as owner-reviewed). Round 4: the 14 ixazomib catalogue entries, all match.

**Next:** an independent reviewer. The AI-written catalogue summaries are to be replaced by verbatim label sections once the label pilot passes, so the review of the ixazomib summaries is dropped (decision 0007, amendment of 23 November). Later: plain-language questions answered only from platform data, and cited summaries.

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
- **Done 9 November:** 1.1e, the timeline and running amounts (a 2D panel; the 3D viewer is unchanged).
- **Later:** kidney-to-nephron zoom, the target explorer (cereblon), and a female reference body with hormone effects (owner's goal).

**Detail:** [DIGITAL_HUMAN_1_LENALIDOMIDE_ELIMINATION.md](DIGITAL_HUMAN_1_LENALIDOMIDE_ELIMINATION.md), [DIGITAL_HUMAN_1_1_FLOW_AND_TIME.md](DIGITAL_HUMAN_1_1_FLOW_AND_TIME.md).

## Long term — the computational human

Multi-organ physiology, disease progression, combination therapies, the body → organ → tissue → cell → target interface, and mechanistic + machine-learning hybrid models. Each builds only on models that have passed the earlier phases' checks.

## Now (20 November 2026): evidence first, the release pipeline next

Decided with the owner on 18 November ([REGROUP_2026-11-18.md](REGROUP_2026-11-18.md)) and brought to 20 November ([REGROUP_2026-11-20.md](REGROUP_2026-11-20.md), whose order of next steps is proposed, not yet decided). Earlier versions of this section are in [history/](history/) (18 and 20 November). The 4 November rule still holds: consolidate and check before adding.

**Scope, 19 November:** the first release covers every drug with a US label, built automatically from the label with its review state shown, not only myeloma ([decision 0007](decisions/0007-first-release-covers-every-us-labelled-drug.md); five open choices for the owner). Hand-built drug pages stop at the ten catalogue drugs until the pipeline exists.

**Patients, 20 November:** the owner's aim is to compare what trials found with a real person's situation and to show how a drug behaves in bodies like theirs, for women and men. A real patient enters only as a banded profile that many people share, computed in the browser and never sent or stored ([decision 0008](decisions/0008-patient-profiles-not-patient-records.md)). Outputs describe patients matching the profile, never what one patient will gain; a privacy lawyer reviews the design before real patients' profiles are invited.

**Direction.** The first release leads with sourced evidence: the trial landscape, special-population evidence, regulatory references and the check findings. The models stay research tools behind their credibility records, because two months of checks show most of them carry a recorded disagreement or an indeterminate result (37 locked checks on 20 November; 8 blind uses in the ledger). No outside user conversations yet; the owner works with one engineer, and will include an independent reviewer.

**Done 19–20 November:** review rounds 3 and 4 closed; eligibility round two met its bar; carfilzomib's label curve not eligible (Badros 2013 and Quach 2017 stay unread until a published carfilzomib model is chosen to test against them, the owner's choice); evidence-first items 1–7; decisions 0007 and 0008; bortezomib's first blind check (3.0n, both models under-predict day 11).

**Queue, in the order proposed on 20 November:**
1. **The release pipeline:** the owner answered decision 0007's choices on 20 November; storage is decision 0009 (accepted); then a pilot of about 50 labels on the owner's computer, with sampled review.
2. **Eligibility:** an adjudicated two-reader reference under its own plan (round two's 22 disagreements), then an extractor revision tested only on trials posted after the cohort freeze, never on the 200.
3. ~~Catalogue growth~~ (evidence-first item 8): dropped on 23 November; these drugs come in through the label pipeline (decision 0007, amendment).
4. **An independent reviewer** for the lenalidomide model and its credibility record.
5. **Models, lower priority:** selinexor and thalidomide label-consistency plans; a reading plan for the FDA and PMDA carfilzomib reviews (population-model sections only), then a carfilzomib model to test blind against Badros and Quach.
6. **Organ-level model:** lumped compartments first ([decision 0005](decisions/0005-organ-level-model-lumped-first.md)). Phased-plan steps 2 and 4, the tissue-distribution evidence and evidence classes on the map, are evidence work and come first; the model and its check follow.
7. **Later:** decision 0008's blood-count bands; Phase 7, once the release scope is concrete.

**Blocked or waiting:**
- **Lenalidomide kidney model:** every renal-impairment dataset available has been seen.
- **Bortezomib exposure:** individual concentrations or a mechanism (Phase 2); the first blind check (3.0n) did not change this. Zhang and Mager 2015 and the 2020 supplement are held unread.
- **Exposure–efficacy for lenalidomide (O7):** recorded as a gap in the published evidence, and searching stopped (reviewer's checklist O7, 18 November). Reopens only if an analysis is published or released.
- **Author answers, none blocking:** Zhang and Mager (reprint requested 17 November), Hughes (LinkedIn, pending), Kim (email bounced 18 November). Iwasaki answered on 24 and 30 October (equations, dose input, attribution; SIMULATION_3_BORTEZOMIB_PLATELETS.md 3.0j–3.0l); the line here saying he was never contacted, written 18 November, was wrong and was corrected on 20 November.

**Repository:** work goes in batches: one commit per update, one push and one pull request per batch, the branch pushed when its first commit exists (`CLAUDE.md`, HANDOFF). No model is validated for clinical prediction.

## Rules that do not change

- Every drug may have identity, mechanism, safety and interaction references without any simulation model. These are recorded independently.
- Each new model records: drug, formulation, route, schedule and disease context; the endpoint; equations, inputs, units, source locations and versions; population, dose and sampling coverage with extrapolation limits; verification, source review, outside-data evaluation and uncertainty; and what the output supports for a synthetic profile.
- Checks follow a plan locked before computation; a blind claim must pass the dataset ledger's gate.
- A group mean is not an individual observation. Marginal covariate ranges do not establish joint coverage. A generic demonstration is never relabelled as a researched drug model.
- Software verification is kept distinct from empirical or independent scientific validation. Passing every check supports research use only.
