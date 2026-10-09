"""Retained event snapshots are distinct from sampled after-request values."""
import copy
import importlib.util
from pathlib import Path
import unittest
from flask import Flask, render_template
from jinja2 import FileSystemLoader

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('dose_timeline_projection',ROOT/'landscape_ui/pk_compartment_timeline.py')
view=importlib.util.module_from_spec(spec);spec.loader.exec_module(view)


def point(t,first,central,eliminated,requested,concentration=0,auc=0):
    return {'time_h':t,'precentral_amounts_mg':[first]+[0]*7,'central_amount_mg':central,
            'eliminated_amount_mg':eliminated,'cumulative_requested_amount_mg':requested,
            'concentration_ng_ml':concentration,'auc_0_t_ng_h_ml':auc}


def report():
    first=point(0,25,0,0,25)
    later=point(24,35,5,10,50,70,20)
    return {'method_version':'hughes-educational-pk-v1.0','status':'completed_educational_calculation',
            'point_amount_order':view.ORDER[:],
            'points':[first,point(.1,10,5,10,25,70,3),later],
            'preflight_review':{'treatment_request_preview':{'request':{'events':[
                {'time':{'value':0},'amount':{'value':25}},
                {'time':{'value':24},'amount':{'value':25}}]}}},
            'event_boundaries':[
                {'time_h':0,'amount_mg':25,'before':point(0,0,0,0,0),'after':copy.deepcopy(first)},
                {'time_h':24,'amount_mg':25,'before':point(24,10,5,10,25,70,20),'after':copy.deepcopy(later)}]}


class DoseEventTimelineTests(unittest.TestCase):
    def test_exact_retained_before_after_index_and_no_mutation(self):
        archived=report(); original=copy.deepcopy(archived)
        result=view.build_compartment_timeline(archived)
        self.assertTrue(result['available']);self.assertTrue(result['events']['available'])
        events=result['events']['items']
        self.assertEqual([e['index'] for e in events],[0,2])
        self.assertEqual(events[0]['before']['requested_mg'],0)
        self.assertEqual(events[0]['after']['amounts_mg'][0],25)
        self.assertEqual(events[1]['before']['amounts_mg'][0],10)
        self.assertEqual(events[1]['after']['amounts_mg'][0],35)
        self.assertEqual(events[1]['after'],result['points'][2])
        self.assertEqual(archived,original)

    def test_request_time_concentration_auc_and_central_are_continuous(self):
        events=view.build_compartment_timeline(report())['events']['items']
        for e in events:
            self.assertEqual(e['before']['concentration_ng_ml'],e['after']['concentration_ng_ml'])
            self.assertEqual(e['before']['auc_ng_h_ml'],e['after']['auc_ng_h_ml'])
            self.assertEqual(e['before']['amounts_mg'][8:],e['after']['amounts_mg'][8:])
            self.assertEqual(e['after']['requested_mg']-e['before']['requested_mg'],e['amount_mg'])

    def test_missing_or_subset_boundaries_withhold_only_event_controls(self):
        for mode in ('missing','subset'):
            archived=report()
            if mode=='missing':del archived['event_boundaries']
            else:archived['event_boundaries']=archived['event_boundaries'][:1]
            result=view.build_compartment_timeline(archived)
            self.assertTrue(result['available']);self.assertFalse(result['events']['available'])
            self.assertEqual(result['events']['items'],[])
            self.assertEqual(len(result['points']),3)

    def test_wrong_amount_duplicate_time_or_non_sample_time_withhold_events(self):
        for field,value in [('amount_mg',26),('time_h',0),('time_h',23.999),('amount_mg',True)]:
            archived=report();archived['event_boundaries'][1][field]=value
            result=view.build_compartment_timeline(archived)
            self.assertTrue(result['available']);self.assertFalse(result['events']['available'])

    def test_mismatched_after_snapshot_and_impossible_jump_withhold(self):
        archived=report(); archived['event_boundaries'][1]['after']['concentration_ng_ml']=71
        self.assertFalse(view.build_compartment_timeline(archived)['events']['available'])
        archived=report()
        # Keep before mass balanced but move central amount at the request instant.
        archived['event_boundaries'][1]['before']['central_amount_mg']=4
        archived['event_boundaries'][1]['before']['precentral_amounts_mg'][0]=11
        self.assertFalse(view.build_compartment_timeline(archived)['events']['available'])
        archived=report();archived['event_boundaries'][1]['before']['auc_0_t_ng_h_ml']=19
        self.assertFalse(view.build_compartment_timeline(archived)['events']['available'])

    def test_template_has_jump_and_phase_controls_and_safe_missing_fallback(self):
        app=Flask(__name__);app.jinja_loader=FileSystemLoader(ROOT/'landscape_ui/templates')
        app.add_url_rule('/assets/<path:filename>','landscape.static',lambda filename:'')
        with app.test_request_context():
            html=render_template('pk_compartment_timeline.html',timeline=view.build_compartment_timeline(report()))
            self.assertEqual(html.count('data-pk-jump='),2)
            self.assertIn('Before request',html);self.assertIn('After request',html)
            self.assertIn('data-pk-events',html);self.assertIn('not a confirmed administration',html)
            archived=report();del archived['event_boundaries']
            html=render_template('pk_compartment_timeline.html',timeline=view.build_compartment_timeline(archived))
            self.assertNotIn('data-pk-jump=',html)
            self.assertNotIn('data-pk-phase',html)
            self.assertIn('request-time controls are withheld',html)
            self.assertIn('type="range"',html)


if __name__=='__main__':unittest.main()
