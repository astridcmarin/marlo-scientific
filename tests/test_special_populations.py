"""Phase 4.2: special-population evidence summaries."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from intelligence_store import special_populations as sp

ROOT = Path(__file__).resolve().parent.parent


class Summaries(unittest.TestCase):
    def test_every_summary_builds_and_every_value_matches_its_source(self):
        for drug in sp.available():
            view = sp.build(drug)
            self.assertEqual([r['domain'] for r in view['rows']], list(sp.DOMAINS))
            self.assertFalse(view['clinical_prediction_validated'])
            for row in view['rows']:
                for st in row['statements']:
                    self.assertIn(st['kind'], sp.KINDS)
                    if st['kind'] != 'gap':
                        self.assertIn('pointer', st['source'])

    def test_sources_are_the_files_the_platform_pins(self):
        """A summary may only cite a source file whose checksum some platform module already pins."""
        modules = [p.read_text(encoding='utf-8') for p in (ROOT / 'intelligence_store').glob('*.py')
                   if p.name != 'special_populations.py']
        for drug in sp.available():
            for ref in sp.load_summary(drug)['sources'].values():
                self.assertTrue(any(ref['sha256'] in m for m in modules), f'{drug}: {ref["file"]} not pinned elsewhere')

    def test_a_changed_value_is_refused(self):
        drug = 'ixazomib'
        name, _ = sp.SUMMARIES[drug]
        data = json.loads((sp.DATA / name).read_text())
        bad = copy.deepcopy(data)
        bad['domains']['kidney'][0]['value'] = [1.0, 0.5, 1.5]
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / name
            raw = (json.dumps(bad) + '\n').encode()
            path.write_bytes(raw)
            import hashlib
            with mock.patch.dict(sp.SUMMARIES, {drug: (name, hashlib.sha256(raw).hexdigest())}), \
                    mock.patch.object(sp, 'DATA', Path(d)):
                with self.assertRaises(sp.SummaryError):
                    sp.build(drug)

    def test_a_changed_summary_file_is_refused(self):
        with mock.patch.dict(sp.SUMMARIES, {'ixazomib': (sp.SUMMARIES['ixazomib'][0], '0' * 64)}):
            with self.assertRaises(sp.SummaryError):
                sp.build('ixazomib')

    def test_pointer_resolution(self):
        doc = {'a': {'b/c': [10, {'d~e': 5}]}}
        self.assertEqual(sp.resolve(doc, '/a/b~1c/1/d~0e'), 5)
        with self.assertRaises(sp.SummaryError):
            sp.resolve(doc, '/a/missing')

    def test_key_findings(self):
        ixa = {r['domain']: r for r in sp.build('ixazomib')['rows']}
        self.assertEqual(ixa['kidney']['statements'][0]['value'], [1.39, 0.88, 2.2])
        self.assertEqual(ixa['liver']['statements'][1]['value'], [1.13, 0.69, 1.84])
        pom = {r['domain']: r for r in sp.build('pomalidomide')['rows']}
        self.assertEqual([s['value'] for s in pom['liver']['statements'] if s['kind'] == 'study_exposure_change'], [1.51, 1.58, 1.72])
        self.assertEqual(pom['age']['statements'][0]['kind'], 'gap')
        len_ = {r['domain']: r for r in sp.build('lenalidomide')['rows']}
        aucs = [s['value'] for s in len_['kidney']['statements'][:4]]
        self.assertEqual(aucs, [2181, 2767, 6021, 8191])                     # CC-5013-PK-001 Table 4
        self.assertEqual([st['kind'] for st in len_['liver']['statements']], ['label_statement', 'not_studied'])
        actions = [st['value'] for st in len_['kidney']['statements'] if st['kind'] == 'label_action']
        self.assertEqual(actions[:3], ['10 mg once daily', '15 mg every other day', '5 mg once daily; on dialysis days, after dialysis'])
        self.assertFalse(any(st['kind'] == 'gap' for r in sp.build('lenalidomide')['rows'] for st in r['statements']))
        dara = {r['domain']: r for r in sp.build('daratumumab')['rows']}
        self.assertEqual(dara['kidney']['statements'][0]['kind'], 'covariate_not_retained')
        self.assertEqual([s['value'] for s in dara['body_size']['statements'][:2]], [1.24, 0.91])
        dex = {r['domain']: r for r in sp.build('dexamethasone')['rows']}
        self.assertEqual(dex['kidney']['statements'][0]['kind'], 'not_studied')
        self.assertEqual(dex['other_covariates']['statements'][2]['value'], [182, 43.8])      # MM-017 CL/F
        btz = {r['domain']: r for r in sp.build('bortezomib')['rows']}
        self.assertEqual(btz['liver']['statements'][0]['value'], 60)                      # 2012 label 12.3
        self.assertEqual(btz['age']['statements'][0]['value'], 25)
        self.assertEqual(btz['kidney']['statements'][2]['value']['dialysis'], 8)

    def test_ixazomib_label_replaces_study_reported_actions(self):
        from intelligence_store.ixazomib_label import load_label_extract
        e = load_label_extract()
        self.assertEqual((e['renal']['auc_increase_percent_severe_esrd'], e['hepatic']['auc_increase_percent_moderate_severe']), (39, 20))
        ixa = {r['domain']: r for r in sp.build('ixazomib')['rows']}
        for dom in ('kidney', 'liver'):
            actions = [st for st in ixa[dom]['statements'] if st['kind'] == 'label_action']
            self.assertEqual([a['value'] for a in actions], [3])
            self.assertEqual(actions[0]['source']['ref'], 'label')
        self.assertIn('cd3b68f8ec285160dadd81140b0d3aae9748971e6176bfef8032564ecc9bf423', sp.SUPERSEDED.values())

    def test_lenalidomide_label_extract_is_pinned(self):
        from intelligence_store.lenalidomide_label import load_label_extract
        e = load_label_extract()
        self.assertEqual(e['multiple_myeloma_dosing']['capsule_strengths_mg'], [2.5, 5, 10, 15, 20, 25])
        self.assertEqual([r['crcl_ml_min'] for r in e['renal_dose_adjustments']['rows']], [[30, 60], [None, 30], [None, 30]])
        self.assertIn('Revised: 3/2023', e['source']['document'])
        self.assertIn('406618748fe544594f44d8b7e6c8cf7c0677138842f4c3715138a0c22ea4e1c8', sp.SUPERSEDED.values())

    def test_lenalidomide_v3_records_the_renal_study_population(self):
        view = sp.build('lenalidomide')
        kidney = {r['domain']: r for r in view['rows']}['kidney']['statements']
        self.assertIn('non-malignant', kidney[0]['population'])
        self.assertIn('non-malignant', view['intro'])
        files = {s['ref']: s['file'] for s in view['sources']}
        self.assertTrue(files['renal'].endswith('renal_pk_group_evidence_v2.json'))
        self.assertTrue(files['hughes_scope'].endswith('lenalidomide_hughes_scope_v2.json'))
        self.assertTrue(files['kim_scope'].endswith('lenalidomide_kim_scope_v3.json'))
        kim_bands = next(st for st in kidney if st['source']['ref'] == 'kim_scope')['value']
        self.assertEqual([b['tier'] for b in kim_bands], ['externally_checked', 'external_check_disagrees', 'external_check_disagrees'])
        self.assertIn('7236f8899c71ff7268db5edffe062dd7a3aa49a0499f3436767f10dcca2e84b3', sp.SUPERSEDED.values())

    def test_bortezomib_label_extract_is_pinned(self):
        from intelligence_store.bortezomib_label_special_populations import load_extract
        e = load_extract()
        self.assertEqual(e['hepatic']['pk_12_3']['n_patients'], 51)
        self.assertIn('rendered page images', e['source']['extraction'])


class Page(unittest.TestCase):
    def setUp(self):
        from app.app import app
        self.client = app.test_client()

    def test_pages(self):
        from landscape_ui.special_population_pages import fmt_value
        self.assertEqual(fmt_value([1.39, 0.88, 2.2]), '1.39 (90% CI 0.88–2.20)')
        self.assertEqual(fmt_value([11121, 2133], 'mean_sd'), '11121 (SD 2133)')
        self.assertEqual(fmt_value([182, 43.8], 'gm_cv'), '182 (CV 43.8%)')
        self.assertEqual(fmt_value([30, 297]), '30–297')
        self.assertEqual(fmt_value([{'range': [50, 211], 'tier': 'externally_checked'}], 'bands'), '50–211: checked against outside data')
        for drug in sp.available():
            r = self.client.get(f'/landscape/drugs/{drug}/special-populations')
            self.assertEqual(r.status_code, 200)
            self.assertIn(b'not dosing guidance', r.data)
            j = self.client.get(f'/landscape/drugs/{drug}/special-populations?format=json')
            self.assertEqual(json.loads(j.data)['drug'], drug)
        page = self.client.get('/landscape/drugs/pomalidomide/special-populations').get_data(as_text=True)
        self.assertIn("Not in the platform", page)
        self.assertEqual(self.client.get('/landscape/drugs/unknown/special-populations').status_code, 404)
        self.assertEqual(self.client.get('/landscape/drugs/ixazomib/special-populations?x=1').status_code, 400)


if __name__ == '__main__':
    unittest.main()
