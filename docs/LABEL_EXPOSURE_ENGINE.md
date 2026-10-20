# Label-based exposure engine — evidence and design plan (Phase 3.1a)

Status: **3.1a–3.1c done, 20 October 2026.** Engine `intelligence_store/label_exposure.py`; pomalidomide consistency check passed with the myeloma-only parameter set (below). Roadmap Phase 3.1: give any approved small-molecule drug a sourced, typical-value exposure curve built from its label, at the capability level *Label-based exposure*.

## What it is for

Today, seven of the nine curated drugs are *Knowledge only*. Published population models exist for few drugs and each takes weeks to transcribe and check. Every approved drug, however, has a label with a clinical pharmacology section (12.3 in the US format). A label-based curve answers a narrow question honestly: *what does a typical patient's exposure look like at the labelled dose, according to the label, and what does the label say changes it?*

It is not a substitute for a population model. The interface and run record must make that difference visible every time.

## What a label gives, and what it does not

| Usually in the label | Usually not |
|---|---|
| Typical clearance (often apparent, CL/F, for oral drugs) | Between-patient variability as model parameters |
| Volume of distribution (often V/F, sometimes a range) | Distribution kinetics (a second compartment) |
| Half-life; Tmax; Cmax and AUC at one dose, often at steady state | Absorption rate constant (ka) |
| Fraction excreted unchanged in urine and faeces | Covariate equations (CrCl, weight) |
| Fold-changes in AUC for kidney and liver impairment, food and interacting drugs, each from one study | The population each number comes from, unless read carefully |

Two consequences shape the design.

**1. Label numbers often come from different studies.** A single label can combine healthy-volunteer and patient data. The pilot drug shows this (below). The engine must never mix parameters silently; each parameter set is drawn from one stated population, and a check across them is shown.

**2. A label clearance can be an artefact of the study design.** The bortezomib label's first-dose clearance (102–112 L/h) comes from studies sampled for two hours; a 72-hour study measured 17.9 L/h (3.0h). Short sampling misses the long tail and inflates clearance. The engine therefore checks each label against itself before drawing anything.

## Scientific scope

**The model.** One compartment, linear, typical value only.
- IV bolus or infusion: C(t) = Dose/V · e^(−k·t), with k = CL/V.
- Oral: first-order absorption, C(t) = F·Dose·ka / (V·(ka − k)) · (e^(−k·t) − e^(−ka·t)), with apparent parameters CL/F and V/F, so F is not needed separately.
- ka is not in labels. It is **derived** from the label's Tmax and k by solving Tmax = ln(ka/k)/(ka − k). It is recorded as derived, with the Tmax used, and a sensitivity band across the label's Tmax range is shown.
- Repeated doses by superposition (valid because the model is linear).

**Why one compartment.** A label rarely gives enough for two. A one-compartment curve is a deliberate simplification: it is right about the scale of exposure and accumulation, and wrong about the shape in the first hours for drugs with marked distribution. Bortezomib is the extreme example and is **not eligible** (see below).

**Special populations and interactions: label fold-changes only.** If the label says "AUC increased 38% in severe renal impairment on dialysis", the engine offers a *scenario* scaling CL/F by 1/1.38. It does not turn this into a covariate equation, does not interpolate between categories, and does not apply any change the label does not state.

## Eligibility: when a drug is not given a label-based curve

A drug is marked **not eligible**, with the reason shown, if any of these holds:
- The label states dose- or time-dependent PK (non-linearity, auto-induction, target-mediated disposition). Examples: bortezomib (clearance falls with repeated doses), daratumumab (target-mediated).
- The active moiety is a metabolite and the label gives no metabolite PK. Example: cyclophosphamide (a prodrug; the parent curve says little about the active species). The parent curve may be offered only with that warning, if at all.
- Clearance, or an AUC at a stated dose, is missing.
- The internal-consistency check fails beyond the tolerance (below) and no parameter set from one population passes.

