"""Paginated cohort retrieval with per-run evidence and completeness checks."""

import hashlib
import json

import click
import requests
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from .extensions import db
from .models import AnalysisCohort, CohortTrial, utc_now
from .normalization import NORMALIZATION_VERSION, upsert_trial_from_snapshot
from .snapshots import make_trial_snapshot

API_URL = "https://clinicaltrials.gov/api/v2/studies"
QUERY_VERSION = "cohort-query-v1.0"
SCOPES = ("drug-biologic", "all-interventional", "all-studies")


def build_cohort_query(
    condition, scope="drug-biologic", start_year=None, end_year=None, page_size=100
):
    condition = condition.strip()
    if not condition or scope not in SCOPES:
        raise ValueError("Provide a condition and a supported scope.")
    if type(page_size) is not int or not 1 <= page_size <= 1000:
        raise ValueError("Page size must be between 1 and 1000.")
    if (start_year is None) != (end_year is None):
        raise ValueError("Provide both --start-year and --end-year, or neither.")
    if start_year is not None and (
        type(start_year) is not int
        or type(end_year) is not int
        or not 1900 <= start_year <= end_year <= 2100
    ):
        raise ValueError(
            "Use a valid inclusive start-year range between 1900 and 2100."
        )
    terms = []
    if scope != "all-studies":
        terms.append("AREA[StudyType]INTERVENTIONAL")
    if scope == "drug-biologic":
        terms.append("(AREA[InterventionType]DRUG OR AREA[InterventionType]BIOLOGICAL)")
    if start_year is not None:
        terms.append(f"AREA[StartDate]RANGE[{start_year}-01-01,{end_year}-12-31]")
    params = {
        "query.cond": condition,
        "pageSize": page_size,
        "countTotal": "true",
        "format": "json",
    }
    if terms:
        params["query.term"] = " AND ".join(terms)
    return params


def _finish(cohort_id, status, reason=None):
    cohort = db.session.get(AnalysisCohort, cohort_id)
    cohort.status = status
    cohort.failure_reason = reason
    cohort.finished_at_utc = utc_now()
    db.session.commit()


def _count(value):
    return value if type(value) is int and value >= 0 else None


def fetch_cohort(
    condition,
    scope="drug-biologic",
    start_year=None,
    end_year=None,
    page_size=100,
    max_pages=100,
    client=None,
    progress=None,
):
    """Commit complete pages and retain partial runs if later retrieval fails.

    COMPLETE means pagination ended and observed unique count matches the
    initial API count, with no detected record/count anomalies. It does not
    imply a fixed registry-wide point-in-time snapshot across all HTTP requests.
    """
    params = build_cohort_query(condition, scope, start_year, end_year, page_size)
    if type(max_pages) is not int or max_pages < 1:
        raise ValueError("Maximum pages must be a positive integer.")
    cohort = AnalysisCohort(
        condition=condition.strip(),
        api_url=API_URL,
        query_params=params,
        query_version=QUERY_VERSION,
        normalization_version=NORMALIZATION_VERSION,
        scope=scope,
        max_pages=max_pages,
        start_year=start_year,
        end_year=end_year,
    )
    db.session.add(cohort)
    db.session.commit()
    cohort_id = cohort.id
    seen_ids = set()
    seen_tokens = set()
    issues = set()
    token = None
    owned_client = client is None
    client = client if client is not None else requests.Session()
    try:
        for page_number in range(1, max_pages + 1):
            request_params = dict(params)
            if token is not None:
                request_params["pageToken"] = token
            response = client.get(API_URL, params=request_params, timeout=(10, 45))
            response.raise_for_status()
            data = response.json()
            retrieved_at = utc_now()
            if not isinstance(data, dict) or not isinstance(data.get("studies"), list):
                raise ValueError("API response does not contain a valid study list.")
            next_token = data.get("nextPageToken")
            if next_token is not None and not isinstance(next_token, str):
                raise ValueError("API response contains an invalid pagination token.")
            next_token = next_token or None
            reported_count = _count(data.get("totalCount"))
            cohort = db.session.get(AnalysisCohort, cohort_id)
            if page_number == 1:
                cohort.expected_count = reported_count
            elif reported_count is not None and reported_count != cohort.expected_count:
                issues.add("API total count changed during retrieval")

            rows = []
            page_ids = set()
            rejected = 0
            for study in data["studies"]:
                snapshot = make_trial_snapshot(study, retrieved_at)
                if snapshot is None:
                    rejected += 1
                    issues.add("invalid study records were returned")
                    continue
                if snapshot.nct_id in seen_ids or snapshot.nct_id in page_ids:
                    rejected += 1
                    issues.add("duplicate study IDs were returned during pagination")
                    continue
                page_ids.add(snapshot.nct_id)
                rows.append(snapshot)
            db.session.add_all(rows)
            db.session.flush()
            for snapshot in rows:
                upsert_trial_from_snapshot(snapshot)
                db.session.add(
                    CohortTrial(
                        cohort_id=cohort_id,
                        nct_id=snapshot.nct_id,
                        snapshot_id=snapshot.id,
                    )
                )
            cohort.retrieved_count += len(rows)
            cohort.pages_fetched = page_number
            cohort.page_log = list(cohort.page_log) + [
                {
                    "page": page_number,
                    "requested_token": token,
                    "next_token": next_token,
                    "reported_count": reported_count,
                    "returned_records": len(data["studies"]),
                    "saved_records": len(rows),
                    "rejected_records": rejected,
                    "retrieved_at_utc": retrieved_at.isoformat(),
                    "response_json_sha256": hashlib.sha256(
                        json.dumps(
                            data,
                            sort_keys=True,
                            separators=(",", ":"),
                            ensure_ascii=False,
                        ).encode("utf-8")
                    ).hexdigest(),
                }
            ]
            db.session.commit()
            seen_ids.update(page_ids)
            if progress:
                progress(page_number, len(seen_ids), cohort.expected_count)
            if next_token is None:
                if cohort.expected_count is None:
                    issues.add(
                        "API total count was unavailable; completeness cannot be verified"
                    )
                elif len(seen_ids) != cohort.expected_count:
                    issues.add("stored unique count does not match initial API total")
                _finish(
                    cohort_id,
                    "PARTIAL" if issues else "COMPLETE",
                    "; ".join(sorted(issues)) if issues else None,
                )
                return cohort_id
            if next_token in seen_tokens:
                _finish(
                    cohort_id,
                    "PARTIAL",
                    "Pagination token repeated; retrieval stopped.",
                )
                return cohort_id
            seen_tokens.add(next_token)
            token = next_token
        _finish(
            cohort_id, "PARTIAL", "Maximum page limit reached before pagination ended."
        )
    except (requests.RequestException, ValueError, KeyboardInterrupt) as exc:
        db.session.rollback()
        if isinstance(exc, KeyboardInterrupt):
            reason = "Retrieval interrupted. Saved earlier pages remain available."
        elif isinstance(exc, requests.HTTPError):
            code = exc.response.status_code if exc.response is not None else "unknown"
            reason = f"ClinicalTrials.gov returned HTTP {code}. Retry as a new cohort."
        elif isinstance(exc, requests.RequestException):
            reason = (
                "ClinicalTrials.gov request failed or timed out. Retry as a new cohort."
            )
        else:
            reason = "ClinicalTrials.gov response was invalid. Retry as a new cohort."
        cohort = db.session.get(AnalysisCohort, cohort_id)
        _finish(cohort_id, "PARTIAL" if cohort.pages_fetched else "FAILED", reason)
    except SQLAlchemyError:
        # Discard only the failed page; preserve previously committed evidence.
        db.session.rollback()
        cohort = db.session.get(AnalysisCohort, cohort_id)
        _finish(
            cohort_id,
            "PARTIAL" if cohort.pages_fetched else "FAILED",
            "Database page write failed. Check configuration and migrations.",
        )
    finally:
        if owned_client:
            client.close()
    return cohort_id


