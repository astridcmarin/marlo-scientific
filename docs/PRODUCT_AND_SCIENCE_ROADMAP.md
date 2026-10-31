# Product and science roadmap

Direction recorded 19 October 2026; status updated 30 October 2026. Owner: Astrid Marin. The previous roadmap (10 October 2026) is kept in [history/PRODUCT_AND_SCIENCE_ROADMAP_2026-10-10.md](history/PRODUCT_AND_SCIENCE_ROADMAP_2026-10-10.md). The latest verification is in [REPOSITORY_CHECKPOINT.md](REPOSITORY_CHECKPOINT.md).

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
| **Checks planned before they run.** Comparisons with outside data follow a plan locked by commit before computation. | In place (Simulation 2.0a–2.0c, 3.0f–3.0i, 4.0; label engine 3.1b–3.1g). Negative results are recorded and shown. |
| **A regulatory reviewer's structure.** Evidence organized like a clinical pharmacology review: special populations, interactions, exposure–response, dose justification. | Partly (kidney work for lenalidomide). To generalize. |
| **The whole chain in one place.** Trial → drug → evidence → exposure → regulatory context, with the links kept. | Partly (pages exist; the guided path does not). |
| **Reproducible snapshots.** Frozen cohorts and checksum-pinned, versioned reference data. | In place. |
| **AI that cites and is checked.** Extracted values link to their source page and show whether a person confirmed them. | Not started. |
| **Built for the individual expert.** Rigorous and affordable for consultants, academics and small teams. | Product decision; pricing not set. |

Not differentiating on their own, so not the lead message: trial search, dashboards, "AI-powered" claims, and the digital human while it is still distant.

## Where we are (30 October 2026, evening)

| Area | Status |
|---|---|
| Clinical trial intelligence | **Available:** explorer at `/trials`, cohorts, normalization and regulatory indicators. The myeloma interventional cohort (3,450 trials) is pinned as an eligibility corpus. |
| Drug and regulatory knowledge | **Foundation:** nine curated drug entities with mechanisms, safety, interactions and regulatory references. |
| Exposure models | **Lenalidomide:** Hughes 2019, Kim 2026, and a kidney-pathway model (2.0a–2.0c). **Bortezomib:** the PK component disagrees with two outside studies (3.0f, 3.0h). Three candidate fixes failed under locked plans: Kuan 2012 (3.0g), an empirical falling clearance (3.0i) and Iwasaki 2020 (3.0k). **Ixazomib:** Gupta 2017, checked against the dedicated renal and hepatic studies (3.2a). **Daratumumab:** Luo 2021, checked against GEN501 and SIRIUS (3.2b–3.2c). |
| Model scope (Phase 2.5) | Each model's context of use is a set of enforced rules with evidence tiers: checked against outside data, inside the model's data only, or flagged where a check disagrees. Requests beyond the model's data are refused. Public scope pages at `/models/<id>/scope`. |
| Label-based exposure (Phase 3.1) | Pomalidomide and dexamethasone are shown, each after a locked label check and an outside check. Melphalan is not eligible. |
| Effect and safety models | Bortezomib platelet course (Lignet 2022); lenalidomide relative odds of grade 3/4 cytopenia (4.0a–4.0c). |
| Protocol benchmarking (Phase 4.1) | **v1:** all eight criterion types failed the locked accuracy check (4.1e). **v2:** locked, with 200 new trials and extractor v1.1 frozen; annotation is in progress. |
| Provenance | Every Patient Lab result has a run record. Evidence status v7 covers eight models. There are public scorecards, capability levels and ICH M15 credibility records. |
| Special populations (Phase 4.2) | Sourced summaries for six drugs (kidney, liver, age, body size, other covariates), every value checked against its pinned source before display. |
| Interface | Landing page, shared brand and navigation, About and intended-use pages, eligibility annotation and review pages. |
| Online | Not deployed. No accounts. |

Latest verification: [repository checkpoint, 30 October 2026 (second)](REPOSITORY_CHECKPOINT.md). No model is validated for clinical prediction.

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

**30 October 2026, model scope (Phase 2.5)** ([MODEL_SCOPE.md](MODEL_SCOPE.md)): what each model may be run on is now a pinned rule set, not prose. Following the owner's decision for lenalidomide, the Patient Lab computes and flags results where an outside check disagrees inside the model's data (showing the observed data), and refuses beyond the model's data. Hughes, Kim, ixazomib and daratumumab have scopes; the ixazomib exposure page is the first page built on one.

### Phase 3 — Any drug, at an honest level

