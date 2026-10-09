"""Join validated curated drug references to frozen reported-name evidence."""
import copy
from .drug_aliases import load_alias_catalog, reconcile_drug_aliases
from .mechanisms import load_annotation_catalog
from .safety import load_safety_catalog
from .interactions import load_interaction_catalog, summarize_interactions
from .regulatory import digest

METHOD = 'drug-knowledge-explorer-v1.0'
LIMITATION = ('Exact curated aliases identify reported DRUG/BIOLOGICAL names only. '
    'Name matches do not establish administration, formulation, route, dose, intervention role, '
    'approval, efficacy or clinical risk. Mechanism classifications and label references are curated context, '
    'not trial-specific measurements. Missing or unmapped knowledge remains unassessed.')


def build_drug_knowledge(summary):
    catalog = load_alias_catalog()
    aliases = reconcile_drug_aliases(summary, catalog=catalog)
    annotations = load_annotation_catalog(aliases)
    safety = load_safety_catalog(aliases)
    interaction_catalog = load_interaction_catalog(aliases)
    interactions = summarize_interactions(summary, aliases=aliases, catalog=interaction_catalog)
    groups = {r['catalog_entry']['id']:r for r in aliases['groups'] if r['catalog_entry']}
    interaction_index = {r['entity_id']:r for r in interactions['entries']}
    total = set(summary['evidence'])
    recruiting = set(summary['metrics']['recruiting_trials']['nct_ids'])
    matched = set()
    entries = []
    for entry in sorted(catalog['entries'], key=lambda e:e['canonical_name']):
        group = groups.get(entry['id'])
        ids = set(group['nct_ids']) if group else set()
        matched.update(ids)
        entries.append({'entity_id':entry['id'], 'label':entry['canonical_name'],
            'curated_aliases':copy.deepcopy(entry['aliases']), 'source':copy.deepcopy(entry['source']),
            'count':len(ids), 'nct_ids':sorted(ids), 'recruiting_count':len(ids & recruiting),
            'variants':copy.deepcopy(group['variants']) if group else [],
            'annotation':copy.deepcopy(annotations['entity_index'].get(entry['id'])),
            'safety':copy.deepcopy(safety['entity_index'].get(entry['id'])),
            'interactions':copy.deepcopy(interaction_index.get(entry['id'])),
            'evidence':{nct:copy.deepcopy(summary['evidence'][nct]) for nct in sorted(ids)}})
    unmapped = [copy.deepcopy(r) for r in aliases['groups'] if r['catalog_entry'] is None]
    unmapped_ids = {nct for row in unmapped for nct in row['nct_ids']}
    def coverage(ids):return {'count':len(ids), 'nct_ids':sorted(ids)}
    result = {'method_version':METHOD, 'cohort':copy.deepcopy(summary['cohort']),
        'total_trials':len(total), 'entries':entries, 'unmapped_groups':unmapped,
        'coverage':{'mapped_names':coverage(matched), 'no_mapped_names':coverage(total-matched),
                    'unmapped_names':coverage(unmapped_ids), 'unmapped_group_count':len(unmapped)},
        'provenance':{'alias_catalog_version':catalog['catalog_version'], 'alias_catalog_sha256':catalog['sha256'],
            'annotation_catalog_version':annotations['catalog_version'], 'annotation_catalog_sha256':annotations['sha256'],
            'safety_catalog_version':safety['catalog_version'], 'safety_catalog_sha256':safety['sha256'],
            'interaction_catalog_version':interaction_catalog['catalog_version'], 'interaction_catalog_sha256':interaction_catalog['sha256']},
        'view_scope':'Frozen cohort evidence combined with the currently installed validated catalogs. This view is not saved automatically; existing saved scenarios and briefs are not changed.',
        'limitation':LIMITATION}
    result['report_sha256'] = digest(result)
    return result
