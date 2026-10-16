"""Selected label references and exact reported-name pairs, never exposure."""

import hashlib
import json
from pathlib import Path
import re

import click
from sqlalchemy.exc import SQLAlchemyError

from .drug_aliases import AliasCatalogError, reconcile_drug_aliases
from .intervention_names import group_intervention_names, name_key
from .summaries import CohortSummaryError, summarize_cohort

METHOD_VERSION = "cohort-interaction-references-v1.0"
CATALOG_PATH = Path(__file__).parent / "data" / "drug_interactions_v1.json"
CATALOG_SHA256 = '0f830fa2ac6b071452959ac0d36e74be66b36a2c6042460efe214f9c0339ec53'
KINDS = {
    "drug_pair": "Selected drug-name pair",
    "class_reference": "Class-level reference; not expanded to individual drugs",
    "laboratory_reference": "Laboratory-test interference; not a drug-drug pair",
}
FINDINGS = {
    "exposure_change_reported": "Exposure change reported",
    "label_precaution": "Label precaution",
    "no_significant_effect_reported": "No significant effect reported in the studied context",
    "laboratory_interference": "Laboratory-test interference",
}
LIMITATION = (
    "Selected label references, not a complete interaction checker. A name pair means two "
    "selected names appear as DRUG/BIOLOGICAL entries in the same retained study. "
    "It does not establish same-arm treatment, simultaneous administration, patient exposure "
    "or an observed interaction. Missing matches do not establish compatibility."
)


class InteractionCatalogError(ValueError):
    pass


