"""Versioned label references attached to exact names; never adverse-event counts."""

from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re

import click
from sqlalchemy.exc import SQLAlchemyError

from .drug_aliases import AliasCatalogError, reconcile_drug_aliases
from .summaries import CohortSummaryError, summarize_cohort

METHOD_VERSION = "cohort-safety-references-v1.0"
CATALOG_PATH = Path(__file__).parent / "data" / "drug_safety_v1.json"
LIMITATION = (
    "Selected warning references from pinned product labels. Trial counts mean reported intervention names, "
    "not patient exposure, observed adverse events, adverse-event rates or trial risk scores. "
    "Name matches do not establish formulation, dose, regimen or investigational role. "
    "Missing references do not mean an absence of safety warnings."
)


class SafetyCatalogError(ValueError):
    pass


def load_safety_catalog(aliases, path=CATALOG_PATH):
    try:
        content = Path(path).read_bytes()
        catalog = json.loads(content)
        if (
            not isinstance(catalog, dict)
            or catalog.get("schema_version") != "drug-safety-references-v1"
        ):
            raise ValueError("Unsupported schema")
        if (
            catalog.get("alias_catalog_version") != aliases["catalog_version"]
            or catalog.get("alias_catalog_sha256") != aliases["catalog_sha256"]
        ):
            raise ValueError("Alias catalog does not match")
        if (
            not isinstance(catalog.get("catalog_version"), str)
            or not catalog["catalog_version"].strip()
        ):
            raise ValueError("Missing catalog version")
        if not isinstance(catalog.get("entries"), list):
            raise ValueError("Missing catalog entries")
        alias_index = {a["id"]: a for a in aliases["catalog_entries"]}
        index = {}
        for entry in catalog["entries"]:
            if not isinstance(entry, dict):
                raise ValueError("Invalid entry")
            entity = entry.get("entity_id")
            if (
                not isinstance(entity, str)
                or entity not in alias_index
                or entity in index
            ):
                raise ValueError("Unknown or duplicate entity")
            if entry.get("source") != alias_index[entity]["source"]:
                raise ValueError("Source differs from the pinned reference")
            if (
                not isinstance(entry.get("reference_product"), str)
                or not entry["reference_product"].strip()
            ):
                raise ValueError("Missing reference product")
            boxed = entry.get("boxed_warning")
            if (
                not isinstance(boxed, dict)
                or (
                    boxed.get("present") is not None
                    and type(boxed["present"]) is not bool
                )
                or "present" not in boxed
            ):
                raise ValueError("Invalid boxed-warning presence")
            if not isinstance(boxed.get("basis"), str) or not boxed["basis"].strip():
                raise ValueError("Missing boxed-warning rationale")
            if boxed.get("sections") != (
                ["Boxed warning"] if boxed["present"] is True else []
            ):
                raise ValueError("Invalid boxed-warning section reference")
            warnings = entry.get("selected_warnings")
            if not isinstance(warnings, list) or not warnings:
                raise ValueError("Missing selected warnings")
            topics = set()
            for warning in warnings:
                if not isinstance(warning, dict):
                    raise ValueError("Invalid warning")
                for field in ("topic", "basis"):
                    if (
                        not isinstance(warning.get(field), str)
                        or not warning[field].strip()
                    ):
                        raise ValueError("Missing warning rationale")
                if warning["topic"] in topics:
                    raise ValueError("Duplicate topic in one entry")
                topics.add(warning["topic"])
                if warning.get("interpretation") != "curated_summary":
                    raise ValueError("Missing interpretation type")
                sections = warning.get("sections")
                if (
                    not isinstance(sections, list)
                    or not sections
                    or any(
                        not isinstance(s, str) or not re.fullmatch(r"5\.[1-9][0-9]*", s)
                        for s in sections
                    )
                ):
                    raise ValueError("Invalid warning section references")
            index[entity] = entry
        return {
            "catalog_version": catalog["catalog_version"],
            "sha256": hashlib.sha256(content).hexdigest(),
            "entries": catalog["entries"],
            "entity_index": index,
        }
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise SafetyCatalogError(
            "Safety reference catalog is missing, invalid or incompatible with the alias catalog; no safety references were applied."
        ) from exc


