# Simulation 3.0 — bortezomib platelet time course (first drug-effect module)

Status: **3.0a–3.0d done.** Evidence, PK engine, locked reading check and page (`/landscape/simulation-lab/bortezomib-platelets`).

## Why this model

The Patient Lab 2.x work stopped short of a drug effect for lenalidomide. No published, transcribable model of lenalidomide's effect on blood counts over time could be found; see the evidence scan and thesis review in `PATIENT_LAB_2_0.md`. For bortezomib one exists:

**Lignet et al. 2022** (CPT Pharmacometrics Syst Pharmacol 11:594–603, doi 10.1002/psp4.12743).
- **Structure:** an established platelet model.
- **What is printed:** all equations, the bortezomib parameters, and the PK model that drives it.
- **Data:** fitted to the mean platelet counts in Lonial et al. 2005, from the SUMMIT/CREST trials.

The earlier bortezomib steps (104–108) used the Zhang & Mager 2019 proteasome model, which stalled on its ambiguous Equation 4 and its 71% inhibition ceiling. This module is separate: it brings its own PK model, and its parameters were estimated with that PK model, so the two must be used together.

## The science

**Platelet production.** Progenitor cells in the marrow divide (Prol), mature through three transit stages (Trans1–3) and enter the blood (Circ). The mean maturation time is MTT = 4/Ktr. When circulating platelets fall below baseline, the feedback term (Circ0/Circ)^γ speeds up division. That is why counts recover between cycles.

**Drug effect.** The drug effect is linear in plasma concentration, (1 − slope·C). The paper fits two places where it might act:

| Variant | Where the drug acts | γ | MTT | Fit (Table S2, AIC) | Plausibility |
|---|---|---|---|---|---|
| Myelosuppression | Division of progenitors | 0.38 | 99 h | 2037 | Within published ranges |
| Platelet budding | Release of platelets from megakaryocytes | 0.16 | 846 h | **2013** (better) | MTT about 6× above any published value |

**A model can fit and still be wrong.** For bortezomib, the budding variant fits better and matches the mechanism suggested by laboratory work (Lonial 2005; Murai 2014). But its maturation time is biologically implausible. The paper's discussion says the myelosuppression variant "better describes the data"; that holds for ixazomib and carfilzomib, not for bortezomib. The platform will show both variants, each labelled with its fit, its plausibility and its mechanism evidence, and will call neither correct.

## Open questions (recorded in `bortezomib_platelet_model_extract_v1.json`)

1. **Units of C.** Not stated for the effect term; the PK figures use ng/mL. Using nM instead would rescale the drug effect 2.6-fold.
2. **Negative effect term.** With ng/mL, (1 − slope·C) is negative above 14.3 ng/mL (myelosuppression) or 2.0 ng/mL (budding). Bortezomib briefly exceeds both after each IV dose. A negative term would mean cells are destroyed rather than slowed. The paper does not say whether the term was capped at zero.
3. **Kcirc, Kprol and the starting values.**
   - Kprol = Ktr is given in Figure 1a.
   - Kcirc is not given. It is assumed equal to Ktr, as in the cited base models.
   - Starting values are assumed to be the pre-treatment steady state at Circ0.
4. **Administration.** Treated as an IV bolus; the label describes a 3–5 second push.
5. **PK scaling.** The published adult values check out arithmetically: pediatric ÷ 1.30 × (1.62/1.30), which gives about 14.9 L/h for a 1.62 m² adult. Two concerns are recorded:
   - The pediatric model may already have been referenced to adult size, so it may have been scaled twice.
   - Bortezomib's clearance falls after the first dose, which a linear model cannot show.

   The model is reproduced as published regardless, because the platelet parameters depend on it.

Questions 1 and 2 change the result substantially. They will be settled the same way the Kim CL/F equation was: by a plan locked before computation that reproduces the observed means under each reading.

## Observed reference values (Lonial 2005; `bortezomib_platelet_observed_v1.json`)

- Baseline mean platelet count: 165 ×10⁹/L (SD 91.3, n = 228).
- Mean count on cycle 1, day 11: 107 ×10⁹/L (SD 65.7). The ratio of means is 0.65.
- Cyclic dip and recovery to baseline during each rest week.
- An approximately 60% mean reduction from each patient's start to their own nadir. This is not comparable with a typical-value curve, and it is recorded but not used.

These are the data the model was fitted to, so reproducing them is an internal consistency check, not validation.

## Limits that stay on every output

- **Typical values only:** the model was fitted to mean data, with no between-patient variability.
- **Late rises may be an artefact:** the paper notes that higher mean counts in later cycles may reflect patients with low counts dropping out.
- **Myeloma-related low platelets are not modelled,** other than through a low starting count.
- **No external validation;** `clinical_prediction_validated` stays false.

## Plan

- **3.0a (this step):** transcription, open questions and observed values, pinned and tested; `articles/` added to `.gitignore`.
- **3.0b:** PK engine (three compartments, IV bolus, per-m² parameters × BSA), checked against an independent numerical solution and against the reported bortezomib exposure.

## 3.0b — PK engine (`intelligence_store/bortezomib_pk.py`)

**The solution.** After an IV bolus, a three-compartment model gives a plasma concentration that is a sum of three exponentials. Their rates are the roots of the model's characteristic cubic. The engine computes them exactly and adds up doses by superposition. It agrees with an independent fixed-step RK4 integration to within 10⁻⁶ relative at every tested time, including the instants before and after each dose. AUC equals dose/CL.

**Body size cancels.** Every parameter is per m² and the dose is per m², so concentration depends only on the dose in mg/m². In this model every adult on 1.3 mg/m² has the same curve. That is the assumption behind mg/m² dosing, built in rather than tested.

