"""Conservative formatting groups of reported names, not drug identities."""

from collections import defaultdict
import json

import click
from sqlalchemy.exc import SQLAlchemyError

from .summaries import CohortSummaryError, summarize_cohort

NAME_GROUP_VERSION = "intervention-names-v1.0"
RULES = [
    "collapse whitespace",
    "compare without capitalization",
    "union contributing NCT IDs",
]


def name_key(label):
    """Preserve punctuation, dosage, salts and combination wording."""
    return " ".join(label.split()).casefold()


def group_intervention_names(summary):
    """Group existing raw-name rows, retaining each variant and its evidence.

    Drug and biologic entries use the same source population as the raw-name
    summary. A trial contributes once per formatting group, even when several
    variants occur in that trial. No vocabulary or pharmacologic inference is
    used. The display label is the most frequent raw variant (stable tie-break).
    """
    variants = defaultdict(list)
    for row in summary["groups"]["drug_intervention"]:
        key = name_key(row["label"])
        if key:
            variants[key].append(row)
    groups = []
    for key, rows in variants.items():
        rows = sorted(rows, key=lambda row: (-row["count"], row["label"]))
        ids = sorted({nct for row in rows for nct in row["nct_ids"]})
        groups.append(
            {
                "key": key,
                "label": " ".join(rows[0]["label"].split()),
                "count": len(ids),
                "nct_ids": ids,
                "variants": [
                    {
                        "label": row["label"],
                        "count": row["count"],
                        "nct_ids": list(row["nct_ids"]),
                    }
                    for row in rows
                ],
            }
        )
    groups.sort(key=lambda row: (-row["count"], row["label"], row["key"]))
    contributing = {nct for row in groups for nct in row["nct_ids"]}
    return {
        "method_version": NAME_GROUP_VERSION,
        "rules": list(RULES),
        "raw_name_count": len(summary["groups"]["drug_intervention"]),
        "group_count": len(groups),
        "groups_with_multiple_variants": sum(
            len(row["variants"]) > 1 for row in groups
        ),
        "contributing_trial_count": len(contributing),
        "groups": groups,
    }


def register_intervention_name_commands(app):
    @app.cli.command("cohort-interventions")
    @click.option("--id", "cohort_id", type=click.IntRange(1), required=True)
    @click.option("--top", type=click.IntRange(1, 100), default=10, show_default=True)
    @click.option("--json", "json_output", is_flag=True)
    def cohort_interventions(cohort_id, top, json_output):
        """Inspect formatting groups and original labels in a complete cohort."""
        try:
            summary = summarize_cohort(cohort_id)
            result = group_intervention_names(summary)
        except CohortSummaryError as exc:
            raise click.ClickException(str(exc)) from exc
        except SQLAlchemyError as exc:
            raise click.ClickException(
                "Database unavailable. Check configuration and migrations."
            ) from exc
        if json_output:
            click.echo(
                json.dumps(
                    {"cohort": summary["cohort"], **result},
                    indent=2,
                    ensure_ascii=False,
                )
            )
            return
        click.echo(
            f"Cohort {cohort_id}: {summary['cohort']['condition']} | {summary['cohort']['scope']}"
        )
        click.echo(f"Method: {result['method_version']}")
        click.echo(f"Raw reported names: {result['raw_name_count']}")
        click.echo(f"Formatting name groups: {result['group_count']}")
        click.echo(
            f"Groups with multiple raw variants: {result['groups_with_multiple_variants']}"
        )
        click.echo(
            "Counts are distinct contributing trials per name group; groups overlap."
        )
        for row in result["groups"][:top]:
            click.echo(f"\n  {row['label']}: {row['count']}")
            for variant in row["variants"]:
                click.echo(f"    Raw: {variant['label']} — {variant['count']} trials")
        click.echo(
            "\nCapitalization/whitespace only. Brands, codes, salts and combinations remain separate. These are not unique drugs or development programs."
        )
