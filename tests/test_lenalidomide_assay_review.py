import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('assay_cli',ROOT/'scripts/review_lenalidomide_assay.py')
cli=importlib.util.module_from_spec(spec);spec.loader.exec_module(cli)
model=cli._load()


class AssayReviewTests(unittest.TestCase):
    def test_unknown_measurements_are_preserved_and_report_integrity(self):
        old=model.REVIEW_PATH.read_bytes();report=model.build_assay_review();packet=report['assay_extraction']
        self.assertEqual(packet['assay']['protein_measurements'],[])
        self.assertIsNone(packet['assay']['sampling_times_h'])
        self.assertIsNone(packet['assay']['replicate_count'])
        self.assertFalse(packet['supplement']['reviewed'])
        self.assertEqual(report['packet_sha256'],hashlib.sha256(old).hexdigest())
        self.assertFalse(report['ready_for_patient_simulation'])
        self.assertEqual(report,model.build_assay_review());self.assertEqual(old,model.REVIEW_PATH.read_bytes())
        digest=report.pop('report_sha256')
        self.assertEqual(digest,hashlib.sha256(json.dumps(report,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest())

    def test_units_duplicates_nonfinite_and_measurement_promotions_rejected(self):
        packet=json.loads(model.REVIEW_PATH.read_text());variants=[]
        for value in [True,'2',float('inf'),-1]:
            p=copy.deepcopy(packet);p['assay']['conditions'][0]['value']=value;variants.append(p)
        p=copy.deepcopy(packet);p['assay']['conditions'][0]['unit']='mmol/L';variants.append(p)
        p=copy.deepcopy(packet);p['assay']['conditions'][1]=p['assay']['conditions'][0];variants.append(p)
        p=copy.deepcopy(packet);p['assay']['protein_measurements']=[{'value':0}];variants.append(p)
        p=copy.deepcopy(packet);p['model_assessment']['data_ready_for_fitting']=True;variants.append(p)
        p=copy.deepcopy(packet);p['model_assessment']['pk_run_id']=1;variants.append(p)
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'packet.json'
            with patch.object(model,'REVIEW_PATH',source):
                for p in variants:
                    source.write_text(json.dumps(p))
                    with self.assertRaises(ValueError):model.build_assay_review()
                for raw in ['{"a":1,"a":2}','[]','{']:
                    source.write_text(raw)
                    with self.assertRaises(ValueError):model.build_assay_review()

    def test_zero_condition_value_is_not_converted_to_unknown(self):
        packet=json.loads(model.REVIEW_PATH.read_text())
        packet['assay']['conditions'][1]['value']=0
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'packet.json';source.write_text(json.dumps(packet))
            with patch.object(model,'REVIEW_PATH',source):
                self.assertEqual(model.build_assay_review()['assay_extraction']['assay']['conditions'][1]['value'],0)

    def test_standalone_json_export_and_overwrite_protection(self):
        with tempfile.TemporaryDirectory() as folder:
            output=Path(folder)/'review.json'
            command=[sys.executable,str(ROOT/'scripts/review_lenalidomide_assay.py'),'--json','--output',str(output)]
            result=subprocess.run(command,text=True,capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(result.stdout),json.loads(output.read_text()))
            old=output.read_bytes();again=subprocess.run(command,text=True,capture_output=True)
            self.assertNotEqual(again.returncode,0);self.assertEqual(output.read_bytes(),old)


if __name__=='__main__':unittest.main()
