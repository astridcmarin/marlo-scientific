"""Patient Lab 2.0f: one run record and banner for every Patient Lab result page."""
import copy
import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_kim_pk_runs as fixtures  # noqa: E402

from intelligence_store.bortezomib_patient_platelets import patient_platelet_view
from intelligence_store.bortezomib_platelet_evidence import load_model_extract
from intelligence_store.covariate_estimation import CovariateEstimationError
from intelligence_store.estimated_pk import calculate_estimated_pk, primary_weight_basis
from intelligence_store.kim_pk_runs import read_kim_pk_run
from intelligence_store.patient_state import SCHEMA_V2, digest
from intelligence_store.patient_state_revisions import save_revision
from intelligence_store.run_record import (record_for_relative_odds, EVIDENCE_PATH, EVIDENCE_V1_SHA256, EVIDENCE_V2_SHA256, EVIDENCE_V3_SHA256, EVIDENCE_V4_SHA256, EVIDENCE_V5_SHA256, LAYER_ORDER, SCHEMA_VERSION, load_evidence_status,
                                           record_for_estimated_pk, record_for_kim_run, record_for_patient_platelets)

ROOT = Path(__file__).resolve().parents[1]
COMMON_KEYS = {'schema_version', 'evidence_status_version', 'evidence_status_sha256', 'kind', 'title', 'result_type',
               'patient_record', 'model', 'status', 'inputs_from_record', 'derived_inputs', 'assumptions', 'applicability',
               'warnings', 'limitations', 'checksums', 'validation', 'record_sha256'}


