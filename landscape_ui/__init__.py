"""Landscape analysis pages and local saved-workspace routes."""

import csv
import io
import json
from math import ceil

from flask import Blueprint, Response, abort, render_template, request, url_for
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from intelligence_store.extensions import db
from intelligence_store.models import AnalysisCohort, CohortTrial, TrialSnapshot
from intelligence_store.summaries import CohortSummaryError, summarize_cohort
from intelligence_store.normalization import _mapping, _text
from intelligence_store.intervention_names import group_intervention_names, name_key
from intelligence_store.drug_aliases import reconcile_drug_aliases, load_alias_catalog
from intelligence_store.mechanisms import (
    summarize_annotations,
    FIELDS as ANNOTATION_FIELDS,
)
from intelligence_store.protocols import summarize_protocols, RULES
from intelligence_store.stopping import summarize_stopping, STOPPING_STATUSES
from intelligence_store.safety import summarize_safety
from intelligence_store.interactions import summarize_interactions
from intelligence_store.trial_criteria import summarize_criteria, COMPARISON_LABELS, DIMENSION_LABELS
from intelligence_store.pharmacokinetics import simulate_pk, pk_availability, PKValidationError, digest as pk_digest
from intelligence_store.site_feasibility import (
    summarize_locations, region_rows, location_metrics, facility_groups, calculate_patient_pool,
    empty_pool_inputs, POOL_FIELDS, FeasibilityError, name_key as geography_key,
    digest as feasibility_digest,
)
from intelligence_store.regulatory import summarize_regulatory, OVERSIGHT_FIELDS, REVIEW_LABELS, BOOL_STATES
from intelligence_store.patient_scenarios import (
    load_scenario_presets, summarize_scenario, validate_scenario, ScenarioValidationError, SCHEMA_VERSION, SEX_VALUES, DOSE_UNITS,
)

bp = Blueprint(
    "landscape",
    __name__,
    url_prefix="/landscape",
    template_folder="templates",
    static_folder="static",
)
PAGE_SIZE = 50
METRICS = [
    ("total_trials", "Trials", "Unique registered studies in this saved analysis."),
    ("recruiting_trials", "Recruiting", "Registry status reported as RECRUITING."),
    (
        "lead_sponsor_names",
        "Lead sponsor names",
        "Distinct reported names; collaborators are separate.",
    ),
    (
        "industry_lead_sponsor_names",
        "Industry sponsor names",
        "Reported lead names with at least one INDUSTRY-class record.",
    ),
    (
        "drug_biologic_interventional_trials",
        "Drug / biologic trials",
        "Interventional studies with at least one reported drug or biologic.",
    ),
    (
        "listed_countries",
        "Listed countries",
        "Distinct country names in reported trial locations.",
    ),
]
GROUP_TITLES = {
    "study_type": "Study types",
    "status": "Trial statuses",
    "phase": "Interventional phases",
    "sponsor": "Lead sponsors",
    "drug_intervention": "Drug / biologic intervention names",
    "country": "Listed countries",
    "intervention_name": "Intervention name groups",
    "drug_alias": "Drug alias groups",
    "mechanism": "Curated mechanism",
    "modality": "Curated modality",
    "target": "Curated target / family",
}
METRIC_NOTES = {key: note for key, _label, note in METRICS}
GROUP_NOTES = {
    "study_type": "One reported study-type group per trial, with missing values identified.",
    "status": "Registry status in the saved source record, not reconstructed historical status.",
    "phase": "Interventional trials only. Combined phases count once per trial.",
    "sponsor": "Exact lead sponsor names; collaborators and corporate aliases are not consolidated.",
    "drug_intervention": "Distinct trials per raw reported name. Aliases, comparators and combinations may appear separately.",
    "country": "Distinct trials with at least one listed location in this country; trials can appear in several countries.",
    "intervention_name": "Reported DRUG/BIOLOGICAL names grouped by capitalization and whitespace only. Each trial counts once per group; original labels remain available.",
    "drug_alias": "Exact source-backed brand/generic aliases, with unmatched formatting groups retained separately. Each trial counts once per group. Catalog naming references do not establish trial-specific approval or formulation.",
}
for field in ANNOTATION_FIELDS:
    GROUP_NOTES[field] = (
        "Reference annotations attached through exact source-backed name matches. Each trial counts once per category. No curated annotation means a coverage gap; interventions and comparators can overlap across categories."
    )


def _complete_cohorts():
    return list(
        db.session.scalars(
            select(AnalysisCohort)
            .where(AnalysisCohort.status == "COMPLETE")
            .order_by(AnalysisCohort.id.desc())
        )
    )


def _summary(cohort_id):
    try:
        summary = summarize_cohort(cohort_id)
        names = group_intervention_names(summary)
        summary["intervention_names"] = names
        summary["drug_aliases"] = reconcile_drug_aliases(summary)
        summary["groups"]["drug_alias"] = summary["drug_aliases"]["groups"]
        summary["groups"]["intervention_name"] = names["groups"]
        summary["metric_source_paths"] = {
            **summary["metric_source_paths"],
            "intervention_name": list(
                summary["metric_source_paths"]["drug_intervention"]
            ),
            "drug_alias": list(summary["metric_source_paths"]["drug_intervention"]),
        }
        summary["annotations"] = summarize_annotations(
            summary, aliases=summary["drug_aliases"]
        )
        for field in ANNOTATION_FIELDS:
            summary["groups"][field] = summary["annotations"]["groups"][field]
            summary["metric_source_paths"][field] = [
                *summary["metric_source_paths"]["drug_intervention"],
                "drug_annotations_v1.json.entries[].fields." + field + ".label",
            ]
        return summary
    except CohortSummaryError as exc:
        raise ValueError(str(exc)) from exc


def _pretty(value):
    return value.replace("_", " ").title() if value.isupper() else value


def _decorate_rows(summary, key):
    return [
        {
            **row,
            "display_label": (
                _pretty(row["label"])
                if key in ("study_type", "status")
                else row["label"]
            ),
            "evidence_url": url_for(
                "landscape.evidence",
                cohort_id=summary["cohort"]["id"],
                group=key,
                value=row.get("key", row["label"]),
            ),
        }
        for row in summary["groups"][key]
    ]


@bp.get("/")
def index():
    error = None
    summary = None
    cohorts = []
    charts = {}
    groups = {}
    cards = []
    status_code = 200
    condition = request.args.get("condition", "").strip()
    try:
        cohorts = _complete_cohorts()
        if "cohort_id" in request.args:
            cohort_id = request.args.get("cohort_id", type=int)
            if cohort_id is None or cohort_id < 1:
                abort(400, description="Choose a valid saved analysis ID.")
            selected = db.session.get(AnalysisCohort, cohort_id)
            if selected is None:
                abort(404)
        else:
            candidates = [
                c
                for c in cohorts
                if not condition or c.condition.casefold() == condition.casefold()
            ]
            # Prefer the agreed pharmaceutical scope, all years, when available.
            preferred = [
                c
                for c in candidates
                if c.scope == "drug-biologic"
                and c.start_year is None
                and c.end_year is None
            ]
            selected = (preferred or candidates or [None])[0]
        if selected is not None:
            summary = _summary(selected.id)
            groups = {key: _decorate_rows(summary, key) for key in summary["groups"]}
            for key, label, note in METRICS:
                cards.append(
                    {
                        "key": key,
                        "label": label,
                        "note": note,
                        "value": summary["metrics"][key]["value"],
                        "url": url_for(
                            "landscape.evidence", cohort_id=selected.id, metric=key
                        ),
                    }
                )
            charts = {
                key: [
                    {
                        "label": row["display_label"],
                        "count": row["count"],
                        "url": row["evidence_url"],
                    }
                    for row in groups[key]
                ]
                for key in ["study_type", "status", "phase"]
            }
    except ValueError as exc:
        error = str(exc)
        status_code = 409
    except SQLAlchemyError:
        db.session.rollback()
        error = "Saved analyses are temporarily unavailable."
        status_code = 503
    recruiting_percent = None
    if summary and summary["metrics"]["total_trials"]["value"]:
        recruiting_percent = round(
            100
            * summary["metrics"]["recruiting_trials"]["value"]
            / summary["metrics"]["total_trials"]["value"],
            1,
        )
    return (
        render_template(
            "landscape_overview.html",
            summary=summary,
            cohorts=cohorts,
            condition=condition,
            cards=cards,
            groups=groups,
            charts=charts,
            recruiting_percent=recruiting_percent,
            error=error,
            group_notes=GROUP_NOTES,
        ),
        status_code,
    )


