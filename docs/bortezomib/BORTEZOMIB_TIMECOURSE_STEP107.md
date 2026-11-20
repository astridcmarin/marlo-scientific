# Step 107 — bortezomib time-course reproduction candidate

This implements Equations 1–3 in drug amounts and couples central concentration to the existing Step 104 Equation 5. Source: https://pmc.ncbi.nlm.nih.gov/articles/PMC6495529/ (Table 1). It is a computational candidate, not confirmed reproduction of the authors' code or observations.

## Explicit unresolved assumption
Printed Equation 4 simplifies to dk1/dt = -(k1-k1ss). With t in hours and k1 in h^-1, dimensional consistency requires a relaxation factor. This candidate assumes 1/h and uses the exact exponential solution. The source calls the expression logistic; the printed algebra instead gives linear relaxation. We have not obtained author code to resolve the intended time scale or formulation. The clock starts at the first dose and is not reset. No alternate formulation is silently substituted.

## Regimen and units
Source regimen: 1.3 mg/m² IV on days 1, 4, 8, 11. Mean BSA 1.79 m² was borrowed by the authors, not measured in the original PK report. Dose is 2.327 mg, administered at elapsed hours 0,72,168,240; end at 288 hours. Molecular weight 384.24 g/mol from the historical FDA chemistry reference; the model article rounds it to 384.2. Amount in mg / volume in L × 10^6 / molecular weight gives nM. Initial amounts are zero before the first bolus. Peripheral compartments are not anatomical organs.

## Numerical method
Fixed-step RK4, at most 0.02 h, split at every requested sample and dose event. Retain separate pre/post-dose records. Elimination is tracked as cumulative amount so total administered = central + peripheral 2 + peripheral 3 + eliminated. No clipping is used to hide negative states. Tests compare finer steps, bolus jumps, mass balance, baseline, and source integrity. An independent SciPy DOP853 comparison is recorded in NUMERICAL_VERIFICATION.json.

## Interpretation
Activity is a direct algebraic function, not dynamic occupancy. No patient covariates, prediction intervals, dosing recommendations, empirical-validation metrics, bone biomarkers, tumour response, or toxicity outputs. The peak-inhibition discrepancy remains unresolved. Do not call this validated integrated patient PK/PD. The next scientific task is resolving Equation 4 against author code or clarification and verifying fuller numeric profiles.

Install after Step 106. No database migration. Export retains parameters, equations, assumptions, pre/post events, solver settings and hashes.
