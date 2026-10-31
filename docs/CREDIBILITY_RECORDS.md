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
- Evidence status v6 predates the Iwasaki check. That check appears under the bortezomib PK record's rejected alternatives, not as a new evidence layer.