@bp.get("/evidence")
def evidence():
    cohort_id = request.args.get("cohort_id", type=int)
    if cohort_id is None or cohort_id < 1:
        abort(400)
    try:
        summary = _summary(cohort_id)
        name_variants = []
        alias_entry = None
        alias_group = False
        annotation_entities = []
        annotation_dimension = None
        metric = request.args.get("metric")
        group = request.args.get("group")
        if bool(metric) == bool(group):
            abort(400, description="Choose one metric or one group.")
        if metric:
            if metric not in summary["metrics"]:
                abort(404)
            key = metric
            ids = summary["metrics"][key]["nct_ids"]
            title = next(label for name, label, _note in METRICS if name == key)
            note = METRIC_NOTES[key]
            aggregate_value = summary["metrics"][key]["value"]
        else:
            if group not in GROUP_TITLES:
                abort(404)
            value = request.args.get("value")
            row = next(
                (
                    r
                    for r in summary["groups"][group]
                    if r.get("key", r["label"]) == value
                ),
                None,
            )
            if row is None:
                abort(404)
            key = group
            ids = row["nct_ids"]
            label = (
                _pretty(row["label"])
                if group in ("study_type", "status")
                else row["label"]
            )
            title = f"{GROUP_TITLES[group]}: {label}"
            if group in ("intervention_name", "drug_alias"):
                alias_group = group == "drug_alias"
                alias_entry = row.get("catalog_entry")
                name_variants = [
                    {
                        **variant,
                        "evidence_url": url_for(
                            "landscape.evidence",
                            cohort_id=cohort_id,
                            group="drug_intervention",
                            value=variant["label"],
                        ),
                    }
                    for variant in row["variants"]
                ]
            if group in ANNOTATION_FIELDS:
                annotation_dimension = group
                annotation_entities = [
                    {
                        **entity,
                        "evidence_url": url_for(
                            "landscape.evidence",
                            cohort_id=cohort_id,
                            group="drug_alias",
                            value="catalog:" + entity["entity_id"],
                        ),
                    }
                    for entity in row["entities"]
                ]
            note = GROUP_NOTES[group]
            aggregate_value = row["count"]
        page = request.args.get("page", 1, type=int)
        page_count = max(1, ceil(len(ids) / PAGE_SIZE))
        if page is None or not 1 <= page <= page_count:
            abort(404)
        page_ids = ids[(page - 1) * PAGE_SIZE : page * PAGE_SIZE]
        snapshot_ids = [summary["evidence"][nct]["snapshot_id"] for nct in page_ids]
        snapshots = (
            {
                s.id: s
                for s in db.session.scalars(
                    select(TrialSnapshot).where(TrialSnapshot.id.in_(snapshot_ids))
                )
            }
            if snapshot_ids
            else {}
        )
        rows = []
        for nct in page_ids:
            ref = summary["evidence"][nct]
            raw = _mapping(snapshots[ref["snapshot_id"]].raw_study)
            identification = _mapping(
                _mapping(raw.get("protocolSection")).get("identificationModule")
            )
            rows.append(
                {
                    "nct_id": nct,
                    **ref,
                    "title": _text(identification.get("briefTitle"))
                    or "Title not reported",
                    "snapshot_url": url_for(
                        "landscape.snapshot",
                        snapshot_id=ref["snapshot_id"],
                        cohort_id=cohort_id,
                    ),
                    "registry_url": f"https://clinicaltrials.gov/study/{nct}",
                }
            )
        query = {"cohort_id": cohort_id}
        if metric:
            query["metric"] = metric
        else:
            query.update(group=group, value=value)
        previous_url = (
            url_for("landscape.evidence", **query, page=page - 1) if page > 1 else None
        )
        next_url = (
            url_for("landscape.evidence", **query, page=page + 1)
            if page < page_count
            else None
        )
        return render_template(
            "landscape_evidence.html",
            summary=summary,
            title=title,
            note=note,
            aggregate_value=aggregate_value,
            contributing_count=len(ids),
            rows=rows,
            page=page,
            page_count=page_count,
            previous_url=previous_url,
            next_url=next_url,
            source_paths=summary["metric_source_paths"][key],
            name_variants=name_variants,
            alias_entry=alias_entry,
            alias_group=alias_group,
            annotation_entities=annotation_entities,
            annotation_dimension=annotation_dimension,
        )
    except ValueError as exc:
        return render_template("landscape_message.html", message=str(exc)), 409
    except SQLAlchemyError:
        db.session.rollback()
        return (
            render_template(
                "landscape_message.html",
                message="Saved evidence is temporarily unavailable.",
            ),
            503,
        )


@bp.get("/mechanisms")
def mechanisms():
    cohort_id = request.args.get("cohort_id", type=int)
    if cohort_id is None or cohort_id < 1:
        abort(400)
    try:
        summary = _summary(cohort_id)
        groups = {field: _decorate_rows(summary, field) for field in ANNOTATION_FIELDS}
        charts = {
            field: [
                {"label": r["label"], "count": r["count"], "url": r["evidence_url"]}
                for r in rows
            ]
            for field, rows in groups.items()
        }
        return render_template(
            "landscape_mechanisms.html", summary=summary, groups=groups, charts=charts
        )
    except ValueError as exc:
        return render_template("landscape_message.html", message=str(exc)), 409
    except SQLAlchemyError:
        db.session.rollback()
        return (
            render_template(
                "landscape_message.html",
                message="Saved annotations are temporarily unavailable.",
            ),
            503,
        )


