"""Exact source-backed alias reconciliation over frozen cohort evidence."""

from collections import defaultdict
from datetime import date
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import parse_qs, urlparse

import click
from sqlalchemy.exc import SQLAlchemyError

from .intervention_names import group_intervention_names, name_key
from .summaries import CohortSummaryError, summarize_cohort

ALIAS_METHOD_VERSION = "drug-aliases-v1.1"
CATALOG_PATH = Path(__file__).parent / "data" / "drug_aliases_v1.json"
FORMATTING_MAP_PATH = Path(__file__).parent / "data" / "formatting_group_mappings_v1.json"


class AliasCatalogError(ValueError):
    pass


class FormattingMapError(ValueError):
    pass


def load_formatting_group_mappings(path=FORMATTING_MAP_PATH):
    """Load only explicitly approved reviewed formatting-group mappings."""
    try:
        content = Path(path).read_bytes()
        catalog = json.loads(content)
        if (
            not isinstance(catalog, dict)
            or catalog.get("schema_version") != "formatting-group-mappings-v1"
        ):
            raise ValueError("Unsupported formatting-map schema")

        entries = catalog.get("entries")
        if not isinstance(entries, list):
            raise ValueError("Missing formatting-map entries")

        index = {}
        for entry in entries:
            if not isinstance(entry, dict):
                raise ValueError("Invalid formatting-map entry")

            formatting_group = entry.get("formatting_group")
            entity_id = entry.get("entity_id")
            canonical_name = entry.get("canonical_name")

            if not isinstance(formatting_group, str) or not formatting_group.strip():
                raise ValueError("Missing formatting-group label")
            if (
                not isinstance(entity_id, str)
                or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", entity_id)
            ):
                raise ValueError("Invalid formatting-map entity ID")
            if not isinstance(canonical_name, str) or not canonical_name.strip():
                raise ValueError("Missing formatting-map canonical name")

            if entry.get("mapping_status") != "approved":
                raise ValueError("Formatting-map entries must be explicitly approved")
            if entry.get("review_status") not in {"approved", "approved_with_changes"}:
                raise ValueError("Formatting-map entry lacks an approved review status")

            key = name_key(formatting_group)
            if not key:
                raise ValueError("Invalid normalized formatting-group key")
            if key in index:
                prior = index[key]
                if (
                    prior["entity_id"] != entity_id
                    or name_key(prior["canonical_name"]) != name_key(canonical_name)
                ):
                    raise ValueError("A formatting group maps to multiple entities")
                raise ValueError("Duplicate formatting-group mapping")

            index[key] = entry

        return {
            "schema_version": catalog["schema_version"],
            "sha256": hashlib.sha256(content).hexdigest(),
            "entries": entries,
            "mapping_index": index,
        }
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise FormattingMapError(
            "Formatting-group mapping catalog is missing or invalid; "
            "reviewed formatting mappings were not applied."
        ) from exc


def load_alias_catalog(path=CATALOG_PATH):
    """Validate every entry before using any mappings; reject ambiguity."""
    try:
        content = Path(path).read_bytes()
        catalog = json.loads(content)
        if (
            not isinstance(catalog, dict)
            or catalog.get("schema_version") != "drug-alias-catalog-v1"
        ):
            raise ValueError("Unsupported schema")
        version = catalog.get("catalog_version")
        if not isinstance(version, str) or not version.strip():
            raise ValueError("Missing catalog version")
        entries = catalog.get("entries")
        if not isinstance(entries, list):
            raise ValueError("Missing entries")
        index, entity_ids = {}, set()
        for entry in entries:
            if not isinstance(entry, dict):
                raise ValueError("Invalid entry")
            entity_id = entry.get("id")
            canonical = entry.get("canonical_name")
            if (
                not isinstance(entity_id, str)
                or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", entity_id)
                or entity_id in entity_ids
            ):
                raise ValueError("Invalid or duplicate entity ID")
            if not isinstance(canonical, str) or not canonical.strip():
                raise ValueError("Missing canonical name")
            entity_ids.add(entity_id)
            aliases = entry.get("aliases")
            if (
                not isinstance(aliases, list)
                or not aliases
                or any(not isinstance(a, str) or not a.strip() for a in aliases)
            ):
                raise ValueError("Missing alias labels")
            keys = [name_key(a) for a in aliases]
            if len(keys) != len(set(keys)) or name_key(canonical) not in keys:
                raise ValueError("Duplicate aliases or missing canonical alias")
            source = entry.get("source")
            if not isinstance(source, dict):
                raise ValueError("Missing provenance")
            for field in (
                "publisher",
                "title",
                "note",
                "set_id",
                "verified_on",
                "retrieved_xml_sha256",
            ):
                if not isinstance(source.get(field), str) or not source[field].strip():
                    raise ValueError("Incomplete provenance")
            date.fromisoformat(source["verified_on"])
            if not re.fullmatch(r"[0-9a-f]{64}", source["retrieved_xml_sha256"]):
                raise ValueError("Invalid source digest")
            label_version = source.get("label_version")
            if type(label_version) is not int or label_version < 1:
                raise ValueError("Invalid label version")
            if not isinstance(source.get("url"), str):
                raise ValueError("Missing source URL")
            url = urlparse(source["url"])
            query = parse_qs(url.query)
            if (
                url.scheme != "https"
                or url.netloc != "dailymed.nlm.nih.gov"
                or url.path != "/dailymed/lookup.cfm"
                or query.get("setid") != [source["set_id"]]
                or query.get("version") != [str(label_version)]
            ):
                raise ValueError("Invalid version-specific source URL")
            for key in keys:
                if key in index:
                    raise ValueError("An alias maps to multiple entities")
                index[key] = entry
        return {
            "catalog_version": version,
            "sha256": hashlib.sha256(content).hexdigest(),
            "entries": entries,
            "alias_index": index,
        }
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise AliasCatalogError(
            "Alias catalog is missing or invalid; no mappings were applied. Check the bundled catalog file."
        ) from exc


