"""Evidence-linked descriptive metrics from a COMPLETE cohort's frozen records."""

from collections import defaultdict
import json

import click
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from .extensions import db
from .models import AnalysisCohort, CohortTrial, TrialSnapshot
from .normalization import _mapping, _string_list, _text

SUMMARY_VERSION = "cohort-summary-v1.0"
UNKNOWN = "Unknown / not reported"
PHASE_NAMES = {
    "EARLY_PHASE1": "Early Phase 1",
    "PHASE1": "Phase 1",
    "PHASE2": "Phase 2",
    "PHASE3": "Phase 3",
    "PHASE4": "Phase 4",
    "NA": "Not applicable (reported NA)",
}
METRIC_PATHS = {
    "total_trials": ["cohort_trial.nct_id"],
    "recruiting_trials": ["protocolSection.statusModule.overallStatus"],
    "lead_sponsor_names": [
        "protocolSection.sponsorCollaboratorsModule.leadSponsor.name"
    ],
    "industry_lead_sponsor_names": [
        "protocolSection.sponsorCollaboratorsModule.leadSponsor.name",
        "protocolSection.sponsorCollaboratorsModule.leadSponsor.class",
    ],
    "drug_biologic_interventional_trials": [
        "protocolSection.designModule.studyType",
        "protocolSection.armsInterventionsModule.interventions[].type",
    ],
    "listed_countries": ["protocolSection.contactsLocationsModule.locations[].country"],
    "study_type": ["protocolSection.designModule.studyType"],
    "status": ["protocolSection.statusModule.overallStatus"],
    "phase": ["protocolSection.designModule.phases"],
    "sponsor": ["protocolSection.sponsorCollaboratorsModule.leadSponsor.name"],
    "drug_intervention": [
        "protocolSection.armsInterventionsModule.interventions[].name",
        "protocolSection.armsInterventionsModule.interventions[].type",
    ],
    "country": ["protocolSection.contactsLocationsModule.locations[].country"],
}


class CohortSummaryError(ValueError):
    pass


def _phase_bucket(value):
    phases = _string_list(value)
    if not phases:
        return UNKNOWN
    phases = sorted(phases)
    if phases == ["PHASE1", "PHASE2"]:
        return "Phase 1/2"
    if phases == ["PHASE2", "PHASE3"]:
        return "Phase 2/3"
    return " + ".join(PHASE_NAMES.get(phase, phase) for phase in phases)


def _group_rows(groups):
    return [
        {"label": name, "count": len(ids), "nct_ids": sorted(ids)}
        for name, ids in sorted(
            groups.items(), key=lambda pair: (-len(pair[1]), pair[0])
        )
    ]