@bp.get("/aliases")
def aliases():
    cohort_id = request.args.get("cohort_id", type=int)
    if cohort_id is None or cohort_id < 1:
        abort(400)
    view = request.args.get("view", "all")
    if view not in ("all", "matched", "unmapped"):
        abort(400)
    try:
        summary = _summary(cohort_id)
        query = request.args.get("q", "").strip()
        search_key = name_key(query)
        groups = _decorate_rows(summary, "drug_alias")
        if view != "all":
            status = "source-backed" if view == "matched" else "unmapped"
            groups = [row for row in groups if row["mapping_status"] == status]
        if search_key:
            groups = [
                row
                for row in groups
                if search_key in name_key(row["label"])
                or any(search_key in name_key(v["label"]) for v in row["variants"])
            ]
        page = request.args.get("page", 1, type=int)
        page_count = max(1, ceil(len(groups) / PAGE_SIZE))
        if page is None or not 1 <= page <= page_count:
            abort(404)
        page_rows = groups[(page - 1) * PAGE_SIZE : page * PAGE_SIZE]
        for row in page_rows:
            row["variants"] = [
                {
                    **v,
                    "evidence_url": url_for(
                        "landscape.evidence",
                        cohort_id=cohort_id,
                        group="drug_intervention",
                        value=v["label"],
                    ),
                }
                for v in row["variants"]
            ]
        params = {"cohort_id": cohort_id, "q": query, "view": view}
        return render_template(
            "landscape_aliases.html",
            summary=summary,
            groups=page_rows,
            query=query,
            view=view,
            matching_count=len(groups),
            page=page,
            page_count=page_count,
            catalog={"entries": summary["drug_aliases"]["catalog_entries"]},
            previous_url=(
                url_for("landscape.aliases", **params, page=page - 1)
                if page > 1
                else None
            ),
            next_url=(
                url_for("landscape.aliases", **params, page=page + 1)
                if page < page_count
                else None
            ),
        )
    except ValueError as exc:
        return render_template("landscape_message.html", message=str(exc)), 409
    except SQLAlchemyError:
        db.session.rollback()
        return (
            render_template(
                "landscape_message.html",
                message="Saved aliases are temporarily unavailable.",
            ),
            503,
        )


@bp.get("/interventions")
def interventions():
    cohort_id = request.args.get("cohort_id", type=int)
    if cohort_id is None or cohort_id < 1:
        abort(400)
    try:
        summary = _summary(cohort_id)
        query = request.args.get("q", "").strip()
        search_key = name_key(query)
        groups = _decorate_rows(summary, "intervention_name")
        if search_key:
            groups = [row for row in groups if search_key in row["key"]]
        page = request.args.get("page", 1, type=int)
        page_count = max(1, ceil(len(groups) / PAGE_SIZE))
        if page is None or not 1 <= page <= page_count:
            abort(404)
        page_rows = groups[(page - 1) * PAGE_SIZE : page * PAGE_SIZE]
        for row in page_rows:
            row["variants"] = [
                {
                    **variant,
                    "evidence_url": url_for(
                        "landscape.evidence",
                        cohort_id=cohort_id,
                        group="drug_intervention",
                        value=variant["label"],
                    ),
                }
                for variant in row["variants"]
            ]
        params = {"cohort_id": cohort_id, "q": query}
        return render_template(
            "landscape_interventions.html",
            summary=summary,
            groups=page_rows,
            query=query,
            matching_count=len(groups),
            page=page,
            page_count=page_count,
            previous_url=(
                url_for("landscape.interventions", **params, page=page - 1)
                if page > 1
                else None
            ),
            next_url=(
                url_for("landscape.interventions", **params, page=page + 1)
                if page < page_count
                else None
            ),
        )
    except ValueError as exc:
        return render_template("landscape_message.html", message=str(exc)), 409
    except SQLAlchemyError:
        db.session.rollback()
        return (
            render_template(
                "landscape_message.html",
                message="Saved names are temporarily unavailable.",
            ),
            503,
        )


@bp.get("/snapshot/<int:snapshot_id>")
def snapshot(snapshot_id):
    cohort_id = request.args.get("cohort_id", type=int)
    if cohort_id is None or cohort_id < 1:
        abort(400)
    try:
        cohort = db.session.get(AnalysisCohort, cohort_id)
        if cohort is None:
            abort(404)
        if cohort.status != "COMPLETE":
            return (
                render_template(
                    "landscape_message.html", message="This analysis is incomplete."
                ),
                409,
            )
        row = db.session.execute(
            select(CohortTrial, TrialSnapshot)
            .join(TrialSnapshot, CohortTrial.snapshot_id == TrialSnapshot.id)
            .where(
                CohortTrial.cohort_id == cohort_id,
                CohortTrial.snapshot_id == snapshot_id,
            )
        ).first()
        if row is None:
            abort(404)
        membership, evidence_row = row
        raw_id = _mapping(
            _mapping(_mapping(evidence_row.raw_study).get("protocolSection")).get(
                "identificationModule"
            )
        ).get("nctId")
        if membership.nct_id != evidence_row.nct_id or raw_id != membership.nct_id:
            abort(409)
        return render_template(
            "landscape_snapshot.html",
            cohort=cohort,
            snapshot=evidence_row,
            raw_json=json.dumps(evidence_row.raw_study, indent=2, ensure_ascii=False),
        )
    except SQLAlchemyError:
        db.session.rollback()
        return (
            render_template(
                "landscape_message.html",
                message="Saved evidence is temporarily unavailable.",
            ),
            503,
        )


def _protocol_cohort_id():
    if "cohort_id" in request.args:
        cohort_id = request.args.get("cohort_id", type=int)
        if cohort_id is None or cohort_id < 1:
            abort(400, description="Choose a valid saved analysis ID.")
        if db.session.get(AnalysisCohort, cohort_id) is None:
            abort(404)
        return cohort_id
    cohorts = _complete_cohorts()
    preferred = [
        c
        for c in cohorts
        if c.scope == "drug-biologic" and c.start_year is None and c.end_year is None
    ]
    return (preferred or cohorts)[0].id if cohorts else None


@bp.get("/protocols")
def protocols():
    try:
        cohort_id = _protocol_cohort_id()
        cohorts = _complete_cohorts()
        if cohort_id is None:
            return render_template(
                "landscape_protocols.html", summary=None, cohorts=cohorts
            )
        report = summarize_protocols(cohort_id)
        query = request.args.get("q", "").strip()
        coverage = request.args.get("coverage", "all")
        if coverage not in ("all", "complete", "partial", "not_assessed"):
            abort(400)
        score = request.args.get("score", "")
        if score and score not in {str(i) for i in range(len(RULES) + 1)}:
            abort(400)
        indicator = request.args.get("indicator", "")
        state = request.args.get("state", "")
        if bool(indicator) != bool(state) or (
            indicator
            and (
                indicator not in {r["key"] for r in RULES}
                or state not in ("met", "not_met", "unknown")
            )
        ):
            abort(400)
        profiles = report["profiles"]
        if query:
            profiles = [
                p
                for p in profiles
                if query.casefold() in p["nct_id"].casefold()
                or query.casefold() in p["title"].casefold()
            ]
        if coverage != "all":
            profiles = [p for p in profiles if p["assessment_status"] == coverage]
        if score:
            profiles = [p for p in profiles if p["score"] == int(score)]
        if indicator:
            profiles = [
                p
                for p in profiles
                if any(
                    i["key"] == indicator and i["state"] == state
                    for i in p["indicators"]
                )
            ]
        page = request.args.get("page", 1, type=int)
        page_count = max(1, ceil(len(profiles) / PAGE_SIZE))
        if page is None or not 1 <= page <= page_count:
            abort(404)
        params = {
            "cohort_id": cohort_id,
            "q": query,
            "coverage": coverage,
            "score": score,
            "indicator": indicator,
            "state": state,
        }
        return render_template(
            "landscape_protocols.html",
            summary=report,
            cohorts=cohorts,
            profiles=profiles[(page - 1) * PAGE_SIZE : page * PAGE_SIZE],
            matching_count=len(profiles),
            query=query,
            coverage=coverage,
            score=score,
            indicator=indicator,
            state=state,
            page=page,
            page_count=page_count,
            filter_label=next((r["label"] for r in RULES if r["key"] == indicator), ""),
            previous_url=(
                url_for("landscape.protocols", **params, page=page - 1)
                if page > 1
                else None
            ),
            next_url=(
                url_for("landscape.protocols", **params, page=page + 1)
                if page < page_count
                else None
            ),
        )
    except CohortSummaryError as exc:
        return render_template("landscape_message.html", message=str(exc)), 409
    except SQLAlchemyError:
        db.session.rollback()
        return (
            render_template(
                "landscape_message.html",
                message="Saved protocols are temporarily unavailable.",
            ),
            503,
        )


