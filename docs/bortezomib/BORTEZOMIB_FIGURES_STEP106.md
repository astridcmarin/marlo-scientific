# Step 106 — provisional figure review

Rechecked 2026-10-12 against original-resolution Figures 1B and 2B from https://pmc.ncbi.nlm.nih.gov/articles/PMC3951913/ . Model source: https://pmc.ncbi.nlm.nih.gov/articles/PMC6495529/ Equation 5 and Table 1, as retained in Step 104.

The original Step 106 preview is now reproducibly calculated. These are two manually read, AI-assisted group means from the 1.3 mg/m² IV arm, cycle 1 day 11. Marker positions, axis calibration, source-image SHA256 values, unit conversion and selection limitations are exported. Original figures are linked, not redistributed.

24-hour PK markers overlap; assignment remains provisional. 48-hour PD is near the image boundary. Independent extraction review is pending. ±5 pixels is only a reading sensitivity assumption; it omits calibration, marker identity, parameter and biological uncertainty. Error bars were not extracted. Pointwise denominators and individual membership are unknown. Study visits include prior dosing; these are not single-dose synthetic profiles.

Response evaluated at mean concentration is not generally the mean response of a nonlinear model. Do not interpret descriptive differences as patient residuals, fit scores or evidence of suitability. No RMSE, MAE, refitting or readiness promotion. The two late-time points do not resolve the peak-inhibition ceiling discrepancy. The study contributed to model development, so this is not independent validation.

Install after Step 105 using scripts/install_bortezomib_figures.py --project PATH. Run test_bortezomib_figure_review.py and scripts/review_bortezomib_figures.py. Open /landscape/simulation-lab/bortezomib-figure-review. No database migration.

Next scientific dependency: independent marker/series verification and broader suitable numerical data before assessing model adequacy or connecting patient PK.