class EvidenceStatus(unittest.TestCase):
    def test_changed_file_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / EVIDENCE_PATH.name
            path.write_bytes(EVIDENCE_PATH.read_bytes() + b' ')
            with self.assertRaises(CovariateEstimationError):
                load_evidence_status(path)

    def test_superseded_versions_are_kept_unchanged(self):
        v1 = EVIDENCE_PATH.with_name('model_evidence_status_v1.json')
        v2 = EVIDENCE_PATH.with_name('model_evidence_status_v2.json')
        self.assertEqual(hashlib.sha256(v1.read_bytes()).hexdigest(), EVIDENCE_V1_SHA256)
        self.assertEqual(hashlib.sha256(v2.read_bytes()).hexdigest(), EVIDENCE_V2_SHA256)
        self.assertEqual(json.loads(v2.read_text())['supersedes']['status_version'], json.loads(v1.read_text())['status_version'])
        v3 = EVIDENCE_PATH.with_name('model_evidence_status_v3.json')
        self.assertEqual(hashlib.sha256(v3.read_bytes()).hexdigest(), EVIDENCE_V3_SHA256)
        self.assertEqual(json.loads(v3.read_text())['supersedes']['status_version'], json.loads(v2.read_text())['status_version'])
        v4 = EVIDENCE_PATH.with_name('model_evidence_status_v4.json')
        self.assertEqual(hashlib.sha256(v4.read_bytes()).hexdigest(), EVIDENCE_V4_SHA256)
        self.assertEqual(json.loads(v4.read_text())['supersedes']['status_version'], json.loads(v3.read_text())['status_version'])
        v5 = EVIDENCE_PATH.with_name('model_evidence_status_v5.json')
        self.assertEqual(hashlib.sha256(v5.read_bytes()).hexdigest(), EVIDENCE_V5_SHA256)
        self.assertEqual(json.loads(v5.read_text())['supersedes']['status_version'], json.loads(v4.read_text())['status_version'])
        current = load_evidence_status()
        self.assertEqual(current['supersedes']['status_version'], json.loads(v5.read_text())['status_version'])

    def test_v6_only_adds_the_can1004_report_to_the_bortezomib_pk_component(self):
        current = load_evidence_status()['models']
        v5 = json.loads(EVIDENCE_PATH.with_name('model_evidence_status_v5.json').read_text())['models']
        self.assertEqual(set(current), set(v5))
        for model_id in v5:
            if model_id != 'bortezomib_pk_lignet_2022':
                self.assertEqual(current[model_id], v5[model_id])
        layer = current['bortezomib_pk_lignet_2022']['layers']['external_consistency']
        old = v5['bortezomib_pk_lignet_2022']['layers']['external_consistency']
        self.assertEqual({k: v for k, v in layer.items() if k != 'further_reports'}, old)
        extra = layer['further_reports'][-1]
        report = json.loads((ROOT / extra['evidence_report']).read_text())
        self.assertEqual(extra['results'], {'can1004_' + k: v for k, v in report['decision']['result'].items()})

    def test_v5_adds_the_exposure_safety_model_without_overstating_it(self):
        current = json.loads(EVIDENCE_PATH.with_name('model_evidence_status_v5.json').read_text())['models']
        v4 = json.loads(EVIDENCE_PATH.with_name('model_evidence_status_v4.json').read_text())['models']
        self.assertEqual(set(current) - set(v4), {'lenalidomide_exposure_safety_2016'})
        layers = current['lenalidomide_exposure_safety_2016']['layers']
        self.assertEqual({k: v['status'] for k, v in layers.items()},
                         {'software_verification': 'done', 'transcription_verification': 'partial',
                          'reproduction': 'not_done', 'external_consistency': 'not_done'})
        self.assertIn('not independent', layers['external_consistency']['summary'])
        for model_id in v4:
            if model_id != 'lenalidomide_renal_pathways_2026':
                self.assertEqual(current[model_id], v4[model_id])

    def test_bortezomib_external_search_is_recorded(self):
        layer = load_evidence_status()['models']['bortezomib_platelets_lignet_2022']['layers']['external_consistency']
        self.assertEqual(layer['status'], 'not_done')
        self.assertTrue(any('CR009058' in c['source'] for c in layer['search']['candidates']))

    def test_every_model_states_all_four_layers(self):
        evidence = load_evidence_status()
        self.assertIs(evidence['clinical_prediction_validated'], False)
        for model in evidence['models'].values():
            self.assertEqual(set(model['layers']), set(LAYER_ORDER))

    def test_cited_reports_exist_unchanged_and_say_what_is_quoted(self):
        """Each cited verification report has the pinned file checksum, and the classification and per-group
        results quoted in the evidence file are the ones in the report."""
        cited = 0
        for model in load_evidence_status()['models'].values():
            for layer in model['layers'].values():
                for extra in layer.get('further_reports', []):
                    cited += 1
                    raw = (ROOT / extra['evidence_report']).read_bytes()
                    self.assertEqual(hashlib.sha256(raw).hexdigest(), extra['evidence_report_file_sha256'])
                    self.assertEqual(json.loads(raw)['classification'], extra['classification'])
                if 'evidence_report' not in layer:
                    continue
                cited += 1
                raw = (ROOT / layer['evidence_report']).read_bytes()
                self.assertEqual(hashlib.sha256(raw).hexdigest(), layer['evidence_report_file_sha256'])
                report = json.loads(raw)
                if 'classification' in layer:
                    self.assertEqual(report['classification'], layer['classification'])
                if 'result_at_1_3_mg_m2' in layer:
                    lead = next(r for r in report['rows'] if r['dose_mg_m2'] == 1.3)['readings'][0]['endpoints']
                    self.assertEqual({k: lead[k]['classification'] for k in layer['result_at_1_3_mg_m2']}, layer['result_at_1_3_mg_m2'])
                if 'result_by_group' in layer:
                    self.assertEqual(report['primary_endpoint_by_group'], layer['result_by_group'])
        self.assertEqual(cited, 8)

    def test_bortezomib_reproduction_matches_the_adopted_reading(self):
        report = json.loads((ROOT / 'docs/verification/bortezomib_platelet_check_v1.json').read_text())
        self.assertEqual(report['decision']['adopted_primary_reading'], {'units': 'ng_per_ml', 'effect_bound': 'unbounded_as_printed'})