@bp.get("/protocols/<nct_id>")
def protocol_profile_page(nct_id):
    cohort_id = request.args.get("cohort_id", type=int)
    if cohort_id is None or cohort_id < 1:
        abort(400)
    try:
        report = summarize_protocols(cohort_id)
        profile = next((p for p in report["profiles"] if p["nct_id"] == nct_id), None)
        if profile is None:
            abort(404)
        snapshot = db.session.get(TrialSnapshot, profile["evidence"]["snapshot_id"])
        protocol = _mapping(_mapping(snapshot.raw_study).get("protocolSection"))
        # Display source text escaped; omit contact details and results modules.
        arms = _mapping(protocol.get("armsInterventionsModule")).get("armGroups")
        outcomes = _mapping(protocol.get("outcomesModule"))
        locations = _mapping(protocol.get("contactsLocationsModule")).get("locations")

        def reported_rows(value):
            return (
                [r for r in value if isinstance(r, dict)]
                if isinstance(value, list)
                else []
            )

        return render_template(
            "landscape_protocol_profile.html",
            summary=report,
            profile=profile,
            arms=reported_rows(arms),
            primary=reported_rows(outcomes.get("primaryOutcomes")),
            secondary=reported_rows(outcomes.get("secondaryOutcomes")),
            eligibility_text=_text(
                _mapping(protocol.get("eligibilityModule")).get("eligibilityCriteria")
            ),
            locations=reported_rows(locations)[:100],
            snapshot_url=url_for(
                "landscape.snapshot", snapshot_id=snapshot.id, cohort_id=cohort_id
            ),
        )
    except CohortSummaryError as exc:
        return render_template("landscape_message.html", message=str(exc)), 409
    except SQLAlchemyError:
        db.session.rollback()
        return (
            render_template(
                "landscape_message.html",
                message="Saved protocol evidence is temporarily unavailable.",
            ),
            503,
        )


@bp.get("/stopped")
def stopped():
    try:
        cohort_id = _protocol_cohort_id()
        cohorts = _complete_cohorts()
        if cohort_id is None:
            return render_template(
                "landscape_stopped.html", summary=None, cohorts=cohorts
            )
        status = request.args.get("status", "TERMINATED")
        if status not in (*STOPPING_STATUSES, "ALL"):
            abort(400)
        report = summarize_stopping(cohort_id, status)
        view = request.args.get("view", "groups")
        presence = request.args.get("presence", "all")
        if view not in ("groups", "trials") or presence not in (
            "all",
            "reported",
            "unknown",
            "invalid",
        ):
            abort(400)
        group_key = request.args.get("reason_group", "")
        variant_key = request.args.get("variant", "")
        if view == "groups" and (group_key or variant_key or presence != "all"):
            abort(400)
        if variant_key and not group_key:
            abort(400)
        selected_group = None
        selected_variant = None
        if group_key:
            selected_group = next(
                (g for g in report["reasons"] if g["key"] == group_key), None
            )
            if selected_group is None:
                abort(404)
        if variant_key:
            selected_variant = next(
                (v for v in selected_group["variants"] if v["key"] == variant_key), None
            )
            if selected_variant is None:
                abort(404)
        query = request.args.get("q", "").strip()
        search = " ".join(query.split()).casefold()
        if view == "groups":
            rows = report["reasons"]
            if search:
                rows = [
                    g
                    for g in rows
                    if any(
                        search in " ".join(v["text"].split()).casefold()
                        for v in g["variants"]
                    )
                ]
        else:
            rows = report["records"]
            if selected_group:
                rows = [r for r in rows if r["reason_key"] == group_key]
            if selected_variant:
                rows = [r for r in rows if r["variant_key"] == variant_key]
            if presence != "all":
                rows = (
                    [r for r in rows if r["reason_coverage"] in ("missing", "invalid")]
                    if presence == "unknown"
                    else [r for r in rows if r["reason_coverage"] == presence]
                )
            if search:
                rows = [
                    r
                    for r in rows
                    if any(
                        search in " ".join((r.get(field) or "").split()).casefold()
                        for field in ("nct_id", "title", "reason")
                    )
                ]
        page = request.args.get("page", 1, type=int)
        page_count = max(1, ceil(len(rows) / PAGE_SIZE))
        if page is None or not 1 <= page <= page_count:
            abort(404)
        params = {
            "cohort_id": cohort_id,
            "status": status,
            "view": view,
            "presence": presence,
            "q": query,
            "reason_group": group_key,
            "variant": variant_key,
        }
        return render_template(
            "landscape_stopped.html",
            summary=report,
            cohorts=cohorts,
            status=status,
            view=view,
            presence=presence,
            query=query,
            selected_group=selected_group,
            selected_variant=selected_variant,
            rows=rows[(page - 1) * PAGE_SIZE : page * PAGE_SIZE],
            matching_count=len(rows),
            page=page,
            page_count=page_count,
            previous_url=(
                url_for("landscape.stopped", **params, page=page - 1)
                if page > 1
                else None
            ),
            next_url=(
                url_for("landscape.stopped", **params, page=page + 1)
                if page < page_count
                else None
            ),
        )
    except CohortSummaryError as exc:
        return render_template("landscape_message.html", message=str(exc)), 409
    except SQLAlchemyError:
        db.session.rollback()
        return (
            render_template(
                "landscape_message.html",
                message="Saved stopping evidence is temporarily unavailable.",
            ),
            503,
        )


def _safety_summary(cohort_id):
    summary = summarize_cohort(cohort_id)
    summary["drug_aliases"] = reconcile_drug_aliases(summary)
    summary["safety"] = summarize_safety(summary, aliases=summary["drug_aliases"])
    return summary


@bp.get("/safety")
def safety():
    try:
        cohort_id = _protocol_cohort_id()
        cohorts = _complete_cohorts()
        if cohort_id is None:
            return render_template(
                "landscape_safety.html", summary=None, cohorts=cohorts
            )
        summary = _safety_summary(cohort_id)
        return render_template(
            "landscape_safety.html", summary=summary, cohorts=cohorts
        )
    except ValueError as exc:
        return render_template("landscape_message.html", message=str(exc)), 409
    except SQLAlchemyError:
        db.session.rollback()
        return (
            render_template(
                "landscape_message.html",
                message="Saved safety references are temporarily unavailable.",
            ),
            503,
        )


