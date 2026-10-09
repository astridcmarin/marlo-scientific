"""A file inventory must not become scientific or access-rights acceptance."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from flask import Flask
from intelligence_store.pk_validation_artifacts import (
 artifact_manifest_example,artifact_inventory,register_pk_validation_artifact_commands)
from intelligence_store.patient_state import digest

class PKValidationArtifactTests(unittest.TestCase):
    def test_blank_manifest_inventory_is_missing_and_not_approved(self):
        manifest=artifact_manifest_example();before=copy.deepcopy(manifest)
        with tempfile.TemporaryDirectory() as directory,patch('sqlalchemy.engine.base.Connection.execute',side_effect=AssertionError('No DB')),patch('socket.socket.connect',side_effect=AssertionError('No network')),patch('intelligence_store.educational_pk.solve_transit',side_effect=AssertionError('No solver')):
            report=artifact_inventory(manifest,directory)
        self.assertEqual(report['file_status_counts'],{'not_supplied':8})
        self.assertEqual(report['accepted_artifact_count'],0)
        for flag in ('access_rights_verified','clinical_prediction_validated','ready_for_patient_simulation','database_writes_performed','ode_solver_rerun','network_refresh_performed','data_parsing_performed'):
            self.assertFalse(report[flag])
        self.assertIsNone(report['governance_approval']);self.assertEqual(manifest,before)
        self.assertEqual(digest({k:v for k,v in report.items() if k!='report_sha256'}),report['report_sha256'])

    def test_present_matched_mismatched_missing_and_directory_states(self):
        manifest=artifact_manifest_example();rows=manifest['artifacts']
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory);(p/'data.bin').write_bytes(b'Synthetic artifact, not source evidence')
            sha=hashlib.sha256((p/'data.bin').read_bytes()).hexdigest()
            rows[0].update(file='data.bin',expected_sha256=sha,access_basis='Declared test permission',source_reference='Synthetic reference')
            rows[1].update(file='data.bin',expected_sha256='0'*64)
            rows[2]['file']='missing';rows[3]['file']='data.bin';rows[4]['file']='.'
            report=artifact_inventory(manifest,p)
        states=[r['file_status'] for r in report['artifacts']]
        self.assertEqual(states[:5],['present_digest_matches','digest_mismatch','file_missing','present_digest_not_bound','not_regular_file'])
        self.assertTrue(all(r['accepted_for_validation'] is False for r in report['artifacts']))
        self.assertEqual(report['artifacts'][0]['access_status'],'not_verified')
        self.assertEqual(report['artifacts'][0]['provenance_status'],'not_verified')

    def test_bad_manifest_shapes_and_duplicates_are_rejected(self):
        bad=[]
        m=artifact_manifest_example();m['artifacts'].append(copy.deepcopy(m['artifacts'][0]));bad.append(m)
        m=artifact_manifest_example();m['artifacts'][0]['requirement']='unknown';bad.append(m)
        m=artifact_manifest_example();m['artifacts'][0]['expected_sha256']='0'*64;bad.append(m)
        m=artifact_manifest_example();m['artifacts'][0]['access_basis']=True;bad.append(m)
        m=artifact_manifest_example();m['approval']=True;bad.append(m)
        for manifest in bad:
            with self.subTest(manifest=manifest),self.assertRaises(ValueError):artifact_inventory(manifest,'.')

    def test_absolute_parent_and_symlink_escape_paths_fail_before_read(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);folder=root/'inside';folder.mkdir();outside=root/'outside';outside.write_bytes(b'Test')
            (folder/'link').symlink_to(outside)
            for filename in (str(outside),'../outside','link'):
                m=artifact_manifest_example();m['artifacts'][0]['file']=filename
                with self.subTest(filename=filename),self.assertRaisesRegex(ValueError,'paths|escapes'):
                    artifact_inventory(m,folder)

    def test_model_or_intended_use_change_blocks_report(self):
        for name in ('transcription_review_packet','intended_use_report'):
            with patch('intelligence_store.pk_validation_artifacts.'+name,side_effect=ValueError('Changed contract')):
                with self.assertRaises(ValueError):artifact_inventory(artifact_manifest_example(),'.')

    def test_cli_modes_exports_limits_and_duplicate_json_keys(self):
        app=Flask(__name__);register_pk_validation_artifact_commands(app);runner=app.test_cli_runner()
        self.assertNotEqual(runner.invoke(args=['pk-validation-artifacts']).exit_code,0)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);manifest=root/'manifest.json'
            result=runner.invoke(args=['pk-validation-artifacts','--example','--output',str(manifest)])
            self.assertEqual(result.exit_code,0,result.output);original=manifest.read_bytes()
            self.assertNotEqual(runner.invoke(args=['pk-validation-artifacts','--example','--output',str(manifest)]).exit_code,0)
            self.assertEqual(manifest.read_bytes(),original)
            args=['pk-validation-artifacts','--manifest',str(manifest),'--json']
            result=runner.invoke(args=args);self.assertEqual(result.exit_code,0,result.output)
            self.assertEqual(json.loads(result.output)['file_status_counts'],{'not_supplied':8})
            self.assertNotEqual(runner.invoke(args=args+['--example']).exit_code,0)
            output=root/'inventory.json';self.assertEqual(runner.invoke(args=args+['--output',str(output)]).exit_code,0)
            first=output.read_bytes();self.assertNotEqual(runner.invoke(args=args+['--output',str(output)]).exit_code,0);self.assertEqual(output.read_bytes(),first)
            manifest.write_text('{"purpose":"validation_planning","purpose":"other"}')
            self.assertNotEqual(runner.invoke(args=args).exit_code,0)
            manifest.write_bytes(b' '*131073);self.assertNotEqual(runner.invoke(args=args).exit_code,0)

if __name__=='__main__':unittest.main()