1. **Label-based exposure engine**: a one- or two-compartment typical-value curve from label parameters (clearance, volume, half-life, bioavailability, fraction excreted unchanged), with the label's own kidney and liver guidance. Tagged *Label-based*; never presented like a population model. **Design plan written 20 October 2026** ([LABEL_EXPOSURE_ENGINE.md](LABEL_EXPOSURE_ENGINE.md)): one compartment, label fold-changes as scenarios only, eligibility rules, and an internal-consistency check before any curve is drawn. Pilot: pomalidomide. **20 October 2026 (3.1b–3.1c):** label and Li 2017 extracts pinned; engine built; under a locked plan the myeloma-only parameter set reproduces the label's steady-state Cmax (71.6 vs 75 ng/mL), while the label's pooled clearance and volume ranges would predict about half the myeloma exposure and fail. **3.1d:** the selected curve is consistent with the Li 2017 population model (AUC 860 vs simulated 788, 90% interval 602–1026; peak ratio 1.21, trough 0.97), and the label's dialysis fold (1.38) matches Li's (1.38); a model-to-model check, not observed data. **3.1e:** pomalidomide is the first drug at *Label-based exposure*, with a page showing the curve, one label scenario at a time, both checks and the peak caveat; the landing page links to it and now flags the bortezomib exposure model's disagreements. **3.1f, melphalan (EVOMELA):** not eligible under a locked plan; a one-compartment infusion curve under-predicts the label's peak (3.64 vs 5.8 µg/mL) because of melphalan's distribution phase, and the label's clearance and volume ranges imply a 197-minute half-life against the stated 75. Melphalan needs a published two-compartment model instead. **3.1f, dexamethasone (HEMADY):** passes its label check under a locked plan (clearance and AUC within 1%, peak 186 vs 247 ng/mL, ratio 0.75); not shown until an outside check, as the 3.1e rule requires. **3.1g:** consistent with the NEOFORDEX EPAR studies under a locked plan (myeloma patients: AUC ratio 0.70 inside a wide 6-patient interval; healthy volunteers: 1.05–1.12); patients' apparent clearance was lower than the label's, a caveat any display must carry. **3.1h:** dexamethasone shown at *Label-based exposure* with those caveats; two drugs now at that level.
2. **Drug catalog growth** from public sources (FDA labels via openFDA, RxNorm names, ChEMBL targets). Each entry sourced, versioned and marked reviewed or not reviewed.
3. **More published population models with outside checks.** **30 October 2026:** ixazomib (Gupta 2017, 3.2a) is consistent with the dedicated renal and hepatic studies in myeloma patients with normal kidney function, under-predicts solid-tumour patients about 1.4-fold and puts peaks 2–4-fold low, so the platform shows AUC only. Daratumumab (Luo 2021, 3.2b–3.2c) reproduces the GEN501 and SIRIUS peaks but over-predicts the 16 mg/kg first-week AUC, and the albumin effect runs the other way across the two studies; its scope is defined but no page runs it. Neither model passed its plan's registration rule; both are used only within their scopes.
4. **First published models beyond myeloma**, chosen where outside data exist for a check.

*Done when:* a user can open most approved small-molecule drugs and see at least a sourced, label-based exposure curve with its capability level.

### Phase 4 — Trial design support (first focus: oncology, starting with multiple myeloma)

1. **Protocol benchmarking**: compare eligibility criteria across similar trials (kidney and liver cutoffs, blood-count thresholds, prior therapy), with counts and links to each trial. **Design plan written 21 October 2026** ([PROTOCOL_BENCHMARKING.md](PROTOCOL_BENCHMARKING.md)): eight criterion types, rule-based extraction, and a hand-annotated validation sample with pass thresholds fixed before any check.
   - **v1 (4.1a–4.1e, 21–28 October):** corpus pinned (3,450 trials), 120 trials annotated by hand. In the locked check, **all eight types failed**: precision 0.73–0.83, recall 0.64–0.80. In a post-hoc analysis, the largest cause was a convention: exclusion criteria were annotated as written, not as the eligible side. The pass rule was also unreachable at that sample size.
   - **v2 (4.2a–4.2b, 28 October):** a fresh 200-trial sample. Comparators are recorded as written and the eligible side is derived. The pass rule is sized to the sample (precision ≥ 0.90 with lower bound ≥ 0.80; recall ≥ 0.80 with lower bound ≥ 0.70). Extractor v1.1 is frozen before scoring.
   - **Next:** the annotation, which is in progress; then the locked check, then the benchmarking page with passing types only.
