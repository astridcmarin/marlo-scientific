# Simulation 3.2b — daratumumab: Luo 2021 population PK model against GEN501 and SIRIUS (Clemens 2017)

Exploratory external consistency check. Not validation, not a dosing tool, and nothing on the platform changes because of it.

## Why daratumumab

It is the platform's first antibody and its first model with **target-mediated drug disposition**: part of the drug is cleared by binding its own target, so clearance depends on dose and changes over time.
- **Luo 2021** (J Clin Pharmacol 61:614) publishes every parameter in its Table S1.
- **Clemens 2017** (Clin Pharmacokinet 56:915) reports first-dose intravenous exposure from GEN501 and SIRIUS, which were not used to estimate Luo's parameters.

## Sources (pinned)

| File | Content | Checksum (first 8) |
|---|---|---|
| `intelligence_store/data/daratumumab_pk_luo_2021_extract_v1.json` | Structure, Table S1, covariate equations as read, studies used | 8c68ddb7 |
| `intelligence_store/data/daratumumab_iv_clemens_2017_observed_v1.json` | Clemens Tables 1–3 (read from the rendered pages) and text values | 2872913f |
| `intelligence_store/data/daratumumab_pk_luo_check_plan_v1.json` | Plan, locked in commit `817f8e2` before any concentration was computed | de2682e4 |
| `docs/verification/daratumumab_pk_luo_check_v1.json` | Locked report | report_sha256 ac3369f7 |

## The model, in plain terms

- **Two compartments.** A central compartment of about 5.25 L (close to plasma volume, because antibodies stay mostly in the blood) and a peripheral one of 3.78 L.
- **Two ways out of the central compartment:**
  - **Linear clearance** (0.005 L/h). This is the slow catabolism every IgG antibody undergoes, protected by the FcRn receptor. It is about 2.3 times higher in IgG myeloma, where the patient's own monoclonal IgG competes for FcRn. It also falls with higher albumin.
  - **Saturable clearance**, Vmax·C/(Km + C). Daratumumab binds CD38 on myeloma cells and is internalised with it. At low concentrations this route is fast; above Km (2.56 µg/mL) the targets are saturated and it removes at most Vmax (1.15 mg/h). Vmax declines slowly over treatment (KDES) as CD38-positive cells are killed.
- **Why this matters for dosing.** In the typical patient's first week, the saturable route removes 73% of what is eliminated at 8 mg/kg but only 56% at 16 mg/kg. That is why exposure more than doubles when the dose doubles, and why the label starts with weekly dosing: to saturate the target quickly.

**Solver.** Fourth-order Runge-Kutta. Mass balance held to 5×10⁻¹⁶, halving the step changed results by 2×10⁻⁸, and with the saturable route switched off the AUC equalled dose/CL.

## Results (primary scenario, 1,000 virtual trials, 8 scenarios)

| Endpoint (first infusion) | Observed mean | Model, 5th–95th of group means | Observed / median | Result |
|---|---|---|---|---|
| SIRIUS 8 mg/kg Cmax (n = 18) | 138.7 µg/mL | 114.6–153.0 | 1.05 | consistent, robust |
| SIRIUS 8 mg/kg AUC to infinity (n = 15) | 21,070 µg·h/mL | 15,330–23,154 | 1.11 | consistent, robust |
| GEN501 16 mg/kg Cmax (n = 40) | 263.4 µg/mL | 241.6–291.6 | 1.00 | consistent, robust |
| GEN501 16 mg/kg AUC 0–7 days (n = 20) | 25,123 µg·h/mL | 26,011–32,201 | 0.87 | **model over-predicts, robust** |
| GEN501 8 mg/kg Cmax (n = 28; secondary) | 133.5 µg/mL | 117.0–148.3 | 1.02 | consistent, robust |

The **locked decision** is not consistent, because one of the four primary endpoints is outside the range. The result is robust: every endpoint's classification was the same in all eight scenarios. The model is not proposed for registration.

**Descriptive (no classification).**
- **SIRIUS 16 mg/kg** (group sizes not stated): observed / simulated population mean was 1.18 for the first end-of-infusion concentration, 1.26 for the trough before the ninth infusion (573 vs 456 µg/mL) and 1.27 for the ninth end-of-infusion concentration.
- **GEN501 Part 1, 16 mg/kg** (n = 3, after a pre-dose): ratio 1.53 for Cmax and 1.03 for AUC to infinity.

## What this means

1. **The model gets the volume and the 8 mg/kg exposure right.** Peaks at both doses match almost exactly, so the central volume and its covariates transfer from the newer studies to the older ones. Exposure to infinity at 8 mg/kg is also consistent.
2. **At 16 mg/kg, the first week's exposure in GEN501 is 13% lower than the model's range.** The peak matches, so the drug is cleared faster over that week than the model expects. One plausible reading: GEN501 Part 2 patients were heavily pretreated and may have carried more CD38 target, so more saturable clearance. Clemens 2017 itself attributes falling clearance to falling tumour burden. Two other explanations are open:
   - the AUC calculation: the plan uses the exact integral, while GEN501 used linear trapezoids on cohort-specific samples;
   - an undocumented pre-dose. This would push the observed value up, not down, so it does not explain the gap.
3. **Later in SIRIUS 16 mg/kg, observed troughs run above the model** (by about a quarter). This is the opposite direction, and these are descriptive values without group sizes. So the model's time course of saturable clearance may not match these older studies in either direction. That is the part of the model built from the newer studies' patients (CD38 burden and its decline). It is also the part this check can test least well from summary data.
4. **The assumptions did not decide anything.** The decline form (KDES), the sex reading, the IgG share, covariate spread and infusion length each changed results by a few percent at most.

## What the platform does with this

Nothing yet. The model is not registered. If a later, separately planned step proposes it, the record would show:
- the volume and the 8 mg/kg results as consistent;
- the first-week 16 mg/kg exposure as over-predicted by 13% in GEN501;
- the partial independence.

## Open items

- **Independent review** of both transcriptions, especially the garbled sex-on-V1 line.
- **The earlier intravenous model** (Xu 2017, ref 24 in Luo) would confirm the KDES form.
- **Clemens' electronic supplementary material** (Table 2, demographics; Fig. 1, dosing schedules) would replace the covariate assumptions and settle the pre-dose question.
