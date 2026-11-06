# Model credibility records (Phase 6.1)

One record per model, in the structure of **ICH M15, *General Principles for Model-Informed Drug Development*** (ICH Step 4, January 2026; FDA guidance, June 2026). They are served at `/models/credibility`, `/models/<id>/credibility` and `/models/<id>/credibility.json`.

**Which models.** Records cover the six registered models (scorecards) and the two label-based exposure curves: pomalidomide and dexamethasone.

## What a record contains

| M15 element | Where it comes from |
|---|---|
| **Question of interest; context of use**, with outputs, users and excluded uses | `model_credibility_context_v2.json` (pinned; v2 adds ixazomib and daratumumab, v1 kept unchanged) |
| **Model influence, consequence of a wrong decision, model risk, model impact** | The same file. These are the platform's own ratings for its intended use: low influence, because outputs are descriptive and no decision is made from them; low consequence and low risk within that use; impact not applicable, because there is no regulatory submission. Every record states that individual dosing, clinical decision support and regulatory submission are excluded uses. |
| **Model analysis plans** | The locked plan files, each with its checksum and whether code pins it |
| **Verification and validation** | Copied from `model_evidence_status_v7.json` (the file every run record cites), or, for label curves, from their locked reports |
| **Applicability and limitations** | Copied from the pinned model extracts and plans, not rewritten |
| **Assumptions** | Context file: each assumption with its status (unresolved, assumed, settled by a locked check, by design) and basis |
| **Alternatives considered and rejected** | For bortezomib PK: Kuan 2012, an empirical falling clearance and Iwasaki 2020, each with its plan and report |

Each record carries a checksum. The record computes nothing scientific. Changing a rating or an assumption means a new context file version and a new pin.

## Limits

- The ratings describe the platform's use. They are not a regulatory assessment, and a sponsor using a model in a submission would need its own.
- The evidence status (v16 since 4 November; v6 when this was first written) does not list the Iwasaki check. That check appears under the bortezomib PK record's rejected alternatives, not as a new evidence layer.

## Context v3 (5 November 2026)

While preparing the first model analysis report, the kidney pathway model's record was found to still state that renal elimination falls faster than in proportion to creatinine clearance, a finding Simulation 2.0e showed is not established, and to list only two of its four locked plans. The bortezomib exposure and platelet records said "two outside studies" where every study tested now disagrees. `model_credibility_context_v3.json` corrects these (v2 kept unchanged): the pathway record now carries three assumptions (calibration and secretion readings; bioavailability; the unbound fraction) and the 2.0e limitations. To stop plan lists going stale, `credibility_records.plan_files` now adds every locked plan the dataset ledger records for a model, and a test requires it.

## Model analysis reports (5 November 2026)

ICH M15 asks for the results of each model analysis to be documented in a Model Analysis Report, with the plan as an appendix; Appendix 2 lists the usual sections: Executive Summary, Introduction, Objectives, Data and Methods, Results, Discussion, Conclusions, Appendices (EMA/CHMP/ICH/496426/2024, pages 12 and 16-17). `model_analysis_report.py` assembles one in that order. Data and methods come from the credibility record and the dataset ledger; results are one table per locked check, read from its report, with its line and blindness from the findings page; the appendices list the locked plans, reports and reviews with checksums. Only the narrative sections (summary, introduction, objectives, discussion, conclusions) are written by hand, by the AI assistant, in a pinned file per model (`model_analysis_report_text_lenalidomide_renal_pathways_v1.json`); a test checks they do not repeat the superseded "faster than proportional" claim.

First report: the kidney pathway model, at `/models/lenalidomide_renal_pathways_2026/report` (also JSON), linked from its credibility record. The exposure–safety odds ratios followed the same day: with no locked check, its results section shows the published estimates as implemented and what the implemented formula gives at example exposures, and says plainly that nothing is a check against data. Hughes 2019 and Kim 2026 followed on 6 November, each with three result tables (CC-5013-PK-001, the matched recheck, Bridoux 2016 with its recorded deviation). Not independent and not a regulatory submission.