def _show_cohort(cohort):
    memberships = db.session.scalar(
        select(func.count())
        .select_from(CohortTrial)
        .where(CohortTrial.cohort_id == cohort.id)
    )
    click.echo(f"Cohort ID: {cohort.id}")
    click.echo(f"Condition: {cohort.condition}")
    click.echo(f"Scope: {cohort.scope}; geography: global")
    years = (
        f"{cohort.start_year}-{cohort.end_year}"
        if cohort.start_year is not None
        else "all years"
    )
    click.echo(f"Start-date range: {years}")
    click.echo(f"Status: {cohort.status}")
    click.echo(f"Stored unique trials: {memberships}")
    click.echo(
        f"Expected API total: {cohort.expected_count if cohort.expected_count is not None else 'unknown'}"
    )
    click.echo(f"Pages fetched: {cohort.pages_fetched}")
    if cohort.failure_reason:
        click.echo(f"Reason: {cohort.failure_reason}")
    if cohort.status != "COMPLETE":
        click.echo(
            "This run is incomplete; do not use it for complete-landscape metrics."
        )


def register_cohort_commands(app):
    @app.cli.command("fetch-cohort")
    @click.option("--condition", default="Multiple Myeloma", show_default=True)
    @click.option(
        "--scope", type=click.Choice(SCOPES), default="drug-biologic", show_default=True
    )
    @click.option("--start-year", type=click.IntRange(1900, 2100))
    @click.option("--end-year", type=click.IntRange(1900, 2100))
    @click.option(
        "--page-size", type=click.IntRange(1, 1000), default=100, show_default=True
    )
    @click.option("--max-pages", type=click.IntRange(1), default=100, show_default=True)
    def fetch_cohort_command(
        condition, scope, start_year, end_year, page_size, max_pages
    ):
        """Retrieve and save all pages of matching studies for a new analysis run."""
        try:
            cohort_id = fetch_cohort(
                condition,
                scope,
                start_year,
                end_year,
                page_size,
                max_pages,
                progress=lambda page, count, expected: click.echo(
                    f"Page {page}: stored {count} / {expected if expected is not None else '?'} trials"
                ),
            )
            cohort = db.session.get(AnalysisCohort, cohort_id)
            _show_cohort(cohort)
        except ValueError as exc:
            raise click.UsageError(str(exc)) from exc
        except SQLAlchemyError as exc:
            db.session.rollback()
            raise click.ClickException(
                "Database unavailable. Apply the Step 4 migration and retry."
            ) from exc
        if cohort.status != "COMPLETE":
            raise click.ClickException(
                "Cohort retrieval did not complete. See the saved run's reason above."
            )

    @app.cli.command("cohort-info")
    @click.option("--id", "cohort_id", type=click.IntRange(1), required=True)
    def cohort_info(cohort_id):
        """Inspect one saved run without accessing ClinicalTrials.gov."""
        try:
            cohort = db.session.get(AnalysisCohort, cohort_id)
            if cohort is None:
                raise click.ClickException("No cohort has that ID.")
            _show_cohort(cohort)
        except SQLAlchemyError as exc:
            db.session.rollback()
            raise click.ClickException(
                "Database unavailable. Check configuration and migrations."
            ) from exc
