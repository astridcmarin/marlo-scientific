# Step 66 — Original-model data access assessment

Checked 2026-10-08. Decision: original Hughes model reproduction remains pending. No original analysis dataset or numeric reference output was obtained. This is a bounded research finding, not a claim that data are unavailable everywhere. No contact was made and no participant data were imported.

## Evidence located

The [Hughes article](https://pmc.ncbi.nlm.nih.gov/articles/PMC6475687/) provides a supplementary document with study designs, final and exploratory control streams, and plots. The supplied document references `nmprep_flagged.csv` and `run016_cl_crcl2_ffm_vpc.fit`; those filenames do not supply their contents. The article/publisher pages inspected did not reveal an original-analysis dataset download. Exact DOI/filename searches and a repository-domain search also did not identify one. The search log records the scope and limitations.

| Material | Current evidence | Consequence |
|---|---|---|
| Article and final control stream | Located and inspected | Supports assisted transcription work |
| Analysis-ready observations and covariates | Public download not identified; not received | Cannot reproduce empirical source fitting or subject-level predictive checks |
| Actual administration/sampling records | Not received | Nominal schedules cannot replace subject-specific histories |
| Numeric source predictions and NONMEM outputs | Not received | Cannot compare project predictions against an exact source run |
| Data dictionary, exclusions and preprocessing | Not received | Cannot reconstruct units, flags or analysis population reliably |
| Permission and permitted use | Not established for original data | No approved dataset import or redistribution |

Original-data access status is unknown beyond the sources inspected. A missing search result is not a denial of access. ClinicalTrials.gov study metadata is a cross-reference, not an analysis-ready concentration dataset.

## Study references and source ambiguity

The supplied supplement lists NCT00398515, NCT00466895, NCT00735930 and NCT01132586. Its footnote also names NCT01351896 without a corresponding displayed study row. Record this as an unresolved source-document ambiguity for the independent reviewer or data custodian. Do not invent an additional analysis group or silently change the source identifiers.

Direct registry page reads did not expose complete records, so this assessment does not establish current IPD-sharing plans for the four studies. Search snippets or a blank field in an old record are not sufficient evidence of a current permission decision.

## Separate candidate: Liang 2024

A [different primary study](https://pmc.ncbi.nlm.nih.gov/articles/PMC10830448/) points to [OSF 9m2hz](https://osf.io/9m2hz/) in its data availability statement. It describes samples collected after five consecutive doses. Project and public API lookups could not inspect the repository; files, licenses and usable covariates remain unverified.

This is a possible future external-evaluation lead, not the Hughes development dataset. Our four-event, zero-initial-amount execution cannot directly replay the reported sampling context. Do not reinterpret those samples as first-dose observations, assume missing administration histories, or substitute guessed FFM/CrCl. The genetic and adverse-event analyses in that paper do not justify adding toxicity predictions to our platform.

## Recommended next action

Prepare a specific original-materials request using the accompanying checklist. A current custodian/contact and permitted access process would need to be verified before any outreach. Nothing has been sent. A historical publication email is not assumed to be a current verified recipient.

In parallel, specify a narrowly scoped replay/validation protocol. Keep acceptance criteria, endpoints and exclusions fixed before reviewing model performance. If original files cannot be obtained, explicitly choose a different study objective rather than marking source-model reproduction as complete.

This step leaves all scientific gates unchanged: independent review pending; source reproduction and external validation unestablished; clinical prediction validated false; patient simulation ready false. No deployment or new pharmacology engine is introduced.
