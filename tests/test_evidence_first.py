"""Evidence-first small fixes (docs/EVIDENCE_FIRST_PLAN.md items 1-4 and 9, 18 November 2026): which checks belong to
which drug, the cohort note, the home page's check card, the live-search note and the folded caveat."""
import unittest
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime

import jinja2

from intelligence_store import check_findings as cf

ROOT = Path(__file__).resolve().parent.parent


class FindingsForDrug(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.view = cf.findings_view()

    def ids(self, drug):
        return {r['id'] for r in cf.findings_for_drug(drug, self.view)}

    def test_each_drug_gets_its_own_checks_and_only_those(self):
        self.assertEqual(self.ids('bortezomib'), {'ogawa', 'kuan', 'can1004', 'falling_clearance', 'iwasaki', 'mmy3021',
                                                  'reece', 'platelets', 'nct01801436'})
        self.assertEqual(self.ids('ixazomib'), {'ixazomib', 'acceptance_rule_v2_gupta_luo'})
        self.assertEqual(self.ids('daratumumab'), {'daratumumab_v1', 'daratumumab_v2', 'acceptance_rule_v2_gupta_luo'})
        self.assertEqual(self.ids('pomalidomide'), {'pomalidomide_label', 'pomalidomide_li'})
        self.assertEqual(self.ids('melphalan'), {'melphalan_label'})
        self.assertEqual(self.ids('carfilzomib'), {'carfilzomib_label'})     # its label check, 19 November 2026

    def test_every_drug_check_is_claimed_and_eligibility_is_not(self):
        claimed = set()
        for drug in ('lenalidomide', 'bortezomib', 'ixazomib', 'daratumumab', 'pomalidomide', 'dexamethasone', 'melphalan',
                     'carfilzomib'):
            claimed |= self.ids(drug)
        every = {r['id'] for a in self.view['areas'] for r in a['rows']}
        unclaimed = every - claimed
        self.assertTrue(unclaimed)
        self.assertTrue(all(i.startswith('eligibility_') for i in unclaimed), unclaimed)

    def test_a_prefix_is_not_a_match(self):
        self.assertFalse(cf.subject_drug_matches('lenalidomide_hughes_2019', 'lenalid'))
        self.assertTrue(cf.subject_drug_matches('label_exposure_dexamethasone', 'dexamethasone'))


class CohortNote(unittest.TestCase):
    def render(self, cohorts, current):
        env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(ROOT / 'landscape_ui/templates')))
        return env.from_string('{% from "cohort_note_macros.html" import cohort_note %}{{ cohort_note(c, cur) }}').render(c=cohorts, cur=current)

    def test_lists_every_cohort_in_order_and_marks_this_page(self):
        when = datetime(2026, 10, 5, 17, 40)
        cohorts = [SimpleNamespace(id=i, condition='Multiple Myeloma', scope=s, start_year=y0, end_year=y1, finished_at_utc=when)
                   for i, s, y0, y1 in ((4, 'all-studies', None, None), (2, 'drug-biologic', 2021, 2026), (1, 'drug-biologic', None, None))]
        html = self.render(cohorts, 1)
        self.assertLess(html.index('#1:'), html.index('#2:'))
        self.assertLess(html.index('#2:'), html.index('#4:'))
        self.assertIn('starting 2021–2026', html)
        self.assertIn('every registered study', html)
        self.assertIn('retrieved 05 October 2026', html)
        self.assertEqual(html.count('(this page)'), 1)

    def test_no_cohorts_no_note(self):
        self.assertEqual(self.render([], None).strip(), '')


class Templates(unittest.TestCase):
    def test_home_leads_with_the_check_record_not_a_model(self):
        src = (ROOT / 'app/templates/landing.html').read_text()
        hero = src[src.index('<section class="hero">'):src.index('</section>')]
        self.assertIn("url_for('landscape.index')", hero)
        self.assertIn("url_for('check_findings')", hero)
        self.assertIn('findings.counts.gap', hero)
        self.assertNotIn('Patient Lab', hero)
        self.assertIn('(cohort #4)', src)

    def test_explorer_says_it_is_live(self):
        src = (ROOT / 'app/templates/index.html').read_text()
        self.assertIn('class="live-note"', src)
        self.assertIn("url_for('landscape.index')", src)

    def test_drug_pages_fold_the_caveat_without_changing_it(self):
        for name in ('landscape_drug_detail.html', 'landscape_drug_knowledge.html'):
            src = (ROOT / 'landscape_ui/templates' / name).read_text()
            self.assertIn('<details class="scope-details">', src)
            self.assertIn('{{ report.limitation }}', src)
            self.assertIn('{{ report.view_scope }}', src)

    def test_findings_rows_carry_anchors(self):
        self.assertIn('<li id="{{ r.id }}">', (ROOT / 'app/templates/findings.html').read_text())


if __name__ == '__main__':
    unittest.main()
