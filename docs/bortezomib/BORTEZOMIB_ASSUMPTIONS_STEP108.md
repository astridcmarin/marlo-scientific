# Step 108 — sensitivity to the unresolved elimination time scale

The linked supplementary document was identified in the main article, but the attempted PMC and Europe PMC downloads did not yield readable DOCX content. We cannot claim that it resolves Equation 4 or that author code is absent from it. Main article: https://pmc.ncbi.nlm.nih.gov/articles/PMC6495529/ . Supplement link: https://pmc.ncbi.nlm.nih.gov/articles/instance/6495529/bin/NIHMS1514233-supplement-1.docx . Access attempts: 2026-10-12.

This experiment compares analyst-selected relaxation rates of 0.1, 1 and 10 per hour in k1(t)=k1ss+(k10-k1ss)*exp(-rate*t). Only this assumption changes. These are neither source estimates nor statistically supported plausible limits. The original source extraction stays unchanged; overrides are recorded separately in each alternative run. The original default Step 107 output remains identical.

Graphs, selected-time tables, sampled maximum differences, full curves and provenance export quantify the consequences of this choice. No fitting, likelihood, probability weights, confidence intervals, physiological validation or patient-readiness promotion occurs. Differences are not a reason to choose a curve that looks preferable. Small differences at a late time do not resolve the source ambiguity.

Numerical verification covers the three assumed rates against a separately coded DOP853 system; see NUMERICAL_VERIFICATION.json and optional scripts/verify_bortezomib_assumptions.py (SciPy needed only for this developer check).

Requires Step 107. No database migration or new application dependency. Next scientific dependency remains author clarification or code, or another adequately specified model, before downstream biomarkers are treated as supported predictions.
