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
| Melphalan | Nath et al., *Br J Clin Pharmacol* 2010 (open access; high-dose, renal function and body size) | not found in this scan | PK only for now |
| **Carfilzomib** | Ou et al., *J Clin Pharmacol* 2017;57(5):663–677 (population PK; used by Lignet); not obtained | **Lignet 2022, Table 2**: the same platelet model as bortezomib, fitted to **individual** platelet counts (Alsina et al.) with between-patient variability in the starting count. Myelosuppression variant: γ 0.35, MTT 82 h (within the published 37–134 h), Circ0 114, slope 0.014. Lignet reports this variant "described the observed data well". | **best candidate**, pending Ou 2017 |
| Bortezomib | Lignet 2022 PK (installed; 3.0f found first-dose exposure overstated) | Lignet 2022 platelets (installed) | installed; PK needs a time-dependent-clearance model |

## What this means

- **Carfilzomib is the strongest lead, for two reasons:**
  - its platelet parameters were fitted to individual rather than mean data and are biologically plausible, unlike bortezomib's budding variant;
  - Lignet's PK model is a published population model rather than scaled pediatric medians.
- **The limitation is the same as for bortezomib.** The platelet model is scale-invariant in the starting count. A patient's characteristics change the predicted platelet course only through the PK model's covariates. Whether carfilzomib exposure depends on anything beyond dose per m² is exactly what Ou 2017 must answer. If it has no covariates, "patient-dependent" would come down to the starting count again, which Patient Lab 2.2 already shows.
- **Lignet's own PK caveat.** For carfilzomib, the PK overlay "was not optimal". The model captured peak exposure but overestimated later time points, with only three patients' mean data to compare against.

## Next step

Obtain Ou Y, Doshi S, Nguyen A, et al. *Population pharmacokinetics and exposure–response relationship of carfilzomib in patients with multiple myeloma.* J Clin Pharmacol. 2017;57(5):663–677. If it reports a full parameter table with covariates, carfilzomib becomes Simulation 4.0, with the same discipline as before: transcription file, locked reproduction plan, then a patient page. The pomalidomide 2020 exposure–response paper and the daratumumab supplement are secondary.

Sources were read from the platform owner's local copies (Lignet 2022, Luo 2021) or from publisher pages found by search; PubMed Central and Europe PMC refused automated access.
