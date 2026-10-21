# Label-based exposure engine — evidence and design plan (Phase 3.1a)

Status: **3.1a–3.1e done, 20 October 2026.** Pomalidomide is the first drug at *Label-based exposure*, shown at `/landscape/patient-lab/label-exposure/pomalidomide`. Engine `intelligence_store/label_exposure.py`; pomalidomide consistency check passed with the myeloma-only parameter set (below). Roadmap Phase 3.1: give any approved small-molecule drug a sourced, typical-value exposure curve built from its label, at the capability level *Label-based exposure*.

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

## 3.1d result — label curve against the Li 2017 population model

Plan `label_exposure_pomalidomide_li_check_plan_v1.json`, locked in commit `012c776` before any Li curve was computed. Report `docs/verification/label_exposure_pomalidomide_li_check_v1.json`; CLI `label-exposure-li-check`. Li 2017 reports a fitted model and simulated exposures, not observed concentrations, so this is a **model-to-model** check: weaker than agreement with data, and not fully independent (both come from the sponsor's programme).

| 4 mg daily, steady state | Label curve (3.1c set A) | Li 2017 typical (normal kidney function) | Result |
|---|---|---|---|
| AUC 0–24 h (primary) | 860 ng·h/mL | simulated mean 788 (90% interval 602–1026) | consistent |
| Peak | 71.6 ng/mL at 2.4 h | 59.4 ng/mL at 3.3 h | ratio 1.21, pass (0.8–1.25) |
| Trough (24 h) | 10.6 ng/mL | 10.9 ng/mL | ratio 0.97, pass |
| AUC ratio | | | 1.10, pass |
| Dialysis AUC fold | 1.38 (label) | 1.38 (1 / CL ratio 0.724); Table 4 1.36 (1.08–1.70) | consistent |
| Moderate or severe kidney impairment, no dialysis | no significant effect (label) | CL ratios 1.02 and 1.01, intervals include 1 | consistent |

- **Recorded as consistent with Li 2017**, together with the dialysis scenario and the label's no-effect statement.
- **The peak is the weak point.** The label curve peaks earlier and higher than Li's typical curve because its ka (1.07 per h, from the label's Tmax) is faster than Li's (0.72 per h, plus a 0.15 h lag). With ka from a 2 h Tmax the peak ratio would be 1.26, just outside the band. Daily exposure and trough are robust.
- **Volume:** the label-derived V/F (50.3 L) is just below Li's interval (51.6–66.1 L); clearance and ka are inside theirs.
- **What this allows:** 3.1e may show the curve on the pomalidomide page at *Label-based exposure*, citing both checks, with the peak's uncertainty stated.

## 3.1f result — melphalan (EVOMELA): not eligible

Label: EVOMELA (melphalan) for injection, Acrotech Biopharma, DailyMed set 69f55869-dc11-408e-8fc7-47634269a52c, revised 9/2026; extract `label_pk_melphalan_evomela_v1.json`. Plan `label_exposure_consistency_plan_melphalan_v1.json`, locked in commit `322488e` before the intravenous engine existed. Engine `intelligence_store/label_exposure_iv.py` (one compartment, constant-rate infusion); report `docs/verification/label_exposure_melphalan_consistency_v1.json`; CLI `label-exposure-melphalan-consistency`. Same tolerance as pomalidomide (0.67–1.5).

| 100 mg/m² over 30 min | Set A: myeloma exposure | Set B: label ranges |
|---|---|---|
| CL, V | 222 mL/min/m², 24.0 L/m² | 285 mL/min/m², 81.2 L/m² |
| C1 clearance vs Dose/AUC | 1.00 (by construction) | 1.29, pass |
| C2 half-life vs 75 min | 1.00 (by construction) | 197 min, **2.63, fail** |
| C3 end-of-infusion Cmax vs 5.8 µg/mL | 3.64, **0.63, fail** (24 min: 0.64; 48 min: 0.58) | 1.17, **0.20, fail** |
| C4 AUC vs 451 µg·min/mL | 1.00 (by construction) | 0.78, pass |

- **Recorded as not eligible.** No set passes; melphalan stays at *Knowledge only* and no curve is shown.
- **Why the myeloma set fails:** melphalan has a fast distribution phase. Right after a short infusion, plasma concentrations are higher than a single compartment with the terminal half-life allows, so the one-compartment curve under-predicts the peak by about 37%. The label gives one half-life and no central volume, so it cannot support a two-compartment curve.
- **The label's ranges disagree with each other:** clearance 250–325 mL/min/m² and volume 35.5–185.7 L/m² imply a half-life of about 197 minutes, against the 75 minutes stated in the same section. The volume range is probably a steady-state or terminal volume from other studies.
- **Numerical checks passed:** numerical AUC equals Dose/CL (about 6e-12); a 0.0036-second infusion matches a bolus (about 3e-7); the curve is continuous at the end of the infusion.
- **The route for melphalan** is a published population model with two compartments (a *Published model*), not a label curve.

## 3.1f result — dexamethasone (HEMADY): passes its label check; not shown until an outside check

Label: HEMADY (dexamethasone tablets) 20 mg, Edenbridge Pharmaceuticals, DailyMed set 6b9cf32c-6d60-4853-bbfd-2304ffc2c129, revised 1/2026; extract `label_pk_dexamethasone_hemady_v1.json`. Plan `label_exposure_consistency_plan_dexamethasone_v1.json`, locked in commit `8b63b8e` before any curve was computed. Engine `intelligence_store/label_exposure_single_dose.py` (the oral functions of 3.1c, one dose); report `docs/verification/label_exposure_dexamethasone_consistency_v1.json`; CLI `label-exposure-dexamethasone-consistency`.

