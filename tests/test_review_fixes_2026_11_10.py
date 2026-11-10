"""Provenance fixes after the AI review of 10 November 2026 (docs/reviews/2026-11_fable_review.md)."""
import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOTES = ROOT / 'intelligence_store' / 'data' / 'lenalidomide_source_notes_v1.json'


def resolve(doc, pointer):
    for part in pointer.lstrip('/').split('/'):
        doc = doc[int(part)] if isinstance(doc, list) else doc[part]
    return doc


class SourceNotes(unittest.TestCase):
    def setUp(self):
        from intelligence_store.source_notes import load_source_notes
        self.notes = load_source_notes()

    def test_changed_notes_are_refused(self):
        import tempfile
        from intelligence_store.source_notes import load_source_notes
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / NOTES.name
            path.write_bytes(NOTES.read_bytes() + b' ')
            with self.assertRaises(ValueError):
                load_source_notes(path)

    def test_every_note_points_at_a_pinned_value_that_exists(self):
        self.assertEqual(self.notes['schema_version'], 'source-notes-v1')
        for note in self.notes['notes']:
            for key in ('concerns', 'also'):
                if key in note:
                    ref = note[key]
                    raw = (ROOT / ref['file']).read_bytes()
                    self.assertEqual(hashlib.sha256(raw).hexdigest(), ref['sha256'], note['id'])
                    resolve(json.loads(raw), ref['pointer'])
        self.assertFalse(self.notes['clinical_prediction_validated'])

    def test_the_noted_values_are_the_ones_described(self):
        by_id = {n['id']: n for n in self.notes['notes']}
        value = lambda n, k='concerns': resolve(json.loads((ROOT / by_id[n][k]['file']).read_text()), by_id[n][k]['pointer'])
        self.assertEqual(value('ema_2008_severe_clf_sd_misprint'), [52, 101])
        self.assertEqual(value('esrd_on_dialysis_auc_two_sources')[0], 6778)
        self.assertEqual(value('esrd_on_dialysis_auc_two_sources', 'also')['geometric_mean'], 6776)
        self.assertEqual(value('bridoux_total_age_misprint'), [68, 62, 74])


class GuidanceSourceMarker(unittest.TestCase):
    def test_fda_extracts_without_a_local_file_are_marked_not_pinned(self):
        from intelligence_store import hepatic_classifications, kidney_function_classifications
        self.assertFalse(kidney_function_classifications.build()['guidance_source_pinned'])
        self.assertFalse(hepatic_classifications.build()['guidance']['source_pinned'])


class QuoteScript(unittest.TestCase):
    def test_quotes_are_found_in_a_text_source(self):
        import importlib.util
        import tempfile
        spec = importlib.util.spec_from_file_location('check_source_quotes', ROOT / 'scripts' / 'check_source_quotes.py')
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / 'source.txt'
            src.write_text('The clearance was\n  12.0 L/h in the final model.')
            ext = Path(tmp) / 'extract.json'
            ext.write_text(json.dumps({'a': {'row_quote': 'clearance was 12.0 L/h'}, 'quotes': ['not in the source']}))
            out = mod.check(ext, src)
        self.assertEqual(out['results'], [('/a/row_quote', True), ('/quotes/0', False)])


if __name__ == '__main__':
    unittest.main()
