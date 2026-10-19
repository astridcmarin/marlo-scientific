# Clinical Trials Intelligence Explorer
from flask import Flask, redirect, render_template, request, url_for
import requests
from intelligence_store import init_storage
from intelligence_store.snapshots import save_trial_snapshots
from landscape_ui import register_landscape

app = Flask(__name__)
init_storage(app)
register_landscape(app)


# ==================================================
# FORMATTING HELPERS
# ==================================================
def format_api_value(value):
    if not value or value == "Not available":
        return "Not available"
    return value.replace("_", " ").title()


def format_api_list(values):
    if not values:
        return "Not available"
    unique_values = []
    for value in values:
        if value and value not in unique_values:
            unique_values.append(value)
    return ", ".join(value.replace("_", " ").title() for value in unique_values)


def format_boolean(value):
    if value is True:
        return "Yes"
    if value is False:
        return "No"
    return "Not available"


# ==================================================
# API REQUEST
# ==================================================
def fetch_trials(params):
    url = "https://clinicaltrials.gov/api/v2/studies"
    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response.json(), None
    except requests.exceptions.Timeout:
        return None, ("The ClinicalTrials.gov request timed out. " "Please try again.")
    except requests.exceptions.ConnectionError:
        return None, (
            "Unable to connect to ClinicalTrials.gov. "
            "Please check your connection and try again."
        )
    except requests.exceptions.HTTPError:
        return None, (
            "ClinicalTrials.gov returned an error. " "Please try again later."
        )
    except requests.exceptions.RequestException:
        return None, (
            "An unexpected error occurred while retrieving " "clinical trial data."
        )
    except ValueError:
        return None, ("ClinicalTrials.gov returned an invalid response.")


