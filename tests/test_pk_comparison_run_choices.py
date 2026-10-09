"""Revision-scoped archive choices; no selection implies a compatible pair."""
from html.parser import HTMLParser
import unittest
from unittest.mock import patch
from sqlalchemy import select
import test_educational_pk_comparison as fixtures
from intelligence_store.extensions import db
from intelligence_store.patient_state_revisions import save_revision
from intelligence_store.educational_pk_runs import save_pk_run
from intelligence_store.pk_model_inputs import model_input_example
from intelligence_store.treatment_requests import treatment_request_example


class Selects(HTMLParser):
    def __init__(self, text):
        super().__init__(); self.fields={}; self.current=None
        self.feed(text)
    def handle_starttag(self, tag, attrs):
        attrs=dict(attrs)
        if tag=='select':
            self.current=attrs['name']; self.fields[self.current]=[]
        elif tag=='option' and self.current:
            self.fields[self.current].append(attrs)
    def handle_endtag(self, tag):
        if tag=='select': self.current=None


class PKComparisonRunChoiceTests(unittest.TestCase):
    setUp=fixtures.EducationalPKComparisonTests.setUp
    tearDown=fixtures.EducationalPKComparisonTests.tearDown
    save_scenario=fixtures.EducationalPKComparisonTests.save_scenario
    baseline=fixtures.EducationalPKComparisonTests.baseline
    save=fixtures.EducationalPKComparisonTests.save
    pair=fixtures.EducationalPKComparisonTests.pair

    def url(self, a=None, b=None):
        path=f'/landscape/workspace/scenarios/{self.scenario.id}/patient-state/revisions/{self.revision.id}/pk-runs/compare'
        return path if a is None else path+f'?left={a.id}&right={b.id}'

    def tables(self):
        return {t.name:sorted(repr(dict(r)) for r in db.session.execute(select(t)).mappings())
                for t in db.metadata.sorted_tables}

    def test_choices_show_titles_timestamps_and_preserve_pair_selection_without_writes(self):
        a,b=self.pair();before=self.tables()
        with patch('socket.socket.connect',side_effect=AssertionError('No network')), patch('intelligence_store.educational_pk.solve_transit',side_effect=AssertionError('No solver')):
            response=self.client.get(self.url(a,b))
        self.assertEqual(response.status_code,200)
        text=response.get_data(as_text=True);fields=Selects(text).fields
        for side,chosen in [('left',a),('right',b)]:
            self.assertEqual([x['value'] for x in fields[side]],['',str(b.id),str(a.id)])
            self.assertEqual([x['value'] for x in fields[side] if 'selected' in x],[str(chosen.id)])
            self.assertIn(chosen.created_at_utc.isoformat()+'Z',text)
            self.assertIn(chosen.title,text)
        self.assertEqual(text.count('data-metric='),7)
        self.assertEqual(text.count('<polyline '),2)
        self.assertEqual(self.tables(),before)

    def test_blank_form_has_no_automatic_selection_and_empty_record_has_no_dead_form(self):
        self.baseline();text=self.client.get(self.url()).get_data(as_text=True)
        self.assertIn('No saved runs for this patient-state record',text)
        self.assertNotIn('<select ',text);self.assertNotIn('name="left"',text)
        a=self.save();text=self.client.get(self.url()).get_data(as_text=True)
        for options in Selects(text).fields.values():
            self.assertEqual([x['value'] for x in options],['',str(a.id)])
            self.assertFalse(any('selected' in x for x in options))
        self.assertNotIn('<polyline ',text)
        # Self comparison is intentional and audited, not prevented by the chooser.
        response=self.client.get(self.url(a,a))
        self.assertEqual(response.status_code,200)
        self.assertIn('No declared numerical input change',response.get_data(as_text=True))

    def test_other_revisions_are_excluded_and_cannot_be_compared(self):
        a,b=self.pair()
        other_revision=save_revision(self.scenario.id,self.base,parent_revision_id=self.revision.id,title='Separate state record')
        other=save_pk_run(other_revision.id,model_input_example(),treatment_request_example(),'MM',title='Other record archive')
        text=self.client.get(self.url()).get_data(as_text=True)
        self.assertNotIn('Other record archive',text)
        for options in Selects(text).fields.values():
            self.assertNotIn(str(other.id),[x['value'] for x in options])
        self.assertEqual(self.client.get(self.url(a,other)).status_code,409)

    def test_choice_limit_keeps_older_selected_runs_and_manual_id_fallback(self):
        a,b=self.pair()
        with patch('landscape_ui.educational_pk_compare_pages.CHOICE_LIMIT',1):
            text=self.client.get(self.url()).get_data(as_text=True)
            for options in Selects(text).fields.values():
                self.assertEqual([x['value'] for x in options],['',str(b.id)])
            self.assertIn('newest 1 of 2',text)
            self.assertIn('Compare using run IDs',text)
            text=self.client.get(self.url(a,b)).get_data(as_text=True)
            for options in Selects(text).fields.values():
                self.assertEqual([x['value'] for x in options],['',str(b.id),str(a.id)])
            self.assertEqual(sum('selected' in option for options in Selects(text).fields.values() for option in options),2)

    def test_titles_are_escaped_and_json_downloads_do_not_load_chooser(self):
        self.baseline();a=self.save('<img src=x onerror=alert(1)>')
        text=self.client.get(self.url()).get_data(as_text=True)
        self.assertNotIn('<img src=x',text);self.assertIn('&lt;img src=x',text)
        with patch('landscape_ui.educational_pk_compare_pages._run_choices',side_effect=AssertionError('JSON needs no chooser')):
            for mode in ('json','summary-json'):
                response=self.client.get(self.url(a,a)+'&format='+mode)
                self.assertEqual(response.status_code,200)
                self.assertEqual(response.headers['Cache-Control'],'no-store')
                self.assertFalse(response.get_json()['clinical_prediction_validated'])


if __name__=='__main__':unittest.main()
