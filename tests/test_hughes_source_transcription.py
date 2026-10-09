"""Bounded source extraction and discrepancy detection without clinical approval."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SCRIPT=Path(__file__).resolve().parents[1]/'scripts'/'check_hughes_source_transcription.py'
spec=importlib.util.spec_from_file_location('hughes_source_check',SCRIPT)
checker=importlib.util.module_from_spec(spec);spec.loader.exec_module(checker)

FIXTURE='Supplementary Material 2: NONMEM Control Stream\n\n$PROBLEM LENA PK\n; UNITS MG, L AND H\n\n$INPUT ID TIME TAD AMT EVID DV CMT MDV ADDL II STUDY AGE SEX WT HT SECR CRCL2 RACE DXCAT FFM FLAG\n$DATA ..\\nmprep_flagged.csv IGNORE=# IGNORE=(FLAG.EQ.1)\n\n$SUBR ADVAN6 TOL=3\n\n$MODEL COMP=(ABS)  ; ABSORPTION COMPARTMENT\n       COMP=(CEN)  ; CENTRAL COMPARTMENT\n    COMP=(TRANS1)  ; TRANSIT COMPARTMENT 1\n    COMP=(TRANS2)  ; TRANSIT COMPARTMENT 2\n    COMP=(TRANS3)  ; TRANSIT COMPARTMENT 3\n    COMP=(TRANS4)  ; TRANSIT COMPARTMENT 4\n    COMP=(TRANS5)  ; TRANSIT COMPARTMENT 5\n    COMP=(TRANS6)  ; TRANSIT COMPARTMENT 6\n    COMP=(TRANS7)  ; TRANSIT COMPARTMENT 7\n\n$THETA\n  (0.01,12.)   ; POPCL\n  (0.01,68.8)  ; POPV\n  (0.01,13.5)  ; POPKA  \n  (0,0.43,)    ; RUV_PROP\n  (0.224)      ; CRCL_COV\n\n$OMEGA BLOCK(2)\n0.296      ; PPVCL\n0.25 0.284 ; PPVV\n$OMEGA \n0.367      ; PPVKA\n  \n$SIGMA 1. FIX ; EPS1\n\n$PK\n  WTS=55       ; mean fat free mass\n  RF=CRCL2/90  ; individual CRCL / mean CRCL\n\n; define typical values\n  TVCL=THETA(1)*(FFM/WTS)**0.75  \n  TVV=THETA(2)*(FFM/WTS)**1      \n  TVKTR=THETA(3)                 \n  RUVPROP=THETA(4)               \n\n; apply covariate to typical value\n  GRPCL=TVCL*RF**THETA(5)  \n  \n; define parameters for $DES\n  CL=GRPCL*EXP(ETA(1))   \n  V2=TVV*EXP(ETA(2))     \n  K=CL/V2                \n  \n  KTR=TVKTR*EXP(ETA(3)) \n\n  S2=V2  ; SCALE FACTOR FOR VC\n\n$DES\n  DADT(1)=-KTR*A(1)\n  DADT(2)=KTR*A(9)-K*A(2)\n  DADT(3)=KTR*A(1)-KTR*A(3)\n  DADT(4)=KTR*A(3)-KTR*A(4)\n  DADT(5)=KTR*A(4)-KTR*A(5)\n  DADT(6)=KTR*A(5)-KTR*A(6)\n  DADT(7)=KTR*A(6)-KTR*A(7)\n  DADT(8)=KTR*A(7)-KTR*A(8)\n  DADT(9)=KTR*A(8)-KTR*A(9)\n\n$ERROR\n  CP=A(2)/V2\n  IPRED=CP\n  PROP=CP*RUVPROP  ; proportional error\n  Y=CP+PROP*ERR(1)\n   \n$SIM(555) ONLYSIM SUBPROB=1000\n;$EST METHOD=1 INTERACTION MAXEVALS=9999 POSTHOC NOABORT NSIG=3 SIGL=9\n;$COV PRINT=E\n\n$TABLE ID TIME TAD AMT DV IPRED CWRES MDV EVID ADDL II STUDY AGE SEX WT HT FFM SECR RACE DXCAT CRCL2 FLAG CL V2 KTR ETA1 ETA2 ETA3\n\nONEHEADER NOPRINT FILE=run016_cl_crcl2_ffm_vpc.fit\n\n\nSupplementary Material 3: excluded exploratory stream'

class SourceTranscriptionTests(unittest.TestCase):
    def source(self):return checker.parse_final_stream(FIXTURE.splitlines())

    def test_final_stream_is_isolated_and_indexing_is_explicit(self):
        source=self.source()
        self.assertEqual(source['values']['apparent_clearance'],12)
        self.assertEqual(source['values']['transit_rate'],13.5)
        self.assertEqual(source['source_order'][1],'CEN')
        self.assertEqual(len(source['precentral_order']),8)
        self.assertEqual(source['dadt_expressions'][2],'KTR*A(9)-K*A(2)')
        self.assertEqual(source['observation_proportional_factor'],0.43)
        # Material 3 is not examined or promoted to the final model.
        extended=FIXTURE+'\nDADT(2)=0\n(999)'
        self.assertEqual(checker.parse_final_stream(extended.splitlines()),source)

    def test_ambiguous_sections_topology_and_equations_are_rejected(self):
        for modified in (FIXTURE.replace('Supplementary Material 2:','Missing section:'),
                         FIXTURE.replace('DADT(2)=KTR*A(9)-K*A(2)','DADT(2)=KTR*A(8)-K*A(2)'),
                         FIXTURE.replace('TVCL=THETA(1)*(FFM/WTS)**0.75','TVCL=THETA(1)'),
                         FIXTURE.replace('COMP=(TRANS7)','COMP=(TRANS8)'),
                         'Supplementary Material 2: NONMEM Control Stream\n'+FIXTURE):
            with self.assertRaises(ValueError):checker.parse_final_stream(modified.splitlines())

    def test_assessment_has_no_solver_network_database_or_approval(self):
        from intelligence_store.extensions import db
        with patch.object(checker,'extract_source',return_value=(self.source(),checker.SOURCE_SHA)), \
             patch('intelligence_store.transit_kernel.solve_transit',side_effect=AssertionError('No ODE')), \
             patch('socket.socket.connect',side_effect=AssertionError('No network')), \
             patch.object(db.session,'execute',side_effect=AssertionError('No database')):
            report=checker.assess(Path('unused.docx'))
        self.assertEqual(report['status'],'assisted_source_comparison_matches')
        self.assertEqual(len(report['contract_checks']),14)
        self.assertEqual(len(report['parameter_algebra_cases']),4)
        self.assertFalse(report['independent_review_completed'])
        self.assertFalse(report['clinical_prediction_validated'])
        self.assertFalse(report['ready_for_patient_simulation'])
        from intelligence_store.patient_state import digest
        body=dict(report);sha=body.pop('report_sha256');self.assertEqual(digest(body),sha)

    def test_project_parameter_discrepancy_is_reported(self):
        source=self.source();source['values']['apparent_clearance']=12.1
        with patch.object(checker,'extract_source',return_value=(source,checker.SOURCE_SHA)):
            report=checker.assess(Path('unused.docx'))
        self.assertEqual(report['status'],'assisted_source_discrepancy')
        self.assertEqual(next(c for c in report['contract_checks'] if c['code']=='parameter_apparent_clearance')['status'],'differs')
        self.assertTrue(any(c['status']=='differs' for c in report['parameter_algebra_cases']))

    def test_missing_changed_or_oversized_source_cannot_be_assessed(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'source.docx'
            with self.assertRaises(OSError):checker.extract_source(path)
            path.write_bytes(b'not the verified supplement')
            with self.assertRaisesRegex(ValueError,'SHA256'):checker.extract_source(path)
            path.write_bytes(b'x'*(checker.MAX_SOURCE_BYTES+1))
            with self.assertRaisesRegex(ValueError,'size'):checker.extract_source(path)

    def test_output_never_overwrites_and_mismatch_exits_nonzero(self):
        import contextlib,io
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'review.json'
            report={'status':'assisted_source_comparison_matches','contract_checks':[], 'parameter_algebra_cases':[]}
            args=['check','--source-file','unused.docx','--output',str(path)]
            with patch('sys.argv',args),patch.object(checker,'assess',return_value=report),contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(checker.main(),0);before=path.read_bytes()
                self.assertEqual(checker.main(),1);self.assertEqual(path.read_bytes(),before)
            report['status']='assisted_source_discrepancy'
            with patch('sys.argv',['check','--source-file','unused.docx']),patch.object(checker,'assess',return_value=report),contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(checker.main(),1)

if __name__=='__main__':unittest.main()