# ==================================================
# CLEAN ONE CLINICAL TRIAL
# ==================================================
def clean_trial(study):
    protocol = study.get("protocolSection", {})
    derived = study.get("derivedSection", {})
    # --------------------------------------------------
    # IDENTIFICATION
    # --------------------------------------------------
    identification = protocol.get("identificationModule", {})
    official_title = identification.get("officialTitle", "Not available")
    acronym = identification.get("acronym", "Not available")
    org_study_id = identification.get("orgStudyIdInfo", {}).get("id", "Not available")
    # --------------------------------------------------
    # STATUS
    # --------------------------------------------------
    status = protocol.get("statusModule", {})
    start_date = status.get("startDateStruct", {}).get("date", "Not available")
    completion_date = status.get("completionDateStruct", {}).get(
        "date", "Not available"
    )
    last_update = status.get("lastUpdatePostDateStruct", {}).get(
        "date", "Not available"
    )
    # --------------------------------------------------
    # REGISTRATION / RESULTS TIMELINE
    # --------------------------------------------------
    study_first_submit_date = status.get("studyFirstSubmitDate", "Not available")
    study_first_submit_qc_date = status.get("studyFirstSubmitQcDate", "Not available")
    study_first_post_date = status.get("studyFirstPostDateStruct", {}).get(
        "date", "Not available"
    )
    results_first_submit_date = status.get("resultsFirstSubmitDate", "Not available")
    results_first_submit_qc_date = status.get(
        "resultsFirstSubmitQcDate", "Not available"
    )
    # --------------------------------------------------
    # PENDING RESULTS SUBMISSION TRACKING
    # --------------------------------------------------
    misc_info_module = derived.get("miscInfoModule", {})
    submission_tracking = misc_info_module.get("submissionTracking", {})
    estimated_results_first_submit_date = submission_tracking.get(
        "estimatedResultsFirstSubmitDate", "Not available"
    )
    results_first_post_date = status.get("resultsFirstPostDateStruct", {}).get(
        "date", "Not available"
    )
    results_waived = format_boolean(status.get("resultsWaived"))
    certification_extension_submit_date = status.get(
        "dispFirstSubmitDate", "Not available"
    )
    certification_extension_post_date = status.get("dispFirstPostDateStruct", {}).get(
        "date", "Not available"
    )
    last_update_submit_date = status.get("lastUpdateSubmitDate", "Not available")
    # --------------------------------------------------
    # RESULTS REPORTING STATUS
    # --------------------------------------------------
    if results_first_post_date != "Not available":
        results_reporting_status = "Results Posted"
    elif results_waived == "Yes":
        results_reporting_status = "Results Waived"
    elif (
        estimated_results_first_submit_date != "Not available"
        or results_first_submit_date != "Not available"
    ):
        results_reporting_status = "Results Submitted / Not Yet Posted"
    else:
        results_reporting_status = "No Results Posted"
    # --------------------------------------------------
    # EXPANDED ACCESS
    # --------------------------------------------------
    expanded_access_info = status.get("expandedAccessInfo", {})
    has_expanded_access = format_boolean(expanded_access_info.get("hasExpandedAccess"))
    expanded_access_nct_id = expanded_access_info.get("nctId", "Not available")
    expanded_access_status = format_api_value(
        expanded_access_info.get("statusForNctId", "Not available")
    )
    # --------------------------------------------------
    # REGULATORY / FDA OVERSIGHT
    # --------------------------------------------------
    oversight_module = protocol.get("oversightModule", {})
    is_fda_regulated_drug = oversight_module.get("isFdaRegulatedDrug")
    is_fda_regulated_device = oversight_module.get("isFdaRegulatedDevice")
    is_unapproved_device = oversight_module.get("isUnapprovedDevice")
    oversight_has_dmc = oversight_module.get("oversightHasDmc")
    fdaaa_801_violation = oversight_module.get("fdaaa801Violation")
    # --------------------------------------------------
    # SPONSOR / COLLABORATORS
    # --------------------------------------------------
    sponsor_module = protocol.get("sponsorCollaboratorsModule", {})
    lead_sponsor = sponsor_module.get("leadSponsor", {})
    sponsor_name = lead_sponsor.get("name", "Not available")
    sponsor_class = lead_sponsor.get("class", "Not available")
    responsible_party_type = sponsor_module.get("responsibleParty", {}).get(
        "type", "Not available"
    )
    collaborators = sponsor_module.get("collaborators", [])
    collaborator_names = [
        collaborator.get("name")
        for collaborator in collaborators
        if collaborator.get("name")
    ]
    collaborators_text = (
        ", ".join(collaborator_names) if collaborator_names else "Not available"
    )
    # --------------------------------------------------
    # CONDITIONS
    # --------------------------------------------------
    conditions_module = protocol.get("conditionsModule", {})
    conditions = conditions_module.get("conditions", [])
    condition_names = ", ".join(conditions) if conditions else "Not available"
    keywords = conditions_module.get("keywords", [])
    keywords_text = ", ".join(keywords) if keywords else "Not available"
    # --------------------------------------------------
    # STUDY DESIGN
    # --------------------------------------------------
    design = protocol.get("designModule", {})
    study_type = design.get("studyType", "Not available")
    phase_labels = {
        "NA": "Not Applicable",
        "EARLY_PHASE1": "Early Phase 1",
        "PHASE1": "Phase 1",
        "PHASE2": "Phase 2",
        "PHASE3": "Phase 3",
        "PHASE4": "Phase 4",
    }
    phases = design.get("phases", [])
    readable_phases = [phase_labels.get(phase, phase) for phase in phases]
    if not readable_phases:
        readable_phases = ["Not available"]
    design_info = design.get("designInfo", {})
    primary_purpose = design_info.get("primaryPurpose", "Not available")
    allocation = design_info.get("allocation", "Not available")
    intervention_model = design_info.get("interventionModel", "Not available")
    masking = design_info.get("maskingInfo", {}).get("masking", "Not available")
    enrollment_count = design.get("enrollmentInfo", {}).get("count", "Not available")
    # --------------------------------------------------
    # EXPANDED ACCESS TYPES
    # --------------------------------------------------
    expanded_access_types = design.get("expandedAccessTypes", {})
    expanded_access_individual = format_boolean(expanded_access_types.get("individual"))
    expanded_access_intermediate = format_boolean(
        expanded_access_types.get("intermediate")
    )
    expanded_access_treatment = format_boolean(expanded_access_types.get("treatment"))
    # --------------------------------------------------
    # ARMS / INTERVENTIONS
    # --------------------------------------------------
    interventions_module = protocol.get("armsInterventionsModule", {})
    arm_groups = interventions_module.get("armGroups", [])
    arm_labels = []
    arm_types = []
    arm_descriptions = []
    for arm in arm_groups:
        if arm.get("label"):
            arm_labels.append(arm["label"])
        if arm.get("type"):
            arm_types.append(arm["type"])
        if arm.get("description"):
            arm_descriptions.append(arm["description"])
    arm_labels_text = ", ".join(arm_labels) if arm_labels else "Not available"
    arm_descriptions_text = (
        " | ".join(arm_descriptions) if arm_descriptions else "Not available"
    )
    interventions = interventions_module.get("interventions", [])
    intervention_names = []
    intervention_types = []
    intervention_descriptions = []
    for intervention in interventions:
        if intervention.get("name"):
            intervention_names.append(intervention["name"])
        if intervention.get("type"):
            intervention_types.append(intervention["type"])
        if intervention.get("description"):
            intervention_descriptions.append(intervention["description"])
    intervention_text = (
        ", ".join(intervention_names) if intervention_names else "Not available"
    )
    intervention_description_text = (
        " | ".join(intervention_descriptions)
        if intervention_descriptions
        else "Not available"
    )
    # --------------------------------------------------
    # ELIGIBILITY
    # --------------------------------------------------
    eligibility_module = protocol.get("eligibilityModule", {})
    sex = eligibility_module.get("sex", "Not available")
    minimum_age = eligibility_module.get("minimumAge", "Not available")
    maximum_age = eligibility_module.get("maximumAge", "Not available")
    healthy_volunteers = eligibility_module.get("healthyVolunteers")
    if healthy_volunteers is True:
        healthy_volunteers_text = "Yes"
    elif healthy_volunteers is False:
        healthy_volunteers_text = "No"
    else:
        healthy_volunteers_text = "Not available"
    eligibility_criteria = eligibility_module.get(
        "eligibilityCriteria", "Not available"
    )
    # --------------------------------------------------
    # CONTACTS / LOCATIONS
    # --------------------------------------------------
    contacts_locations = protocol.get("contactsLocationsModule", {})
    locations = contacts_locations.get("locations", [])
    location_names = []
    country_names = []
    for location in locations:
        city = location.get("city")
        state = location.get("state")
        country = location.get("country")
        if country and country not in country_names:
            country_names.append(country)
        location_parts = []
        if city:
            location_parts.append(city)
        if state:
            location_parts.append(state)
        if country:
            location_parts.append(country)
        if location_parts:
            location_names.append(", ".join(location_parts))
    location_text = "; ".join(location_names) if location_names else "Not available"
    countries_text = ", ".join(country_names) if country_names else "Not available"
    # --------------------------------------------------
    # STUDY OFFICIALS
    # --------------------------------------------------
    overall_officials = contacts_locations.get("overallOfficials", [])
    official_names = []
    official_roles = []
    official_affiliations = []
    for official in overall_officials:
        if official.get("name"):
            official_names.append(official["name"])
        if official.get("role"):
            official_roles.append(official["role"])
        if official.get("affiliation"):
            official_affiliations.append(official["affiliation"])
    official_names_text = (
        ", ".join(official_names) if official_names else "Not available"
    )
    official_affiliations_text = (
        ", ".join(official_affiliations) if official_affiliations else "Not available"
    )
    # --------------------------------------------------
    # CENTRAL CONTACTS
    # --------------------------------------------------
    central_contacts = contacts_locations.get("centralContacts", [])
    central_contact_names = []
    central_contact_roles = []
    central_contact_phones = []
    central_contact_emails = []
    for contact in central_contacts:
        if contact.get("name"):
            central_contact_names.append(contact["name"])
        if contact.get("role"):
            central_contact_roles.append(contact["role"])
        if contact.get("phone"):
            central_contact_phones.append(contact["phone"])
        if contact.get("email"):
            central_contact_emails.append(contact["email"])
    central_contact_names_text = (
        ", ".join(central_contact_names) if central_contact_names else "Not available"
    )
    central_contact_phones_text = (
        ", ".join(central_contact_phones) if central_contact_phones else "Not available"
    )
    central_contact_emails_text = (
        ", ".join(central_contact_emails) if central_contact_emails else "Not available"
    )
    # --------------------------------------------------
    # DESCRIPTION
    # --------------------------------------------------
    description_module = protocol.get("descriptionModule", {})
    brief_summary = description_module.get("briefSummary", "Not available")
    detailed_description = description_module.get(
        "detailedDescription", "Not available"
    )
    # --------------------------------------------------
    # OUTCOMES
    # --------------------------------------------------
    outcomes_module = protocol.get("outcomesModule", {})
    primary_outcome_names = [
        outcome.get("measure")
        for outcome in outcomes_module.get("primaryOutcomes", [])
        if outcome.get("measure")
    ]
    secondary_outcome_names = [
        outcome.get("measure")
        for outcome in outcomes_module.get("secondaryOutcomes", [])
        if outcome.get("measure")
    ]
    primary_outcome_text = (
        ", ".join(primary_outcome_names) if primary_outcome_names else "Not available"
    )
    secondary_outcome_text = (
        ", ".join(secondary_outcome_names)
        if secondary_outcome_names
        else "Not available"
    )
    # --------------------------------------------------
    # RETURN CLEANED STUDY
    # --------------------------------------------------
    return {
        # IDENTIFICATION
        "nct_id": identification.get("nctId", "Not available"),
        "title": identification.get("briefTitle", "Not available"),
        "official_title": official_title,
        "acronym": acronym,
        "org_study_id": org_study_id,
        # STATUS
        "status": format_api_value(status.get("overallStatus", "Not available")),
        # FDA OVERSIGHT
        "is_fda_regulated_drug": format_boolean(is_fda_regulated_drug),
        "is_fda_regulated_device": format_boolean(is_fda_regulated_device),
        "is_unapproved_device": format_boolean(is_unapproved_device),
        "oversight_has_dmc": format_boolean(oversight_has_dmc),
        "fdaaa_801_violation": format_boolean(fdaaa_801_violation),
        # EXPANDED ACCESS
        "has_expanded_access": has_expanded_access,
        "expanded_access_nct_id": expanded_access_nct_id,
        "expanded_access_status": expanded_access_status,
        "expanded_access_individual": expanded_access_individual,
        "expanded_access_intermediate": expanded_access_intermediate,
        "expanded_access_treatment": expanded_access_treatment,
        # CONDITIONS
        "condition": condition_names,
        "keywords": keywords_text,
        # SPONSOR
        "sponsor": sponsor_name,
        "sponsor_class": format_api_value(sponsor_class),
        "collaborators": collaborators_text,
        "responsible_party_type": format_api_value(responsible_party_type),
        "study_officials": official_names_text,
        "official_roles": format_api_list(official_roles),
        "official_affiliations": official_affiliations_text,
        # DESIGN
        "study_type": format_api_value(study_type),
        "phase": ", ".join(readable_phases),
        "primary_purpose": format_api_value(primary_purpose),
        "allocation": format_api_value(allocation),
        "intervention_model": format_api_value(intervention_model),
        "masking": format_api_value(masking),
        "enrollment": enrollment_count,
        # ARMS / INTERVENTIONS
        "arm_groups": arm_labels_text,
        "arm_types": format_api_list(arm_types),
        "arm_descriptions": arm_descriptions_text,
        "interventions": intervention_text,
        "intervention_type": format_api_list(intervention_types),
        "intervention_description": intervention_description_text,
        # STUDY DATES
        "start_date": start_date,
        "completion_date": completion_date,
        "last_update": last_update,
        # REGISTRATION / RESULTS
        "study_first_submit_date": study_first_submit_date,
        "study_first_submit_qc_date": study_first_submit_qc_date,
        "study_first_post_date": study_first_post_date,
        "results_first_submit_date": results_first_submit_date,
        "estimated_results_first_submit_date": estimated_results_first_submit_date,
        "results_first_submit_qc_date": results_first_submit_qc_date,
        "results_first_post_date": results_first_post_date,
        "results_waived": results_waived,
        "results_reporting_status": results_reporting_status,
        "certification_extension_submit_date": certification_extension_submit_date,
        "certification_extension_post_date": certification_extension_post_date,
        "last_update_submit_date": last_update_submit_date,
        # ELIGIBILITY
        "sex": format_api_value(sex),
        "minimum_age": minimum_age,
        "maximum_age": maximum_age,
        "healthy_volunteers": healthy_volunteers_text,
        "eligibility_criteria": eligibility_criteria,
        # LOCATIONS
        "locations": location_text,
        "countries": countries_text,
        # CONTACTS
        "central_contact_names": central_contact_names_text,
        "central_contact_roles": format_api_list(central_contact_roles),
        "central_contact_phones": central_contact_phones_text,
        "central_contact_emails": central_contact_emails_text,
        # DESCRIPTION
        "summary": brief_summary,
        "detailed_description": detailed_description,
        # OUTCOMES
        "primary_outcome": primary_outcome_text,
        "secondary_outcomes": secondary_outcome_text,
    }


