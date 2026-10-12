import requests

url = "https://clinicaltrials.gov/api/v2/studies"

params = {
    "query.cond": "Alzheimer Disease",
    "pageSize": 5,
}

response = requests.get(url, params=params, timeout=30)

print("Status Code:", response.status_code)

data = response.json()

print("Studies Returned:", len(data.get("studies", [])))

studies = data.get("studies", [])

for study in studies:

    # Study identification
    identification = study["protocolSection"]["identificationModule"]

    # Recruitment status
    status = study["protocolSection"]["statusModule"]

    # Study phase and design
    design = study["protocolSection"].get("designModule", {})
    phases = design.get("phases", ["Not available"])

    phase_labels = {
        "NA": "Not Applicable",
        "EARLY_PHASE1": "Early Phase 1",
        "PHASE1": "Phase 1",
        "PHASE2": "Phase 2",
        "PHASE3": "Phase 3",
        "PHASE4": "Phase 4",
    }

    readable_phases = [
        phase_labels.get(phase, phase)
        for phase in phases
    ]

    # Study type
    study_type = design.get("studyType", "Not available")

    #Enrollment
    enrollment_info = design.get("enrollmentInfo", {})
    enrollment_count = enrollment_info.get("count", "Not available")

    # Sponsor
    sponsor_module = study["protocolSection"].get(
        "sponsorCollaboratorsModule", {}
    )

    lead_sponsor = sponsor_module.get("leadSponsor", {})
    sponsor_name = lead_sponsor.get("name", "Not available")

    # Conditions
    conditions_module = study["protocolSection"].get("conditionsModule", {})
    conditions = conditions_module.get("conditions", ["Not available"])

    # Interventions
    interventions_module = study["protocolSection"].get("armsInterventionsModule", {})
    interventions = interventions_module.get("interventions", [])

    intervention_names = [
        intervention.get("name", "Not available")
        for intervention in interventions
    ]

    if not intervention_names:
        intervention_names = ["Not available"]  

    # Location of Studies
    locations_module = study["protocolSection"].get("contactsLocationsModule", {})
    locations = locations_module.get("locations", [])

    location_labels = []

    for location in locations:
        city = location.get("city")
        state = location.get("state")
        country = location.get("country")

        parts = [part for part in [city, state, country] if part]

        if parts:
            location_labels.append(", ".join(parts))

        if not location_labels:
            location_labels = ["Not available"]

    # Display results
    print()
    print("NCT ID:", identification["nctId"])
    print("Title:", identification["briefTitle"])
    print("Status:", status["overallStatus"])
    print("Study Type:", study_type)
    print("Phases:", ", ".join(readable_phases))
    print("Sponsor:", sponsor_name)
    print("Conditions:", ", ".join(conditions))
    print("Interventions:", ", ".join(intervention_names))
    print("Enrollment:", enrollment_count)
    print("Locations:", "| ".join(location_labels))