2. **Special-population evidence summary** per drug: kidney, liver, age and body size, in the structure of a clinical pharmacology review, with every value sourced. **Built 30 October 2026** ([SPECIAL_POPULATIONS.md](SPECIAL_POPULATIONS.md)) for ixazomib, pomalidomide, lenalidomide, daratumumab, dexamethasone and bortezomib, at `/landscape/drugs/<drug>/special-populations`. Bortezomib uses a new extract of the 2012 label. Gaps are shown as gaps.
3. **Dose-optimization view** (FDA Project Optimus): dose-ranging trials, published exposure–response findings and exposure comparisons between dose levels for one drug. **v1 built 30 October 2026 for lenalidomide** ([DOSE_OPTIMISATION.md](DOSE_OPTIMISATION.md)): typical daily exposure and relative grade 3/4 cytopenia odds at each model's own study doses, inside each model's scope, for one synthetic record, with the corpus trials by phase. No dose is ranked. Exposure–efficacy, label dose reductions, combination regimens and trial dose levels are shown as gaps.
4. **A guided path** for one drug through the whole chain: trials → evidence → exposure → regulatory context. **Built 31 October 2026 for lenalidomide** (`guided_path.py`, `/landscape/drugs/lenalidomide/guide`): six steps (trials, drug knowledge and label, special populations, exposure models, dose, credibility and review). Each step is read from pinned sources and says what has been checked and what is missing. It is linked from the landing page, the special-populations page and the dose view.

*Done when:* a trial designer can benchmark a draft protocol's eligibility criteria and see the exposure evidence for a dose choice in one session.

### Phase 5 — AI that cites and is checked

1. **Assisted extraction** of parameters and findings from labels and FDA, EMA and TGA reviews. Each value links to its page and shows *AI-extracted* or *human-verified*. Unverified values never feed a model.
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

### Long term — the computational human

Multi-organ physiology, disease progression, combination therapies, the body → organ → tissue → cell → target interface, and mechanistic + machine-learning hybrid models. Each builds only on models that have passed the earlier phases' checks.

## Immediate next steps

Updated 31 October 2026. Done on 31 October: dose view (4.3) with the exposure–efficacy evidence search, the REVLIMID label extract, source reconciliation and evidence status v8, the extraction review page, the lenalidomide guided path (4.4). Done on 30 October after the morning checkpoint: benchmarking page (4.1f), credibility records (6.1, 6.1b), ixazomib and daratumumab models with outside checks (3.2a–3.2c), Iwasaki author answers (3.0l), model scope (2.5), special-population summaries (4.2), second checkpoint.

1. **Owner review of the extractions** (`/models/extraction-review`, 166 values). Needs the platform owner's time; the result changes "review pending" on every source.
2. **User conversations** with five to ten trial designers, clinical pharmacologists or regulatory professionals, using the lenalidomide guided path as the demonstration.
3. **Dose-optimisation view (4.3).** v1 built for lenalidomide. Next: trial dose levels, once a dose extractor passes a locked hand-checked sample, and an exposure–efficacy source (candidate: later FDA or EMA myeloma reviews).
4. **Sources requested:** Chen et al. 2007 (renal study publication), later REVLIMID regulatory reviews, an earlier REVLIMID label.
5. **v2 annotation and locked check (4.2c).** The 200-trial annotation is in progress, by the platform owner.
6. **Special-population gaps:** new pinned extracts for the gaps each page lists.

Blocked or waiting:
- **Drug catalog growth (3.2), including ixazomib:** DailyMed label files cannot be reached from the development environment.
- **Bortezomib PK:** needs individual concentration data or a mechanism that changes clearance between doses.
- **Author answers:** Hughes (Cockcroft–Gault weight basis), Kim (CL/F equation form), Iwasaki (which human data evaluated the model).

In parallel, outside the code: speak with five to ten trial designers, clinical pharmacologists or regulatory professionals about what they do by hand today, to confirm the Phase 4 focus.

## Rules that do not change

- Every drug may have identity, mechanism, safety and interaction references without any simulation model. These are recorded independently.
- Each new model records: drug, formulation, route, schedule and disease context; the endpoint; equations, inputs, units, source locations and versions; population, dose and sampling coverage with extrapolation limits; verification, source review, outside-data evaluation and uncertainty; and what the output supports for a synthetic profile.
- A group mean is not an individual observation. Marginal covariate ranges do not establish joint coverage. A generic demonstration is never relabelled as a researched drug model.
- Software verification is kept distinct from empirical or independent scientific validation. Passing every check supports research use only.
