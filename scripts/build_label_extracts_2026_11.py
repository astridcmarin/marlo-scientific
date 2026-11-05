"""Builds the five label extracts of 4 November 2026 (carfilzomib, selinexor, thalidomide, isatuximab, elotuzumab).

Run once on the platform owner's PDFs (not committed): python3 scripts/build_label_extracts_2026_11.py LABEL_DIR OUT_DIR
Every quote is checked against the PDF text layer (pdftotext; spaces and hyphens ignored in matching) and its PDF page is recorded; the
build stops if any quote is not found. Table cells whose text layout is scrambled were also read from the rendered page,
which is recorded per value. The outputs are then pinned in intelligence_store/drug_label_extracts.py.
"""
import hashlib, json, re, subprocess, sys
from pathlib import Path

def norm(t):
    t = t.replace('­', '').replace('‐', '-').replace('‑', '-')
    return re.sub(r'\s+', ' ', t).strip()


def key(t):
    """Matching form: the text layer drops hyphens at line breaks (isatuximab-irfc -> isatuximabirfc), so quotes are
    matched with spaces and hyphens removed. The stored quote keeps the label's wording."""
    return re.sub(r'[\s\-]', '', norm(t))

LABELS = {
 'carfilzomib': dict(brand='KYPROLIS', file='KYPROLIS (carfilzomib) label - DailyMed [20250626_ea66eb30-e665-4693-99a1-a9d3b4bbe2d6].pdf',
   setid='ea66eb30-e665-4693-99a1-a9d3b4bbe2d6', revised='6/2025', route='intravenous', modality='small molecule (epoxyketone peptide)',
   document='KYPROLIS (carfilzomib) for injection, for intravenous use. Full prescribing information. Onyx Pharmaceuticals, Inc. (Amgen).'),
 'selinexor': dict(brand='XPOVIO', file='XPOVIO (selinexor) label - DailyMed [20260513_f6dd2682-75a6-4863-90a8-a3197f6f78a8].pdf',
   setid='f6dd2682-75a6-4863-90a8-a3197f6f78a8', revised='4/2026', route='oral', modality='small molecule',
   document='XPOVIO (selinexor) tablets, for oral use. Full prescribing information. Karyopharm Therapeutics Inc.'),
 'thalidomide': dict(brand='THALOMID', file='THALOMID (thalidomide) label - DailyMed [20261025_2eda833b-1357-4ed4-a093-194524fcb061].pdf',
   setid='2eda833b-1357-4ed4-a093-194524fcb061', revised='9/2026', route='oral', modality='small molecule',
   document='THALOMID (thalidomide) capsules, for oral use. Full prescribing information. Celgene Corporation; marketed by Bristol-Myers Squibb Company.'),
 'isatuximab': dict(brand='SARCLISA', file='SARCLISA (isatuximab) label - DailyMed [20260709_a0473462-6f9d-4eca-a5bf-8620aea68e8a].pdf',
   setid='a0473462-6f9d-4eca-a5bf-8620aea68e8a', revised='6/2026', route='intravenous', modality='monoclonal antibody (anti-CD38)',
   document='SARCLISA (isatuximab-irfc) injection, for intravenous use. Full prescribing information. sanofi-aventis U.S. LLC.'),
 'elotuzumab': dict(brand='EMPLICITI', file='EMPLICITI (elotuzumab) label - DailyMed [20240628_80686b7e-f6f4-4154-b5c0-c846425e2d91].pdf',
   setid='80686b7e-f6f4-4154-b5c0-c846425e2d91', revised='3/2022', route='intravenous', modality='monoclonal antibody (anti-SLAMF7)',
   document='EMPLICITI (elotuzumab) for injection, for intravenous use. Full prescribing information. Bristol-Myers Squibb Company.'),
}

