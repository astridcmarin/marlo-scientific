# Product and science roadmap

Direction recorded 19 October 2026; status updated 5 November 2026 (claims verified against the repository). Owner: Astrid Marin. The previous roadmap (10 October 2026) is kept in [history/PRODUCT_AND_SCIENCE_ROADMAP_2026-10-10.md](history/PRODUCT_AND_SCIENCE_ROADMAP_2026-10-10.md). The latest verification is in [REPOSITORY_CHECKPOINT.md](REPOSITORY_CHECKPOINT.md).

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

| Differentiator | Status in the code |
|---|---|
| **Shows its work.** Every value carries its source; every model shows what has and has not been checked, including failures. | In place and visible: run records, four validation layers, public scorecards at `/models`, a capability level on every drug (Phase 1.1–1.2). |
| **Checks planned before they run.** Comparisons with outside data follow a plan locked by commit before computation. | In place for 27 checks, all listed with their results at `/models/findings`, failures included. The dataset ledger records which data each model has seen: only 3 checks were blind. |
| **A regulatory reviewer's structure.** Evidence organized like a clinical pharmacology review: special populations, interactions, exposure–response, dose justification. | Partly. Scored against an FDA clinical pharmacology reviewer's questions for lenalidomide: 12 of 29 answered, 13 partly, 4 gaps ([REVIEWER_CHECKLIST.md](REVIEWER_CHECKLIST.md)). To generalize. |
| **The whole chain in one place.** Trial → drug → evidence → exposure → regulatory context, with the links kept. | Partly: a guided path through the whole chain exists for lenalidomide only. |
| **Reproducible snapshots.** Frozen cohorts and checksum-pinned, versioned reference data. | In place. |
| **AI that cites and is checked.** Extracted values link to their source page and show whether a person confirmed them. | In place for the 166 values that feed calculations: reviewed against the sources by the platform owner (rounds 1–2, 3–4 November) and shown on model, label, special-population and dose pages. Not independent; the 74 values of the 4 November labels are not yet reviewed. |
| **Built for the individual expert.** Rigorous and affordable for consultants, academics and small teams. | Product decision; pricing not set. |

Not differentiating on their own, so not the lead message: trial search, dashboards, "AI-powered" claims, and the digital human while it is still distant.

## Where we are (5 November 2026)