Eligibility is recorded per drug, with the label text that decides it.

## Internal-consistency check (before any curve is drawn)

For each candidate parameter set, from a single population, the engine recomputes what the label also states:
1. **Clearance against exposure:** CL/F against Dose/AUCτ at steady state (or Dose/AUC∞ after one dose).
2. **Half-life against volume and clearance:** t½ against ln 2 · V/CL.
3. **Peak and accumulation:** the model's steady-state Cmax and Tmax against the label's.

Each comparison is reported as a ratio with the label sentence it came from. A tolerance (proposed: within 0.67–1.5-fold, the edge of what a label's rounding and between-study differences can explain) is fixed before any drug is checked, in a pinned plan. A set that fails is not used. If all sets fail, the drug is not eligible.

This is **software and source consistency**, not validation. Where outside data exist (a population PK paper or a review with concentration summaries), a separate locked check against them follows, exactly as for the published models.

## Pilot: pomalidomide

Chosen because it is a myeloma drug already in the catalog, oral, linear, with renal, hepatic and interaction fold-changes in the label, and an outside population PK model for a check (Li et al. 2017, *Clin Pharmacol Adv Appl* 9:133–145, 63 patients with myeloma and normal to dialysis-dependent kidney function; one compartment with first-order absorption and lag).

US label, section 12.3, as read on 20 October 2026 from a mirror of the prescribing information (the pinned extract will be taken from the DailyMed SPL with its set ID and version):
- Myeloma patients, 4 mg daily, steady state: AUC 860 ng·h/mL (CV 37%), Cmax 75 ng/mL (CV 32%).
- Tmax 2–3 h. CL/F 7–10 L/h. V/F 62–138 L at steady state. Median t½ 9.5 h in healthy subjects, 7.5 h in patients.
- Renal: moderate or severe impairment, no significant effect; dialysis-dependent, AUC +38% (dialysis days) and +40% (non-dialysis days).
- Hepatic: AUC +51%, +58%, +72% in Child-Pugh A, B, C.
- Interactions: fluvoxamine (strong CYP1A2 inhibitor) +125%; ketoconazole +19%; carbamazepine −20%; smoking AUC −32%.

**The check already finds a mismatch.** In myeloma patients, Dose/AUCτ = 4 mg / 860 ng·h/mL = **4.65 L/h**, outside the label's CL/F of 7–10 L/h. *Correction, 20 October 2026, after reading the full label (3.1b):* the label attributes 7–10 L/h and 62–138 L to patients with myeloma **or Kaposi sarcoma**, not to healthy volunteers as first written here. The likely source of the difference is pooling across the two diseases (Kaposi sarcoma: 5 mg / 462.3 ng·h/mL = 10.8 L/h). Li 2017 reports 5.13 L/h in myeloma patients. With CL/F 4.65 L/h and t½ 7.5 h, V/F is about 50 L, below the pooled 62–138 L. So the label holds a myeloma-only exposure and pooled parameter ranges; the engine prefers the myeloma-only set and shows why.

## 3.1c result — pomalidomide checked against its own label

Plan `label_exposure_consistency_plan_v1.json`, locked in commit `d9a0ac4` before the engine existed. Report `docs/verification/label_exposure_pomalidomide_consistency_v1.json`; CLI `label-exposure-consistency`. Regimen 4 mg every 24 h at steady state; ka derived from Tmax 2.5 h (sensitivity 2 and 3 h); tolerance 0.67–1.5.

| | Set A: myeloma exposure | Set B: label ranges (myeloma or Kaposi) |
|---|---|---|
| CL/F, V/F, ka | 4.65 L/h, 50.3 L, 1.07 per h | 8.37 L/h, 92.5 L, 1.08 per h |
| C1 clearance vs Dose/AUC | 1.00 (by construction) | **1.80, fail** |
| C2 half-life vs 7.5 h | 1.00 (by construction) | 1.02 |
| C3 steady-state Cmax vs 75 ng/mL | **71.6, ratio 0.95, pass** | 39.4, ratio 0.53, **fail** |
| C4 steady-state AUC vs 860 ng·h/mL | 1.00 (by construction) | 478, ratio 0.56, **fail** |
| V/F inside 62–138 L (descriptive) | no (50.3) | yes |
| Steady-state Tmax (descriptive) | 2.38 h | 2.38 h |

- **Selected: set A.** Its one informative check, the steady-state peak, agrees with the label within 5%, and it stays inside tolerance at Tmax 2 h (Cmax 74.7) and 3 h (68.6).
- **The pooled label ranges would halve myeloma exposure.** A curve drawn from "CL/F 7–10 L/h, V/F 62–138 L" predicts about 56% of the AUC and 53% of the peak the same label reports for myeloma patients at the same dose. Using the headline numbers without this check would have drawn a wrong curve.
- **Numerical checks passed:** closed-form steady state equals the sum of 60 single doses (difference about 1e-15); grid AUC equals Dose/CL (about 8e-9); grid Tmax within the 0.001 h grid of the closed form.
- **Not shown yet:** the curve is not on any page and the capability level is unchanged until the outside check (3.1d) and the drug page (3.1e).
- **Seen in passing, not tested:** Li 2017's typical values (CL/F 5.13 L/h, V/F 58.3 L, ka 0.72 per h) are close to set A. The comparison belongs to 3.1d, under its own locked plan.

## Data model

One pinned file per drug: `label_pk_<drug>_v1.json`
- `source`: SPL set ID, version and date, section, and the quoted sentence for every value.
- `parameter_sets`: each with its population (patients or healthy subjects), the values with units, and the quote each value comes from.
- `derived`: ka (from Tmax), k, accumulation, with formula and inputs.
- `scenarios`: label fold-changes, each with its quote and the population it applies to.
- `eligibility`: eligible or not, with the deciding quote.
- `consistency`: the check results for each set (written by the engine, pinned in a report).

Engine: `intelligence_store/label_exposure.py`, with the same run record and `clinical_prediction_validated: false` as the published models. Capability level *Label-based exposure* is assigned only to drugs with an eligible, consistency-passing set.

## Interface

On a drug's page, at the *Label-based exposure* level:
- A typical-value curve at the labelled regimen, with the label's own Cmax and AUC as marked points to compare against.
- Scenario toggles, one for each label fold-change, each with its quote.
- A permanent banner: *Typical value from the label. No variability. Not a population model. Not a dose recommendation.*
- The consistency table and the parameter-set choice, one click away.

## Steps

1. **3.1a — this plan.**
2. **3.1b — Pomalidomide extract and locked consistency plan** (done 20 October 2026: `label_pk_pomalidomide_v1.json`, `pomalidomide_popk_li_2017_extract_v1.json`, `label_exposure_consistency_plan_v1.json`): DailyMed SPL pinned, quotes for every value, parameter sets by population; tolerance and checks fixed before computation.
3. **3.1c — Engine and the pomalidomide consistency report** (done; see the result below). Numerical check against the exact solution and against superposition.
4. **3.1d — Outside check against Li 2017** under a locked plan (typical curve against the population model's typical curve, and against any reported summaries).
5. **3.1e — Drug page and capability level.**
6. **3.1f — Second and third drugs** (candidates: melphalan, dexamethasone), to test that the format generalises before Phase 3.2 scales the catalog.

## What this does not attempt

- Variability, prediction intervals or individual predictions.
- Covariate models from category fold-changes, or extrapolation beyond the categories studied.
- Two-compartment or PBPK models from label data.
- Interactions not stated in the label, or combinations of fold-changes (for example, renal impairment *and* an inhibitor) unless the label studied them together.
- Effect, efficacy or toxicity. Exposure only.
