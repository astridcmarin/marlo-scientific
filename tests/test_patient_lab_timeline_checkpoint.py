"""File checkpoint failures, CSV matching, pending review and no-overwrite behavior."""
import copy
import csv
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout,redirect_stderr

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('timeline_checkpoint',ROOT/'scripts/verify_patient_lab_timeline.py')
tool=importlib.util.module_from_spec(spec);spec.loader.exec_module(tool)
SOURCE=Path(os.environ.get('TIMELINE_CHECKPOINT_TEST_PROJECT_ROOT',ROOT))


def archive():
    before={'time_h':0,'precentral_amounts_mg':[0]*8,'central_amount_mg':0,'eliminated_amount_mg':0,
        'cumulative_requested_amount_mg':0,'concentration_ng_ml':0,'auc_0_t_ng_h_ml':0}
    first={**before,'precentral_amounts_mg':[25]+[0]*7,'cumulative_requested_amount_mg':25}
    later={**first,'time_h':.1,'precentral_amounts_mg':[10]+[0]*7,'central_amount_mg':5,
        'eliminated_amount_mg':10,'concentration_ng_ml':70.12345678901234,'auc_0_t_ng_h_ml':3}
    treatment={'request':{'events':[{'time':{'value':0},'amount':{'value':25}}]}}
    treatment['report_sha256']=tool.digest(treatment)
    binding={'revision_id':3,'scenario_id':2,'revision_payload_sha256':'c'*64}
    review={'binding':binding,'binding_sha256':tool.digest(binding),'treatment_request_preview':treatment}
    review['report_sha256']=tool.digest(review)
    report={'method_version':'hughes-educational-pk-v1.0','status':'completed_educational_calculation',
        'clinical_prediction_validated':False,'ready_for_patient_simulation':False,
        'solver_method_version':'rk4-v1.0','execution_contract_sha256':'d'*64,
        'point_amount_order':['ABS']+[f'TRANS{i}' for i in range(1,8)],'points':[first,later],
        'event_boundaries':[{'time_h':0,'amount_mg':25,'before':before,'after':first}],
        'preflight_review':review,'preflight_report_sha256':review['report_sha256']}
    report['report_sha256']=tool.digest(report)
    p={'schema_version':'saved-educational-pk-run-v1','revision_id':3,'title':'Synthetic fixture',
        'identity':{'revision_id':3,'title':'Synthetic fixture','report_sha256':report['report_sha256']},'report':report}
    return {'run_id':1,'payload':p,'payload_sha256':tool.digest(p)}


class TimelineCheckpointTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.manifest=ROOT/'scripts/patient_lab_timeline_assets_v1.json'
        for relative in tool.read_json(self.manifest)['assets']:
            destination=self.root/relative;destination.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(SOURCE/relative,destination)
        (self.root/'landscape_ui/educational_pk_run_pages.py').write_text(
            'from .pk_compartment_timeline import build_compartment_timeline\ntimeline=build_compartment_timeline(report)')
        (self.root/'landscape_ui/templates/landscape_saved_pk_run.html').write_text(
            '{% include "pk_compartment_timeline.html" %}<svg data-pk-archive-chart="{{ chart.unit }}">')
        self.data=archive();self.archive=self.root/'archive.json';self.write_archive()

    def write_archive(self): self.archive.write_text(json.dumps(self.data))
    def verify(self,csv_path=None): return tool.checkpoint(self.root,self.archive,self.manifest,csv_path)

    def test_pass_is_explicitly_browser_and_science_pending_no_file_writes(self):
        files={str(p.relative_to(self.root)):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        report=self.verify()
        self.assertEqual(report['status'],'static_and_archive_checks_passed_browser_review_pending')
        self.assertEqual(report['details']['sampled_points'],2)
        self.assertEqual(report['details']['request_boundaries'],1)
        self.assertIs(report['clinical_prediction_validated'],False)
        self.assertEqual(report['browser_review_status'],'not_verified')
        self.assertEqual(report['checks'][-1]['status'],'pending')
        self.assertEqual(files,{str(p.relative_to(self.root)):p.read_bytes() for p in self.root.rglob('*') if p.is_file()})

    def test_asset_change_and_missing_hooks_fail_without_loading_projection(self):
        path=self.root/'landscape_ui/pk_compartment_timeline.py'
        path.write_text('raise RuntimeError("must never execute changed code")')
        report=self.verify();self.assertEqual(report['status'],'checkpoint_failed')
        self.assertNotIn('sampled_points',report['details'])
        (self.root/'landscape_ui/templates/landscape_saved_pk_run.html').write_text('custom unsupported layout')
        report=self.verify();self.assertEqual(report['checks'][1]['status'],'failed')

    def test_archive_corruption_nested_mismatch_and_true_readiness_fail(self):
        for change in ('payload','nested','readiness'):
            self.data=archive()
            if change=='payload':self.data['payload']['title']='changed'
            if change=='nested':
                self.data['payload']['report']['points'][0]['concentration_ng_ml']=1
                self.data['payload_sha256']=tool.digest(self.data['payload'])
            if change=='readiness':
                report=self.data['payload']['report'];report['clinical_prediction_validated']=True
                report.pop('report_sha256');report['report_sha256']=tool.digest(report)
                self.data['payload']['identity']['report_sha256']=report['report_sha256']
                self.data['payload_sha256']=tool.digest(self.data['payload'])
            self.write_archive();self.assertEqual(self.verify()['status'],'checkpoint_failed')

    def csv_fixture(self):
        report,m=tool.archive_context(self.data)
        # Independently assembled CSV using explicit columns and source values.
        prefix=['archived-pk-timeline-csv-v1','synthetic_educational','false','false','1','2','3',
            m['payload_sha256'],m['report_sha256'],'c'*64,'d'*64,m['method_version'],m['solver_method_version'],'available']
        points=[report['event_boundaries'][0]['before'],*report['points']]
        rows=[tool.HEADERS]
        for p,index,state,amount in zip(points,[0,0,1],['boundary_before_request','sampled_after_request','sampled'],[25,25,'']):
            rows.append(prefix+[index,state,amount,p['time_h'],*p['precentral_amounts_mg'],p['central_amount_mg'],
                p['eliminated_amount_mg'],p['concentration_ng_ml'],p['auc_0_t_ng_h_ml'],
                p['cumulative_requested_amount_mg'],p['cumulative_requested_amount_mg']])
        return rows

    def test_csv_exact_match_then_wrong_value_state_order_and_missing_row_fail(self):
        path=self.root/'download.csv';rows=self.csv_fixture()
        def write(rows):
            with path.open('w',newline='') as stream:csv.writer(stream).writerows(rows)
        write(rows);report=self.verify(path)
        self.assertEqual(report['details']['verified_csv_rows'],3)
        self.assertEqual(report['checks'][-1]['status'],'passed')
        for mutation in ('value','state','order','missing'):
            changed=copy.deepcopy(rows)
            if mutation=='value':changed[-1][tool.HEADERS.index('concentration_ng_ml')]=70
            if mutation=='state':changed[1][tool.HEADERS.index('state')]='sampled'
            if mutation=='order':changed[1],changed[2]=changed[2],changed[1]
            if mutation=='missing':changed.pop()
            write(changed);self.assertEqual(self.verify(path)['status'],'checkpoint_failed')

    def test_duplicate_json_and_nonfinite_values_rejected(self):
        for text in ('{"a":1,"a":2}','{"a":NaN}'):
            self.archive.write_text(text)
            self.assertEqual(self.verify()['status'],'checkpoint_failed')

    def test_cli_never_overwrites_and_failure_exit_is_nonzero(self):
        output=self.root/'checkpoint.json';output.write_text('keep')
        args=['--project-root',str(self.root),'--archive-file',str(self.archive),'--manifest',str(self.manifest),'--output',str(output)]
        with redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()):self.assertEqual(tool.main(args),1)
        self.assertEqual(output.read_text(),'keep')
        output.unlink()
        with redirect_stdout(io.StringIO()):self.assertEqual(tool.main(args),0)
        self.assertIs(tool.read_json(output)['patient_simulation_ready'],False)


if __name__=='__main__':unittest.main()