@bp.get("/safety/evidence")
def safety_evidence():
    cohort_id = request.args.get("cohort_id", type=int)
    if cohort_id is None or cohort_id < 1:
        abort(400)
    try:
        summary = _safety_summary(cohort_id)
        report = summary["safety"]
        entity = request.args.get("entity")
        topic = request.args.get("topic")
        coverage = request.args.get("coverage")
        if sum(bool(value) for value in (entity, topic, coverage)) != 1:
            abort(400)
        entries = []
        selected_topic = None
        if entity:
            entry = next(
                (e for e in report["entries"] if e["entity_id"] == entity), None
            )
            if entry is None:
                abort(404)
            ids = entry["nct_ids"]
            title = "Label reference: " + entry["label"]
            entries = [entry]
            params = {"entity": entity}
        elif topic:
            row = next((r for r in report["topics"] if r["label"] == topic), None)
            if row is None:
                abort(404)
            ids = row["nct_ids"]
            title = "Selected label topic: " + topic
            source_ids = {e["entity_id"] for e in row["entries"]}
            entries = [e for e in report["entries"] if e["entity_id"] in source_ids]
            selected_topic = topic
            params = {"topic": topic}
        else:
            if coverage not in report["coverage"]:
                abort(404)
            ids = report["coverage"][coverage]["nct_ids"]
            title = {
                "referenced": "Trials containing at least one referenced name",
                "unreferenced": "Trials without a curated safety reference",
                "uncurated_names": "Trials containing at least one uncurated name",
                "no_named_drug_biologic": "Trials without a named drug / biologic entry",
            }[coverage]
            params = {"coverage": coverage}
        page = request.args.get("page", 1, type=int)
        page_count = max(1, ceil(len(ids) / PAGE_SIZE))
        if page is None or not 1 <= page <= page_count:
            abort(404)
        page_ids = ids[(page - 1) * PAGE_SIZE : page * PAGE_SIZE]
        refs = summary["evidence"]
        snapshots = (
            {
                s.id: s
                for s in db.session.scalars(
                    select(TrialSnapshot).where(
                        TrialSnapshot.id.in_(
                            [refs[nct]["snapshot_id"] for nct in page_ids]
                        )
                    )
                )
            }
            if page_ids
            else {}
        )
        rows = []
        for nct_id in page_ids:
            snapshot = snapshots[refs[nct_id]["snapshot_id"]]
            protocol = _mapping(_mapping(snapshot.raw_study).get("protocolSection"))
            raw_interventions = _mapping(protocol.get("armsInterventionsModule")).get(
                "interventions"
            )
            names = (
                sorted(
                    {
                        name
                        for intervention in raw_interventions
                        if isinstance(intervention, dict)
                        and _text(intervention.get("type")) in ("DRUG", "BIOLOGICAL")
                        and (name := _text(intervention.get("name")))
                    }
                )
                if isinstance(raw_interventions, list)
                else []
            )
            rows.append(
                {
                    "nct_id": nct_id,
                    "title": _text(
                        _mapping(protocol.get("identificationModule")).get("briefTitle")
                    )
                    or "Title not reported",
                    "names": names,
                    "evidence": refs[nct_id],
                    "snapshot_url": url_for(
                        "landscape.snapshot",
                        snapshot_id=snapshot.id,
                        cohort_id=cohort_id,
                    ),
                }
            )
        params["cohort_id"] = cohort_id
        return render_template(
            "landscape_safety_evidence.html",
            summary=summary,
            title=title,
            entries=entries,
            selected_topic=selected_topic,
            coverage=coverage,
            rows=rows,
            contributing_count=len(ids),
            page=page,
            page_count=page_count,
            previous_url=(
                url_for("landscape.safety_evidence", **params, page=page - 1)
                if page > 1
                else None
            ),
            next_url=(
                url_for("landscape.safety_evidence", **params, page=page + 1)
                if page < page_count
                else None
            ),
        )
    except ValueError as exc:
        return render_template("landscape_message.html", message=str(exc)), 409
    except SQLAlchemyError:
        db.session.rollback()
        return (
            render_template(
                "landscape_message.html",
                message="Saved safety evidence is temporarily unavailable.",
            ),
            503,
        )


def _interaction_summary(cohort_id):
    summary = summarize_cohort(cohort_id)
    summary["drug_aliases"] = reconcile_drug_aliases(summary)
    summary["interactions"] = summarize_interactions(summary, aliases=summary["drug_aliases"])
    return summary


@bp.get("/interactions")
def interactions():
    try:
        cohort_id = _protocol_cohort_id()
        summary = _interaction_summary(cohort_id) if cohort_id is not None else None
        return render_template("landscape_interactions.html", summary=summary, cohorts=_complete_cohorts())
    except ValueError as exc:
        return render_template("landscape_message.html", message=str(exc)), 409
    except SQLAlchemyError:
        db.session.rollback()
        return render_template("landscape_message.html", message="Saved interaction references are temporarily unavailable."), 503


@bp.get("/interactions/evidence")
def interaction_evidence():
    cohort_id = request.args.get("cohort_id", type=int)
    if cohort_id is None or cohort_id < 1:
        abort(400)
    try:
        summary = _interaction_summary(cohort_id)
        report = summary["interactions"]
        rule_id, entity, coverage = (request.args.get(k) for k in ("rule", "entity", "coverage"))
        if sum(bool(v) for v in (rule_id, entity, coverage)) != 1:
            abort(400)
        selected_rule, selected_entry = None, None
        if rule_id:
            selected_rule = next((r for r in report["pairs"] + report["contexts"] if r["id"] == rule_id), None)
            if selected_rule is None:
                abort(404)
            if selected_rule["kind"] == "drug_pair":
                ids = selected_rule["pair_nct_ids"]
                title = selected_rule["anchor_label"] + " + " + selected_rule["partner_name"]
            else:
                ids = selected_rule["anchor_nct_ids"]
                title = selected_rule["title"]
            params = {"rule": rule_id}
        elif entity:
            selected_entry = next((e for e in report["entries"] if e["entity_id"] == entity), None)
            if selected_entry is None:
                abort(404)
            ids = selected_entry["anchor_nct_ids"]
            title = "Reference-name evidence: " + selected_entry["label"]
            params = {"entity": entity}
        else:
            if coverage not in report["coverage"]:
                abort(404)
            ids = report["coverage"][coverage]["nct_ids"]
            title = {
                "referenced_names": "Studies with at least one reference name",
                "no_reference_name": "Studies without a reference-name match",
                "selected_pairs": "Studies containing at least one selected name pair",
                "no_selected_pair": "Studies without a selected name-pair match",
            }[coverage]
            params = {"coverage": coverage}
        page = request.args.get("page", 1, type=int)
        page_count = max(1, ceil(len(ids) / PAGE_SIZE))
        if page is None or not 1 <= page <= page_count:
            abort(404)
        page_ids = ids[(page - 1) * PAGE_SIZE:page * PAGE_SIZE]
        refs = summary["evidence"]
        snapshots = {s.id: s for s in db.session.scalars(
            select(TrialSnapshot).where(TrialSnapshot.id.in_([refs[nct]["snapshot_id"] for nct in page_ids]))
        )} if page_ids else {}
        rows = []
        for nct in page_ids:
            snapshot = snapshots[refs[nct]["snapshot_id"]]
            protocol = _mapping(_mapping(snapshot.raw_study).get("protocolSection"))
            raw = _mapping(protocol.get("armsInterventionsModule")).get("interventions")
            names = sorted({name for item in raw if isinstance(item, dict)
                and _text(item.get("type")) in ("DRUG", "BIOLOGICAL")
                and (name := _text(item.get("name")))}) if isinstance(raw, list) else []
            rows.append({
                "nct_id": nct, "title": _text(_mapping(protocol.get("identificationModule")).get("briefTitle")) or "Title not reported",
                "names": names, "evidence": refs[nct],
                "snapshot_url": url_for("landscape.snapshot", snapshot_id=snapshot.id, cohort_id=cohort_id),
            })
        params["cohort_id"] = cohort_id
        return render_template("landscape_interaction_evidence.html", summary=summary, title=title,
            selected_rule=selected_rule, selected_entry=selected_entry, coverage=coverage, rows=rows,
            contributing_count=len(ids), page=page, page_count=page_count,
            previous_url=url_for("landscape.interaction_evidence", **params, page=page-1) if page > 1 else None,
            next_url=url_for("landscape.interaction_evidence", **params, page=page+1) if page < page_count else None)
    except ValueError as exc:
        return render_template("landscape_message.html", message=str(exc)), 409
    except SQLAlchemyError:
        db.session.rollback()
        return render_template("landscape_message.html", message="Saved name-pair evidence is temporarily unavailable."), 503