# (section, key, fields, quote, section_ref, check)  check: 'text' or 'text_and_rendered_page'
E = {}
E['carfilzomib'] = [
 ('dosing', 'weekly_20_70_mg_m2', {'regimen': '20 mg/m2 Cycle 1 Day 1, then 70 mg/m2; 30-minute infusion, Days 1, 8, 15 of 28-day cycles', 'dose_mg_m2': [20, 70]},
  'The recommended starting dosage of Kyprolis is 20 mg/m2 on Cycle 1, Day 1. If tolerated, escalate the dose to 70 mg/m2 on Cycle 1, Day 8. Administer Kyprolis intravenously as a 30-minute infusion on Days 1, 8, and 15 of each 28-day cycle', '2.2', 'text'),
 ('dosing', 'twice_weekly_20_56_mg_m2', {'regimen': '20 mg/m2 Cycle 1 Days 1-2, then 56 mg/m2; 30-minute infusion, Days 1, 2, 8, 9, 15, 16 of 28-day cycles', 'dose_mg_m2': [20, 56]},
  'The recommended starting dosage of Kyprolis is 20 mg/m2 on Cycle 1, Days 1 and 2. If tolerated, escalate the dose to 56 mg/m2 on Cycle 1, Day 8. Administer Kyprolis intravenously as a 30-minute infusion on Days 1, 2, 8, 9, 15, and 16 of each 28-day cycle', '2.2', 'text'),
 ('dosing', 'hepatic_mild_moderate', {'modification': 'reduce dose by 25%'},
  'For patients with mild (total bilirubin 1 to 1.5 × ULN and any AST or total bilirubin ≤ ULN and AST > ULN) or moderate (total bilirubin > 1.5 to 3 × ULN and any AST) hepatic impairment, reduce the dose of Kyprolis by 25%', '2.4', 'text'),
 ('dosing', 'esrd_hemodialysis', {'modification': 'administer after hemodialysis'},
  'For patients with end stage renal disease who are on hemodialysis, administer Kyprolis after the hemodialysis procedure.', '2.5', 'text'),
 ('pk', 'auc_c1_avg_ng_h_ml', {'by_regimen': {'20/27 twice weekly, 2-10 min': [95, 40], '20/56 twice weekly, 30 min': [170, 35], '20/70 once weekly, 30 min': [114, 36]}, 'format': 'mean (CV%)', 'statistic': 'estimated mean average daily AUC, first cycle'},
  'Table 21: Carfilzomib Exposure Parameters for Different Dosing Regimens', '12.3', 'text_and_rendered_page'),
 ('pk', 'auc_ss_ng_h_ml', {'by_regimen': {'20/27 twice weekly, 2-10 min': [111, 34], '20/56 twice weekly, 30 min': [228, 28], '20/70 once weekly, 30 min': [150, 35]}, 'format': 'mean (CV%)', 'statistic': 'average daily AUC at steady state'},
  'Table 21: Carfilzomib Exposure Parameters for Different Dosing Regimens', '12.3', 'text_and_rendered_page'),
 ('pk', 'cmax_c1_ng_ml', {'by_regimen': {'20/27 twice weekly, 2-10 min': [1282, 17], '20/56 twice weekly, 30 min': [1166, 29], '20/70 once weekly, 30 min': [1595, 36]}, 'format': 'mean (CV%)', 'statistic': 'Cmax at the highest dose in the first cycle'},
  'Table 21: Carfilzomib Exposure Parameters for Different Dosing Regimens', '12.3', 'text_and_rendered_page'),
 ('pk', 'table_21_definition', {'note': 'AUCC1,avg and AUCss are average daily AUCs, not AUC per dose.'},
  'Table 21 lists the estimated mean average daily area under the curve in the first cycle (AUCC1,avg), average daily area under the curve at steady-state (AUCss) and Cmax at the highest dose in the first cycle (Cmax,C1) for the different dosing regimens.', '12.3', 'text'),
 ('pk', 'infusion_duration_effect', {'cmax_30min_vs_2_10min': '2- to 3-fold lower', 'auc': 'similar'},
  'A 30-minute infusion resulted in a similar AUC0-INF, but 2- to 3-fold lower Cmax than that observed with a 2- to 10-minute infusion at the same dose.', '12.3', 'text'),
 ('pk', 'accumulation', {'stated': 'none'},
  'There was no evidence of carfilzomib accumulation following repeated administration of carfilzomib 70 mg/m2 as a 30-minute once weekly infusion or 15 and 20 mg/m2 as a 2- to 10-minute twice weekly infusion.', '12.3', 'text'),
 ('pk', 'vss_l', {'value': 28, 'note': 'mean, 20 mg/m2 dose'},
  'The mean steady-state volume of distribution of a 20 mg/m2 dose of carfilzomib was 28 L.', '12.3', 'text'),
 ('pk', 'protein_binding_percent', {'value': 97},
  'Carfilzomib is 97% bound to human plasma proteins over the concentration range of 0.4 to 4 micromolar in vitro.', '12.3', 'text'),
 ('pk', 'half_life_h', {'upper_bound': 1, 'note': 'Day 1 of Cycle 1, doses of 15 mg/m2 or more'},
  'Carfilzomib has a half-life of ≤ 1 hour on Day 1 of Cycle 1 following intravenous doses ≥ 15 mg/m2.', '12.3', 'text'),
 ('pk', 'cl_l_h', {'range': [151, 263]},
  'The systemic clearance ranged from 151 to 263 L/hour.', '12.3', 'text'),
 ('pk', 'excretion', {'urine_metabolites_24h_percent': 25, 'parent_urine_and_feces_percent': 0.3},
  'Approximately 25% of the administered dose of carfilzomib was excreted in urine as metabolites in 24 hours. Urinary and fecal excretion of the parent compound was negligible (0.3% of total dose).', '12.3', 'text'),
 ('special_populations', 'covariates_no_effect', {'factors': ['age 35-89 years', 'sex', 'race or ethnicity', 'mild to severe renal impairment (CLcr 15-89 mL/min)']},
  'Age (35-89 years), sex, race or ethnicity (80% White, 11% Black, 6% Asians, 3% Hispanics), and mild to severe renal impairment (creatinine clearance 15-89 mL/min) did not have clinically meaningful effects on the pharmacokinetics of carfilzomib.', '12.3', 'text'),
 ('special_populations', 'hepatic_mild_moderate_auc_fold', {'value': 1.5, 'stated_as': 'approximately 50% higher AUC'},
  'Compared to patients with normal hepatic function, patients with mild (total bilirubin 1 to 1.5 × ULN and any AST or total bilirubin ≤ ULN and AST > ULN) and moderate (total bilirubin > 1.5 to 3 × ULN and any AST) hepatic impairment had approximately 50% higher carfilzomib AUC.', '12.3', 'text'),
 ('special_populations', 'hepatic_severe', {'value': None, 'stated_as': 'not evaluated'},
  'The pharmacokinetics of carfilzomib has not been evaluated in patients with severe hepatic impairment (total bilirubin > 3 × ULN and any AST).', '12.3', 'text'),
 ('special_populations', 'esrd_hemodialysis_auc_fold', {'value': 1.33, 'stated_as': '33% higher AUC'},
  'Relative to patients with normal renal function, ESRD patients on hemodialysis showed 33% higher carfilzomib AUC.', '12.3', 'text'),
 ('interactions', 'midazolam', {'effect_on': 'midazolam (CYP3A substrate)', 'result': 'not affected'},
  'Midazolam (a sensitive CYP3A substrate) pharmacokinetics was not affected by concomitant administration of carfilzomib.', '12.3', 'text'),
 ('interactions', 'pgp_inhibitors_inducers', {'result': 'unlikely to be affected (in vitro P-gp substrate; IV and extensively metabolized)'},
  'However, given that Kyprolis is administered intravenously and is extensively metabolized, the pharmacokinetics of Kyprolis is unlikely to be affected by P-gp inhibitors or inducers.', '12.3', 'text'),
]
E['selinexor'] = [
 ('dosing', 'xvd_100_mg_weekly', {'dose_mg': 100, 'interval': 'once weekly, Day 1', 'combination': 'bortezomib and dexamethasone'},
  'The recommended dosage of XPOVIO is 100 mg taken orally once weekly on Day 1 of each week until disease progression or unacceptable toxicity in combination with:', '2.1', 'text'),
 ('dosing', 'xd_80_mg_twice_weekly', {'dose_mg': 80, 'interval': 'Days 1 and 3 of each week', 'combination': 'dexamethasone'},
  'The recommended dosage of XPOVIO is 80 mg taken orally on Days 1 and 3 of each week until disease progression or unacceptable toxicity in combination with dexamethasone', '2.1', 'text'),
 ('dosing', 'hepatic_severe_starting_dose', {'xvd': '80 mg once weekly', 'xd': '100 mg once weekly', 'definition': 'total bilirubin >3x ULN, any AST'},
  'Table 4: XPOVIO Starting Dosage in Patients with Severe Hepatic Impairment', '2.5', 'text_and_rendered_page'),
 ('pk', 'linearity', {'dose_proportional_range_mg_m2': [3, 85], 'accumulation': 'no clinically relevant accumulation'},
  'Selinexor Cmax and AUC increased proportionally over a dose range from 3 mg/m2 to 85 mg/m2 (0.05 to 1.44) times the maximum approved recommended dose, based on 1.7 m2 body surface area. No clinically relevant accumulation at steady state was observed.', '12.3', 'text'),
 ('pk', 'single_dose_cmax_ng_ml', {'by_dose_mg': {'60': [442, 188], '80': [680, 124], '100': [693, 201]}, 'format': 'mean (SD)', 'population': 'patients with hematologic malignancies'},
  'Table 9: Selinexor Cmax and AUC After Administration of a Single Dose of XPOVIO', '12.3', 'text_and_rendered_page'),
 ('pk', 'single_dose_auc_inf_ng_h_ml', {'by_dose_mg': {'60': [4096, 1185], '80': [5386, 1116], '100': [6998, 818]}, 'format': 'mean (SD)', 'population': 'patients with hematologic malignancies'},
  'Table 9: Selinexor Cmax and AUC After Administration of a Single Dose of XPOVIO', '12.3', 'text_and_rendered_page'),
 ('pk', 'tmax_h', {'upper_bound': 4},
  'The Cmax is reached within 4 hours following oral administration of XPOVIO.', '12.3', 'text'),
 ('pk', 'food', {'result': 'no clinically significant effect (high-fat meal)'},
  'Concomitant administration of a high-fat meal (800 to 1,000 calories with approximately 50% of total caloric content of the meal from fat) did not affect the pharmacokinetics of selinexor to a clinically significant extent.', '12.3', 'text'),
 ('pk', 'v_f_l', {'value': 133, 'population': 'patients with cancer'},
  'The apparent volume of distribution of selinexor is 133 L in patients with cancer.', '12.3', 'text'),
 ('pk', 'protein_binding_percent', {'value': 95},
  'The protein binding of selinexor is 95%.', '12.3', 'text'),
 ('pk', 'half_life_h', {'range': [6, 8], 'note': 'single dose, mean'},
  'Following a single dose of XPOVIO, the mean half-life is 6 to 8 hours.', '12.3', 'text'),
 ('pk', 'cl_f_l_h', {'value': 18.6, 'population': 'patients with cancer'},
  'The apparent total clearance of selinexor is 18.6 L/h in patients with cancer.', '12.3', 'text'),
 ('pk', 'metabolism', {'pathways': ['CYP3A4', 'UGTs', 'GSTs']},
  'Selinexor is metabolized by CYP3A4, multiple UDP-glucuronosyltransferases (UGTs) and glutathione S-transferases (GSTs).', '12.3', 'text'),
 ('special_populations', 'covariates_no_effect', {'factors': ['age 18-94 years', 'sex', 'body weight 36-168 kg', 'ethnicity', 'mild to severe renal impairment (CLcr 15-89 mL/min, Cockcroft-Gault)', 'disease type']},
  'No clinically significant differences in the pharmacokinetics of selinexor were observed based on age (18 to 94 years old), sex, body weight (36 to 168 kg), ethnicity, mild to severe renal impairment (CLCR: 15 to 89 mL/min, estimated by the Cockcroft-Gault equation), and disease type (hematological, solid tumor).', '12.3', 'text'),
 ('special_populations', 'esrd_hemodialysis', {'value': None, 'stated_as': 'unknown'},
  'The effect of end-stage renal disease (CLCR <15 mL/min) or hemodialysis on selinexor pharmacokinetics is unknown.', '12.3', 'text'),
 ('special_populations', 'hepatic_mild_moderate', {'value': 1.0, 'stated_as': 'comparable to normal hepatic function'},
  'hepatic impairment the pharmacokinetics of selinexor was comparable to patients with normal hepatic function (total bilirubin and AST <ULN).', '12.3', 'text'),
 ('special_populations', 'hepatic_severe_exposure_fold', {'value': 1.32, 'stated_as': 'approximately 32% increase in total and free exposure', 'n': 6},
  'In patients with severe hepatic impairment (total bilirubin >3 ULN and any AST, n=6) there was approximately 32% increase in total and free selinexor exposure compared to patients with normal hepatic function', '12.3', 'text'),
 ('interactions', 'clarithromycin_strong_cyp3a4_inhibitor', {'result': 'no clinically significant difference'},
  'Clarithromycin (a strong CYP3A4 inhibitor): No clinically significant differences in selinexor pharmacokinetics were observed when co-administered with clarithromycin (up to 1,000 mg daily dose of clarithromycin).', '12.3', 'text'),
 ('interactions', 'carbamazepine_strong_cyp3a4_inducer', {'result': 'no clinically significant difference'},
  'Carbamazepine (a strong CYP3A4 inducer): No clinically significant differences in selinexor pharmacokinetics were observed when co-administered with carbamazepine (up to 300 mg twice-daily dose of carbamazepine).', '12.3', 'text'),
 ('interactions', 'acetaminophen', {'result': 'no clinically significant difference'},
  'Acetaminophen: No clinically significant differences in selinexor pharmacokinetics were observed when co-administered with acetaminophen (up to 1,000 mg daily dose of acetaminophen).', '12.3', 'text'),
]
E['thalidomide'] = [
 ('dosing', 'mm_200_mg_daily', {'dose_mg': 200, 'interval_h': 24, 'combination': 'dexamethasone'},
  'The recommended dose of THALOMID in combination with dexamethasone is 200 mg once daily (in 28-day treatment cycles) orally with water, preferably at bedtime and at least 1 hour after the evening meal.', '2.2', 'text'),
 ('pk', 'single_dose_table_healthy', {'by_dose_mg': {'50': {'auc_inf_ug_h_ml': [4.9, 16], 'cmax_ug_ml': [0.62, 52], 'tmax_h': [2.9, 66], 't_half_h': [5.52, 37]},
                                                     '200': {'auc_inf_ug_h_ml': [18.9, 17], 'cmax_ug_ml': [1.76, 30], 'tmax_h': [3.5, 57], 't_half_h': [5.53, 25]},
                                                     '400': {'auc_inf_ug_h_ml': [36.4, 26], 'cmax_ug_ml': [2.82, 28], 'tmax_h': [4.3, 37], 't_half_h': [7.29, 36]}},
                                      'format': 'mean (%CV)', 'population': 'healthy subjects, n=14'},
  'Table 5: Pharmacokinetic Parameter Values for THALOMID Mean (%CV)', '12.3', 'text'),
 ('pk', 'single_dose_table_hansen', {'by_dose_mg': {'400': {'auc_inf_ug_h_ml': [46.4, 44.1], 'cmax_ug_ml': [3.44, 52.6], 'tmax_h': [5.7, 27], 't_half_h': [6.86, 17]}},
                                     'format': 'mean (%CV)', 'population': "patients with Hansen's disease, n=6; recorded, not for myeloma use"},
  'Table 5: Pharmacokinetic Parameter Values for THALOMID Mean (%CV)', '12.3', 'text'),
 ('pk', 'linearity', {'auc': 'proportional to dose (healthy subjects)', 'cmax': 'less than proportional'},
  'While the extent of absorption (as measured by area under the curve [AUC]) is proportional to dose in healthy subjects, the observed peak concentration (Cmax) increased in a less than proportional manner (see Table 5 below).', '12.3', 'text'),
 ('pk', 'tmax_h', {'range': [2, 5]},
  'The maximum plasma concentrations are reached approximately 2-5 hours after administration.', '12.3', 'text'),
 ('pk', 'bioavailability', {'value': None, 'stated_as': 'not characterized'},
  'The absolute bioavailability of thalidomide from thalidomide capsules has not yet been characterized in human subjects due to its poor aqueous solubility.', '12.3', 'text'),
 ('pk', 'food', {'auc_cmax_change': 'minor (<10%)', 'tmax_h': 6},
  'Coadministration of THALOMID (thalidomide) with a high-fat meal causes minor (<10%) changes in the observed AUC and Cmax values; however, it causes an increase in Tmax to approximately 6 hours.', '12.3', 'text'),
 ('pk', 'protein_binding_percent', {'r_enantiomer': 55, 's_enantiomer': 66, 'statistic': 'geometric mean'},
  'In human plasma, the geometric mean plasma protein binding was 55% and 66%, respectively, for (+)-(R)- and (-)-(S)-thalidomide.', '12.3', 'text'),
 ('pk', 'half_life_h', {'range': [5.5, 7.3], 'note': 'single doses 50-400 mg'},
  'The mean elimination half-life of thalidomide in plasma following single oral doses between 50 mg and 400 mg was 5.5 to 7.3 hours.', '12.3', 'text'),
 ('pk', 'fraction_excreted_unchanged_urine', {'upper_bound': 0.035},
  'Unchanged thalidomide is not eliminated by the kidney to a notable degree (<3.5% of the dose).', '12.3', 'text'),
 ('pk', 'cl_l_h_mm_by_weight', {'range': [6, 12], 'weight_kg_range': [47, 133], 'slope_l_h_per_10_kg': 0.605, 'population': 'MM patients'},
  'In MM patients with body weight from 47-133 kg, thalidomide clearance ranged from approximately 6-12 L/h, representing an increase in thalidomide clearance of 0.605 L/h per 10 kg body weight increase.', '12.3', 'text'),
 ('special_populations', 'renal', {'value': None, 'stated_as': 'not expected to influence exposure (not studied)'},
  'Patients with Renal Impairment: Renal impairment is not expected to influence drug exposure since <3.5% of the dose is excreted in the urine as unchanged drug.', '12.3', 'text'),
 ('special_populations', 'hepatic', {'value': None, 'stated_as': 'not studied'},
  'Patients with Hepatic Impairment: No clinical studies have been conducted in patients with hepatic impairment.', '12.3', 'text'),
 ('special_populations', 'age_sex', {'stated_as': 'no age-related changes (20-69 years); no significant sex differences'},
  'Analysis of the data from pharmacokinetic studies in healthy volunteers and patients with Hansen\'s disease ranging in age from 20 to 69 years does not reveal any age-related changes.', '12.3', 'text'),
 ('interactions', 'cyp450', {'result': 'not a CYP450 substrate, inhibitor or inducer; interactions not anticipated'},
  'Pharmacokinetic drug-drug interactions with substrates, inhibitors or inducers of CYP450 are not anticipated.', '12.3', 'text'),
]
E['isatuximab'] = [
 ('dosing', 'dose_10_mg_kg', {'dose_mg_kg': 10, 'basis': 'actual body weight'},
  'The recommended dose of SARCLISA is 10 mg/kg actual body weight administered as an intravenous infusion', '2.1', 'text'),
 ('pk', 'steady_state_ipd', {'cmax_ug_ml': [351, 36.0], 'auc_ug_h_ml': [72600, 51.7], 'format': 'mean (CV%), predicted', 'combination': 'pomalidomide and dexamethasone'},
  'the steady-state mean (CV%) predicted maximum plasma concentration (Cmax) and area under the plasma concentration-time curve (AUC) of isatuximab-irfc were 351 µg/mL (36.0%) and 72,600 µg∙h/mL (51.7%), respectively.', '12.3', 'text'),
 ('pk', 'steady_state_ikd', {'cmax_ug_ml': [655, 30.8], 'auc_ug_h_ml': [159000, 37.1], 'format': 'mean (CV%), predicted', 'combination': 'carfilzomib and dexamethasone'},
  'the steady state mean (CV%) predicted Cmax and AUC of isatuximab-irfc were 655 µg/mL (30.8%) and 159,000 µg∙h/mL (37.1%), respectively.', '12.3', 'text'),
 ('pk', 'time_to_steady_state', {'weeks_median': 18, 'accumulation_fold': 3.1},
  'The median time to reach steady state of isatuximab-irfc was 18 weeks with a 3.1-fold accumulation.', '12.3', 'text'),
 ('pk', 'nonlinearity', {'stated_as': 'greater than dose proportional AUC, 1-20 mg/kg every 2 weeks; clearance decreases with dose and with multiple doses'},
  'Isatuximab-irfc AUC increases in a greater than dose proportional manner over a dosage range from 1 mg/kg to 20 mg/kg (0.1 to 2 times the approved recommended dosage) every 2 weeks.', '12.3', 'text'),
 ('pk', 'clearance_time_dependence', {'stated_as': 'total clearance decreased with increasing dose and with multiple doses'},
  'Isatuximab-irfc total clearance decreased with increasing dose and with multiple doses.', '12.3', 'text'),
 ('pk', 'v_total_l', {'value': 8.13, 'cv_percent': 26.2, 'statistic': 'mean (CV%), predicted'},
  'The mean (CV%) predicted total volume of distribution of isatuximab-irfc is of 8.13 L (26.2%).', '12.3', 'text'),
 ('special_populations', 'covariates_no_effect', {'factors': ['age 36-85 years', 'sex', 'renal impairment including ESRD or dialysis (eGFR <90 mL/min/1.73 m2)', 'mild hepatic impairment']},
  'The following factors have no clinically meaningful effect on the exposure of isatuximab-irfc: age (36 to 85 years, 70 patients were ≥75 years old), sex, renal impairment including patients with End-Stage Renal Disease (ESRD) or on dialysis (eGFR <90 mL/min/1.73 m2), and mild hepatic impairment', '12.3', 'text'),
 ('special_populations', 'hepatic_moderate_severe', {'value': None, 'stated_as': 'unknown'},
  'The effect of moderate (total bilirubin >1.5 to 3 × ULN and any AST) and severe (total bilirubin >3 × ULN and any AST) hepatic impairment on isatuximab-irfc pharmacokinetics is unknown.', '12.3', 'text'),
 ('special_populations', 'body_weight', {'stated_as': 'clearance increases with body weight'},
  'The clearance of isatuximab-irfc increased with increasing body weight.', '12.3', 'text'),
]
E['elotuzumab'] = [
 ('dosing', 'erd_10_mg_kg', {'dose_mg_kg': 10, 'schedule': 'weekly for cycles 1-2, then every 2 weeks', 'combination': 'lenalidomide and dexamethasone'},
  'The recommended dosage of EMPLICITI is 10 mg/kg administered intravenously every week for the first two cycles (28-day cycle) and every 2 weeks thereafter in conjunction with the recommended dosing of lenalidomide and low-dose dexamethasone', '2.1', 'text'),
 ('pk', 'nonlinearity', {'stated_as': 'nonlinear; greater than proportional AUC; target-mediated clearance'},
  'Elotuzumab exhibits nonlinear pharmacokinetics (PK) resulting in greater than proportional increases in area under the concentration-time curve (AUC) indicative of target-mediated clearance.', '12.3', 'text'),
 ('pk', 'trough_ss_erd_ug_ml', {'value': 194, 'cv_percent': 52, 'statistic': 'geometric mean (CV%), predicted'},
  'The administration of the recommended 10 mg/kg EMPLICITI regimen with lenalidomide and dexamethasone is predicted to result in geometric mean (CV%) steady-state trough concentrations of 194 μg/mL (52%).', '12.3', 'text'),
 ('pk', 'trough_ss_epd_ug_ml', {'value': 124, 'cv_percent': 59, 'statistic': 'geometric mean (CV%), predicted'},
  'The administration of the recommended EMPLICITI regimen with pomalidomide and dexamethasone is predicted to result in geometric mean (CV%) steady-state trough concentrations of 124 μg/mL (59%).', '12.3', 'text'),
 ('pk', 'clearance_by_dose_ml_day_kg', {'at_0_5_mg_kg': [17.5, 21.2], 'at_20_mg_kg': [5.8, 31], 'statistic': 'geometric mean (CV%)'},
  'The clearance of elotuzumab in combination with lenalidomide and dexamethasone decreased from a geometric mean (CV%) of 17.5 (21.2%) to 5.8 (31%) mL/day/kg with an increase in dose from 0.5 (i.e., 0.05 times the recommended dosage) to 20 mg/kg', '12.3', 'text'),
 ('special_populations', 'covariates_no_effect', {'factors': ['age 37-88 years', 'sex', 'race', 'LDH', 'albumin', 'renal impairment CLcr 15-89 mL/min', 'ESRD with or without hemodialysis', 'mild hepatic impairment', 'coadministered lenalidomide/dexamethasone or pomalidomide/dexamethasone']},
  'Clinically significant differences were not observed in the PK of elotuzumab based on age (37 to 88 years), sex, race, baseline lactate dehydrogenase, albumin, renal impairment (creatinine clearance (CLcr) 15 to 89 mL/min), end-stage renal disease (CLcr <15 mL/min) with or without hemodialysis', '12.3', 'text'),
 ('special_populations', 'hepatic_moderate_severe', {'value': None, 'stated_as': 'unknown'},
  'The PK of elotuzumab in patients with moderate (total bilirubin > 1.5 to 3 times the ULN and AST any value) to severe (total bilirubin > 3 times the ULN and AST any value) hepatic impairment is unknown.', '12.3', 'text'),
 ('special_populations', 'body_weight', {'stated_as': 'clearance increases with body weight, supporting weight-based dosing'},
  'The clearance of elotuzumab increased with increasing body weight supporting a weight-based dose.', '12.3', 'text'),
]
NOT_STATED = {
 'carfilzomib': ['A single clearance value (only a range, 151-263 L/h) or the population it applies to.', 'The infusion duration and dose behind the 28 L volume beyond "a 20 mg/m2 dose".', 'Exposure in renal impairment other than on hemodialysis, as numbers (stated only as not clinically meaningful).'],
 'selinexor': ['Absolute bioavailability; clearance and volume are apparent (divided by F).', 'Absorption rate and lag time.', 'The body surface area or weight of the patients in Table 9.'],
 'thalidomide': ['Exposure in multiple myeloma patients at the 200 mg dose (Table 5 is healthy subjects and Hansen\'s disease).', 'Absolute bioavailability.', 'Clearance in healthy subjects as a number.'],
 'isatuximab': ['A clearance value; the label states only that clearance falls with dose and over time.', 'Observed (rather than model-predicted) exposure.'],
 'elotuzumab': ['Cmax or AUC at the recommended dose.', 'Volume of distribution.'],
}

