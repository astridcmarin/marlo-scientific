import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('metadata_cli',ROOT/'scripts/review_lenalidomide_assay_metadata.py')
tool=importlib.util.module_from_spec(spec);spec.loader.exec_module(tool)


class MetadataTests(unittest.TestCase):
    def test_time_conversion_groups_and_preserved_unknowns(self):
        report=tool.build_report();p=report['assay_metadata'];a=p['assay']
        self.assertEqual(a['sampling_times_h'],[t/60 for t in a['sampling_time_provenance']['original_values']])
        self.assertEqual(len(a['groups']),4)
        self.assertEqual(a['loading_control'],'Vinculin')
        self.assertEqual(a['protein_measurements'],[])
        self.assertIsNone(a['replicate_count']);self.assertIsNone(a['normalization_method'])
        self.assertIsNone(a['assay_medium']);self.assertFalse(p['model_assessment']['data_ready_for_fitting'])
        self.assertEqual(report['local_source_checks']['main']['status'],'not_checked')

    def test_matching_sources_wrong_role_and_mismatch(self):
        p=json.loads(tool.PACKET_PATH.read_text())
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);main=root/'main.pdf';supp=root/'supp.pdf';packet=root/'metadata.json'
            main.write_bytes(b'main fixture');supp.write_bytes(b'supplement fixture')
            p['source']['source_bytes_sha256']=tool.file_sha(main)
            p['supplement']['source_bytes_sha256']=tool.file_sha(supp)
            packet.write_text(json.dumps(p))
            with patch.object(tool,'PACKET_PATH',packet):
                report=tool.build_report(main,supp)
                self.assertTrue(all(c['status']=='matches_inspected_source' for c in report['local_source_checks'].values()))
                with self.assertRaises(ValueError):tool.build_report(main,main)
                with self.assertRaises(ValueError):tool.build_report(supp,main)

    def test_export_roundtrip_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            output=Path(folder)/'review.json'
            command=[sys.executable,str(ROOT/'scripts/review_lenalidomide_assay_metadata.py'),'--json','--output',str(output)]
            first=subprocess.run(command,text=True,capture_output=True)
            self.assertEqual(first.returncode,0,first.stderr)
            self.assertEqual(json.loads(first.stdout),json.loads(output.read_text()))
            old=output.read_bytes();again=subprocess.run(command,text=True,capture_output=True)
            self.assertNotEqual(again.returncode,0);self.assertEqual(output.read_bytes(),old)

    def test_promoted_readiness_and_equal_source_identities_rejected(self):
        p=json.loads(tool.PACKET_PATH.read_text())
        with tempfile.TemporaryDirectory() as folder:
            packet=Path(folder)/'metadata.json'
            with patch.object(tool,'PACKET_PATH',packet):
                for key in ['clinical_prediction_validated','ready_for_patient_simulation']:
                    changed=copy.deepcopy(p);changed[key]=True;packet.write_text(json.dumps(changed))
                    with self.assertRaises(ValueError):tool.build_report()
                changed=copy.deepcopy(p);changed['supplement']['source_bytes_sha256']=changed['source']['source_bytes_sha256'];packet.write_text(json.dumps(changed))
                with self.assertRaises(ValueError):tool.build_report()


if __name__=='__main__':unittest.main()
