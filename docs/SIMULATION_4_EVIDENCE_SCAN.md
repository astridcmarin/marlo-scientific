# Simulation 4.0 — evidence scan for a patient-dependent exposure–effect model

Recorded 16 October 2026. This is a literature check only; nothing was built.

## Why a scan first

Simulation 4.0 links a patient's own exposure to a drug effect over time. For lenalidomide, which has the two best-checked PK models, no usable exposure–effect model exists (`PATIENT_LAB_2_0.md`, evidence scan of 14 October). The pooled exposure–safety analysis cannot be reconstructed, the Guglieri hazard model lacks its baseline hazard, and every quantitative mechanism input is still missing. Building lenalidomide PK/PD now would mean inventing the effect half.

**Criteria for a candidate:**
- one of the nine curated drugs;
- a published effect-over-time model with every equation and parameter reported;
- the effect for a patient changes with patient characteristics, not only with the dose;
- outside data exist, or could exist, to check it.

## Candidates

| Drug | Exposure model | Effect model | Verdict |
|---|---|---|---|
| Lenalidomide | Hughes 2019, Kim 2026 (installed) | none usable | blocked (see above) |
| Pomalidomide | Li et al., *Clin Pharmacol Adv Appl* 2017;9:133–145 (open access; renal impairment; parameter tables are images) | none in that paper; *J Clin Pharmacol* 2020;60(8):1061–1075 has an exposure–response analysis, not read | PK only for now |
| Daratumumab | Luo et al., *J Clin Pharmacol* 2021;61(5):614–627 (open access): 2 compartments, linear plus saturable target-mediated clearance that falls over time, weight on volumes; final parameters in supplement Table S1, not obtained | graphical and logistic only (response rate against trough; adverse events against body weight); no neutropenia–exposure relationship found | no effect-over-time model |
| Melphalan | Nath et al., *Br J Clin Pharmacol* 2010 (open access; high-dose therapy; found by title only, not read) | not found in this scan | PK only for now |
| Carfilzomib | Ou et al., *J Clin Pharmacol* 2017;57(5):663–677, doi:10.1002/jcph.850 (population PK; used by Lignet). Paywalled; abstract read: **body surface area was the only significant covariate on clearance**, and no exposure–adverse-event relationship was found | **Lignet 2022, Table 2**: the same platelet model as bortezomib, fitted to **individual** platelet counts (Alsina et al.) with between-patient variability in the starting count. Myelosuppression variant: γ 0.35, MTT 82 h (within the published 37–134 h), Circ0 114, slope 0.014. Lignet reports this variant "described the observed data well". | **does not meet the patient-dependence criterion** (see below) |
| Bortezomib | Lignet 2022 PK (installed; 3.0f found first-dose exposure overstated) | Lignet 2022 platelets (installed) | installed; PK needs a time-dependent-clearance model |

## What this means

- **Carfilzomib fails the patient-dependence criterion.** Its platelet parameters are good: fitted to individual counts, with biologically plausible values. But carfilzomib is dosed per m², and body surface area is the only covariate on its clearance (Ou 2017 abstract). So every patient gets essentially the same concentration curve once dose is scaled to body size. The platelet model depends only on the starting count, so a carfilzomib patient simulation would add nothing beyond Patient Lab 2.2. It remains a possible second *drug-effect* module, for comparing drugs rather than patients.
- **No curated drug meets all four criteria today.** Where patient characteristics clearly change exposure (lenalidomide and renal function), the effect model is missing. Where an effect model exists (proteasome inhibitors and platelets), exposure barely depends on the patient.

## Next step

The most promising route back to lenalidomide is the **public FDA and EMA reviews**. The pooled exposure–safety analysis (AUC against grade 3/4 thrombocytopenia and neutropenia; Chen 2017 reports an odds ratio of 3.34 for thrombocytopenia) was sponsor work submitted for approvals. Regulatory clinical pharmacology reviews often print the full logistic model: intercept, slope and AUC units. That is exactly what the published summary lacks. If found, it gives a patient-dependent link: renal function → exposure (Hughes or Kim) → probability of a grade 3/4 event. It would be a probability per treatment course, not a time course, and would be labelled as such.

Searched sources for carfilzomib, kept for reference: the FDA clinical pharmacology review for NDA 202714 (2012) and an EMA variation assessment report for Kyprolis. Neither could be downloaded from this workspace.