def summarize_safety(summary, aliases=None, catalog=None):
    aliases = aliases if aliases is not None else reconcile_drug_aliases(summary)
    catalog = catalog if catalog is not None else load_safety_catalog(aliases)
    all_ids = set(summary["metrics"]["total_trials"]["nct_ids"])
    named_ids, reference_ids, uncurated_ids = set(), set(), set()
    matched = []
    topics = defaultdict(list)
    for group in aliases["groups"]:
        ids = set(group["nct_ids"])
        named_ids.update(ids)
        alias_entry = group.get("catalog_entry")
        entity = alias_entry["id"] if alias_entry else None
        entry = catalog["entity_index"].get(entity)
        if entry is None:
            uncurated_ids.update(ids)
            continue
        reference_ids.update(ids)
        row = {
            **entry,
            "label": group["label"],
            "count": len(ids),
            "nct_ids": sorted(ids),
            "variants": group["variants"],
        }
        matched.append(row)
        for warning in entry["selected_warnings"]:
            topics[warning["topic"]].append(
                {
                    "entity_id": entity,
                    "label": group["label"],
                    "source": entry["source"],
                    "reference_product": entry["reference_product"],
                    "warning": warning,
                    "count": len(ids),
                    "nct_ids": sorted(ids),
                }
            )
    matched.sort(key=lambda r: r["label"])
    topic_rows = []
    for topic, entries in sorted(topics.items()):
        ids = set().union(*(set(e["nct_ids"]) for e in entries))
        topic_rows.append(
            {
                "label": topic,
                "count": len(ids),
                "nct_ids": sorted(ids),
                "entries": entries,
            }
        )
    return {
        "method_version": METHOD_VERSION,
        "catalog_version": catalog["catalog_version"],
        "catalog_sha256": catalog["sha256"],
        "alias_catalog_version": aliases["catalog_version"],
        "alias_catalog_sha256": aliases["catalog_sha256"],
        "catalog_entries": catalog["entries"],
        "catalog_entry_count": len(catalog["entries"]),
        "matched_entry_count": len(matched),
        "total_trials": len(all_ids),
        "entries": matched,
        "topics": topic_rows,
        "coverage": {
            "referenced": {
                "count": len(reference_ids),
                "nct_ids": sorted(reference_ids),
            },
            "unreferenced": {
                "count": len(all_ids - reference_ids),
                "nct_ids": sorted(all_ids - reference_ids),
            },
            "uncurated_names": {
                "count": len(uncurated_ids),
                "nct_ids": sorted(uncurated_ids),
            },
            "no_named_drug_biologic": {
                "count": len(all_ids - named_ids),
                "nct_ids": sorted(all_ids - named_ids),
            },
        },
        "boxed_reference_entries": sum(
            e["boxed_warning"]["present"] is True for e in matched
        ),
        "limitation": LIMITATION,
    }


def register_safety_commands(app):
    @app.cli.command("cohort-safety")
    @click.option("--id", "cohort_id", type=click.IntRange(1), required=True)
    @click.option("--json", "json_output", is_flag=True)
    def cohort_safety(cohort_id, json_output):
        """Attach selected label references to reported names, not clinical events."""
        try:
            summary = summarize_cohort(cohort_id)
            result = summarize_safety(summary)
        except (CohortSummaryError, AliasCatalogError, SafetyCatalogError) as exc:
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
                        **result,
                        "evidence": summary["evidence"],
                    },
                    indent=2,
                    ensure_ascii=False,
                )
            )
            return
        click.echo(
            f"Cohort {cohort_id}: {summary['cohort']['condition']} | {summary['cohort']['scope']} | COMPLETE"
        )
        click.echo(f"Method: {METHOD_VERSION} | Catalog: {result['catalog_version']}")
        click.echo(f"Catalog SHA256: {result['catalog_sha256']}")
        click.echo(f"Saved trials: {result['total_trials']}")
        click.echo(
            f"Matched label references: {result['matched_entry_count']} of {result['catalog_entry_count']}"
        )
        click.echo(
            f"Trials with at least one referenced name: {result['coverage']['referenced']['count']}"
        )
        click.echo(
            f"Trials without a referenced name: {result['coverage']['unreferenced']['count']}"
        )
        click.echo(
            f"Trials with at least one uncurated name: {result['coverage']['uncurated_names']['count']} (can overlap)"
        )
        for entry in result["entries"]:
            boxed = entry["boxed_warning"]["present"]
            click.echo(
                f"\n{entry['label']}: {entry['count']} trials containing a matched name | Boxed warning in reference label: {'present' if boxed is True else 'absent' if boxed is False else 'not curated'}"
            )
            for warning in entry["selected_warnings"]:
                click.echo(
                    f"  {warning['topic']} | Sections {', '.join(warning['sections'])}: {warning['basis']}"
                )
            click.echo(entry["source"]["url"])
        click.echo("\n" + LIMITATION)