def main(label_dir, out_dir):
    out = {}
    for drug, meta in LABELS.items():
        pdf = Path(label_dir) / meta['file']
        raw = pdf.read_bytes()
        n = int(re.search(r'Pages:\s+(\d+)', subprocess.run(['pdfinfo', str(pdf)], capture_output=True, text=True).stdout).group(1))
        pages = [norm(subprocess.run(['pdftotext', '-f', str(i), '-l', str(i), str(pdf), '-'], capture_output=True, text=True).stdout) for i in range(1, n + 1)]
        keys = [key(p) for p in pages]
        whole = ''.join(keys)
        doc = {'schema_version': 'drug-label-extract-v1', 'extract_version': f'{drug}-label-extract-v1.0', 'drug': drug, 'brand': meta['brand'],
               'recorded_on': '2026-11-04', 'modality': meta['modality'], 'route': meta['route'],
               'source': {'document': meta['document'], 'dailymed_set_id': meta['setid'], 'revised': f"{meta['revised']} (as printed on the label)",
                          'url': f"https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid={meta['setid']}",
                          'file_reviewed': {'file': meta['file'] + f' ({n} pages)', 'sha256': hashlib.sha256(raw).hexdigest()},
                          'storage': "Kept on the platform owner's computer only; not committed.",
                          'extraction': ('AI-assisted from the PDF text layer (pdftotext). Every quote is checked by the build script against the '
                                         'text layer (spaces and hyphens ignored, as the text layer drops hyphens at line breaks), and its PDF page recorded; table cells marked text_and_rendered_page '
                                         'were also read from the rendered page because the text layout is scrambled. Independent review pending.')},
               'dosing': {}, 'pk': {}, 'special_populations': {}, 'interactions': {}, 'not_stated': NOT_STATED[drug],
               'clinical_prediction_validated': False}
        for section, name, fields, quote, sec, check in E[drug]:
            q = key(quote)
            if q not in whole:
                sys.exit(f'{drug}/{name}: quote not found in the label text: {quote[:90]}')
            page = next((i + 1 for i, p in enumerate(keys) if q in p), None)
            if page is None:   # the sentence runs over a page break
                first = next(i + 1 for i, p in enumerate(keys) if q[:30] in p)
                where = f'PDF pages {first}-{first + 1}'
            else:
                where = f'PDF page {page}'
            doc[section][name] = dict(fields, quote=quote, location=f'section {sec}, {where}', check=check)
        path = Path(out_dir) / f'label_extract_{drug}_v1.json'
        path.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + '\n')
        out[drug] = (path.name, hashlib.sha256(path.read_bytes()).hexdigest(), sum(len(doc[s]) for s in ('dosing', 'pk', 'special_populations', 'interactions')))
    for d, v in out.items():
        print(d, *v)

if __name__ == '__main__':
    main(*sys.argv[1:3])