def _scenario_form_profile():
    if request.form.get("profile_json"):
        return json.loads(request.form["profile_json"])
    dose = request.form.get("dose_value", "").strip()
    return {
        "schema_version": SCHEMA_VERSION, "purpose": request.form.get("purpose"),
        "age_years": request.form.get("age_years", "").strip(),
        "biological_sex": request.form.get("biological_sex"),
        "weight_kg": request.form.get("weight_kg", "").strip(),
        "egfr_ml_min_1_73m2": request.form.get("egfr_ml_min_1_73m2", "").strip(),
        "selected_drug": request.form.get("selected_drug"), "dose_value": dose,
        "dose_unit": request.form.get("dose_unit") if dose else None,
        "indication": request.form.get("indication", ""),
        "medications": [line.strip() for line in request.form.get("medications", "").splitlines() if line.strip()],
    }


@bp.route("/patient-lab", methods=["GET", "POST"])
def patient_lab():
    """Transient preview/download; explicit persistence uses separate Workspace routes."""
    if request.content_length is not None and request.content_length > 32768:
        abort(413)
    try:
        alias_catalog = load_alias_catalog()
        presets = load_scenario_presets(alias_catalog=alias_catalog)
        cohorts = _complete_cohorts()
        preset_id = request.args.get("preset", "interaction-reference")
        if preset_id not in presets["index"]:
            abort(404)
        form_profile = dict(presets["index"][preset_id]["profile"])
        report, error, summary = None, None, None
        if request.method == "POST":
            cohort_id = request.form.get("cohort_id", type=int)
            if cohort_id is None or cohort_id < 1:
                abort(400)
            action = request.form.get("action", "preview")
            if action not in ("preview", "download"):
                abort(400)
            form_profile = _scenario_form_profile()
            summary = summarize_cohort(cohort_id)
            try:
                report = summarize_scenario(summary, form_profile)
                form_profile = report["profile"]
            except ScenarioValidationError as exc:
                error = str(exc)
            if report and action == "download":
                payload = json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False)
                response = Response(payload, mimetype="application/json")
                response.headers["Content-Disposition"] = f'attachment; filename="synthetic_scenario_cohort_{cohort_id}.json"'
            else:
                response = Response(render_template("landscape_patient_lab.html", summary=summary,
                    cohorts=cohorts, presets=presets["presets"], preset_id=preset_id,
                    profile=form_profile, report=report, error=error,
                    drugs=alias_catalog["entries"], sexes=SEX_VALUES, dose_units=DOSE_UNITS),
                    status=400 if error else 200)
        else:
            cohort_id = _protocol_cohort_id()
            summary = summarize_cohort(cohort_id) if cohort_id is not None else None
            response = Response(render_template("landscape_patient_lab.html", summary=summary,
                cohorts=cohorts, presets=presets["presets"], preset_id=preset_id,
                profile=form_profile, report=None, error=None,
                drugs=alias_catalog["entries"], sexes=SEX_VALUES, dose_units=DOSE_UNITS))
        response.headers["Cache-Control"] = "no-store"
        return response
    except ValueError as exc:
        response = Response(render_template("landscape_message.html", message=str(exc)), status=409)
        response.headers["Cache-Control"] = "no-store"
        return response
    except SQLAlchemyError:
        db.session.rollback()
        response = Response(render_template("landscape_message.html", message="Saved scenario evidence is temporarily unavailable."), status=503)
        response.headers["Cache-Control"] = "no-store"
        return response


@bp.post("/patient-lab/criteria")
def patient_criteria():
    if request.content_length is not None and request.content_length > 32768:
        abort(413)
    cohort_id = request.form.get("cohort_id", type=int)
    if cohort_id is None or cohort_id < 1:
        abort(400)
    dimension = request.form.get("dimension", "combined")
    result_key = request.form.get("result", "all")
    if dimension not in ("combined", "age", "sex") or result_key not in ("all", "within", "outside", "unresolved"):
        abort(400)
    page = request.form.get("page", 1, type=int)
    try:
        summary = summarize_cohort(cohort_id)
        profile = validate_scenario(_scenario_form_profile())
        report = summarize_criteria(summary, profile)
        rows = [r for r in report["records"] if result_key == "all" or r[dimension + "_result"] == result_key]
        page_count = max(1, ceil(len(rows) / PAGE_SIZE))
        if page is None or not 1 <= page <= page_count:
            abort(404)
        selected_rows = rows[(page - 1) * PAGE_SIZE:page * PAGE_SIZE]
        response = Response(render_template("landscape_patient_criteria.html", summary=summary,
            profile=profile, report=report, rows=selected_rows, filtered_count=len(rows),
            dimension=dimension, result_key=result_key, page=page, page_count=page_count,
            combined_labels=COMPARISON_LABELS, dimension_labels=DIMENSION_LABELS))
        response.headers["Cache-Control"] = "no-store"
        return response
    except ValueError as exc:
        response = Response(render_template("landscape_message.html", message=str(exc)), status=400 if isinstance(exc, ScenarioValidationError) else 409)
        response.headers["Cache-Control"] = "no-store"
        return response
    except SQLAlchemyError:
        db.session.rollback()
        response = Response(render_template("landscape_message.html", message="Retained criteria evidence is temporarily unavailable."), status=503)
        response.headers["Cache-Control"] = "no-store"
        return response