class Records(unittest.TestCase):
    setUp = fixtures.KimPKRunTests.setUp
    tearDown = fixtures.KimPKRunTests.tearDown
    save = fixtures.KimPKRunTests.save

    def check_common(self, record, model_id):
        self.assertEqual(set(record) - {'saved_at_utc'}, COMMON_KEYS)
        self.assertEqual(record['schema_version'], SCHEMA_VERSION)
        self.assertEqual(record['model']['model_id'], model_id)
        self.assertEqual([l['layer'] for l in record['model']['layers']], list(LAYER_ORDER))
        self.assertEqual(record['validation'], {'clinical_prediction_validated': False, 'ready_for_patient_simulation': False})
        self.assertEqual(record['patient_record']['data'], 'synthetic')
        body = {k: v for k, v in record.items() if k != 'record_sha256'}
        self.assertEqual(digest(body), record['record_sha256'])
        for c in record['checksums']:
            self.assertRegex(c['sha256'], r'^[0-9a-f]{64}$')

    def platelet_revision(self, value):
        state = copy.deepcopy(fixtures.full_state())
        state['schema_version'] = SCHEMA_V2
        state['fields']['platelet_count'] = {'value': value, 'unit': '10^9/L', 'origin': 'synthetic_input',
                                             'observed_at': None, 'source_ref': 'Invented for test'}
        parent = getattr(self, '_latest', self.revision)
        self._latest = save_revision(self.scenario.id, state, parent_revision_id=parent.id, title=f'Platelets {value}')
        return self._latest

    def test_hughes_record_copies_the_report(self):
        report = calculate_estimated_pk(self.revision.id, primary_weight_basis(), fixtures.request_mg(25), 'MM')
        record = record_for_estimated_pk(report)
        self.check_common(record, 'lenalidomide_hughes_2019')
        self.assertEqual(record['patient_record']['state_sha256'], self.revision.state_sha256)
        names = [r['name'] for r in record['inputs_from_record']]
        for field in ('age_years', 'biological_sex', 'weight', 'height', 'serum_creatinine'):
            self.assertIn(field, names)
        self.assertTrue(all(r['origin'] == 'synthetic_input' for r in record['inputs_from_record']))
        basis = record['assumptions'][0]
        self.assertEqual(basis['status'], report['covariate_estimate']['weight_basis_evidence']['assessment_status'])
        self.assertEqual(record['applicability'][0]['status'], report['covariate_estimate']['coverage_checks'][0]['status'])
        self.assertIn({'label': 'Report', 'sha256': report['report_sha256']}, record['checksums'])
        self.assertEqual(record_for_estimated_pk(report), record)

    def test_kim_record_from_a_verified_saved_run(self):
        row = read_kim_pk_run(self.save().id)
        record = record_for_kim_run(row)
        self.check_common(record, 'lenalidomide_kim_2026')
        self.assertEqual(record['status'], 'completed')
        self.assertEqual(record['assumptions'][0]['reading'], 'linear multiplicative')
        self.assertTrue(any('may under-predict' in w for w in record['warnings']))
        self.assertIn({'label': 'Saved payload', 'sha256': row.payload_sha256}, record['checksums'])

    def test_platelet_record_lists_the_settled_reading_and_the_assumptions(self):
        view = patient_platelet_view(self.platelet_revision(120).id, 1)
        record = record_for_patient_platelets(view, load_model_extract())
        self.check_common(record, 'bortezomib_platelets_lignet_2022')
        self.assertEqual(record['result_type']['id'], 'hypothetical_typical_pd_curve')
        self.assertEqual(record['inputs_from_record'][0]['value'], 120.0)
        self.assertEqual(record['assumptions'][0]['status'], 'settled_by_locked_check')
        statuses = {a['name']: a['status'] for a in record['assumptions']}
        self.assertIn('assumed', statuses.values())
        self.assertEqual(record['applicability'][0]['status'], 'at_or_above_entry_threshold')
        low = record_for_patient_platelets(patient_platelet_view(self.platelet_revision(20).id, 1), load_model_extract())
        self.assertEqual(low['applicability'][0]['status'], 'below_entry_threshold')
        self.assertTrue(low['warnings'])

    def test_relative_odds_record(self):
        from intelligence_store.estimated_pk import compare_published_models, estimate_for_revision
        request = fixtures.request_mg(5.0)
        basis = primary_weight_basis()
        mm = compare_published_models(self.revision.id, basis, 'linear_multiplicative', request, 'MM')
        # Kim runs only for myeloma; relabel a copy to check how another declared disease is flagged.
        other = copy.deepcopy(mm)
        other['declared_disease_code'] = 'OTHER'
        for models, disease, expected in ((mm, 'MM', 'within_reported_range'), (other, 'OTHER', 'outside_reported_range')):
            record = record_for_relative_odds(models, estimate_for_revision(self.revision.id, basis))
            self.check_common(record, 'lenalidomide_exposure_safety_2016')
            self.assertEqual(record['result_type']['id'], 'relative_odds_vs_reference')
            self.assertEqual(record['applicability'][0]['status'], expected)
            self.assertEqual(any('myeloma-only' in w for w in record['warnings']), disease != 'MM')
            ratios = [d for d in record['derived_inputs'] if d['name'].startswith('exposure ratio')]
            self.assertEqual([d['value'] for d in ratios],
                             [r['reference_exposure']['ratio_to_reference'] for r in models['rows'] if 'relative_odds' in r])
            names = {a['name']: a['status'] for a in record['assumptions']}
            self.assertTrue(ratios)
            for row in models['rows']:
                key = f"Between-patient variability in clearance ({row['label']})"
                if 'relative_odds' in row:
                    self.assertEqual(names[key], 'assumed' if row['model'] == 'lenalidomide_kim_2026' else 'sourced')
                else:
                    self.assertNotIn(key, names)
            self.assertIn({'label': 'Model comparison', 'sha256': models['report_sha256']}, record['checksums'])
        blocked = copy.deepcopy(mm)
        for row in blocked['rows']:
            row.pop('relative_odds', None)
        with self.assertRaises(ValueError):
            record_for_relative_odds(blocked, estimate_for_revision(self.revision.id, basis))

    def test_pages_show_the_banner_and_the_run_record(self):
        base = f'/landscape/workspace/scenarios/{self.scenario.id}/patient-state/revisions'
        shared = ('Not a clinical prediction', 'Clinical prediction validated: <strong>false</strong>', 'Run record',
                  'What has been checked about this model', 'Inside the source data?')
        rev = self.platelet_revision(120)
        platelets = self.client.get(f'{base}/{rev.id}/bortezomib-platelets').get_data(as_text=True)
        for text in shared + ('Hypothetical typical effect curve', 'settled by locked check', 'not done', 'doi:10.1002/psp4.12743', 'Sources searched', 'CR009058', 'Ogawa Y'):
            self.assertIn(text, platelets)
        missing = self.client.get(f'{base}/{self.revision.id}/bortezomib-platelets').get_data(as_text=True)
        self.assertIn('Not a clinical prediction', missing)
        self.assertNotIn('Run record', missing)

        page = f'{base}/{self.revision.id}/estimated-pk'
        before = self.client.get(page).get_data(as_text=True)
        self.assertIn('Typical-value concentration curve', before)
        self.assertNotIn('run-record-heading', before)
        token = re.search(r'name="form_token" value="([^"]+)"', before).group(1)
        data = {'form_token': token, 'action': 'calculate', 'weight_basis': 'ideal_body_weight_devine',
                'cl_form': 'linear_multiplicative', 'disease': 'MM', 'horizon': '24', 'events': '0, 25',
                'source_ref': 'Invented request for page test'}
        after = self.client.post(page, data=data).get_data(as_text=True)
        for text in shared + ('Lenalidomide population PK (Hughes et al. 2019)', 'done exploratory', 'moderate and severe under-predicted'):
            self.assertIn(text, after)
        self.assertIn('hughes_renal_group_check_v1.json', after)

        token = re.search(r'name="form_token" value="([^"]+)"', after).group(1)
        compared = self.client.post(page, data=dict(data, form_token=token, action='models', events='0, 5')).get_data(as_text=True)
        for text in ('Run record: relative odds', 'Relative odds versus a reference exposure', 'ro-run-record-heading',
                     'Lenalidomide exposure-safety odds ratios', 'not independent confirmation', 'Exposure-safety evidence'):
            self.assertIn(text, compared)
        self.assertEqual(compared.count('id="ro-run-record-heading"'), 1)
        self.assertNotIn('id="run-record-heading"', compared)
        data.update(action='save_kim', events='0, 5', title='Kim for record')
        saved = self.client.post(page, data=dict(data, form_token=re.search(r'name="form_token" value="([^"]+)"', compared).group(1)))
        kim = self.client.get(saved.headers['Location']).get_data(as_text=True)
        for text in shared + ('Lenalidomide population PK in renal impairment', 'linear multiplicative', 'Archived treatment request'):
            self.assertIn(text, kim)


if __name__ == '__main__':
    unittest.main()
