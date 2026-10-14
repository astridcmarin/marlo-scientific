# Simulation 3.0 — bortezomib platelet time course (first drug-effect module)

Status: **3.0a evidence recorded.** Engine and locked reproduction check are next.

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
- **3.0c:** locked plan, then the platelet model under each reading of questions 1 and 2, compared with the observed cycle-1 dip and the recovery.
- **3.0d:** a page showing typical platelet curves for both variants, clearly labelled, with no dosing interpretation.