@bp.post("/patient-lab/pk")
def patient_pk():
    """Explicit single-dose teaching model, independent of cohort fitting."""
    if request.content_length is not None and request.content_length > 32768:
        abort(413)
    cohort_id = request.form.get("cohort_id", type=int)
    action = request.form.get("action", "preview")
    if cohort_id is None or cohort_id < 1 or action not in ("preview", "json", "csv"):
        abort(400)
    try:
        summary = summarize_cohort(cohort_id)
        profile = validate_scenario(_scenario_form_profile())
        pk, error = None, None
        try:
            available = pk_availability(profile)
            if not available["ready"]:
                raise PKValidationError(available["message"])
            pk = simulate_pk(profile["selected_drug"], profile["dose_value"],
                request.form.get("clearance_scale", "1"))
        except PKValidationError as exc:
            error = str(exc)
        if pk and action == "json":
            envelope = {"schema_version": "synthetic-pk-export-v1", "purpose": "synthetic_educational",
                "profile": profile, "cohort_context": summary["cohort"], "pk": pk,
                "context_note": "Profile and cohort are navigation context only. Only drug and invented mg dose enter the fixed PK model; clearance_scale is an explicit independent what-if."}
            envelope["export_sha256"] = pk_digest(envelope)
            response = Response(json.dumps(envelope, indent=2, ensure_ascii=False, allow_nan=False), mimetype="application/json")
            response.headers["Content-Disposition"] = 'attachment; filename="lenalidomide_pk_teaching_model.json"'
        elif pk and action == "csv":
            output = io.StringIO(newline="")
            writer = csv.writer(output)
            writer.writerow(["time_h", "reference_ng_ml", "comparison_ng_ml", "invented_dose_mg",
                "hypothetical_clearance_scale", "method_version", "catalog_version", "catalog_sha256", "pk_report_sha256"])
            for row in pk["points"]:
                writer.writerow([row["time_h"], row["reference_ng_ml"], row["comparison_ng_ml"],
                    pk["inputs"]["dose_mg"], pk["inputs"]["clearance_scale"], pk["method_version"],
                    pk["catalog_version"], pk["catalog_sha256"], pk["report_sha256"]])
            response = Response(output.getvalue(), mimetype="text/csv")
            response.headers["Content-Disposition"] = 'attachment; filename="lenalidomide_pk_simulated_curve.csv"'
        else:
            response = Response(render_template("landscape_patient_pk.html", summary=summary,
                profile=profile, pk=pk, error=error,
                scale_options=[(0.5, "0.5× reference clearance"), (1.0, "1× reference clearance (same curve)"),
                    (2.0, "2× reference clearance")],
                metric_rows=[("cmax_ng_ml", "Peak concentration (Cmax)", "ng/mL", 2),
                    ("tmax_h", "Time to peak (Tmax)", "hours", 3),
                    ("half_life_h", "Elimination half-life", "hours", 3),
                    ("auc_0_48_ng_h_ml", "AUC 0–48 hours", "ng·h/mL", 2),
                    ("auc_0_infinity_ng_h_ml", "AUC 0–infinity", "ng·h/mL", 2),
                    ("c24_ng_ml", "Concentration at 24 hours", "ng/mL", 4),
                    ("clearance_l_h", "Apparent clearance (CL/F)", "L/h", 2)],
                parameter_rows=[("apparent_clearance_ml_min", "CL/F"), ("apparent_volume_l", "V/F"),
                    ("absorption_rate_h", "Absorption rate ka"), ("lag_h", "Absorption delay")],
                sample_rows=[row for row in pk["points"] if row["time_h"] in (0, 0.5, 1, 2, 4, 8, 12, 24, 36, 48)] if pk else []),
                status=400 if error else 200)
        response.headers["Cache-Control"] = "no-store"
        return response
    except ValueError as exc:
        response = Response(render_template("landscape_message.html", message=str(exc)),
            status=400 if isinstance(exc, ScenarioValidationError) else 409)
        response.headers["Cache-Control"] = "no-store"
        return response
    except SQLAlchemyError:
        db.session.rollback()
        response = Response(render_template("landscape_message.html", message="Saved analysis context is temporarily unavailable."), status=503)
        response.headers["Cache-Control"] = "no-store"
        return response


def _site_region_context(report, country, state):
    rows = region_rows(report, country, state)
    country_options = sorted({r["label"] for r in report["countries"] if r["key"]} | {"United States", country})
    state_options = sorted({r["state"] for r in region_rows(report, country) if r["state"]} | ({state} if state else set()))
    return rows, country_options, state_options


@bp.route("/sites", methods=["GET", "POST"])
def sites():
    if request.content_length is not None and request.content_length > 32768:
        abort(413)
    try:
        cohorts = _complete_cohorts()
        cohort_id = request.form.get("cohort_id", type=int) if request.method == "POST" else _protocol_cohort_id()
        if request.method == "POST" and (cohort_id is None or cohort_id < 1):
            abort(400)
        summary = summarize_cohort(cohort_id) if cohort_id is not None else None
        report = summarize_locations(summary) if summary else None
        if not summary:
            return render_template("landscape_sites.html", summary=None, cohorts=cohorts)
        country = (request.form if request.method == "POST" else request.args).get("country", "United States")
        state = (request.form if request.method == "POST" else request.args).get("state", "")
        if not isinstance(country, str) or not country.strip() or len(country) > 160 or len(state) > 160:
            abort(400)
        country, state = " ".join(country.split()), " ".join(state.split())
        rows, country_options, state_options = _site_region_context(report, country, state)
        inputs = empty_pool_inputs(country, state)
        if geography_key(summary["cohort"]["condition"]) not in ("myeloma", "multiple myeloma") or geography_key(country) != "united states" or state:
            inputs["mode"] = "synthetic_crude_prevalence"
        action = "preview"
        if request.method == "POST":
            action = request.form.get("action", "preview")
            if action not in ("preview", "json"):
                abort(400)
            inputs = {key: request.form.get(key, "") for key in POOL_FIELDS}
            inputs.update(country=country, state=state)
        pool, error = None, None
        try:
            pool = calculate_patient_pool(summary["cohort"]["condition"], inputs)
            inputs = pool["inputs"]
        except FeasibilityError as exc:
            error = str(exc)
        if pool and action == "json":
            envelope = {"schema_version": "site-feasibility-export-v1", "cohort": summary["cohort"],
                "patient_pool": pool, "region_location_metrics": location_metrics(rows),
                "region_location_records": rows, "location_method_version": report["method_version"],
                "location_report_sha256": report["report_sha256"],
                "separation_note": "Location records are frozen descriptive evidence. They do not estimate disease prevalence or the eligibility/access shares."}
            envelope["export_sha256"] = feasibility_digest(envelope)
            response = Response(json.dumps(envelope, indent=2, ensure_ascii=False, allow_nan=False), mimetype="application/json")
            response.headers["Content-Disposition"] = f'attachment; filename="site_feasibility_cohort_{cohort_id}.json"'
        else:
            groups = facility_groups(rows)
            response = Response(render_template("landscape_sites.html", summary=summary, report=report,
                cohorts=cohorts, country=country, state=state, country_options=country_options,
                state_options=state_options, region_metrics=location_metrics(rows),
                facilities=groups[:20], facility_count=len(groups), inputs=inputs, pool=pool, error=error),
                status=400 if error and request.method == "POST" else 200)
        response.headers["Cache-Control"] = "no-store"
        return response
    except ValueError as exc:
        response = Response(render_template("landscape_message.html", message=str(exc)), status=409)
        response.headers["Cache-Control"] = "no-store"
        return response
    except SQLAlchemyError:
        db.session.rollback()
        return Response(render_template("landscape_message.html", message="Saved location evidence is temporarily unavailable."), status=503, headers={"Cache-Control": "no-store"})


@bp.get("/sites/evidence")
def site_evidence():
    try:
        cohort_id = _protocol_cohort_id()
        if cohort_id is None:
            abort(400)
        summary = summarize_cohort(cohort_id)
        report = summarize_locations(summary)
        country, state = request.args.get("country"), request.args.get("state", "")
        coverage = request.args.get("coverage")
        status = request.args.get("location_status", "all")
        facility = request.args.get("facility")
        if status not in ("all", "RECRUITING", "unknown") or (coverage and coverage not in ("no_country", "no_locations")):
            abort(400)
        if coverage and (country is not None or state or facility or status != "all"):
            abort(400)
        if state and country is None:
            abort(400)
        rows = report["rows"] if country is None else region_rows(report, country, state)
        if facility:
            rows = [r for r in rows if r["facility_key"] == facility]
        if status != "all":
            rows = [r for r in rows if r["location_status"] == (None if status == "unknown" else status)]
        if coverage:
            rows = [t for t in report["trials"] if (not t["has_country"] if coverage == "no_country" else t["location_count"] == 0)]
        page = request.args.get("page", 1, type=int)
        page_count = max(1, ceil(len(rows) / PAGE_SIZE))
        if page is None or not 1 <= page <= page_count:
            abort(404)
        query = {"cohort_id": cohort_id, "country": country, "state": state or None,
            "coverage": coverage, "location_status": status, "facility": facility}
        response = Response(render_template("landscape_site_evidence.html", summary=summary, report=report,
            rows=rows[(page - 1)*PAGE_SIZE:page*PAGE_SIZE], total_records=len(rows),
            unique_trials=len({r["nct_id"] for r in rows}), coverage=coverage, country=country,
            state=state, location_status=status, facility=facility,
            page=page, page_count=page_count, previous_url=url_for("landscape.site_evidence", **query, page=page-1) if page>1 else None,
            next_url=url_for("landscape.site_evidence", **query, page=page+1) if page<page_count else None))
        response.headers["Cache-Control"] = "no-store"
        return response
    except ValueError as exc:
        return Response(render_template("landscape_message.html", message=str(exc)), status=409, headers={"Cache-Control": "no-store"})
    except SQLAlchemyError:
        db.session.rollback()
        return Response(render_template("landscape_message.html", message="Saved location evidence is temporarily unavailable."), status=503, headers={"Cache-Control": "no-store"})