def summarize_cohort(cohort_id):
    """Read only the run's snapshot links, never mutable current-trial rows.

    Counts are trial counts unless labeled unique raw names/countries.
    Raw intervention names are not canonical drugs or development programs.
    """
    cohort = db.session.get(AnalysisCohort, cohort_id)
    if cohort is None:
        raise CohortSummaryError("No cohort has that ID.")
    if cohort.status != "COMPLETE":
        raise CohortSummaryError(
            f"Cohort {cohort_id} is {cohort.status}; complete-cohort summaries are unavailable."
        )
    records = db.session.execute(
        select(CohortTrial, TrialSnapshot)
        .outerjoin(TrialSnapshot, CohortTrial.snapshot_id == TrialSnapshot.id)
        .where(CohortTrial.cohort_id == cohort_id)
        .order_by(CohortTrial.nct_id)
    ).all()
    if (
        len(records) != cohort.retrieved_count
        or len(records) != cohort.expected_count
        or cohort.finished_at_utc is None
    ):
        raise CohortSummaryError(
            "Saved membership/expected counts disagree or the run is not finalized."
        )

    groupings = {
        key: defaultdict(set)
        for key in [
            "study_type",
            "status",
            "phase",
            "sponsor",
            "drug_intervention",
            "country",
        ]
    }
    recruiting = set()
    drug_biologic = set()
    unknown_drug_scope = set()
    interventional = set()
    sponsor_names = set()
    industry_names = set()
    industry_trial_ids = set()
    missing_sponsor = set()
    missing_country = set()
    references = {}
    all_ids = set()
    for membership, snapshot in records:
        if snapshot is None or snapshot.nct_id != membership.nct_id:
            raise CohortSummaryError(
                "A cohort member has a missing or mismatched evidence snapshot."
            )
        protocol = _mapping(_mapping(snapshot.raw_study).get("protocolSection"))
        identification = _mapping(protocol.get("identificationModule"))
        nct_id = membership.nct_id
        if identification.get("nctId") != nct_id:
            raise CohortSummaryError(
                "A retained study object does not match its evidence NCT ID."
            )
        all_ids.add(nct_id)
        references[nct_id] = {
            "snapshot_id": snapshot.id,
            "source": snapshot.source,
            "source_url": snapshot.source_url,
            "retrieved_at_utc": snapshot.retrieved_at_utc.isoformat(),
            "source_last_update_date": snapshot.source_last_update_date,
        }
        design = _mapping(protocol.get("designModule"))
        study_type = _text(design.get("studyType"))
        status = _text(_mapping(protocol.get("statusModule")).get("overallStatus"))
        groupings["study_type"][study_type or UNKNOWN].add(nct_id)
        groupings["status"][status or UNKNOWN].add(nct_id)
        if status == "RECRUITING":
            recruiting.add(nct_id)
        if study_type == "INTERVENTIONAL":
            interventional.add(nct_id)
            groupings["phase"][_phase_bucket(design.get("phases"))].add(nct_id)

        lead = _mapping(
            _mapping(protocol.get("sponsorCollaboratorsModule")).get("leadSponsor")
        )
        sponsor = _text(lead.get("name"))
        if sponsor:
            sponsor_names.add(sponsor)
            groupings["sponsor"][sponsor].add(nct_id)
            if lead.get("class") == "INDUSTRY":
                industry_names.add(sponsor)
                industry_trial_ids.add(nct_id)
        else:
            missing_sponsor.add(nct_id)

        interventions = _mapping(protocol.get("armsInterventionsModule")).get(
            "interventions"
        )
        has_drug = False
        uncertain_types = not isinstance(interventions, list)
        if isinstance(interventions, list):
            for item in interventions:
                item = _mapping(item)
                kind = _text(item.get("type"))
                uncertain_types |= kind is None
                if kind in ("DRUG", "BIOLOGICAL"):
                    has_drug = True
                    name = _text(item.get("name"))
                    if name:
                        groupings["drug_intervention"][name].add(nct_id)
        if study_type == "INTERVENTIONAL" and has_drug:
            drug_biologic.add(nct_id)
        elif study_type is None or (study_type == "INTERVENTIONAL" and uncertain_types):
            unknown_drug_scope.add(nct_id)

        locations = _mapping(protocol.get("contactsLocationsModule")).get("locations")
        countries = set()
        if isinstance(locations, list):
            for location in locations:
                country = _text(_mapping(location).get("country"))
                if country:
                    countries.add(country)
        if not countries:
            missing_country.add(nct_id)
        for country in countries:
            groupings["country"][country].add(nct_id)

    if len(all_ids) != len(records):
        raise CohortSummaryError(
            "Duplicate membership IDs prevent a unique-trial summary."
        )
    metrics = {
        "total_trials": {"value": len(all_ids), "nct_ids": sorted(all_ids)},
        "recruiting_trials": {"value": len(recruiting), "nct_ids": sorted(recruiting)},
        "lead_sponsor_names": {
            "value": len(sponsor_names),
            "nct_ids": sorted(all_ids - missing_sponsor),
        },
        "industry_lead_sponsor_names": {
            "value": len(industry_names),
            "nct_ids": sorted(industry_trial_ids),
        },
        "drug_biologic_interventional_trials": {
            "value": len(drug_biologic),
            "nct_ids": sorted(drug_biologic),
        },
        "listed_countries": {
            "value": len(groupings["country"]),
            "nct_ids": sorted(all_ids - missing_country),
        },
    }
    return {
        "method_version": SUMMARY_VERSION,
        "cohort": {
            "id": cohort.id,
            "condition": cohort.condition,
            "scope": cohort.scope,
            "status": cohort.status,
            "query_params": cohort.query_params,
            "query_version": cohort.query_version,
            "start_year": cohort.start_year,
            "end_year": cohort.end_year,
            "started_at_utc": cohort.started_at_utc.isoformat(),
            "finished_at_utc": cohort.finished_at_utc.isoformat(),
        },
        "metrics": metrics,
        "groups": {key: _group_rows(value) for key, value in groupings.items()},
        "phase_denominator": len(interventional),
        "coverage": {
            "missing_lead_sponsor": len(missing_sponsor),
            "no_listed_country": len(missing_country),
            "uncertain_drug_biologic_scope": len(unknown_drug_scope),
        },
        "evidence": references,
        "metric_source_paths": METRIC_PATHS,
    }


def register_summary_commands(app):
    @app.cli.command("cohort-summary")
    @click.option("--id", "cohort_id", type=click.IntRange(1), required=True)
    @click.option("--top", type=click.IntRange(1, 50), default=10, show_default=True)
    @click.option(
        "--json",
        "json_output",
        is_flag=True,
        help="Print full metric/evidence JSON instead of the concise report.",
    )
    def cohort_summary(cohort_id, top, json_output):
        """Summarize a complete saved cohort without any API request."""
        try:
            summary = summarize_cohort(cohort_id)
        except CohortSummaryError as exc:
            raise click.ClickException(str(exc)) from exc
        except SQLAlchemyError as exc:
            raise click.ClickException(
                "Database unavailable. Check configuration and migrations."
            ) from exc
        if json_output:
            click.echo(json.dumps(summary, indent=2, ensure_ascii=False))
            return
        cohort = summary["cohort"]
        click.echo(
            f"Cohort {cohort_id}: {cohort['condition']} | {cohort['scope']} | COMPLETE"
        )
        click.echo(f"Method: {summary['method_version']}")
        for key, label in [
            ("total_trials", "Total trials"),
            ("recruiting_trials", "Recruiting trials"),
            ("lead_sponsor_names", "Unique lead sponsor names"),
            ("industry_lead_sponsor_names", "Unique industry lead sponsor names"),
            (
                "drug_biologic_interventional_trials",
                "Drug/biologic interventional trial subset",
            ),
            ("listed_countries", "Countries with listed locations"),
        ]:
            click.echo(f"{label}: {summary['metrics'][key]['value']}")
        for key, title in [
            ("study_type", "Study types"),
            ("status", "Trial statuses"),
            (
                "phase",
                f"Phases (interventional trials only; denominator {summary['phase_denominator']})",
            ),
            ("sponsor", "Lead sponsors by trial count"),
            (
                "drug_intervention",
                "Drug/biologic intervention names by trial count (raw names)",
            ),
        ]:
            click.echo(f"\n{title}:")
            rows = summary["groups"][key]
            for row in rows[:top]:
                click.echo(f"  {row['label']}: {row['count']}")
            if not rows:
                click.echo("  No reported values")
            if len(rows) > top:
                click.echo(f"  Showing top {top} of {len(rows)} categories")
        click.echo(f"\nCoverage: {summary['coverage']}")
        click.echo(
            "Counts use frozen cohort evidence. Raw sponsor/drug names are not yet alias-normalized."
        )
