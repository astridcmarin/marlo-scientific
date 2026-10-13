"""Read-only audited summary integration and withholding in the existing UI."""
import unittest
from unittest.mock import patch
from sqlalchemy import select
import test_educational_pk_comparison as fixtures
from intelligence_store.extensions import db
from intelligence_store.patient_state import digest
from intelligence_store.educational_pk_comparison_summary import comparison_summary
from intelligence_store.educational_pk_runs import save_pk_run
from intelligence_store.pk_model_inputs import model_input_example
from intelligence_store.treatment_requests import treatment_request_example


class ComparisonSummaryPageTests(unittest.TestCase):
    setUp = fixtures.EducationalPKComparisonTests.setUp
    tearDown = fixtures.EducationalPKComparisonTests.tearDown
    save_scenario = fixtures.EducationalPKComparisonTests.save_scenario
    baseline = fixtures.EducationalPKComparisonTests.baseline
    save = fixtures.EducationalPKComparisonTests.save
    pair = fixtures.EducationalPKComparisonTests.pair

    def url(self, a=None, b=None):
        path = f'/landscape/workspace/scenarios/{self.scenario.id}/patient-state/revisions/{self.revision.id}/pk-runs/compare'
        return path if a is None else path + f'?left={a.id}&right={b.id}'

    def tables(self):
        return {t.name: sorted((repr(dict(r)) for r in db.session.execute(select(t)).mappings()))
                for t in db.metadata.sorted_tables}

    def test_audited_page_and_json_are_read_only_and_preserve_original_download(self):
        a, b = self.pair()
        before = self.tables()
        expected = comparison_summary(a.id, b.id, revision_id=self.revision.id)
        with patch('socket.socket.connect', side_effect=AssertionError('No network')), patch('intelligence_store.educational_pk.solve_transit', side_effect=AssertionError('No solver')):
            response = self.client.get(self.url(a, b))
            self.assertEqual(response.status_code, 200)
            text = response.get_data(as_text=True)
            self.assertEqual(text.count('data-metric='), 7)
            self.assertEqual(text.count('<polyline '), 2)
            for value in ('One declared covariate value changed', 'not exact continuous Cmax/Tmax', 'Download audited summary JSON', expected['report_sha256'], '721 samples'):
                self.assertIn(value, text)
            result = self.client.get(self.url(a, b) + '&format=summary-json')
            self.assertEqual(result.get_json(), expected)
            self.assertIn('educational-pk-comparison-summary-', result.headers['Content-Disposition'])
            for item in (response, result):
                self.assertEqual(item.headers['Cache-Control'], 'no-store')
                self.assertEqual(item.headers['X-Content-Type-Options'], 'nosniff')
            legacy = self.client.get(self.url(a, b) + '&format=json')
            self.assertEqual(legacy.get_json(), fixtures.compare_pk_runs(a.id, b.id, revision_id=self.revision.id))
        self.assertEqual(self.tables(), before)

    def test_empty_form_and_invalid_queries(self):
        self.baseline()
        response = self.client.get(self.url())
        self.assertEqual(response.status_code, 200)
        text = response.get_data(as_text=True)
        self.assertNotIn('data-metric=', text)
        self.assertNotIn('<polyline ', text)
        for query in ('?format=summary-json', '?format=other', '?left=1&right=1&format=json&format=summary-json', '?left=0&right=1', '?left=1', '?unknown=1'):
            self.assertEqual(self.client.get(self.url() + query).status_code, 400)

    def test_incompatible_archives_withhold_curves_metrics_and_paired_auc(self):
        a, b = self.pair()
        other = save_pk_run(self.revision.id, model_input_example(), treatment_request_example(), 'CLL', title='Different declaration')
        response = self.client.get(self.url(a, other))
        self.assertEqual(response.status_code, 200)
        text = response.get_data(as_text=True)
        self.assertIn('Audited numerical metrics are withheld', text)
        self.assertIn('declared_disease_code', text)
        self.assertNotIn('<polyline ', text)
        self.assertNotIn('data-metric=', text)
        self.assertNotIn('AUC difference:', text)
        self.assertIn('Original inputs, assumptions and provenance', text)

    def test_audit_failure_withholds_even_when_original_comparison_is_compatible(self):
        a, b = self.pair()
        summary = comparison_summary(a.id, b.id, revision_id=self.revision.id)
        summary.update(status='comparison_summary_withheld', metrics=None, sampled_peak_context=None,
                       withheld_reasons=['both_archives_require_a_passed_mathematical_audit_and_supported_sampling_grid'])
        summary.pop('report_sha256'); summary['report_sha256'] = digest(summary)
        with patch('landscape_ui.educational_pk_compare_pages.comparison_summary', return_value=summary):
            response = self.client.get(self.url(a, b))
        self.assertEqual(response.status_code, 200)
        text = response.get_data(as_text=True)
        self.assertNotIn('<polyline ', text)
        self.assertNotIn('data-metric=', text)
        self.assertNotIn('AUC difference:', text)
        self.assertIn('both_archives_require_a_passed_mathematical_audit', text)

    def test_source_change_and_wrong_context_are_rejected(self):
        a, b = self.pair()
        summary = comparison_summary(a.id, b.id, revision_id=self.revision.id)
        summary['source_comparison_sha256'] = '0' * 64
        with patch('landscape_ui.educational_pk_compare_pages.comparison_summary', return_value=summary):
            self.assertEqual(self.client.get(self.url(a, b)).status_code, 409)
        self.assertEqual(self.client.get(self.url(a, b).replace('/scenarios/1/', '/scenarios/999/')).status_code, 404)
        self.assertEqual(self.client.get(self.url(a, b) + '9').status_code, 409)

    def test_title_is_escaped_and_identical_inputs_have_clear_context(self):
        self.baseline()
        a = self.save('<script>alert(1)</script>')
        response = self.client.get(self.url(a, a))
        self.assertEqual(response.status_code, 200)
        text = response.get_data(as_text=True)
        self.assertNotIn('<script>alert(1)</script>', text)
        self.assertIn('&lt;script&gt;', text)
        self.assertIn('No declared numerical input change', text)
        self.assertEqual(text.count('data-metric='), 7)


if __name__ == '__main__':
    unittest.main()