**At 1.3 mg/m²:**
- 135 ng/mL at injection, 82 ng/mL at 5 min, about 5.6 ng/mL at 1 h.
- Half-lives of about 6 min, 1.6 h and 98 h. The last is slow return from a very large tissue compartment.

**Against the label** (section 12.3; two copies agree; `bortezomib_label_pk_v1.json`):

| Quantity | Label | Model | Placement |
|---|---|---|---|
| Terminal half-life, repeated doses, 1.3 mg/m² | 76–108 h | 98 h | Inside |
| Distribution volume | 498–1884 L/m² | 975 L/m² | Inside |
| Clearance, repeated doses | 15–32 L/h | 14.9 L/h (1.62 m²) | Just below |
| Clearance, first dose | 102–112 L/h | 14.9 L/h | About 7× lower |
| Cmax | 112 (first dose); 89–120 ng/mL | 135 (0 min) → 82 (5 min) | Not comparable: sampling time unstated |

**Reading.** The model reproduces repeat-dose disposition, as the source states. It has a single clearance, however, so it overstates exposure after the very first dose of cycle 1 about sevenfold. Any platelet result for early cycle 1 inherits this. The 3.0c check uses cycle 1 day 11, after four doses, so it is affected less, though not zero.
- **3.0c:** locked plan, then the platelet model under each reading of questions 1 and 2, compared with the observed cycle-1 dip and the recovery.
- **3.0d:** a page showing typical platelet curves for both variants, clearly labelled, with no dosing interpretation.

## 3.0c — Locked reading check (`bortezomib_platelets.py`, `docs/verification/bortezomib_platelet_check_v1.json`)

**Procedure.** The plan (`bortezomib_platelet_check_plan_v1.json`) was committed alone before any platelet simulation ran. It ran all 8 combinations of units (ng/mL, nM), effect term (as printed, capped at zero) and variant, for one cycle of 1.3 mg/m² on days 1, 4, 8 and 11.
- **Fixed assumptions:** Kprol = Kcirc = Ktr, start at steady state, IV bolus.
- **Primary endpoint:** platelets just before the day-11 dose ÷ baseline. Observed: 107/165 = 0.65. A reading is consistent if it falls in 0.58–0.72, an interval derived in advance from the reported SDs and n = 228.
- **Numerical checks:** RK4, with fine steps in the 4 h after each dose. Halving every step changed nothing at the reported precision. With no drug, every compartment stays exactly at baseline.

**Result.**

| Variant | Units | Effect term | Day-11 ratio | Cycle 2 day 1 | Classification |
|---|---|---|---|---|---|
| Myelosuppression | ng/mL | as printed | 0.69 | 1.03 | **consistent** |
| Myelosuppression | ng/mL | capped at 0 | 0.73 | 0.99 | inconsistent |
| Myelosuppression | nM | as printed | 0.37 | 1.20 | inconsistent |
| Myelosuppression | nM | capped at 0 | 0.46 | 1.02 | inconsistent |
| Platelet budding | ng/mL | as printed | 0.68 | 1.02 | **consistent** |
| Platelet budding | ng/mL | capped at 0 | 0.77 | 0.98 | inconsistent |
| Platelet budding | nM | as printed | — | — | invalid state (platelets reach zero at about 168 h) |
| Platelet budding | nM | capped at 0 | 0.38 | 0.74 | inconsistent |

**Decision, per the plan's rule:** ng/mL with the effect term as printed is the only reading consistent for both variants, and it is adopted. Both consistent readings recover by the next cycle, as Lonial describes.

**What “as printed” means.** The fitted parameters reproduce the data only when (1 − slope·C) is allowed to go negative. In this reading the model briefly removes cells instead of slowing them:
- about 1.8 h per cycle for the myelosuppression variant;
- about 20 h per cycle for the budding variant.

The term should therefore be read as an empirical description of the drug's net effect on platelets, not a literal mechanism. Capping it would require re-estimating the parameters, which the plan forbids. Each variant's curve is still a description of mean data from the patients it was fitted to.

**Descriptive differences between the variants (both consistent at day 11):**
- **Myelosuppression:** the curve bottoms out later and shallower (lowest 0.67 of baseline at about 303 h).
- **Budding:** the curve bottoms out at the end of dosing and deeper (0.53 at about 256 h).

Lonial's mean-of-individual-nadirs (about 60%) cannot separate them, because it is a different statistic.

## 3.0d — Page (`landscape_ui/bortezomib_platelet_pages.py`)

`/landscape/simulation-lab/bortezomib-platelets` (1–4 cycles; JSON export). It is also listed as a research tool on the Simulation Lab page. The registry withholds the link if the model, observed-data or plan files fail their checksums. It is registered as a research tool, not a toxicity model; the inventory still counts 0 toxicity models.

**What the page shows:**
- typical platelet curves for both variants as a percentage of each variant's fitted baseline;
- the observed cycle-1 day-11 mean with the locked-check interval;
- a table of day-11 values by cycle, the lowest point, the start of the next cycle, and the hours with a negative effect term;
- the PK curve on a log axis, with the concentrations above which each variant's effect term turns negative.

Only the fitted regimen is run: 1.3 mg/m² on days 1, 4, 8 and 11 of 21-day cycles.

**What it makes visible:**
- **The budding variant drops sharply at each dose.** This is the negative effect term briefly moving platelets back out of the circulation, as described in 3.0c.
- **Over several cycles the variants diverge.** Myelosuppression sinks slightly each cycle (day 11: 69%, 64%, 62%). Budding rebounds above baseline (day 11: 68%, 77%, 92%; 143% at the start of cycle 4). The data they were fitted to cannot tell them apart, so the unresolved mechanism matters most beyond cycle 1.
