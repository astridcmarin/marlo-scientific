"""Label ingestion pilot: SPL reading, manifest, insert-only tables, draws and the review rule.

Every SPL here is made up for the tests (decision 0009); none is taken from DailyMed.
"""
import io
import json
import random
import sqlite3
import tempfile
import unittest
import zipfile
from pathlib import Path

from intelligence_store import label_pilot, label_store, spl_labels


def make_spl(set_id='11111111-2222-3333-4444-555555555555', version=3, category='NDA', application='NDA000001',
             doc_code='34391-3', unii='AAAAAAAAAA', ingredient='EXAMPLAMIDE', n_extra=0):
    extra = ''.join(
        f'<component><section><code code="42229-5" codeSystem="2.16.840.1.113883.6.1"/><title>Extra {i}</title>'
        f'<text><paragraph>Extra section {i} text.</paragraph></text></section></component>' for i in range(n_extra))
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<document xmlns="urn:hl7-org:v3">
  <id root="AAAAAAAA-0000-0000-0000-000000000001"/>
  <code code="{doc_code}" codeSystem="2.16.840.1.113883.6.1" displayName="HUMAN PRESCRIPTION DRUG LABEL"/>
  <title>EXAMPLA (examplamide) capsules</title>
  <effectiveTime value="20260101"/>
  <setId root="{set_id.upper()}"/>
  <versionNumber value="{version}"/>
  <component><structuredBody>
    <component><section>
      <code code="48780-1" codeSystem="2.16.840.1.113883.6.1" displayName="SPL PRODUCT DATA ELEMENTS SECTION"/>
      <subject><manufacturedProduct><manufacturedProduct>
        <name>Exampla</name>
        <ingredient classCode="ACTIM"><ingredientSubstance>
          <code code="{unii}" codeSystem="2.16.840.1.113883.4.9"/><name>{ingredient}</name>
        </ingredientSubstance></ingredient>
        <ingredient classCode="IACT"><ingredientSubstance>
          <code code="BBBBBBBBBB" codeSystem="2.16.840.1.113883.4.9"/><name>LACTOSE</name>
        </ingredientSubstance></ingredient>
      </manufacturedProduct>
      <subjectOf><approval><id extension="{application}" root="2.16.840.1.113883.3.150"/>
        <code code="C73594" codeSystem="2.16.840.1.113883.3.26.1.1" displayName="{category}"/></approval></subjectOf>
      </manufacturedProduct></subject>
    </section></component>
    <component><section>
      <code code="34067-9" codeSystem="2.16.840.1.113883.6.1" displayName="INDICATIONS &amp; USAGE SECTION"/>
      <title>1  INDICATIONS AND USAGE</title>
      <excerpt><highlight><text><paragraph>Highlight text.</paragraph></text></highlight></excerpt>
      <text><paragraph>Exampla is indicated   for <content styleCode="italics">adults</content> with:</paragraph>
        <list><item>condition one;</item><item>condition two.</item></list></text>
      <component><section>
        <code code="42229-5" codeSystem="2.16.840.1.113883.6.1"/>
        <title>1.1 Limitations</title>
        <text><paragraph>Not for children.</paragraph></text>
      </section></component>
    </section></component>
    <component><section>
      <code code="34068-7" codeSystem="2.16.840.1.113883.6.1" displayName="DOSAGE &amp; ADMINISTRATION SECTION"/>
      <title>2  DOSAGE AND ADMINISTRATION</title>
      <text><paragraph>Give 1.3 mg/m<sup>2</sup> once daily.<br/>Take with water.</paragraph>
        <table><caption>Table 1: Doses</caption><thead><tr><th>Group</th><th>Dose</th></tr></thead>
        <tbody><tr><td>Adults<footnote ID="f1">Over 18   years.</footnote></td><td>10 mg</td></tr><tr><td>CL<sub>cr</sub> &lt; 30<footnoteRef IDREF="f1"/></td><td>5 mg</td></tr></tbody></table>
        <renderMultiMedia referencedObject="img1"/></text>
    </section></component>
    {extra}
  </structuredBody></component>