def reconcile_drug_aliases(summary, catalog=None, formatting_catalog=None):
    catalog = catalog if catalog is not None else load_alias_catalog()
    formatting_catalog = (
        formatting_catalog
        if formatting_catalog is not None
        else load_formatting_group_mappings()
    )

    formatting = group_intervention_names(summary)
    buckets = defaultdict(list)
    entities = {}
    mapped_keys = []

    for group in formatting["groups"]:
        alias_entry = catalog["alias_index"].get(group["key"])
        formatting_entry = None

        if alias_entry is None:
            formatting_entry = formatting_catalog["mapping_index"].get(group["key"])

        if alias_entry is not None:
            key = "catalog:" + alias_entry["id"]
            entities[key] = {
                "canonical_name": alias_entry["canonical_name"],
                "catalog_entry": alias_entry,
                "mapping_entry": None,
                "mapping_status": "source-backed",
            }
            mapped_keys.append(group["key"])

        elif formatting_entry is not None:
            key = "reviewed:" + formatting_entry["entity_id"]
            entities[key] = {
                "canonical_name": formatting_entry["canonical_name"],
                "catalog_entry": None,
                "mapping_entry": formatting_entry,
                "mapping_status": "reviewed-mapping",
            }
            mapped_keys.append(group["key"])

        else:
            key = "unmapped:" + group["key"]

        buckets[key].append(group)

    rows = []
    for key, groups in buckets.items():
        entity = entities.get(key)
        ids = sorted({nct for group in groups for nct in group["nct_ids"]})
        variants = sorted(
            [dict(v) for group in groups for v in group["variants"]],
            key=lambda v: (-v["count"], v["label"]),
        )
        rows.append(
            {
                "key": key,
                "label": entity["canonical_name"] if entity else groups[0]["label"],
                "count": len(ids),
                "nct_ids": ids,
                "variants": variants,
                "mapping_status": entity["mapping_status"] if entity else "unmapped",
                "catalog_entry": entity["catalog_entry"] if entity else None,
                "mapping_entry": entity["mapping_entry"] if entity else None,
            }
        )

    rows.sort(key=lambda r: (-r["count"], r["label"], r["key"]))
    return {
        "method_version": ALIAS_METHOD_VERSION,
        "catalog_version": catalog["catalog_version"],
        "catalog_sha256": catalog["sha256"],
        "catalog_entry_count": len(catalog["entries"]),
        "catalog_entries": catalog["entries"],
        "formatting_mapping_schema_version": formatting_catalog["schema_version"],
        "formatting_mapping_sha256": formatting_catalog["sha256"],
        "formatting_mapping_entry_count": len(formatting_catalog["entries"]),
        "formatting_group_count": formatting["group_count"],
        "mapped_formatting_group_count": len(mapped_keys),
        "unmapped_group_count": formatting["group_count"] - len(mapped_keys),
        "matched_entity_count": len(entities),
        "groups": rows,
    }


def register_alias_commands(app):
    @app.cli.command("cohort-aliases")
    @click.option("--id", "cohort_id", type=click.IntRange(1), required=True)
    @click.option("--top", type=click.IntRange(1, 100), default=10, show_default=True)
    @click.option("--json", "json_output", is_flag=True)
    def cohort_aliases(cohort_id, top, json_output):
        """Show source-backed aliases, coverage and still-unmapped names."""
        try:
            summary = summarize_cohort(cohort_id)
            result = reconcile_drug_aliases(summary)
        except (CohortSummaryError, AliasCatalogError, FormattingMapError) as exc:
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
        click.echo(
            f"Method: {result['method_version']} | Catalog: {result['catalog_version']}"
        )
        click.echo(f"Catalog SHA256: {result['catalog_sha256']}")
        click.echo(
            f"Reviewed formatting mappings: {result['formatting_mapping_entry_count']} | "
            f"SHA256 {result['formatting_mapping_sha256']}"
        )
        click.echo(
            f"Catalog entries: {result['catalog_entry_count']}; matched entries in cohort: {result['matched_entity_count']}"
        )
        click.echo(
            f"Formatting groups matched: {result['mapped_formatting_group_count']} of {result['formatting_group_count']}"
        )
        click.echo(f"Unmapped formatting groups: {result['unmapped_group_count']}")
        for row in result["groups"][:top]:
            click.echo(
                f"\n  {row['label']}: {row['count']} trials [{row['mapping_status']}]"
            )
            for variant in row["variants"]:
                click.echo(f"    Raw: {variant['label']} — {variant['count']} trials")
            if row["catalog_entry"]:
                click.echo(f"    Source: {row['catalog_entry']['source']['url']}")
            elif row["mapping_entry"]:
                click.echo(
                    f"    Reviewed mapping: {row['mapping_entry']['formatting_group']} "
                    f"→ {row['mapping_entry']['canonical_name']}"
                )
        click.echo(
            "\nMappings use either exact approved aliases or explicitly reviewed formatting-group mappings. "
"Everything else remains unmapped/unassessed. Counts are not development programs or approval determinations."
        )
