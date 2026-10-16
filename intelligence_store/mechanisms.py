"""Versioned, source-backed annotations; descriptive counts, not programs."""

from collections import defaultdict
import hashlib
import json
from pathlib import Path

import click
from sqlalchemy.exc import SQLAlchemyError

from .drug_aliases import AliasCatalogError, reconcile_drug_aliases
from .summaries import CohortSummaryError, summarize_cohort

ANNOTATION_PATH = Path(__file__).parent / "data" / "drug_annotations_v1.json"
ANNOTATION_SHA256 = 'be7cbfc716ff90a277f9f8bc009a0a2238da4f75b5a2d350b352026546a94591'
METHOD_VERSION = "cohort-annotations-v1.0"
FIELDS = ("mechanism", "modality", "target")
NOT_CURATED = "No curated annotation"


class AnnotationCatalogError(ValueError):
    pass


def load_annotation_catalog(aliases, path=ANNOTATION_PATH):
    try:
        content = Path(path).read_bytes()
        if hashlib.sha256(content).hexdigest() != ANNOTATION_SHA256:
            raise ValueError('File differs from its pinned checksum (drug_annotations_v1.json)')
        catalog = json.loads(content)
        if (
            not isinstance(catalog, dict)
            or catalog.get("schema_version") != "drug-annotations-v1"
        ):
            raise ValueError("Unsupported annotation schema")
        if (
            catalog.get("alias_catalog_sha256") != aliases["catalog_sha256"]
            or catalog.get("alias_catalog_version") != aliases["catalog_version"]
        ):
            raise ValueError("Alias catalog does not match")
        version = catalog.get("catalog_version")
        if not isinstance(version, str) or not version.strip():
            raise ValueError("Missing version")
        entries = catalog.get("entries")
        if not isinstance(entries, list):
            raise ValueError("Missing entries")
        alias_entries = {entry["id"]: entry for entry in aliases["catalog_entries"]}
        index = {}
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(
                entry.get("entity_id"), str
            ):
                raise ValueError("Invalid entry")
            entity_id = entry["entity_id"]
            if entity_id not in alias_entries or entity_id in index:
                raise ValueError("Unknown or duplicate entity")
            # The alias catalog already validates version-specific URLs and provenance.
            if entry.get("source") != alias_entries[entity_id]["source"]:
                raise ValueError("Source differs from the pinned reference")
            fields = entry.get("fields")
            if not isinstance(fields, dict) or set(fields) != set(FIELDS):
                raise ValueError("Invalid annotation fields")
            for field in fields.values():
                if field is None:
                    continue
                if not isinstance(field, dict):
                    raise ValueError("Invalid field")
                for name in ("label", "basis"):
                    if not isinstance(field.get(name), str) or not field[name].strip():
                        raise ValueError("Incomplete field rationale")
                if field["label"] == NOT_CURATED:
                    raise ValueError("Reserved missing-annotation label")
                if field.get("interpretation") not in (
                    "curated_summary",
                    "curated_classification",
                ):
                    raise ValueError("Missing interpretation type")
                sections = field.get("sections")
                if (
                    not isinstance(sections, list)
                    or not sections
                    or any(
                        section not in ("11 Description", "12.1 Mechanism of Action")
                        for section in sections
                    )
                ):
                    raise ValueError("Invalid source sections")
            index[entity_id] = entry
        return {
            "catalog_version": version,
            "sha256": hashlib.sha256(content).hexdigest(),
            "entries": entries,
            "entity_index": index,
        }
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise AnnotationCatalogError(
            "Annotation catalog is missing, invalid or incompatible with the alias catalog; no annotations were applied."
        ) from exc