</document>'''.encode('utf-8')


def make_zip(xml, name='label.xml'):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as z:
        z.writestr(name, xml)
        z.writestr('img1.jpg', b'not an image')
    return buf.getvalue()


class SplReadingTests(unittest.TestCase):
    def setUp(self):
        self.lab = spl_labels.read_label(make_spl())

    def test_document_fields(self):
        self.assertEqual(self.lab['set_id'], '11111111-2222-3333-4444-555555555555')
        self.assertEqual(self.lab['version'], 3)
        self.assertEqual(self.lab['document_type_code'], '34391-3')
        self.assertEqual(self.lab['marketing_categories'], ['NDA'])
        self.assertEqual(self.lab['category_class'], 'brand')
        self.assertEqual(self.lab['application_numbers'], ['NDA000001'])
        self.assertEqual(self.lab['ingredients'], [{'unii': 'AAAAAAAAAA', 'name': 'EXAMPLAMIDE'}])

    def test_sections_verbatim_rules(self):
        by_head = {s['heading']: s for s in self.lab['sections']}
        ind = by_head['1 INDICATIONS AND USAGE']
        self.assertEqual(ind['text'], 'Exampla is indicated for adults with:\ncondition one;\ncondition two.')
        self.assertEqual(ind['excerpts_skipped'], 1)
        self.assertEqual(ind['code'], '34067-9')
        sub = by_head['1.1 Limitations']
        self.assertEqual(sub['parent_ord'], ind['ord'])
        self.assertEqual(sub['text'], 'Not for children.')
        dose = by_head['2 DOSAGE AND ADMINISTRATION']['text']
        self.assertEqual(dose, 'Give 1.3 mg/m^(2) once daily.\nTake with water.\n[Table]\nTable 1: Doses\n'
                               'Group | Dose\nAdults [Footnote: Over 18 years.] | 10 mg\nCL_(cr) < 30 [See footnote] | 5 mg\n[End table]\n[Image]')

    def test_refuses_dtd_and_non_spl(self):
        with self.assertRaises(spl_labels.SplError):
            spl_labels.read_label(b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "b">]><x/>')
        with self.assertRaises(spl_labels.SplError):
            spl_labels.read_label(b'<document/>')

    def test_category_classes(self):
        self.assertEqual(spl_labels.category_class(['ANDA']), 'generic')
        self.assertEqual(spl_labels.category_class(['NDA AUTHORIZED GENERIC']), 'generic')
        self.assertEqual(spl_labels.category_class(['ANDA', 'BLA']), 'brand')
        self.assertEqual(spl_labels.category_class(['UNAPPROVED DRUG OTHER']), 'other')
        self.assertEqual(spl_labels.category_class([]), 'other')


class StoreTests(unittest.TestCase):
    def _zips(self, d):
        specs = [dict(set_id=f'{i:08d}-0000-0000-0000-000000000000', category='NDA' if i % 2 else 'ANDA',
                      application=f'NDA{i:06d}' if i % 2 else f'ANDA{i:06d}', n_extra=i) for i in range(1, 5)]
        specs.append(dict(set_id='99999999-0000-0000-0000-000000000000', doc_code='34390-5'))  # OTC: refused
        for i, s in enumerate(specs):
            (Path(d) / f'label_{i}.zip').write_bytes(make_zip(make_spl(**s)))
        (Path(d) / 'broken.zip').write_bytes(b'not a zip')
        return sorted(Path(d).glob('*.zip'))

    def test_manifest_build_rebuild_and_insert_only(self):
        with tempfile.TemporaryDirectory() as d:
            zips = self._zips(d)
            man = label_store.build_manifest(zips, '2026-11-20', 'test')
            self.assertEqual(len(man['labels']), 4)
            self.assertEqual(len(man['refused']), 2)
            raw = json.dumps(man, sort_keys=True).encode()
            con1 = label_store.build(Path(d) / 'a.sqlite', raw, d)
            con2 = label_store.build(Path(d) / 'b.sqlite', raw, d)
            self.assertEqual(label_store.content_digest(con1), label_store.content_digest(con2))
            m = label_store.measures(con1, Path(d) / 'a.sqlite', raw)
            self.assertEqual(m['labels'], 4)
            self.assertEqual(m['sections'], 4 * 4 + (1 + 2 + 3 + 4))
            with self.assertRaises(sqlite3.DatabaseError):
                con1.execute("UPDATE label_section SET text = 'x'")
            with self.assertRaises(sqlite3.DatabaseError):
                con1.execute('DELETE FROM label_document')
            with self.assertRaises(FileExistsError):
                label_store.build(Path(d) / 'a.sqlite', raw, d)

    def test_build_refuses_changed_file(self):
        with tempfile.TemporaryDirectory() as d:
            zips = self._zips(d)
            raw = json.dumps(label_store.build_manifest(zips, '2026-11-20', 'test')).encode()
            (Path(d) / 'label_0.zip').write_bytes(make_zip(make_spl(set_id='00000001-0000-0000-0000-000000000000', version=4)))
            with self.assertRaises(ValueError):
                label_store.build(Path(d) / 'c.sqlite', raw, d)


class PilotRuleTests(unittest.TestCase):
    def test_plan_is_locked_and_matches_the_code(self):
        plan = label_pilot.load_plan()
        self.assertEqual(plan['status'], 'locked_before_computation')
        self.assertIn('seed 20261120', plan['labels']['drawn_40'])
        self.assertIn('seed 20261121', plan['review']['draw'])
        self.assertEqual((label_pilot.LABEL_SEED, label_pilot.SECTION_SEED), (20261120, 20261121))
        self.assertEqual((label_pilot.N_REVIEW, label_pilot.N_SPARE, label_pilot.MAX_ERRORS), (80, 20, 2))

    def test_label_draw_is_deterministic_and_stratified(self):
        cands = [{'set_id': f'id{i:04d}', 'marketing_categories': ['NDA' if i % 3 == 0 else 'ANDA']} for i in range(300)]
        a = label_pilot.sample_labels(cands, exclude_set_ids=['id0000'])
        self.assertEqual(a, label_pilot.sample_labels(list(reversed(cands)), exclude_set_ids=['ID0000']))
        self.assertEqual((len(a['brand']), len(a['generic'])), (30, 30))
        self.assertNotIn('id0000', a['brand'])
        with self.assertRaises(ValueError):
            label_pilot.sample_labels(cands + cands[:1])

    def test_candidates_from_openfda_ndc(self):
        recs = [{'product_type': 'HUMAN PRESCRIPTION DRUG', 'marketing_category': 'NDA', 'openfda': {'spl_set_id': ['AAA']}},
                {'product_type': 'HUMAN PRESCRIPTION DRUG', 'marketing_category': 'NDA AUTHORIZED GENERIC', 'openfda': {'spl_set_id': ['aaa']}},
                {'product_type': 'HUMAN OTC DRUG', 'marketing_category': 'OTC MONOGRAPH DRUG', 'openfda': {'spl_set_id': ['bbb']}},
                {'product_type': 'HUMAN PRESCRIPTION DRUG', 'marketing_category': 'ANDA', 'openfda': {}},
                {'product_type': 'HUMAN PRESCRIPTION DRUG', 'marketing_category': 'ANDA', 'openfda': {'spl_set_id': ['c', 'd']}},
                {'product_type': 'HUMAN PRESCRIPTION DRUG', 'marketing_category': '', 'openfda': {'spl_set_id': ['e']}},
                {'product_type': 'HUMAN PRESCRIPTION DRUG', 'marketing_category': 'ANDA', 'openfda': {'spl_set_id': ['f']}}]
        cands, left = label_pilot.candidates_from_openfda_ndc(recs)
        self.assertEqual(cands, [{'set_id': 'aaa', 'marketing_categories': ['NDA', 'NDA AUTHORIZED GENERIC']},
                                 {'set_id': 'f', 'marketing_categories': ['ANDA']}])
        self.assertEqual(left, {'not_prescription': 1, 'no_set_id': 1, 'several_set_ids': 1, 'no_category': 1})

    def test_rule_matches_bar(self):
        for errors in range(6):
            lb = label_pilot.lower_bound(80 - errors, 80)
            self.assertEqual(errors <= label_pilot.MAX_ERRORS, lb >= label_pilot.BAR, errors)

    def _items(self, errors, not_reviewable=0):
        items = []
        for i in range(1, 101):
            v = 'not_reviewable' if i <= not_reviewable else ('error' if i <= not_reviewable + errors else 'match')
            items.append({'draw': i, 'verdict': v, 'error_kind': 'text_missing' if v == 'error' else None})
        return items

    def test_evaluate(self):
        self.assertEqual(label_pilot.evaluate(self._items(2))['result'], 'pass')
        self.assertEqual(label_pilot.evaluate(self._items(3))['result'], 'fail')
        r = label_pilot.evaluate(self._items(0, not_reviewable=20))
        self.assertEqual((r['result'], r['counted']), ('pass', 80))
        self.assertEqual(label_pilot.evaluate(self._items(0, not_reviewable=21))['result'], 'incomplete')
        bad = self._items(1)
        bad[0]['error_kind'] = None
        with self.assertRaises(ValueError):
            label_pilot.evaluate(bad)

    def test_section_draw_and_sheet(self):
        with tempfile.TemporaryDirectory() as d:
            for i in range(1, 7):
                (Path(d) / f'l{i}.zip').write_bytes(make_zip(make_spl(set_id=f'{i:08d}-0000-0000-0000-000000000000', n_extra=20)))
            raw = json.dumps(label_store.build_manifest(sorted(Path(d).glob('*.zip')), '2026-11-20', 't')).encode()
            con = label_store.build(Path(d) / 'p.sqlite', raw, d)
            draws = label_pilot.sample_sections(con)
            self.assertEqual(draws, label_pilot.sample_sections(con))
            self.assertEqual(len(draws), 100)
            sheet = label_pilot.review_sheet(con, draws)
            self.assertTrue(all(it['text'] for it in sheet))


if __name__ == '__main__':
    unittest.main()
