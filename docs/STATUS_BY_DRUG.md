# Status by drug, in plain language

Written 4 November 2026. One section per drug the platform holds anything for: what it has, what was checked, what is known to be wrong and what is missing. Check results are named by their id on [What the checks found](../app/templates/findings.html) (`/models/findings`), shown here in brackets, for example *(finding: ogawa)*. A test requires every finding to appear here and every id here to exist. Capability levels are derived by `capability_levels.py`; this page only describes them. Nothing here is a clinical prediction.

## Lenalidomide (REVLIMID) — published models, checked against outside data

- **On the platform:**
  - label dosing and kidney dose table (reviewed by the owner);
  - two published population models: Hughes 2019 and Kim 2026;
  - the platform's own kidney-pathway model;
  - relative odds of grade 3/4 cytopenia;
  - special populations, the dose view, the guided path, and the body map with blood flow.
- **Checked:**
  - Hughes against CC-5013-PK-001 *(finding: hughes_cc5013)*.
  - Kim against CC-5013-PK-001 *(finding: kim_cc5013)*.
  - Both again with study-matched virtual subjects *(finding: renal_recheck)*, and against myeloma patients, the first blind check of a published population model, with a recorded deviation *(finding: bridoux_hughes_kim)*.
  - The pathway model against its own study's impaired groups *(finding: pathways_2_0a)*, end-stage kidney disease *(finding: pathways_esrd)*, two myeloma studies *(finding: pathways_2_0d)*, and across the bioavailability the data allow *(finding: pathways_2_0e)*.
  - The body map's time course *(finding: time_course_v1)* *(finding: time_course_v2)*.
- **Known to be wrong:**
  - Hughes and Kim predict too little exposure in moderate and severe kidney impairment, in two studies.
  - The pathway model's moderate and severe results depend on bioavailability, which was not measured (absorption at least about 90%): no single value fits CC-5013-PK-001's moderate group and the other studies at once (2.0e). Both bands are marked accordingly; the earlier finding that renal elimination falls faster than in proportion to kidney function is not established.
  - The body map's peak concentration is too low.
- **Missing:**
  - unseen kidney-impairment data (all available sets have been seen);
  - an exposure–efficacy model;
  - author answers on the Hughes weight basis and the Kim clearance equation.

## Bortezomib (VELCADE) — published models, checked against outside data

- **On the platform:**
  - the Lignet 2022 exposure and platelet models;
  - special populations from the 2012 label;
  - research tools for the proteasome target.
- **Checked:**
  - Exposure against three outside studies *(finding: ogawa)* *(finding: can1004)* *(finding: mmy3021)* and the study its source compared it with *(finding: reece)*.
  - Three candidate replacements *(finding: kuan)* *(finding: falling_clearance)* *(finding: iwasaki)*.
  - The platelet model against its fitting data *(finding: platelets)*.
- **Known to be wrong:** the exposure model's single clearance cannot reproduce the rise in exposure from day 1 to day 11 seen in every study. All three candidate fixes failed. The platelet course inherits this.
- **Missing:** individual concentration data, or a mechanism that changes clearance between doses.

## Ixazomib (NINLARO) — published model, checked against outside data

- **On the platform:** the Gupta 2017 population model (AUC shown, peaks not); its scope; special populations.
- **Checked:** against the dedicated kidney and liver impairment studies *(finding: ixazomib)*.
- **Known to be wrong:**
  - exposure is about 1.4-fold too low in solid-tumour and liver-impairment groups;
  - peaks are 2–4-fold too low, which is why only AUC is shown.
- **Missing:** a check in myeloma patients with liver impairment.

## Daratumumab (DARZALEX) — published model, checked against outside data

- **On the platform:** the Luo 2021 population model; its scope (no page runs it); special populations.
- **Checked:** against GEN501 and SIRIUS first-dose data *(finding: daratumumab_v1)*, and again with each study's demographics *(finding: daratumumab_v2)*.
- **Known to be wrong:**
  - first-week exposure at 16 mg/kg is too high;
  - the albumin effect predicts the two studies in the opposite order.
- **Missing:** data that are fully independent of the model's structure.

## Pomalidomide (POMALYST) — label-based exposure

- **On the platform:** a curve from the label's own values, one label scenario at a time; special populations.
- **Checked:** against the label's own exposure *(finding: pomalidomide_label)* and against the Li 2017 population model *(finding: pomalidomide_li)*. The second is model to model, not observed data.
- **Known limits:** the label's pooled clearance and volume ranges would predict about half the myeloma exposure, so only the myeloma-derived set is used.
- **Missing:** a comparison with observed data outside the label.

## Dexamethasone (HEMADY) — label-based exposure

- **On the platform:** a curve from the label; special populations.
- **Checked:** against the label's own exposure *(finding: dexamethasone_label)*, and against the NEOFORDEX studies, a blind check *(finding: dexamethasone_outside)*.
- **Known limits:** myeloma patients' apparent clearance was lower than the label's. The page shows this caveat.

## Melphalan (EVOMELA) — knowledge only

- **On the platform:** curated safety and reference information.
- **Checked:** the label curve was not eligible *(finding: melphalan_label)*. A one-compartment curve cannot reproduce its distribution phase.
- **Missing:** a published two-compartment model; the oral (ALKERAN) label, which is not on DailyMed.

## Carfilzomib (KYPROLIS) — knowledge only; label extracted

- **On the platform:**
  - curated safety and reference information;
  - the label extract (21 values, 4 November; not yet reviewed by the owner).
- **Checked:** nothing yet.
- **Next:** a label-consistency plan for the IV engine. It will not be blind, because a rough hand comparison was made while reading.

## Selinexor (XPOVIO) — label extracted

- **On the platform:** the label extract (20 values, 4 November; not yet reviewed). Not yet a curated catalog entity.
- **Checked:** nothing yet.
- **Next:** a label-consistency plan. It is the strongest candidate of the five new labels (single-dose table at three doses).

## Thalidomide (THALOMID) — label extracted

- **On the platform:** the label extract (15 values, 4 November; not yet reviewed). Not yet a curated catalog entity.
- **Checked:** nothing yet.
- **Known limits:** the peak rises less than in proportion to dose. The label's exposure data come from healthy and Hansen's-disease subjects, not myeloma patients.

## Isatuximab (SARCLISA) and elotuzumab (EMPLICITI) — label extracted

- **On the platform:** label extracts (10 and 8 values, 4 November; not yet reviewed). Not yet curated catalog entities.
- **Checked:** nothing. Both are antibodies whose clearance depends on dose and time (target-mediated), so no label curve is planned. A special-population summary is the next step.

## Cyclophosphamide and fludarabine — knowledge only

- **On the platform:** curated safety and reference information. No label extract, model or check.

## Protocol benchmarking (not a drug)

- **Checked:** extractor v1 failed its blind accuracy check *(finding: eligibility_v1)*. Extractor v2 waits for the owner's annotation of 200 unseen trials.
