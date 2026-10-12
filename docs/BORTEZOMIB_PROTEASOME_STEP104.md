# Step 104 — Drug-specific pharmacodynamics component

This adds a bortezomib concentration/activity explorer to the existing Simulation Lab, plus a database-independent CLI and JSON export. It leaves patient archives and the capability library's efficacy/toxicity classifications unchanged.

## Scientific meaning

Pharmacodynamics describes an effect associated with exposure. Here the endpoint is proteasome activity. It cannot be interpreted as the proportion of patients who respond, tumour killing, target occupancy, safety, or treatment suitability.

The source extraction records the equation, three fitted parameters, baseline, units, source locations and population context. See `intelligence_store/data/bortezomib_proteasome_reference_v1.json`. Source: Zhang and Mager (2019), DOI https://doi.org/10.1016/j.xphs.2018.11.024; Equation 5 and Table 1. An AI-assisted transcription from indexed primary-article text is available; independent source verification is pending. The article and its figures are not redistributed.

Concentrations in this explorer are hypothetical inputs, not measured values. Each point is independent. The model has no temporal memory; it is not a binding-kinetics solver. The browser's 0–100 nM window is a teaching/display choice. The observed concentration domain has not been extracted, so the explorer cannot identify which points interpolate or extrapolate the underlying study data.

At IC50 the model reaches half its maximum inhibition. Remaining activity need not equal 50%. The published maximum inhibition is below complete inhibition, so the mathematical high-concentration limit remains positive. Neither property establishes a biological bound for every patient.

## Architecture and implementation

- A pure calculation module reads a SHA256-pinned source extraction; missing or altered reference bytes block computation.
- The equation is evaluated in log space to avoid overflow/underflow of intermediate powers.
- A read-only Flask route accepts only concentration and export-format inputs. No patient or PK-run identifier is accepted.
- JSON preserves the concentration grid, parameters, source, version, limitations and deterministic report hash. A hash supports integrity, not evidence truth.
- The installer preflights prerequisites and anchors, compiles proposed Python files and backs up existing files under `instance/install_backups/`. It performs no database migration.

## Verification boundaries

Tests check equation evaluation against high-precision decimal arithmetic, limiting behavior, numerical input validation, provenance, altered-reference rejection, CLI export protection, and Flask rendering/export/navigation. They do not reproduce source observations or assess predictive performance. Parameter uncertainty and between-patient variability are not propagated.

## Next scientific work

Verify this extraction independently against the article, then extract the source observation domain and selected observed proteasome-activity data with extraction uncertainty. Only after a compatible bortezomib PK source is reproduced should a concentration-time driver be connected. Lenalidomide PK is not a valid substitute. Downstream biomarkers and clinical outcomes require their own equations, evidence and validation.

The broader disease/drug library roadmap remains active. This component is a reusable implementation pattern for adding supported endpoints drug by drug, without implying that one myeloma source covers other diseases.
