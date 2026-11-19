# Status by drug, in plain language

Written 4 November 2026. One section per drug the platform holds anything for: what it has, what was checked, what is known to be wrong and what is missing. Check results are named by their id on [What the checks found](../app/templates/findings.html) (`/models/findings`), shown here in brackets, for example *(finding: ogawa)*. A test requires every finding to appear here and every id here to exist. Capability levels are derived by `capability_levels.py`; this page only describes them. Nothing here is a clinical prediction.

## Lenalidomide (REVLIMID) — published models, checked against outside data

- **On the platform:**
  - label dosing and kidney dose table (reviewed by the owner); the rest of the label's pharmacokinetics section and its interactions section (extracted 5 November, not yet reviewed);
  - two published population models: Hughes 2019 and Kim 2026;
  - the platform's own kidney-pathway model;
  - relative odds of grade 3/4 cytopenia;
  - special populations, with the FDA 2024 kidney categories and each model's kidney-function measure beside the study's and the label's, and how exposure on each band's label dose compares with the reference (descriptive); the label's liver-function definitions beside NCI ODWG and Child–Pugh;
  - the label's pharmacokinetics and interactions, quoted on the special-populations page and summarised in the guided path;
  - the dose view, the guided path, and the body map with blood flow.
- **Checked:**
  - Hughes against CC-5013-PK-001 *(finding: hughes_cc5013)*.
  - Kim against CC-5013-PK-001 *(finding: kim_cc5013)*.
  - Both again with study-matched virtual subjects *(finding: renal_recheck)*, and against myeloma patients under a plan locked before the per-group values were seen, with a recorded deviation; the outcome was largely known from the abstract *(finding: bridoux_hughes_kim)*.
  - The pathway model against its own study's impaired groups *(finding: pathways_2_0a)*, end-stage kidney disease *(finding: pathways_esrd)*, two myeloma studies *(finding: pathways_2_0d)*, and across the bioavailability the data allow *(finding: pathways_2_0e)*.
  - The body map's time course *(finding: time_course_v1)* *(finding: time_course_v2)*.
- **Known to be wrong:**
  - Under a retrospective check with assumed parameter distributions, Hughes under-predicts moderate and severe exposure ratios in both datasets (CC-5013-PK-001 and Bridoux 2016), while Kim's are mostly indeterminate; Kim still under-predicts severe impairment in Bridoux. This establishes neither model's overall validity nor that one is better *(finding: acceptance_rule_v2)*. Kim's verdicts assume its estimates are independent; their covariance is not published and could widen or narrow the intervals. Before that rule, Kim was flagged in severe impairment in both studies and in the non-cancer study's moderate group, with Bridoux's moderate group flagged by a 0.25% margin.
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

- **On the platform:** a drug page (catalogue v2: names, mechanism, label warnings and interactions from the DailyMed SPL version 18, summaries not yet owner-reviewed); the Gupta 2017 population model (AUC shown, peaks not); its scope; special populations.
- **Checked:** against the dedicated kidney and liver impairment studies *(finding: ixazomib)*. Re-judged with the published estimates' uncertainty added (converted from %RSE, under five ways of doing so): 19 of 20 verdicts hold under all five, and severe kidney impairment AUC becomes too close to call *(finding: acceptance_rule_v2_gupta_luo)*.
- **Known to be wrong:**
  - exposure is about 1.4-fold too low in solid-tumour and liver-impairment groups;
  - peaks are 2–4-fold too low, which is why only AUC is shown.
- **Missing:** a check in myeloma patients with liver impairment.

## Daratumumab (DARZALEX) — published model, checked against outside data

- **On the platform:** the Luo 2021 population model; its scope (no page runs it); special populations.
- **Checked:** against GEN501 and SIRIUS first-dose data *(finding: daratumumab_v1)*, and again with each study's demographics *(finding: daratumumab_v2)*.
- **Known to be wrong:**
  - first-week exposure at 16 mg/kg came out too high; with the published estimates' uncertainty added it sits at the 5% margin of the widened limit, and whether it is too high depends on how that uncertainty is converted *(finding: acceptance_rule_v2_gupta_luo)*;
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

- **Checked:** extractor v1 failed its blind accuracy check *(finding: eligibility_v1)*. Extractor v1.1 also failed, on 200 new trials annotated blind and self-reviewed by the owner (prespecified pair-based precision and recall, not threshold-level measures): no type passes; ECOG comes closest (precision 0.88, recall 0.89) and kidney function, creatinine and the liver tests are furthest off *(finding: eligibility_v2)*. The language-model extractor (Track C, Claude Fable with a frozen prompt) also fails on the same trials: recall is higher for kidney function, platelets and ECOG, precision is similar, and its two runs agree on 99.75% of answers. Both extractors disagree with the reference on 13-33 trial-and-type pairs per type. Neither passes the original rule; a review of the reference will support a separately reported sensitivity analysis *(finding: eligibility_llm_c1)*.
- **The reference itself was then re-read**, blind, before each original answer was revealed: on the pairs both extractors got wrong the owner's new reading matched her own original annotation 27 times in 160, against 44 in 50 on control pairs both extractors got right, and 5 of those 50 controls still needed correcting. Re-scored against the corrected reference both extractors improve, v1.1 as far as 7 of 8 types, but the decision whether to correct was made with both answers visible, so those figures are not extractor accuracy and the original blind results stay primary. What this establishes is about the measurement, not the extractors: a single-annotator reference cannot judge an extractor at the plan v2 bar. The independent second annotator decides whether it can be judged at all *(finding: eligibility_reference_review_v1)*.
- **An independent second reader has now read 50 of the 200 trials**, blind, under guide v2. The two readers agree on 357 of 400 trial-and-type pairs, 89%, with a 95% interval of 85% to 94%. The plan's rule reads the lower bound against 0.90, so the result is that a one-reader reference is **not shown** to be reliable enough to judge an extractor at that bar; the next step is adjudicating the 43 disagreements with the second reader. The readers nearly always agree on whether a limit is stated (kappa 0.93) and differ on its detail. On these 50 trials both extractors again pass none of the eight types against either reader, so neither extractor's failure comes from the owner's annotation in particular *(finding: eligibility_second_annotation_v1)*.
- **The two readers then sat down together and settled the 43 disagreements**, under the guide they had both used. Annotator B's reading stands in 24, the owner's in 9, and 10 are unclear — and 7 of those 10 say both readings were wrong. So the reference annotation is wrong in at least 31 of the 400 pairs and the second reader's in at least 16: the reader who wrote the guide was wrong about twice as often as the reader applying it for the first time. B's reading won in every class of disagreement, including all 7 on kidney function. This measures the readers, not the extractors, and it confirms from a second direction the two defects the re-reading found: values missed, and "or equal to" dropped. The second-annotation verdict is unchanged. An adjudicated reference would be a new annotation version under its own plan *(finding: eligibility_adjudication_v1)*.
- **Round two, under annotation guide v3, cleared the bar.** The owner and annotator B each read the same fresh 50 trials alone and agree on 378 of 400 pairs, 94.5%, with a 95% interval of 91.25% to 97%. The lower bound clears 0.90, narrowly, so a two-reader reference under guide v3 is shown reliable enough to judge an extractor at that bar; the next step is an adjudicated annotation version under its own plan. Round one used different trials, so only the bar compares. The owner is not a naive reader of these trials, and errors both readers share cannot be found this way. The extractor figures on these 50 trials are descriptive and change nothing *(finding: eligibility_second_annotation_v2)*.
