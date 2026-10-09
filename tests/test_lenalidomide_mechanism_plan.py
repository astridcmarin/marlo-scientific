import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('mechanism_plan_cli',ROOT/'scripts/review_lenalidomide_mechanism.py')
cli=importlib.util.module_from_spec(spec);spec.loader.exec_module(cli)


class MechanismPlanTests(unittest.TestCase):
    def test_claim_source_links_and_unextracted_parameter_contract(self):
        report=cli.build_report();plan=report['evidence_plan']
        for claim in plan['claims']:
            self.assertEqual(claim['source_id'],plan['source']['source_id'])
            self.assertTrue(claim['locator']);self.assertTrue(claim['context'])
        self.assertTrue(all(v is None for v in plan['quantitative_inputs'].values()))
        self.assertIsNone(plan['source']['source_bytes_sha256'])
        self.assertFalse(plan['source']['supplement_reviewed'])
        self.assertEqual(report['simulation_status'],'not_run')
        self.assertFalse(report['ready_for_patient_simulation'])
        self.assertFalse(report['clinical_prediction_validated'])
        self.assertFalse(plan['existing_project_links']['simulation_run'])

    def test_export_roundtrip_and_overwrite_refusal(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'plan.json'
            command=[sys.executable,str(ROOT/'scripts/review_lenalidomide_mechanism.py'),'--json','--output',str(path)]
            result=subprocess.run(command,text=True,capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(result.stdout),json.loads(path.read_text()))
            old=path.read_bytes()
            again=subprocess.run(command,text=True,capture_output=True)
            self.assertNotEqual(again.returncode,0);self.assertEqual(path.read_bytes(),old)

    def test_missing_and_unsupported_packet_fail_without_creating_report(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'source.json';output=Path(folder)/'out.json'
            with patch.object(cli,'PACKET_PATH',source):
                self.assertEqual(cli.main(['--output',str(output)]),1)
                source.write_text('{"schema_version":"unsupported","entity_id":"lenalidomide"}')
                self.assertEqual(cli.main(['--output',str(output)]),1)
            self.assertFalse(output.exists())


if __name__=='__main__':unittest.main()