def _regulatory_report():
    cohort_id = _protocol_cohort_id()
    summary = summarize_cohort(cohort_id) if cohort_id is not None else None
    return summary, summarize_regulatory(summary) if summary else None


@bp.get("/regulatory")
def regulatory():
    output_format = request.args.get("format", "html")
    if output_format not in ("html", "json"):
        abort(400)
    try:
        summary, report = _regulatory_report()
        if output_format == "json":
            if not report:
                abort(404)
            response = Response(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False), mimetype="application/json")
            response.headers["Content-Disposition"] = f'attachment; filename="regulatory_cohort_{summary["cohort"]["id"]}.json"'
        else:
            response = Response(render_template("landscape_regulatory.html", summary=summary, report=report,
                cohorts=_complete_cohorts(), bool_states=BOOL_STATES))
        response.headers["Cache-Control"] = "no-store"
        return response
    except ValueError as exc:
        return Response(render_template("landscape_message.html", message=str(exc)), status=409, headers={"Cache-Control": "no-store"})
    except SQLAlchemyError:
        db.session.rollback()
        return Response(render_template("landscape_message.html", message="Saved regulatory evidence is temporarily unavailable."), status=503, headers={"Cache-Control": "no-store"})


@bp.get("/regulatory/evidence")
def regulatory_evidence():
    kind, value, field = request.args.get("kind", "all"), request.args.get("value"), request.args.get("field")
    labels = {"all": "All retained regulatory records", "results": "Results evidence",
        "oversight": "Reported oversight field", "review": "Human-review signal", "metric": "Regulatory source signal"}
    if kind not in labels:
        abort(400)
    try:
        summary, report = _regulatory_report()
        if report is None:
            abort(400)
        if kind == "oversight":
            if field not in OVERSIGHT_FIELDS or value not in BOOL_STATES:
                abort(400)
            group = report["oversight"][field]["groups"][value]
            label = f"{OVERSIGHT_FIELDS[field]} · {value.title()}"
        elif kind in ("results", "review", "metric"):
            mapping = report[{"results": "results_groups", "review": "review_groups", "metric": "metrics"}[kind]]
            if value not in mapping:
                abort(400)
            group = mapping[value]
            label = group.get("label", value.replace("_", " ").title())
        else:
            if value is not None or field is not None:
                abort(400)
            group = {"nct_ids": [r["nct_id"] for r in report["records"]]}
            label = labels[kind]
        ids = set(group["nct_ids"])
        rows = [r for r in report["records"] if r["nct_id"] in ids]
        page, page_count = request.args.get("page", 1, type=int), max(1, ceil(len(rows)/PAGE_SIZE))
        if page is None or not 1 <= page <= page_count:
            abort(404)
        query = {"cohort_id": summary["cohort"]["id"], "kind": kind, "value": value, "field": field}
        response = Response(render_template("landscape_regulatory_evidence.html", summary=summary, report=report,
            rows=rows[(page-1)*PAGE_SIZE:page*PAGE_SIZE], count=len(rows), label=label,
            page=page, page_count=page_count, review_labels=REVIEW_LABELS,
            previous_url=url_for("landscape.regulatory_evidence", **query, page=page-1) if page>1 else None,
            next_url=url_for("landscape.regulatory_evidence", **query, page=page+1) if page<page_count else None))
        response.headers["Cache-Control"] = "no-store"
        return response
    except ValueError as exc:
        return Response(render_template("landscape_message.html", message=str(exc)), status=409, headers={"Cache-Control": "no-store"})
    except SQLAlchemyError:
        db.session.rollback()
        return Response(render_template("landscape_message.html", message="Saved regulatory evidence is temporarily unavailable."), status=503, headers={"Cache-Control": "no-store"})


@bp.get("/regulatory/trial/<nct_id>")
def regulatory_profile(nct_id):
    try:
        summary, report = _regulatory_report()
        if not report:
            abort(400)
        row = next((r for r in report["records"] if r["nct_id"] == nct_id), None)
        if row is None:
            abort(404)
        response = Response(render_template("landscape_regulatory_profile.html", summary=summary,
            report=report, row=row, review_labels=REVIEW_LABELS))
        response.headers["Cache-Control"] = "no-store"
        return response
    except ValueError as exc:
        return Response(render_template("landscape_message.html", message=str(exc)), status=409, headers={"Cache-Control": "no-store"})
    except SQLAlchemyError:
        db.session.rollback()
        return Response(render_template("landscape_message.html", message="Saved regulatory evidence is temporarily unavailable."), status=503, headers={"Cache-Control": "no-store"})


from .workspace_pages import register_workspace_pages
register_workspace_pages(bp)
from .watchlist_pages import register_watchlist_pages
register_watchlist_pages(bp)
from .scenario_pages import register_saved_scenario_pages
register_saved_scenario_pages(bp, _scenario_form_profile)
from .validation_pages import register_validation_pages
register_validation_pages(bp)
from .drug_knowledge_pages import register_drug_knowledge_pages
register_drug_knowledge_pages(bp, _protocol_cohort_id, _complete_cohorts)


from .patient_state_pages import register_patient_state_pages
register_patient_state_pages(bp)

from .patient_state_compare_pages import register_patient_state_compare_pages
register_patient_state_compare_pages(bp)

from .transit_pages import register_transit_pages
register_transit_pages(bp)

from .transit_regimen_pages import register_transit_regimen_pages
register_transit_regimen_pages(bp)

from .educational_pk_pages import register_educational_pk_pages
register_educational_pk_pages(bp)

from .educational_pk_run_pages import register_educational_pk_run_pages
register_educational_pk_run_pages(bp)
from .kim_pk_run_pages import register_kim_pk_run_pages
register_kim_pk_run_pages(bp)
from .patient_platelet_pages import register_patient_platelet_pages
register_patient_platelet_pages(bp)

from .educational_pk_compare_pages import register_educational_pk_compare_pages
register_educational_pk_compare_pages(bp)

from .educational_pk_audit_pages import register_educational_pk_audit_pages
register_educational_pk_audit_pages(bp)

from .educational_pk_metrics_pages import register_educational_pk_metrics_pages
register_educational_pk_metrics_pages(bp)

from .patient_lab_overview_pages import register_patient_lab_overview_pages
register_patient_lab_overview_pages(bp)

from .educational_pk_sensitivity_pages import register_educational_pk_sensitivity_pages
register_educational_pk_sensitivity_pages(bp)

from .target_occupancy_pages import register_target_occupancy_pages
register_target_occupancy_pages(bp)

from .binding_kinetics_pages import register_binding_kinetics_pages
register_binding_kinetics_pages(bp)

from .binding_pulse_pages import register_binding_pulse_pages
register_binding_pulse_pages(bp)

from .mechanism_map_pages import register_mechanism_map_pages
register_mechanism_map_pages(bp)

def register_landscape(app):
    app.register_blueprint(bp)
