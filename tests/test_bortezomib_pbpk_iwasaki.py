"""Simulation 3.0j: structural checks of the Iwasaki 2020 PBPK transcription (no dosing, no clinical data)."""
import json
import random
import unittest

from intelligence_store import bortezomib_pbpk_iwasaki as m


class Extract(unittest.TestCase):
    def test_pinned_and_complete(self):
        e = m.load_extract()
        self.assertEqual([q['number'] for q in e['equations']], [1, 2, 3, 4, 5, 6, 7])
        p = m.parameters(e)
        self.assertEqual(len(p), 22)
        for name in ('MW', 'Vsys', 'Vrbc', 'Vperi', 'Vhp', 'Vhrbc', 'Vh', 'Qh', 'Hct', 'fu_p', 'fu_liver', 'CLint',
                     'PSliv', 'CLperi', 'Bmax', 'Kon', 'Koff') + m.FM:
            self.assertIn(name, p)

    def test_changed_extract_is_refused(self):
        raw = json.loads(m.EXTRACT_PATH.read_text())
        raw['parameters']['CLint']['value'] = 2.0
        import tempfile, pathlib
        with tempfile.TemporaryDirectory() as d:
            path = pathlib.Path(d) / 'x.json'
            path.write_text(json.dumps(raw))
            with self.assertRaises(Exception):
                m.load_extract(path)

    def test_private_correspondence_is_not_in_the_extract(self):
        text = m.EXTRACT_PATH.read_text().lower()
        self.assertNotIn('@', text)
        self.assertNotIn('gmail', text)


class Structure(unittest.TestCase):
    def setUp(self):
        self.p = m.parameters()

    def test_table_consistency(self):
        s = m.structural_summary(self.p)
        self.assertAlmostEqual(s['fm_total'], 0.999, places=9)
        self.assertAlmostEqual(s['hepatic_plasma_fraction'], 1 - self.p['Hct'], places=2)
        self.assertAlmostEqual(s['kd_nM'], 0.5507, places=3)
        self.assertAlmostEqual(s['rbc_capacity_nmol_kg'], 27.93, places=2)

    def test_mass_balance_only_metabolism_removes_drug(self):
        rng = random.Random(3)
        for _ in range(50):
            state = {s: rng.uniform(0, 500) for s in m.STATE}
            d = m.derivatives(state, self.p)
            change = sum(d[s] * self.p[m.VOLUME_OF[s]] for s in m.STATE)
            self.assertAlmostEqual(change, -m.metabolic_rate(state, self.p), places=7)

    def test_empty_body_stays_empty(self):
        d = m.derivatives({s: 0.0 for s in m.STATE}, self.p)
        self.assertTrue(all(v == 0.0 for v in d.values()))

    def test_rbc_binding_saturates_at_bmax(self):
        """Bound drug at Bmax (854 nM = 328 ng/mL) leaves no free sites, so plasma drug cannot bind further."""
        full = self.p['Bmax'] * self.p['MW'] / 1000.0
        state = {s: 0.0 for s in m.STATE}
        state.update(Cp=100.0, Crbc=full)
        bind = m._binding(self.p, full, self.p['Vrbc'], 100.0)
        self.assertAlmostEqual(bind, -self.p['Koff'] * self.p['Vrbc'] * full, places=9)

    def test_liver_equilibrium_ratio(self):
        """Without metabolism, hepatic plasma and liver are at equilibrium when Ch = fu,p / fu,liver x Chp."""
        p = dict(self.p, CLint=0.0)
        state = {s: 0.0 for s in m.STATE}
        state.update(Chp=1.0, Ch=p['fu_p'] / p['fu_liver'])
        self.assertAlmostEqual(m.derivatives(state, p)['Ch'], 0.0, places=9)

    def test_blood_concentration(self):
        self.assertAlmostEqual(m.blood_concentration({'Cp': 10.0, 'Crbc': 100.0}, self.p), 10 * 0.56 + 100 * 0.44)


if __name__ == '__main__':
    unittest.main()
