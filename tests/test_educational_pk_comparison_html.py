"""Exported curves preserve source/audit restrictions and escape input text."""
import copy
from html.parser import HTMLParser
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import test_educational_pk_comparison_summary as fixtures
from intelligence_store.educational_pk_comparison_summary import register_educational_pk_comparison_summary_commands
from intelligence_store.educational_pk_comparison_html import render_comparison_html
from intelligence_store.educational_pk_runs import save_pk_run,export_pk_run
from intelligence_store.pk_model_inputs import model_input_example
from intelligence_store.treatment_requests import treatment_request_example
from intelligence_store.patient_state import digest

class DocumentParser(HTMLParser):
    def __init__(self):super().__init__();self.polylines=[];self.remote=[];self.scripts=0
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag=='polyline':self.polylines.append(attrs)
        if tag=='script':self.scripts+=1
        for key in ('src','href'):
            if key in attrs and attrs[key].startswith(('http:','https:','//')):self.remote.append(attrs[key])

class EducationalPKComparisonHTMLTests(unittest.TestCase):
    setUp=fixtures.EducationalPKComparisonSummaryTests.setUp
    tearDown=fixtures.EducationalPKComparisonSummaryTests.tearDown
    save_scenario=fixtures.EducationalPKComparisonSummaryTests.save_scenario
    baseline=fixtures.EducationalPKComparisonSummaryTests.baseline
    save=fixtures.EducationalPKComparisonSummaryTests.save
    pair=fixtures.EducationalPKComparisonSummaryTests.pair
    summary=fixtures.EducationalPKComparisonSummaryTests.summary

    def test_curves_metrics_hashes_and_no_remote_assets_or_execution(self):
        a,b=self.pair();summary=self.summary(a,b);before=(export_pk_run(a.id),export_pk_run(b.id))
        with patch('socket.socket.connect',side_effect=AssertionError('No network')),patch('intelligence_store.educational_pk.solve_transit',side_effect=AssertionError('No solver')):
            html=render_comparison_html(summary)
        parser=DocumentParser();parser.feed(html)
        self.assertEqual(len(parser.polylines),2);self.assertEqual(len(parser.polylines[0]['points'].split()),721)
        self.assertEqual(parser.remote,[]);self.assertEqual(parser.scripts,0)
        for text in ('Clinical prediction validated: false','Maximum among archived concentration samples','right minus left',summary['report_sha256'],summary['left_source']['payload_sha256']):self.assertIn(text,html)
        self.assertEqual((export_pk_run(a.id),export_pk_run(b.id)),before)

    def test_source_text_is_escaped(self):
        self.baseline();request=treatment_request_example();request['source_ref']='<script>alert(2)</script>'
        a=save_pk_run(self.revision.id,model_input_example(),request,'MM',title='<script>alert(1)</script>')
        html=render_comparison_html(self.summary(a,a))
        self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;',html);self.assertIn('&lt;script&gt;alert(2)&lt;/script&gt;',html)
        self.assertNotIn('<script>',html)

    def test_summary_or_source_binding_change_stops_render(self):
        a,b=self.pair();summary=self.summary(a,b)
        altered=copy.deepcopy(summary);altered['metrics'][0]['right']=999
        with self.assertRaisesRegex(ValueError,'digest differs'):render_comparison_html(altered)
        altered=copy.deepcopy(summary);altered['source_comparison_sha256']='0'*64
        altered['report_sha256']=digest({k:v for k,v in altered.items() if k!='report_sha256'})
        with self.assertRaisesRegex(ValueError,'differs from'):render_comparison_html(altered)

    def test_withheld_comparison_has_no_curves_or_metrics(self):
        a,b=self.pair();request=treatment_request_example();request['horizon']['value']=48
        other=save_pk_run(self.revision.id,model_input_example(),request,'MM',title='Short window')
        html=render_comparison_html(self.summary(a,other));parser=DocumentParser();parser.feed(html)
        self.assertEqual(parser.polylines,[]);self.assertIn('Numerical comparison withheld',html)
        self.assertIn('time_grid',html)

    def test_cli_exports_exclusively_and_rejects_multiple_output_modes(self):
        a,b=self.pair();register_educational_pk_comparison_summary_commands(self.app);runner=self.app.test_cli_runner()
        args=['patient-pk-comparison-summary','--revision-id',str(self.revision.id),'--left',str(a.id),'--right',str(b.id)]
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'comparison.html';result=runner.invoke(args=args+['--html-output',str(p)])
            self.assertEqual(result.exit_code,0,result.output);before=p.read_bytes();self.assertIn(b'<svg',before)
            self.assertNotEqual(runner.invoke(args=args+['--html-output',str(p)]).exit_code,0);self.assertEqual(p.read_bytes(),before)
            self.assertNotEqual(runner.invoke(args=args+['--html-output',str(p),'--json']).exit_code,0)
            self.assertNotEqual(runner.invoke(args=args+['--html-output',str(p),'--output',str(p)]).exit_code,0)

if __name__=='__main__':unittest.main()
