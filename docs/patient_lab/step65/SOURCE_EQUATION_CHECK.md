# Step 65 — Assisted source-equation checkpoint

Assessment date: 2026-10-08. Reviewer type: AI-assisted source comparison. Qualified independent reviewer: not supplied. Result: no discrepancy found within the stated comparison scope. No model or validation-gate change is made by this assessment.

## Materials actually inspected

- The supplied supplementary DOCX, with SHA256 `261734ad9632f1a0f19156b8b4b6cd88d6637cbefe89be4363791caeeda11849`, particularly Supplementary Material 2, `$MODEL`, `$THETA`, `$PK`, `$DES` and `$ERROR`.
- [Hughes et al., 2019, DOI 10.1111/bcp.13873](https://pmc.ncbi.nlm.nih.gov/articles/PMC6475687/), Table 2 and Equation 4. The main paper reports apparent CL/F, V/F and KTR; the control stream clarifies the implemented compartment ordering.
- Project parameter extract, structure contract, `_parameter_math`, generic transit derivative, and the educational execution call. Exact code hashes for the three implementation modules are recorded in the accompanying JSON. A code hash identifies bytes; it does not prove correctness.

## Parameter mapping

| Quantity | Material 2 location | Source value | Project value | Assessment |
|---|---|---:|---:|---|
| CL/F normalization (L/h) | THETA(1) | 12 | 12 | Agrees |
| V/F normalization (L) | THETA(2) | 68.8 | 68.8 | Agrees |
| KTR (1/h) | THETA(3), TVKTR | 13.5 | 13.5 | Agrees |
| CrCl exponent | THETA(5), GRPCL | 0.224 | 0.224 | Agrees |
| FFM exponent on CL/F | TVCL | 0.75 | 0.75 | Agrees |
| FFM exponent on V/F | TVV | 1 | 1 | Agrees |
| Reference FFM (kg) | WTS | 55 | 55 | Agrees |
| Reference CrCl (mL/min) | RF | 90 | 90 | Agrees |

For the project's typical-value calculation, ETA1, ETA2 and ETA3 are explicitly set to zero:

```text
CL/F = 12 × (FFM/55)^0.75 × (CrCl/90)^0.224
V/F  = 68.8 × (FFM/55)
ke   = (CL/F)/(V/F)
KTR  = 13.5 h^-1
```

Equation 4 emphasizes the renal term; Table 2 and Material 2 also contain FFM scaling. Reviewing Equation 4 alone would miss part of the project mapping. Four fixed FFM/CrCl pairs were compared with source-derived algebra: 55/90, 55/45, 50/90 and 70/60. All agree within the tool's numerical tolerance. These cases are synthetic checks, not patient observations.

## Compartment and unit mapping

| Source feature | Project representation | Assessment |
|---|---|---|
| Source order ABS, CEN, TRANS1–TRANS7 | Source indexing retained in the structure contract | Agrees |
| Serial flow ABS → TRANS1 → … → TRANS7 → CEN | Eight precentral stages, followed by central | Agrees |
| Central source index 2, inflow from index 9 | Central is stored last in the reordered solver state | Correct explicit reordering |
| Loss from CEN at CL/V2 | Loss from the modeled central amount at ke | Agrees on inspected derivative |
| CP = central amount / V2, source mg/L | Display central concentration in ng/mL, factor 1000 | Unit conversion agrees on inspected code |

Seven named TRANS compartments plus ABS produce eight transfer stages before the central compartment. Using only seven generic solver stages would change the absorption delay. The current implementation uses eight.

The automated checker recognizes the nine source DADT expressions and compares contract topology. It does **not** execute or formally prove the generic solver derivative. Derivative agreement above is this assisted code inspection; previous numerical and analytic audits remain separate evidence.

## Intentional departures from the full source analysis

Material 2 includes correlated clearance/volume random effects, transit-rate variability and proportional observation error. The educational calculation omits them and returns a deterministic typical-value curve. It does not replay the source observations, estimate parameters in NONMEM, reconstruct diagnostic plots or reproduce a population distribution.

The unit input, initial zero amounts, short horizon and bounded administration schedule are project execution choices. They are not promoted into claims about published validation or a clinical treatment regimen. Apparent CL/F and V/F are paired; the project does not apply an additional guessed bioavailability factor.

## Discrepancy register and remaining work

No numerical or topology discrepancy was identified within this assessment. One documentation issue remains intentionally historical: the original parameter extract says supplementary material had not yet been retrieved. Step 56 already identifies that earlier review-depth note. It must be interpreted alongside the later structure contract, rather than silently editing its hash-bound history.

A qualified second reviewer should independently transcribe the source before seeing this comparison, then compare values, units, indexing and omissions. The existing Step 56 worksheet supports that process. This assessment supplies no reviewer identity, independence attestation or approval.

Next empirical task: determine whether the original analysis dataset, administration records and source-model outputs can be obtained with appropriate access and use rights. Those materials were not supplied for this assessment. If unavailable, document the limitation and define a narrower prespecified verification study using legitimately available observations; do not relabel synthetic solver tests as reproduction of the published population model.

Status remains: independent transcription review pending; source-model reproduction pending; predictive validity unestablished; clinical prediction validated false; patient simulation ready false. No deployment or expansion into organ physiology, efficacy or toxicity is implied.