# ==================================================
# ANALYTICS
# ==================================================
def calculate_analytics(studies):
    recruiting_count = sum(1 for study in studies if study["status"] == "Recruiting")
    industry_count = sum(1 for study in studies if study["sponsor_class"] == "Industry")
    # --------------------------------------------------
    # PHASE DISTRIBUTION
    # --------------------------------------------------
    phase_counts = {
        "Phase 1": 0,
        "Phase 2": 0,
        "Phase 3": 0,
        "Phase 4": 0,
        "Other": 0,
    }
    for study in studies:
        phase_value = study.get("phase", "Not available")
        phases = [phase.strip() for phase in phase_value.split(",")]
        counted_standard_phase = False
        for phase in phases:
            if phase == "Phase 1":
                phase_counts["Phase 1"] += 1
                counted_standard_phase = True
            elif phase == "Phase 2":
                phase_counts["Phase 2"] += 1
                counted_standard_phase = True
            elif phase == "Phase 3":
                phase_counts["Phase 3"] += 1
                counted_standard_phase = True
            elif phase == "Phase 4":
                phase_counts["Phase 4"] += 1
                counted_standard_phase = True
        if not counted_standard_phase:
            phase_counts["Other"] += 1
    # --------------------------------------------------
    # STATUS DISTRIBUTION
    # --------------------------------------------------
    status_counts = {}
    for study in studies:
        status_name = study["status"]
        status_counts[status_name] = status_counts.get(status_name, 0) + 1
    # --------------------------------------------------
    # SPONSOR CLASS
    # --------------------------------------------------
    sponsor_class_counts = {}
    for study in studies:
        sponsor_class = study["sponsor_class"]
        sponsor_class_counts[sponsor_class] = (
            sponsor_class_counts.get(sponsor_class, 0) + 1
        )
    # --------------------------------------------------
    # TOP SPONSORS
    # --------------------------------------------------
    sponsor_counts = {}
    for study in studies:
        sponsor_name = study["sponsor"]
        if sponsor_name == "Not available":
            continue
        sponsor_counts[sponsor_name] = sponsor_counts.get(sponsor_name, 0) + 1
    top_sponsors = sorted(
        sponsor_counts.items(), key=lambda item: item[1], reverse=True
    )[:5]
    # --------------------------------------------------
    # INTERVENTION TYPES
    # --------------------------------------------------
    intervention_type_counts = {}
    for study in studies:
        intervention_types = study["intervention_type"]
        if intervention_types == "Not available":
            continue
        for intervention_type in intervention_types.split(", "):
            intervention_type_counts[intervention_type] = (
                intervention_type_counts.get(intervention_type, 0) + 1
            )
    # --------------------------------------------------
    # COUNTRIES
    # --------------------------------------------------
    country_counts = {}
    for study in studies:
        countries = study["countries"]
        if countries == "Not available":
            continue
        for country in countries.split(", "):
            country_counts[country] = country_counts.get(country, 0) + 1
    country_counts = dict(
        sorted(country_counts.items(), key=lambda item: item[1], reverse=True)
    )
    # --------------------------------------------------
    # ENROLLMENT DISTRIBUTION
    # --------------------------------------------------
    enrollment_distribution = {
        "1–50": 0,
        "51–100": 0,
        "101–500": 0,
        "501–1,000": 0,
        "1,001+": 0,
        "Not available": 0,
    }
    for study in studies:
        enrollment = study["enrollment"]
        if not isinstance(enrollment, int):
            enrollment_distribution["Not available"] += 1
        elif enrollment <= 50:
            enrollment_distribution["1–50"] += 1
        elif enrollment <= 100:
            enrollment_distribution["51–100"] += 1
        elif enrollment <= 500:
            enrollment_distribution["101–500"] += 1
        elif enrollment <= 1000:
            enrollment_distribution["501–1,000"] += 1
        else:
            enrollment_distribution["1,001+"] += 1
    # --------------------------------------------------
    # STUDY TYPES
    # --------------------------------------------------
    study_type_counts = {}
    for study in studies:
        study_type = study["study_type"]
        if study_type == "Not available":
            continue
        study_type_counts[study_type] = study_type_counts.get(study_type, 0) + 1
    # --------------------------------------------------
    # RESULTS REPORTING STATUS
    # --------------------------------------------------
    results_reporting_counts = {}
    for study in studies:
        reporting_status = study.get("results_reporting_status", "No Results Posted")
        results_reporting_counts[reporting_status] = (
            results_reporting_counts.get(reporting_status, 0) + 1
        )
    # --------------------------------------------------
    # EXPANDED ACCESS
    # --------------------------------------------------
    expanded_access_counts = {
        "Available": 0,
        "Individual Patient": 0,
        "Intermediate-size Population": 0,
        "Treatment IND / Protocol": 0,
    }
    for study in studies:
        if study.get("has_expanded_access") == "Yes":
            expanded_access_counts["Available"] += 1
        if study.get("expanded_access_individual") == "Yes":
            expanded_access_counts["Individual Patient"] += 1
        if study.get("expanded_access_intermediate") == "Yes":
            expanded_access_counts["Intermediate-size Population"] += 1
        if study.get("expanded_access_treatment") == "Yes":
            expanded_access_counts["Treatment IND / Protocol"] += 1
    # --------------------------------------------------
    # FDA / REGULATORY OVERSIGHT
    # --------------------------------------------------
    regulatory_fields = {
        "FDA-Regulated Drug": "is_fda_regulated_drug",
        "FDA-Regulated Device": "is_fda_regulated_device",
        "Unapproved Device": "is_unapproved_device",
        "Data Monitoring Committee": "oversight_has_dmc",
        "FDAAA 801 Violation": "fdaaa_801_violation",
    }
    regulatory_analytics = {}
    for label, field_name in regulatory_fields.items():
        yes_count = 0
        no_count = 0
        unavailable_count = 0
        for study in studies:
            value = study.get(field_name, "Not available")
            if value == "Yes":
                yes_count += 1
            elif value == "No":
                no_count += 1
            else:
                unavailable_count += 1
        regulatory_analytics[label] = {
            "yes": yes_count,
            "no": no_count,
            "unavailable": unavailable_count,
        }
    # --------------------------------------------------
    # RETURN ANALYTICS
    # --------------------------------------------------
    return {
        "recruiting_count": recruiting_count,
        "industry_count": industry_count,
        "phase_counts": phase_counts,
        "status_counts": status_counts,
        "sponsor_class_counts": sponsor_class_counts,
        "top_sponsors": top_sponsors,
        "intervention_type_counts": intervention_type_counts,
        "country_counts": country_counts,
        "enrollment_distribution": enrollment_distribution,
        "study_type_counts": study_type_counts,
        "results_reporting_counts": results_reporting_counts,
        "expanded_access_counts": expanded_access_counts,
        "regulatory_analytics": regulatory_analytics,
    }