| Area | Status |
|---|---|
| Clinical trial intelligence | **Available:** explorer at `/trials`, cohorts, normalization and regulatory indicators. The myeloma interventional cohort (3,450 trials) is pinned as an eligibility corpus. |
| Drug and regulatory knowledge | **Foundation:** nine curated drug entities, plus pinned label extracts for carfilzomib, selinexor, thalidomide, isatuximab and elotuzumab (3.2d, 4 November; 74 values, nothing computed yet). |
| Exposure models | **Lenalidomide:** Hughes 2019, Kim 2026 and the kidney-pathway model. Hughes and Kim under-predict moderate and severe kidney impairment in CC-5013-PK-001 and again in myeloma patients (Bridoux 2016: the first blind check of a published population model, with a recorded deviation; the first blind check overall was the dexamethasone label curve's, 21 October). The pathway model's moderate and severe results depend on bioavailability, which was not measured (at least about 90% absorbed): no single value fits CC-5013-PK-001's moderate group and the other studies at once (2.0e), so both bands are marked accordingly and "elimination falls faster than kidney function" is not established. A steeper-secretion version was not adopted (2.0d). **Bortezomib:** the PK component disagrees with three outside studies and its own reproduction study; three candidate fixes failed. **Ixazomib, daratumumab:** checked against outside data, used within their scopes. |
| Model scope (Phase 2.5) | Enforced rule sets with evidence tiers; requests beyond a model's data are refused. |
| Label-based exposure (Phase 3.1) | Pomalidomide and dexamethasone shown, each after a locked label check and an outside check. Melphalan not eligible. |
| Effect and safety models | Bortezomib platelet course; lenalidomide relative odds of grade 3/4 cytopenia. |
| Protocol benchmarking (Phase 4.1) | v1 failed its locked check. v2 is locked with 200 new trials; **the owner's annotation is the platform's only remaining unseen dataset.** |
| Special populations, dose view, guided path (Phase 4.2–4.4) | Built for six drugs (special populations) and lenalidomide (dose view, guided path). |
| Extraction review (Phase 5.1) | **Complete for the 166 listed values** (all match; reviewed by the platform owner, not independently). |
| Credibility and provenance (Phase 6) | Run records, scorecards, ICH M15 credibility records, evidence status v16, the **dataset ledger** (v4), **what the checks found** (`/models/findings`) and the first **AI review** (`docs/reviews/`, not independent). |
| Digital human | **1.0 done; 1.1a–1.1d done:** lenalidomide elimination body map on Human Reference Atlas anatomy, with blood flow from ICRP 89, per-pass kidney extraction, vessel-following flow paths, navigation and a flow key. Time course v1 (peak under-predicted) is used; v2 (two compartments) was not adopted. 1.1e (timeline drawn) next. |
| Interface | Landing page, shared Aurora design, logo and favicon, sidebar by research workflow. |
| Online | Not deployed. No accounts. GitHub reconnected on 5 November: the offline work (49 commits) was merged as PR #112 after CI passed. The account had been flagged for too many commits, so work now goes in batches: one commit per update, one push and one pull request per batch of about five (`CLAUDE.md`). |

Latest verification: [repository checkpoint, 4 November 2026](REPOSITORY_CHECKPOINT.md), all 1,243 tests passing on the owner's Mac; CI passed on PR #112 (5 November) with the 2.0e changes included. No model is validated for clinical prediction.

## Phases

The phases overlap. Each step keeps the existing rules: pinned and versioned sources, plans locked before checks, synthetic records only, and validation flags false unless a documented review changes them.

### Phase 1 — Make the provenance visible

The differentiator already exists in the code; users cannot see it yet.

1. **Model scorecards** (`/models`): one public page per registered model with its source, intended scope, the four validation layers, recorded findings and failures, and the reports behind them. Built from `model_evidence_status_v5.json`; nothing new is computed. **Built 19 October 2026:** `/models` and `/models/<id>`, with recorded outside-data disagreements, inherited warnings (the platelet model through the bortezomib PK model), cited reports served only while their checksums match, and links from the landing page, the footer and every run record.
2. **Capability levels per drug**: *Knowledge only*, *Label-based exposure*, *Published model*, *Published model checked against outside data*. Shown in the drug library and on every drug page. **Built 19 October 2026** (inventory v1.3): derived from the curated catalogs and the scorecards; lenalidomide and bortezomib are at *Published model, checked against outside data* with their recorded disagreements, the other seven curated drugs at *Knowledge only*; *Label-based exposure* was first assigned on 20 October 2026, to pomalidomide (Phase 3.1e).
3. **Repository checkpoint refresh** covering the work since 16 October. **Done 21 October 2026** ([checkpoint](REPOSITORY_CHECKPOINT.md)): all checks pass; two unpinned review packets now frozen by a test.

*Done when:* any visitor can see, for every model, what was checked and what failed, without opening a JSON file.

### Phase 2 — Fix what is known to be wrong

1. **Bortezomib PK with clearance that falls over repeated doses.** Find a published model; lock a check plan; compare with Ogawa 2008 (data already in the repository). If it fits, rebuild the platelet course on it; if not, record why.

*Done when:* the platelet simulation rests on an exposure model that is not contradicted by the outside data, or the gap is documented and shown.

**19 October 2026, first candidate (Simulation 3.0g):** the Kuan 2012 poster model (saturable return from a deep compartment) was checked against Ogawa 2008 under a plan locked beforehand. Under neither reading of its saturable term does it reproduce the day 1 → day 11 rise, so it cannot be implemented from the poster as printed. Nothing on the platform changed. Next: the authors' model code or a full paper, and the Iwasaki 2020 target-mediated PBPK model (paper requested from the authors).

**20 October 2026, second outside study (Simulation 3.0h):** the current constant-clearance model was checked against CAN-1004 (FDA review of NDA 021602 S-027, 72 h sampling) under a locked plan. Day 1 is consistent; day 11 is under-predicted (127 vs 241 ng·h/mL), robust across all NCA readings. With Ogawa, both outside studies show a larger day 1 → day 11 rise than a constant clearance allows. CAN-1004 now gives a second dataset for any candidate model.

**20 October 2026, empirical falling clearance (Simulation 3.0i):** two one-parameter forms of a clearance that falls over repeated doses, calibrated on CAN-1004 under a locked plan, could not reach the CAN-1004 day 11 exposure, so neither was tested against Ogawa. Post hoc, a constant lower clearance reproduces CAN-1004's summary values, while Ogawa's rise comes from its short day 1 half-life: summary means cannot identify the time course. The remaining routes are individual concentration data or the Iwasaki 2020 target-binding model.

**26–29 October 2026, Iwasaki 2020 (Simulation 3.0j–3.0k):**
- **Transcription (3.0j):** the author sent the model equations on request; they are transcribed and pinned.
- **Locked check (3.0k):** the model is **not consistent with either study, and the result is robust**. It over-predicts Ogawa day 1 (107 vs 46.5 ng·h/mL) and under-predicts the day 11 / day 1 ratio (2.0 vs 5.1) and CAN-1004 day 11 (135 vs 241).
- **Why:** the model reproduces the constant-clearance pattern. Red-cell binding fills only partly (24% → 38%) and drug dissociates within hours, so it does not change exposure much between doses.
- **Open assumptions:** independence is pending (the article does not cite either study). The dose input was confirmed by the author on 30 October 2026 (an IV bolus into the central compartment, as assumed), and citing the article is the agreed attribution (3.0l).
- **Where Phase 2 stands:** three candidates have now failed. What remains is individual concentration data, or a mechanism that changes clearance between doses.

**31 October 2026, a third outside study (Simulation 3.0m):** MMY-3021 (Moreau 2012; IV, n = 14, day 11 only). Day 11 exposure is consistent at the edge of the interval and not robust (126.9 vs 126.2–175.8); peak concentration is under-predicted. The two studies' day 11 means differ 1.6-fold (CAN-1004 241, MMY-3021 151). There is no day 1 profile, so the main finding, that the rise from day 1 to day 11 is too small, is untested here and stands.

**31 October 2026, reproduction check (Simulation 3.0n):** Reece 2011, the study the model's source compared it with. The model does not reproduce it: day 1 exposure is about 2-fold too high at both doses, and the rise to day 11 is 1.5-fold against 2.4–3.1. The pattern matches the outside studies, which points to the constant clearance itself.

**30 October 2026, model scope (Phase 2.5)** ([MODEL_SCOPE.md](MODEL_SCOPE.md)): what each model may be run on is now a pinned rule set, not prose. Following the owner's decision for lenalidomide, the Patient Lab computes and flags results where an outside check disagrees inside the model's data (showing the observed data), and refuses beyond the model's data. Hughes, Kim, ixazomib and daratumumab have scopes; the ixazomib exposure page is the first page built on one.

### Phase 3 — Any drug, at an honest level

1. **Label-based exposure engine**: a one- or two-compartment typical-value curve from label parameters (clearance, volume, half-life, bioavailability, fraction excreted unchanged), with the label's own kidney and liver guidance. Tagged *Label-based*; never presented like a population model. **Design plan written 20 October 2026** ([LABEL_EXPOSURE_ENGINE.md](LABEL_EXPOSURE_ENGINE.md)): one compartment, label fold-changes as scenarios only, eligibility rules, and an internal-consistency check before any curve is drawn. Pilot: pomalidomide. **20 October 2026 (3.1b–3.1c):** label and Li 2017 extracts pinned; engine built; under a locked plan the myeloma-only parameter set reproduces the label's steady-state Cmax (71.6 vs 75 ng/mL), while the label's pooled clearance and volume ranges would predict about half the myeloma exposure and fail. **3.1d:** the selected curve is consistent with the Li 2017 population model (AUC 860 vs simulated 788, 90% interval 602–1026; peak ratio 1.21, trough 0.97), and the label's dialysis fold (1.38) matches Li's (1.38); a model-to-model check, not observed data. **3.1e:** pomalidomide is the first drug at *Label-based exposure*, with a page showing the curve, one label scenario at a time, both checks and the peak caveat; the landing page links to it and now flags the bortezomib exposure model's disagreements. **3.1f, melphalan (EVOMELA):** not eligible under a locked plan; a one-compartment infusion curve under-predicts the label's peak (3.64 vs 5.8 µg/mL) because of melphalan's distribution phase, and the label's clearance and volume ranges imply a 197-minute half-life against the stated 75. Melphalan needs a published two-compartment model instead. **3.1f, dexamethasone (HEMADY):** passes its label check under a locked plan (clearance and AUC within 1%, peak 186 vs 247 ng/mL, ratio 0.75); not shown until an outside check, as the 3.1e rule requires. **3.1g:** consistent with the NEOFORDEX EPAR studies under a locked plan (myeloma patients: AUC ratio 0.70 inside a wide 6-patient interval; healthy volunteers: 1.05–1.12); patients' apparent clearance was lower than the label's, a caveat any display must carry. **3.1h:** dexamethasone shown at *Label-based exposure* with those caveats; two drugs now at that level.
2. **Drug catalog growth** from public sources (FDA labels via openFDA, RxNorm names, ChEMBL targets). Each entry sourced, versioned and marked reviewed or not reviewed.
3. **More published population models with outside checks.** **30 October 2026:** ixazomib (Gupta 2017, 3.2a) is consistent with the dedicated renal and hepatic studies in myeloma patients with normal kidney function, under-predicts solid-tumour patients about 1.4-fold and puts peaks 2–4-fold low, so the platform shows AUC only. Daratumumab (Luo 2021, 3.2b–3.2c) reproduces the GEN501 and SIRIUS peaks but over-predicts the 16 mg/kg first-week AUC, and the albumin effect runs the other way across the two studies; its scope is defined but no page runs it. Neither model passed its plan's registration rule; both are used only within their scopes.
4. **First published models beyond myeloma**, chosen where outside data exist for a check.
5. **More labels by hand (3.2d, 4 November 2026).** DailyMed is unreachable from the development environment, so the owner downloaded five current labels. Carfilzomib, selinexor and thalidomide are label-engine candidates (each needs a locked consistency plan); isatuximab and elotuzumab are antibodies with target-mediated clearance and get special-population summaries only.

*Done when:* a user can open most approved small-molecule drugs and see at least a sourced, label-based exposure curve with its capability level.

### Phase 4 — Trial design support (first focus: oncology, starting with multiple myeloma)

1. **Protocol benchmarking**: compare eligibility criteria across similar trials (kidney and liver cutoffs, blood-count thresholds, prior therapy), with counts and links to each trial. **Design plan written 21 October 2026** ([PROTOCOL_BENCHMARKING.md](PROTOCOL_BENCHMARKING.md)): eight criterion types, rule-based extraction, and a hand-annotated validation sample with pass thresholds fixed before any check.
   - **v1 (4.1a–4.1e, 21–28 October):** corpus pinned (3,450 trials), 120 trials annotated by hand. In the locked check, **all eight types failed**: precision 0.73–0.83, recall 0.64–0.80. In a post-hoc analysis, the largest cause was a convention: exclusion criteria were annotated as written, not as the eligible side. The pass rule was also unreachable at that sample size.
   - **v2 (4.2a–4.2b, 28 October):** a fresh 200-trial sample. Comparators are recorded as written and the eligible side is derived. The pass rule is sized to the sample (precision ≥ 0.90 with lower bound ≥ 0.80; recall ≥ 0.80 with lower bound ≥ 0.70). Extractor v1.1 is frozen before scoring.
   - **Next:** the annotation, which is in progress; then the locked check, then the benchmarking page with passing types only. The v2 sample is the only unseen dataset on the platform (dataset ledger), so the extractor must not be run on it before the check.
2. **Special-population evidence summary** per drug: kidney, liver, age and body size, in the structure of a clinical pharmacology review, with every value sourced. **Built 30 October 2026** ([SPECIAL_POPULATIONS.md](SPECIAL_POPULATIONS.md)) for ixazomib, pomalidomide, lenalidomide, daratumumab, dexamethasone and bortezomib, at `/landscape/drugs/<drug>/special-populations`. Bortezomib uses a new extract of the 2012 label. Gaps are shown as gaps.
3. **Dose-optimization view** (FDA Project Optimus): dose-ranging trials, published exposure–response findings and exposure comparisons between dose levels for one drug. **v1 built 30 October 2026 for lenalidomide** ([DOSE_OPTIMISATION.md](DOSE_OPTIMISATION.md)): typical daily exposure and relative grade 3/4 cytopenia odds at each model's own study doses, inside each model's scope, for one synthetic record, with the corpus trials by phase. No dose is ranked. Exposure–efficacy, label dose reductions, combination regimens and trial dose levels are shown as gaps.
4. **A guided path** for one drug through the whole chain: trials → evidence → exposure → regulatory context. **Built 31 October 2026 for lenalidomide** (`guided_path.py`, `/landscape/drugs/lenalidomide/guide`): six steps (trials, drug knowledge and label, special populations, exposure models, dose, credibility and review). Each step is read from pinned sources and says what has been checked and what is missing. It is linked from the landing page, the special-populations page and the dose view.

*Done when:* a trial designer can benchmark a draft protocol's eligibility criteria and see the exposure evidence for a dose choice in one session.

### Phase 5 — AI that cites and is checked

1. **Assisted extraction** of parameters and findings from labels and FDA, EMA and TGA reviews. Each value links to its page and shows *AI-extracted* or *human-verified*. Unverified values never feed a model. **3–4 November 2026:** owner review rounds 1 and 2 cover all 166 values that feed calculations (all match; 12 first marked wrong were percentage changes stored as fold changes, and a round-2 page showing the label's wording settled them). Status is shown on the pages that use each file. Next: round 3 for the 74 new label values; an independent reviewer.
2. **Plain-language questions** over trials and evidence, answered only from platform data, with citations. Example: "Which phase 3 myeloma trials excluded creatinine clearance below 30 mL/min?"
3. **Cited summaries** in which every sentence links to its source.

*Done when:* extraction speeds up Phase 3 and 4 curation measurably, and no unsourced statement reaches a user.

### Phase 6 — Model credibility records (ICH M15)

1. Export a model's run record and evidence status as a structured credibility record organized as ICH M15 describes: question of interest, context of use, model risk, verification, validation, assumptions and limitations. **Built 30 October 2026** ([CREDIBILITY_RECORDS.md](CREDIBILITY_RECORDS.md)): eight records (six registered models, two label curves) at `/models/credibility`, each downloadable as JSON with its checksum. Ixazomib and daratumumab added the same day (6.1b).
2. Later: let teams document their own models in the same structure.

*Done when:* each platform model has an exportable credibility record that a reviewer can read without the code.

### Phase 7 — Going online

1. Production server, hosted database, fixed secrets, backups and monitoring.
2. Accounts and private workspaces; access control before any public write access.
3. Privacy, security and intended-use review by a qualified person before charging users.
4. Pricing aimed at individual experts and small teams.

*Done when:* invited users can use the platform online with their own private workspace.

### Digital human track (started 31 October 2026)

The visual layer of the long-term vision, built only on models that have passed the earlier checks ([DIGITAL_HUMAN_1_1_FLOW_AND_TIME.md](DIGITAL_HUMAN_1_1_FLOW_AND_TIME.md)).
- **1.0 (done):** the lenalidomide elimination split from the pathway model, drawn on Human Reference Atlas anatomy (WebGL), with kidney-function bands carrying each band's check status.
- **1.1a–1.1c (done):** reference blood flow (ICRP 89), blood-to-plasma ratio (Chen 2012), per-pass kidney extraction (about 14% at normal function; about 13.4% if the blood-to-plasma ratio is converted from per gram to per mL, a correction recorded by the AI review), flow paths along the atlas's vessel centre lines, navigation, a flow key and a scale bar.
- **1.1d (done):** a time course checked under locked plans. v1 (one compartment): half-lives mostly consistent, peaks too low in every group. v2 (two compartments from Kim 2026, nothing fitted): did not meet its pre-specified rule, so v1 is shown with its warnings.
- **1.1e (next):** draw the timeline and running amounts, with each band's warnings.
- **Later:** kidney-to-nephron zoom (HRA functional tissue units), the target explorer (cereblon), and a female reference body with hormone effects (owner's goal).

### Long term — the computational human

Multi-organ physiology, disease progression, combination therapies, the body → organ → tissue → cell → target interface, and mechanistic + machine-learning hybrid models. Each builds only on models that have passed the earlier phases' checks.

## Immediate next steps

Updated 5 November 2026. Done since 31 October: Digital human 1.0–1.1d; the Bridoux check (first blind check of a published model, with a deviation); the AI review of the kidney pathway model and the 2.0e bioavailability re-check; the kidney-model test 2.0d and the myeloma note on the body map; extraction review rounds 1–2 and review status on pages; the dataset ledger; what the checks found; five label extracts (3.2d); the git bundle workflow.

**Re-assessment (4 November 2026, with the owner).** The platform has grown faster than it has been used or consolidated: 26 checks at the time (27 after 2.0e), of which 3 were blind; two drugs with a curve that passed both its checks; about 160 pinned data files and 30 docs. Until user conversations are possible, the next few weeks consolidate and review rather than add:

1. **Known-good state.** Full suite passing on the owner's Mac (1,243 tests) and the 4 November checkpoint. Done.
2. **Consolidation.** A docs index grouped by question; a plain-language status page per drug; superseded files indexed in `docs/DATA_FILES.md` (not moved: their paths are pinned). Done.
3. **Reviewer's checklist.** The questions an FDA clinical pharmacology review asks (renal and hepatic impairment guidances, review structure, ICH M15), scored against the lenalidomide workflow; the gaps become the next work. Done: 12 answered, 13 partly, 4 gaps.
4. **Fresh-reviewer pass.** One model and its check reports given to a separate reviewer agent that has not seen the work, asked only to find errors and overclaims. Labelled as an AI review, not an independent one. Done for the kidney pathway model: 16 findings, wording corrected, and the bioavailability re-check (2.0e) changed the moderate and severe bands to "depends on bioavailability".
5. **v2 eligibility annotation** (the owner's, in progress; the only unseen dataset), then its locked check.

6. **Next (batch 1):** the reviewer's checklist's quick fixes. Show FDA 2024 kidney categories beside the study and label bands; state each model's kidney-function measure on the pages; extract the rest of the REVLIMID pharmacokinetics section (for review round 3); interactions in the guided path.

Paused until then: special-population pages and label curves for the five new drugs (extraction review round 3 when the owner has time), Digital human 1.1e, and further kidney or bortezomib modelling without new data. Later: user conversations with five to ten trial designers, clinical pharmacologists or regulatory professionals; an independent human reviewer.

Blocked or waiting:
- **Lenalidomide kidney model:** every renal-impairment dataset available has been seen; a further check needs unseen data (dataset ledger).
- **Bortezomib PK:** needs individual concentration data or a mechanism that changes clearance between doses.
- **Author answers:** Hughes (Cockcroft–Gault weight basis), Kim (CL/F equation form), Iwasaki (which human data evaluated the model).
- **Repository checkpoint:** the 4 November checkpoint predates 2.0e and the merge of PR #112; a new one closes batch 1.

## Rules that do not change

- Every drug may have identity, mechanism, safety and interaction references without any simulation model. These are recorded independently.
- Each new model records: drug, formulation, route, schedule and disease context; the endpoint; equations, inputs, units, source locations and versions; population, dose and sampling coverage with extrapolation limits; verification, source review, outside-data evaluation and uncertainty; and what the output supports for a synthetic profile.
- A group mean is not an individual observation. Marginal covariate ranges do not establish joint coverage. A generic demonstration is never relabelled as a researched drug model.
- Software verification is kept distinct from empirical or independent scientific validation. Passing every check supports research use only.
