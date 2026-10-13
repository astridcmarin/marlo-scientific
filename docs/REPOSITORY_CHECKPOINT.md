# Repository checkpoint — 13 October 2026

This consolidation builds on main commit `5552743607d7d00a68e875cde073712dc913e7e9`. It integrates the previously delivered Step 109 without changing scientific equations or parameters.

| Stable capability | Historical checkpoint | Current scope |
|---|---|---|
| Drug and Model Library | 101, 109 | Nine curated drug entities; one educational exposure model; zero efficacy and toxicity models |
| Bortezomib target activity | 104 | Hypothetical concentration input; target activity, not clinical efficacy |
| Peak-evidence review | 105 | Summary bounds and unresolved discrepancy |
| Provisional figure review | 106 | Approximate aggregate readings; independent review pending |
| Study-regimen time course | 107 | Candidate with unresolved elimination timescale |
| Elimination-assumption comparison | 108 | Three assumed rates; not confidence limits |
| Research-tool discovery | 109 | Five source-checked tools shared by the library and Simulation Lab |
| Observation intake v1 | Separate batch also labeled 106–108 | Archive and pairing checks; empty template remains evidence-incomplete |

Step numbers identify historical deliveries, not a unique global sequence. Use capability names and module/schema versions for the separate observation-intake workflow. Its existing filenames remain compatible.

## Consolidation changes

- Restore the missing saved-scenario tests used by drug-knowledge tests.
- Restore the exact Step 75 timeline template and JavaScript, including CSV controls and provenance metadata. Keep its pinned integrity manifest unchanged.
- Integrate Step 109 with source-integrity failure coverage.
- Run unittest discovery in GitHub Actions on pull requests and main pushes using Python 3.12.
- Move the live API smoke script out of test discovery, and remove the empty Docker placeholder and unsupported containerization claim.

## Remaining gates

Bortezomib source formulation, compatible observed data, independent review and patient applicability remain unresolved. Passing software tests does not satisfy those scientific gates. Lenalidomide empirical reproduction and independent review also remain pending.

Broader disease/drug coverage, efficacy/toxicity models, accounts, billing and production operations remain future work. The locally reported 4,037-study cohort is not included in the repository and was not verified here. Deployment remains deferred.