def load_interaction_catalog(aliases, path=CATALOG_PATH):
    try:
        content = Path(path).read_bytes()
        if hashlib.sha256(content).hexdigest() != CATALOG_SHA256:
            raise ValueError('File differs from its pinned checksum (drug_interactions_v1.json)')
        catalog = json.loads(content)
        if not isinstance(catalog, dict) or catalog.get("schema_version") != "drug-interaction-references-v1":
            raise ValueError("Unsupported schema")
        if (catalog.get("alias_catalog_version") != aliases["catalog_version"]
            or catalog.get("alias_catalog_sha256") != aliases["catalog_sha256"]):
            raise ValueError("Alias catalog differs")
        if not isinstance(catalog.get("catalog_version"), str) or not catalog["catalog_version"].strip():
            raise ValueError("Missing version")
        if not isinstance(catalog.get("entries"), list):
            raise ValueError("Missing entries")
        alias_index = {entry["id"]: entry for entry in aliases["catalog_entries"]}
        index, rule_index, pair_keys = {}, {}, set()
        for entry in catalog["entries"]:
            if not isinstance(entry, dict):
                raise ValueError("Invalid entry")
            entity = entry.get("entity_id")
            if not isinstance(entity, str) or entity not in alias_index or entity in index:
                raise ValueError("Unknown or duplicate entity")
            if entry.get("source") != alias_index[entity]["source"]:
                raise ValueError("Source differs from pinned reference")
            if not isinstance(entry.get("reference_product"), str) or not entry["reference_product"].strip():
                raise ValueError("Missing reference product")
            rules = entry.get("references")
            if not isinstance(rules, list) or not rules:
                raise ValueError("Missing references")
            for rule in rules:
                if not isinstance(rule, dict):
                    raise ValueError("Invalid rule")
                rule_id = rule.get("id")
                if not isinstance(rule_id, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", rule_id) or rule_id in rule_index:
                    raise ValueError("Invalid or duplicate rule ID")
                for field in ("title", "basis"):
                    if not isinstance(rule.get(field), str) or not rule[field].strip():
                        raise ValueError("Missing rationale")
                kind, finding = rule.get("kind"), rule.get("finding")
                if kind not in KINDS or finding not in FINDINGS or rule.get("interpretation") != "curated_summary":
                    raise ValueError("Unsupported interpretation")
                if (kind == "laboratory_reference") != (finding == "laboratory_interference"):
                    raise ValueError("Laboratory reference mislabeled as drug pair")
                sections = rule.get("sections")
                if (not isinstance(sections, list) or not sections
                    or any(not isinstance(s, str) or not re.fullmatch(r"(?:7|(?:7|12)\.[1-9][0-9]*)", s) for s in sections)
                    or len(sections) != len(set(sections))):
                    raise ValueError("Invalid sections")
                partner = rule.get("partner_name")
                if kind == "drug_pair":
                    if (not isinstance(partner, str) or not partner.strip()
                        or name_key(partner) in {name_key(n) for n in alias_index[entity]["aliases"]}):
                        raise ValueError("Missing or self partner")
                    key = (entity, name_key(partner))
                    if key in pair_keys:
                        raise ValueError("Duplicate name pair")
                    pair_keys.add(key)
                elif partner is not None:
                    raise ValueError("Non-pair reference has a drug partner")
                rule_index[rule_id] = {**rule, "entity_id": entity}
            index[entity] = entry
        return {
            "catalog_version": catalog["catalog_version"],
            "sha256": hashlib.sha256(content).hexdigest(),
            "entries": catalog["entries"], "entity_index": index, "rule_index": rule_index,
        }
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise InteractionCatalogError(
            "Interaction reference catalog is missing, invalid or incompatible with the alias catalog; no interaction references were applied."
        ) from exc


def summarize_interactions(summary, aliases=None, catalog=None):
    aliases = aliases if aliases is not None else reconcile_drug_aliases(summary)
    catalog = catalog if catalog is not None else load_interaction_catalog(aliases)
    formatting = {g["key"]: g for g in group_intervention_names(summary)["groups"]}
    anchors = {g["catalog_entry"]["id"]: g for g in aliases["groups"] if g.get("catalog_entry")}
    alias_index = {e["id"]: e for e in aliases["catalog_entries"]}
    all_ids = set(summary["metrics"]["total_trials"]["nct_ids"])
    anchor_ids, pair_ids = set(), set()
    entries, pairs, contexts = [], [], []
    for entry in catalog["entries"]:
        entity = entry["entity_id"]
        group = anchors.get(entity)
        ids = set(group["nct_ids"]) if group else set()
        anchor_ids.update(ids)
        rules = []
        for rule in entry["references"]:
            partner_group = formatting.get(name_key(rule["partner_name"])) if rule["kind"] == "drug_pair" else None
            partner_ids = set(partner_group["nct_ids"]) if partner_group else set()
            matched_ids = ids & partner_ids
            row = {
                **rule, "entity_id": entity, "anchor_label": alias_index[entity]["canonical_name"],
                "source": entry["source"], "reference_product": entry["reference_product"],
                "kind_label": KINDS[rule["kind"]], "finding_label": FINDINGS[rule["finding"]],
                "anchor_count": len(ids), "anchor_nct_ids": sorted(ids),
                "pair_count": len(matched_ids) if rule["kind"] == "drug_pair" else None,
                "pair_nct_ids": sorted(matched_ids) if rule["kind"] == "drug_pair" else None,
                "partner_variants": partner_group["variants"] if partner_group else [],
                "anchor_variants": group["variants"] if group else [],
            }
            rules.append(row)
            if rule["kind"] == "drug_pair":
                pair_ids.update(matched_ids)
                pairs.append(row)
            else:
                contexts.append(row)
        entries.append({
            **entry, "label": alias_index[entity]["canonical_name"],
            "anchor_count": len(ids), "anchor_nct_ids": sorted(ids), "references": rules,
        })
    entries.sort(key=lambda e: e["label"])
    pairs.sort(key=lambda r: (r["anchor_label"], r["partner_name"], r["id"]))
    contexts.sort(key=lambda r: (r["anchor_label"], r["title"], r["id"]))
    return {
        "method_version": METHOD_VERSION, "catalog_version": catalog["catalog_version"],
        "catalog_sha256": catalog["sha256"], "alias_catalog_version": aliases["catalog_version"],
        "alias_catalog_sha256": aliases["catalog_sha256"], "total_trials": len(all_ids),
        "catalog_entry_count": len(entries), "matched_entry_count": sum(e["anchor_count"] > 0 for e in entries),
        "entries": entries, "pairs": pairs, "contexts": contexts,
        "selected_pair_count": len(pairs), "matched_pair_count": sum(p["pair_count"] > 0 for p in pairs),
        "coverage": {
            "referenced_names": {"count": len(anchor_ids), "nct_ids": sorted(anchor_ids)},
            "no_reference_name": {"count": len(all_ids - anchor_ids), "nct_ids": sorted(all_ids - anchor_ids)},
            "selected_pairs": {"count": len(pair_ids), "nct_ids": sorted(pair_ids)},
            "no_selected_pair": {"count": len(all_ids - pair_ids), "nct_ids": sorted(all_ids - pair_ids)},
        },
        "limitation": LIMITATION,
    }


def register_interaction_commands(app):
    @app.cli.command("cohort-interactions")
    @click.option("--id", "cohort_id", type=click.IntRange(1), required=True)
    @click.option("--json", "json_output", is_flag=True)
    def cohort_interactions(cohort_id, json_output):
        """Show selected label references and exact reported-name pairs."""
        try:
            summary = summarize_cohort(cohort_id)
            result = summarize_interactions(summary)
        except (CohortSummaryError, AliasCatalogError, InteractionCatalogError) as exc:
            raise click.ClickException(str(exc)) from exc
        except SQLAlchemyError as exc:
            raise click.ClickException("Database unavailable. Check configuration and migrations.") from exc
        if json_output:
            click.echo(json.dumps({"cohort": summary["cohort"], **result, "evidence": summary["evidence"]}, indent=2, ensure_ascii=False))
            return
        click.echo(f"Cohort {cohort_id}: {summary['cohort']['condition']} | {summary['cohort']['scope']} | COMPLETE")
        click.echo(f"Method: {METHOD_VERSION} | Catalog: {result['catalog_version']}")
        click.echo(f"Catalog SHA256: {result['catalog_sha256']}")
        click.echo(f"Saved trials: {result['total_trials']}")
        click.echo(f"Matched label references: {result['matched_entry_count']} of {result['catalog_entry_count']}")
        click.echo(f"Trials with a reference name: {result['coverage']['referenced_names']['count']}")
        click.echo(f"Trials without a reference name: {result['coverage']['no_reference_name']['count']}")
        click.echo(f"Selected drug-name pairs: {result['selected_pair_count']} | Pairs found: {result['matched_pair_count']}")
        click.echo(f"Trials containing at least one selected pair: {result['coverage']['selected_pairs']['count']}")
        click.echo(f"Trials without a selected pair: {result['coverage']['no_selected_pair']['count']}")
        for row in result["pairs"]:
            click.echo(f"\n{row['anchor_label']} + {row['partner_name']}: {row['pair_count']} studies listing both names")
            click.echo(f"  {row['finding_label']} | Sections {', '.join(row['sections'])}: {row['basis']}")
            click.echo(row["source"]["url"])
        for row in result["contexts"]:
            click.echo(f"\n{row['anchor_label']}: {row['title']} | {row['kind_label']}")
            click.echo(f"  Sections {', '.join(row['sections'])}: {row['basis']}")
        click.echo("\n" + LIMITATION)
