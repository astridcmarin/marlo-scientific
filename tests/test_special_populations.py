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


class Page(unittest.TestCase):
    def setUp(self):
        from app.app import app
        self.client = app.test_client()

    def test_pages(self):
        from landscape_ui.special_population_pages import fmt_value
        self.assertEqual(fmt_value([1.39, 0.88, 2.2]), '1.39 (90% CI 0.88–2.20)')
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