# ==================================================
# LANDING PAGE
# ==================================================
GITHUB_URL = "https://github.com/astridcmarin/marlo-scientific"


@app.route("/")
def landing():
    # Searches used to live at "/?condition=...": send old links and bookmarks to the explorer.
    if request.args:
        return redirect(url_for("home", **request.args.to_dict(flat=False)), code=301)
    from landscape_ui.landing_examples import curve_example, kidney_example
    return render_template("landing.html", github_url=GITHUB_URL, curve=curve_example(), kidney=kidney_example())


# ==================================================
# TRIAL EXPLORER
# ==================================================
@app.route("/trials")
def home():
    condition = request.args.get("condition", "")
    status_filter = request.args.get("status", "")
    sponsor_filter = request.args.get("sponsor", "")
    location_filter = request.args.get("location", "")
    phase_filter = request.args.get("phase", "")
    intervention_filter = request.args.get("intervention", "")
    study_type_filter = request.args.get("study_type", "")
    sex_filter = request.args.get("sex", "")
    sort_filter = request.args.get("sort", "")
    page_token = request.args.get("page_token", "")
    page_size = request.args.get("page_size", "5")
    # --------------------------------------------------
    # PAGE SIZE VALIDATION
    # --------------------------------------------------
    allowed_page_sizes = [5, 10, 25, 50]
    try:
        page_size = int(page_size)
    except ValueError:
        page_size = 5
    if page_size not in allowed_page_sizes:
        page_size = 5
    # --------------------------------------------------
    # API SORT OPTIONS
    # --------------------------------------------------
    sort_options = {
        "newest": "LastUpdatePostDate:desc",
        "oldest": "LastUpdatePostDate:asc",
        "enrollment_high": "EnrollmentCount:desc",
        "enrollment_low": "EnrollmentCount:asc",
    }
    # --------------------------------------------------
    # DEFAULT VALUES
    # --------------------------------------------------
    studies = []
    next_page_token = None
    total_count = 0
    error_message = None
    analytics = calculate_analytics([])
    # --------------------------------------------------
    # DETERMINE WHETHER A SEARCH SHOULD RUN
    # --------------------------------------------------
    has_search_input = any(
        [
            condition,
            status_filter,
            sponsor_filter,
            location_filter,
            phase_filter,
            intervention_filter,
            study_type_filter,
            sex_filter,
        ]
    )
    # --------------------------------------------------
    # SEARCH
    # --------------------------------------------------
    if has_search_input:
        params = {
            "pageSize": page_size,
            "countTotal": "true",
        }
        # --------------------------------------------------
        # CONDITION
        # --------------------------------------------------
        if condition:
            params["query.cond"] = condition
        # --------------------------------------------------
        # API SORTING
        # --------------------------------------------------
        if sort_filter in sort_options:
            params["sort"] = sort_options[sort_filter]
        # --------------------------------------------------
        # STANDARD FILTERS
        # --------------------------------------------------
        if status_filter:
            params["filter.overallStatus"] = status_filter
        if sponsor_filter:
            params["query.spons"] = sponsor_filter
        if location_filter:
            params["query.locn"] = location_filter
        if intervention_filter:
            params["query.intr"] = intervention_filter
        if page_token:
            params["pageToken"] = page_token
        # --------------------------------------------------
        # FIELD-SPECIFIC FILTERS
        # --------------------------------------------------
        query_terms = []
        if phase_filter:
            query_terms.append(f"AREA[Phase]" f"{phase_filter}")
        if study_type_filter:
            query_terms.append(f"AREA[StudyType]" f"{study_type_filter}")
        if sex_filter:
            query_terms.append(f"AREA[Sex]" f"{sex_filter}")
        if query_terms:
            params["query.term"] = " AND ".join(query_terms)
        # --------------------------------------------------
        # FETCH
        # --------------------------------------------------
        data, error_message = fetch_trials(params)
        if data:
            raw_studies = data.get("studies", [])
            # Preserve source evidence before cleaning values for display.
            save_trial_snapshots(raw_studies)
            next_page_token = data.get("nextPageToken")
            total_count = data.get("totalCount", 0)
            # --------------------------------------------------
            # CLEAN STUDIES
            # --------------------------------------------------
            for study in raw_studies:
                studies.append(clean_trial(study))
            # --------------------------------------------------
            # CALCULATE PAGE-LEVEL ANALYTICS
            # --------------------------------------------------
            analytics = calculate_analytics(studies)
    # --------------------------------------------------
    # RENDER
    # --------------------------------------------------
    return render_template(
        "index.html",
        condition=condition,
        status_filter=status_filter,
        sponsor_filter=sponsor_filter,
        location_filter=location_filter,
        phase_filter=phase_filter,
        intervention_filter=intervention_filter,
        study_type_filter=study_type_filter,
        sex_filter=sex_filter,
        sort_filter=sort_filter,
        page_size=page_size,
        next_page_token=next_page_token,
        total_count=total_count,
        studies=studies,
        error_message=error_message,
        recruiting_count=analytics["recruiting_count"],
        industry_count=analytics["industry_count"],
        phase_counts=analytics["phase_counts"],
        status_counts=analytics["status_counts"],
        sponsor_class_counts=analytics["sponsor_class_counts"],
        top_sponsors=analytics["top_sponsors"],
        intervention_type_counts=analytics["intervention_type_counts"],
        country_counts=analytics["country_counts"],
        enrollment_distribution=analytics["enrollment_distribution"],
        study_type_counts=analytics["study_type_counts"],
        results_reporting_counts=analytics["results_reporting_counts"],
        expanded_access_counts=analytics["expanded_access_counts"],
        regulatory_analytics=analytics["regulatory_analytics"],
    )


# ==================================================
# LOCAL DEVELOPMENT
# ==================================================
if __name__ == "__main__":
    app.run(debug=True)