The label reports single-dose values "in subjects" and does not say whether they had myeloma; every output carries that note. It states dose proportionality from 0.5 to 40 mg.

| Single 20 mg dose | Label-based curve (CL/F 15.7 L/h, V/F 90.6 L, ka 3.04 per h) | Label | Ratio |
|---|---|---|---|
| C1 clearance vs dose ÷ AUC | 15.7 L/h | 15.74 L/h | 1.00, pass (informative) |
| C2 half-life | 4.0 h | 4 h | by construction |
| C3 peak | 186 ng/mL | 247 (geometric mean) | **0.75**, pass |
| C4 AUC | 1274 ng·h/mL | 1271 (geometric mean) | 1.00, pass |

- **Eligible**, with the peak as the weak point. With ka from the fastest Tmax (0.5 h) the peak ratio is 0.82; from the slowest (4 h) it is 0.45. A typical curve has a lower peak than the average of individual peaks when individuals peak at different times (0.5–4 h), so some shortfall is expected.
- **Not shown yet.** Under the 3.1e rule a label curve appears only after an outside check. That check is 3.1g below.
- **Scenarios carried, not shown:** itraconazole ×3.7 (studied with a 4.5 mg dose), aprepitant ×2.2; food lowers the peak by 23% without changing AUC (text only). No kidney, liver or inducer numbers in the label.

## 3.1g result — dexamethasone against the NEOFORDEX EPAR: consistent

Source: Neofordex EPAR public assessment report (EMA/CHMP/6613/2016), a different product and applicant. Plan `label_exposure_dexamethasone_outside_check_plan_v1.json`, locked in commit `6770ed8` after reading only the study designs and before the results tables. Extract `dexamethasone_outside_pk_v1.json` (Table 11 from text; Table 14 is an image and was read from the rendered page). Module `label_exposure_dexamethasone_check.py`; report `docs/verification/label_exposure_dexamethasone_outside_check_v1.json`; CLI `label-exposure-dexamethasone-outside-check`.

| Dataset | Endpoint | Label curve | Observed (95% interval) | Ratio | Result |
|---|---|---|---|---|---|
| **MM-017: 6 Japanese myeloma patients, 40 mg (primary)** | AUC0-inf | 2548 | GM 3661 (2359–5682) | 0.70 | consistent |
| | Cmax | 371 | GM 499 (356–699) | 0.74 | consistent |
| CPA-402-11: 24 healthy volunteers, 20 mg, NEOFORDEX | AUC0-inf | 1274 | 1140 (986–1295) | 1.12 | consistent |
| | Cmax | 186 | 126 (116–136) | 1.47 | over |
| CPA-402-11, reference (Dectancyl) | AUC0-inf | 1274 | 1214 (1035–1392) | 1.05 | consistent |
| | Cmax | 186 | 214 (191–236) | 0.87 | under |

- **Recorded as consistent with outside data** (primary and both healthy-volunteer AUCs).
- **The pattern matters more than the classification.** In healthy volunteers the label curve matches total exposure within about 10%. In the 6 myeloma patients it gives 70% of the measured exposure: their apparent clearance was 10.9 L/h against the label's 15.7. With six patients the interval is wide enough to include the curve, but the direction agrees with Spoorenberg 2014 (acutely ill older patients, clearance 7.7 L/h; context only). Patients may clear dexamethasone more slowly than the label's subjects; this platform cannot settle that.
- **The peak depends on the tablet.** The two products peaked at 126 and 214 µg/L with the same AUC; the label curve (186) lies between. A peak from a label curve should not be read as product-independent.
- **Descriptive:** MM-017 day 12 (with lenalidomide, repeated dosing) GM AUCτ 2687, clearance 14.9 L/h.
- **What this allows:** a later step may show dexamethasone at *Label-based exposure*, citing both checks and stating that exposure in myeloma patients was about 1.4 times the curve.

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
4. **3.1d — Outside check against Li 2017** (done; result below) under a locked plan (typical curve against the population model's typical curve, and against any reported summaries).
5. **3.1e — Drug page and capability level** (done): `intelligence_store/label_exposure_view.py` shows a curve only when the label extract and both check reports are intact, the internal check selected a set, the outside check is consistent and the recomputed parameters equal the reported ones; otherwise the page returns 503 and the drug falls back to its previous level. The page shows the steady-state day (with the label's Cmax and Li 2017's typical curve), the first three days, one label scenario at a time (CL/F ÷ AUC fold, with its quote and study population; the single-dose food effect is text only), both checks and the peak caveat. Linked from the capability level box, the model library and the landing page.
6. **3.1f — Second and third drugs** (melphalan: not eligible; dexamethasone: passes its label check, not yet shown — both below), to test that the format generalises before Phase 3.2 scales the catalog.

## What this does not attempt

- Variability, prediction intervals or individual predictions.
- Covariate models from category fold-changes, or extrapolation beyond the categories studied.
- Two-compartment or PBPK models from label data.
- Interactions not stated in the label, or combinations of fold-changes (for example, renal impairment *and* an inhibitor) unless the label studied them together.
- Effect, efficacy or toxicity. Exposure only.