def summarize_annotations(summary, aliases=None, catalog=None):
    aliases = aliases if aliases is not None else reconcile_drug_aliases(summary)
    catalog = catalog if catalog is not None else load_annotation_catalog(aliases)
    all_ids = set(summary["metrics"]["total_trials"]["nct_ids"])
    named_ids = {nct for row in aliases["groups"] for nct in row["nct_ids"]}
    buckets = {field: defaultdict(list) for field in FIELDS}
    uncurated_names = set()
    annotated_entities = []
    for group in aliases["groups"]:
        alias_entry = group["catalog_entry"]
        entry = catalog["entity_index"].get(alias_entry["id"]) if alias_entry else None
        if entry is None or any(entry["fields"][field] is None for field in FIELDS):
            uncurated_names.update(group["nct_ids"])
        if entry is None:
            continue
        if any(entry["fields"][field] is not None for field in FIELDS):
            annotated_entities.append(
                {
                    "entity_id": entry["entity_id"],
                    "label": group["label"],
                    "count": group["count"],
                    "nct_ids": list(group["nct_ids"]),
                    "fields": entry["fields"],
                    "source": entry["source"],
                }
            )
        for field in FIELDS:
            annotation = entry["fields"][field]
            if annotation is not None:
                buckets[field][annotation["label"]].append(
                    {
                        "entity_id": entry["entity_id"],
                        "label": group["label"],
                        "count": group["count"],
                        "nct_ids": list(group["nct_ids"]),
                        "annotation": annotation,
                        "source": entry["source"],
                    }
                )
    groups, coverage = {}, {}
    for field in FIELDS:
        rows = []
        known = set()
        for label, entities in buckets[field].items():
            ids = sorted({nct for entity in entities for nct in entity["nct_ids"]})
            known.update(ids)
            rows.append(
                {
                    "label": label,
                    "count": len(ids),
                    "nct_ids": ids,
                    "entities": sorted(entities, key=lambda e: e["entity_id"]),
                }
            )
        missing = sorted(all_ids - known)
        if missing:
            rows.append(
                {
                    "label": NOT_CURATED,
                    "count": len(missing),
                    "nct_ids": missing,
                    "entities": [],
                }
            )
        groups[field] = sorted(rows, key=lambda row: (-row["count"], row["label"]))
        coverage[field] = {
            "annotated_trials": len(known),
            "no_curated_annotation": len(missing),
        }
    annotated_entities.sort(key=lambda entry: entry["entity_id"])
    return {
        "method_version": METHOD_VERSION,
        "catalog_version": catalog["catalog_version"],
        "catalog_sha256": catalog["sha256"],
        "alias_catalog_version": aliases["catalog_version"],
        "alias_catalog_sha256": aliases["catalog_sha256"],
        "annotation_entries": catalog["entries"],
        "total_trials": len(all_ids),
        "named_intervention_trials": len(named_ids),
        "no_named_drug_biologic": len(all_ids - named_ids),
        "trials_with_uncurated_names": len(uncurated_names),
        "annotated_entities": annotated_entities,
        "groups": groups,
        "coverage": coverage,
    }


def register_mechanism_commands(app):
    @app.cli.command("cohort-mechanisms")
    @click.option("--id", "cohort_id", type=click.IntRange(1), required=True)
    @click.option("--json", "json_output", is_flag=True)
    def cohort_mechanisms(cohort_id, json_output):
        """Summarize curated mechanisms, modalities and targets with coverage."""
        try:
            summary = summarize_cohort(cohort_id)
            result = summarize_annotations(summary)
        except (CohortSummaryError, AliasCatalogError, AnnotationCatalogError) as exc:
            raise click.ClickException(str(exc)) from exc
        except SQLAlchemyError as exc:
            raise click.ClickException(
                "Database unavailable. Check configuration and migrations."
            ) from exc
        if json_output:
            click.echo(
                json.dumps(
                    {
                        "cohort": summary["cohort"],
                        "evidence": summary["evidence"],
                        **result,
                    },
                    indent=2,
                    ensure_ascii=False,
                )
            )
            return
        click.echo(
            f"Cohort {cohort_id}: {summary['cohort']['condition']} | {summary['cohort']['scope']}"
        )
        click.echo(
            f"Method: {result['method_version']} | Annotations: {result['catalog_version']}"
        )
        click.echo(f"Annotation SHA256: {result['catalog_sha256']}")
        click.echo(
            f"Alias catalog: {result['alias_catalog_version']} | SHA256: {result['alias_catalog_sha256']}"
        )
        click.echo(
            f"Total trials: {result['total_trials']}; with a named drug/biologic entry: {result['named_intervention_trials']}"
        )
        click.echo(
            f"Trials with at least one name lacking a complete annotation: {result['trials_with_uncurated_names']}"
        )
        for field in FIELDS:
            click.echo(f"\n{field.title()}:")
            for row in result["groups"][field]:
                click.echo(f"  {row['label']}: {row['count']} trials")
            if not result["groups"][field]:
                click.echo("  No cohort trials")
        click.echo(
            "\nOne trial counts once per category but can appear in multiple categories. No curated annotation is a coverage gap, not absence of a mechanism. These are reference annotations, not trial-specific efficacy, approval or development-program claims."
        )
