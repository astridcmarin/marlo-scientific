"""Archived display projection and safe fallback."""
import copy
import importlib.util
from pathlib import Path
import unittest
from flask import Flask, render_template
from jinja2 import FileSystemLoader

ROOT = Path(__file__).resolve().parents[1]

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module

view = load('timeline_projection', ROOT / 'landscape_ui/pk_compartment_timeline.py')


def archived_report():
    return {'method_version': 'hughes-educational-pk-v1.0', 'status': 'completed_educational_calculation',
            'point_amount_order': view.ORDER[:], 'points': [
                {'time_h': 0, 'precentral_amounts_mg': [25] + [0] * 7, 'central_amount_mg': 0,
                 'eliminated_amount_mg': 0, 'cumulative_requested_amount_mg': 25,
                 'concentration_ng_ml': 0, 'auc_0_t_ng_h_ml': 0},
                {'time_h': .1, 'precentral_amounts_mg': [10] + [0] * 7, 'central_amount_mg': 5,
                 'eliminated_amount_mg': 10, 'cumulative_requested_amount_mg': 25,
                 'concentration_ng_ml': 70, 'auc_0_t_ng_h_ml': 3}]}


class CompartmentTimelineTests(unittest.TestCase):
    def test_exact_projection_and_no_mutation(self):
        report = archived_report(); original = copy.deepcopy(report)
        result = view.build_compartment_timeline(report)
        self.assertTrue(result['available']); self.assertEqual(result['max_index'], 1)
        self.assertEqual(result['points'][1]['amounts_mg'], [10,0,0,0,0,0,0,0,5,10])
        self.assertEqual(result['points'][1]['concentration_ng_ml'], 70)
        self.assertEqual(result['points'][1]['auc_ng_h_ml'], 3)
        self.assertEqual(result['points'][1]['accounted_mg'], 25)
        self.assertEqual(report, original)

    def test_unsupported_structure_and_inconsistent_mass_withhold(self):
        for key, value in [('method_version','other'), ('point_amount_order',view.ORDER[::-1]), ('points',[])]:
            report = archived_report(); report[key] = value
            self.assertFalse(view.build_compartment_timeline(report)['available'])
        report = archived_report(); report['points'][1]['central_amount_mg'] = 6
        self.assertFalse(view.build_compartment_timeline(report)['available'])
        self.assertFalse(view.build_compartment_timeline({})['available'])

    def test_nonfinite_negative_boolean_and_bad_times_withhold(self):
        for value in (float('nan'), float('inf'), -1, True, '2'):
            report = archived_report(); report['points'][1]['concentration_ng_ml'] = value
            self.assertFalse(view.build_compartment_timeline(report)['available'])
        for time in (0, -1, 73):
            report = archived_report(); report['points'][1]['time_h'] = time
            self.assertFalse(view.build_compartment_timeline(report)['available'])
        report = archived_report(); report['points'][1]['precentral_amounts_mg'] = [10]
        self.assertFalse(view.build_compartment_timeline(report)['available'])

    def test_later_request_scale_retained_and_not_future_total(self):
        report = archived_report()
        later = copy.deepcopy(report['points'][1]); later.update(time_h=24, cumulative_requested_amount_mg=50)
        later['precentral_amounts_mg'][0] += 25
        report['points'].append(later)
        result = view.build_compartment_timeline(report)
        self.assertEqual([p['requested_mg'] for p in result['points']], [25,25,50])
        self.assertEqual(result['points'][2]['accounted_mg'], 50)

    def test_template_initial_view_accessibility_and_unavailable_fallback(self):
        app = Flask(__name__); app.jinja_loader = FileSystemLoader(ROOT / 'landscape_ui/templates')
        app.add_url_rule('/assets/<path:filename>', 'landscape.static', lambda filename: '')
        with app.test_request_context():
            html = render_template('pk_compartment_timeline.html', timeline=view.build_compartment_timeline(archived_report()))
            self.assertIn('type="range"', html); self.assertIn('aria-live="polite"', html)
            self.assertEqual(html.count('<progress '), 10)
            self.assertIn('not anatomical organs', html)
            self.assertIn('data-pk-controls hidden', html)
            self.assertIn('type="application/json"', html)
            hidden = render_template('pk_compartment_timeline.html', timeline={'available':False,'reason':'Incomplete archive'})
            self.assertIn('timeline unavailable', hidden)
            self.assertNotIn('type="range"', hidden)
            self.assertNotIn('pk-compartment-timeline.js', hidden)

if __name__ == '__main__': unittest.main()
