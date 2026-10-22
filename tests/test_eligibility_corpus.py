"""Phase 4.1a: eligibility corpus export from a saved cohort's frozen snapshots."""
from datetime import datetime
import json
from pathlib import Path
import tempfile
import unittest

from flask import Flask

from intelligence_store import eligibility_corpus as ec
from intelligence_store.extensions import db
from intelligence_store.models import AnalysisCohort, CohortTrial, TrialSnapshot
from intelligence_store.patient_state import digest

STUDY = {'protocolSection': {
    'identificationModule': {'briefTitle': 'Drug X in relapsed myeloma'},
    'statusModule': {'overallStatus': 'RECRUITING', 'startDateStruct': {'date': '2024-03'}},
    'designModule': {'studyType': 'INTERVENTIONAL', 'phases': ['PHASE2'], 'enrollmentInfo': {'count': 40, 'type': 'ESTIMATED'}},
    'conditionsModule': {'conditions': ['Multiple Myeloma']},
    'sponsorCollaboratorsModule': {'leadSponsor': {'name': 'Acme', 'class': 'INDUSTRY'}},
    'armsInterventionsModule': {'interventions': [{'type': 'DRUG', 'name': 'Drug X'}]},
    'eligibilityModule': {'eligibilityCriteria': 'Inclusion Criteria:\n* Creatinine clearance >= 30 mL/min\n* ANC >= 1.0 x 10^9/L',
                          'minimumAge': '18 Years', 'sex': 'ALL', 'healthyVolunteers': False}}}


class Export(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(TESTING=True, SQLALCHEMY_DATABASE_URI='sqlite://')
        db.init_app(self.app)
        ec.register_eligibility_corpus_commands(self.app)
        self.ctx = self.app.app_context(); self.ctx.push()
        db.create_all()

    def tearDown(self):
        db.session.remove(); db.drop_all(); self.ctx.pop()

    def cohort(self, status='COMPLETE', studies=(STUDY, {}), retrieved=None):
        c = AnalysisCohort(id=1, condition='Multiple Myeloma', api_url='https://clinicaltrials.gov/api/v2/studies',
                           query_params={'query.cond': 'Multiple Myeloma'}, query_version='t', normalization_version='t',
                           scope='all-studies', max_pages=1, status=status, expected_count=len(studies),
                           retrieved_count=len(studies) if retrieved is None else retrieved, pages_fetched=1, page_log=[],
                           finished_at_utc=datetime(2026, 10, 7))
        db.session.add(c)
        for n, study in enumerate(studies, start=1):
            nct = f'NCT{n:08d}'
            s = TrialSnapshot(nct_id=nct, source_url='https://clinicaltrials.gov/study/' + nct, raw_study=study,
                              retrieved_at_utc=datetime(2026, 10, 7))
            db.session.add(s); db.session.flush()
            db.session.add(CohortTrial(cohort_id=1, nct_id=nct, snapshot_id=s.id))
        db.session.commit()

    def test_export_copies_fields_and_keeps_missing_as_missing(self):
        self.cohort()
        corpus = ec.export_corpus(1)
        self.assertEqual(corpus['counts'], {'trials': 2, 'with_eligibility_text': 1, 'interventional': 1})
        first, second = corpus['trials']
        self.assertEqual(first['eligibility']['criteria_text'], STUDY['protocolSection']['eligibilityModule']['eligibilityCriteria'])
        self.assertEqual(first['phases'], ['PHASE2'])
        self.assertEqual(first['interventions'], [{'type': 'DRUG', 'name': 'Drug X'}])
        self.assertIsNone(second['eligibility']['criteria_text'])
        self.assertEqual(second['phases'], [])
        body = {k: v for k, v in corpus.items() if k != 'corpus_sha256'}
        self.assertEqual(corpus['corpus_sha256'], digest(body))

    def test_refuses_incomplete_or_inconsistent_cohorts(self):
        self.cohort(status='PARTIAL')
        with self.assertRaises(ValueError):
            ec.export_corpus(1)
        with self.assertRaises(ValueError):
            ec.export_corpus(99)

    def test_refuses_membership_count_mismatch(self):
        self.cohort(retrieved=3)
        with self.assertRaises(ValueError):
            ec.export_corpus(1)

    def test_cli_lists_exports_and_refuses_to_overwrite(self):
        self.cohort()
        runner = self.app.test_cli_runner()
        self.assertIn('Multiple Myeloma', runner.invoke(args=['eligibility-corpus-export', '--list']).output)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'corpus.json'
            result = runner.invoke(args=['eligibility-corpus-export', '--cohort-id', '1', '--output', str(out)])
            self.assertEqual(result.exit_code, 0, result.output)
            self.assertEqual(json.loads(out.read_text())['counts']['trials'], 2)
            again = runner.invoke(args=['eligibility-corpus-export', '--cohort-id', '1', '--output', str(out)])
            self.assertNotEqual(again.exit_code, 0)


if __name__ == '__main__':
    unittest.main()


class PinnedCorpus(unittest.TestCase):
    """Phase 4.1b: the exported myeloma cohort, pinned."""

    @classmethod
    def setUpClass(cls):
        cls.corpus = ec.load_corpus()

    def test_identity_and_counts(self):
        c = self.corpus
        self.assertEqual(c['schema_version'], 'eligibility-corpus-v1')
        self.assertEqual((c['cohort']['id'], c['cohort']['condition'], c['cohort']['scope']), (3, 'Multiple Myeloma', 'all-interventional'))
        self.assertEqual(c['cohort']['expected_count'], c['cohort']['retrieved_count'])
        self.assertEqual(c['counts'], {'trials': 3450, 'with_eligibility_text': 3449, 'interventional': 3450})
        self.assertEqual(len({t['nct_id'] for t in c['trials']}), 3450)

    def test_a_changed_file_is_refused(self):
        import gzip
        with tempfile.TemporaryDirectory() as tmp:
            changed = Path(tmp) / 'c.json.gz'
            changed.write_bytes(gzip.compress(gzip.decompress(ec.CORPUS_PATH.read_bytes()) + b' '))
            with self.assertRaises(ValueError):
                ec.load_corpus(changed)
