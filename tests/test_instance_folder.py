"""One instance folder (6 November 2026): annotations used to go to app/instance/ while the database used instance/."""
import json
import tempfile
import unittest
from pathlib import Path

from intelligence_store.eligibility_annotations import resolve_store

ROOT = Path(__file__).resolve().parents[1]


def store(n, when):
    return json.dumps({'annotations': {f'NCT{i:08d}': {'criteria': [], 'saved_at_utc': when} for i in range(n)}})


class ResolveStore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.new, self.old = base / 'instance' / 'a.json', base / 'app' / 'instance' / 'a.json'
        self.old.parent.mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def test_nothing_anywhere_uses_the_new_folder(self):
        self.assertEqual(resolve_store(self.new, self.old), self.new)
        self.assertFalse(self.new.exists())

    def test_old_only_is_copied_not_moved(self):
        self.old.write_text(store(38, '2026-11-06T17:01:00Z'))
        self.assertEqual(resolve_store(self.new, self.old), self.new)
        self.assertEqual(self.new.read_bytes(), self.old.read_bytes())

    def test_identical_copies_are_fine(self):
        self.old.write_text(store(38, 'x'))
        self.new.parent.mkdir(parents=True)
        self.new.write_text(store(38, 'x'))
        self.assertEqual(resolve_store(self.new, self.old), self.new)

    def test_newer_work_in_the_old_folder_wins_and_the_older_copy_is_kept(self):
        self.old.write_text(store(40, 'x'))
        self.new.parent.mkdir(parents=True)
        self.new.write_text(store(38, 'x'))
        self.assertEqual(resolve_store(self.new, self.old), self.new)
        self.assertEqual(len(json.loads(self.new.read_text())['annotations']), 40)
        backups = list(self.new.parent.glob('a.before-*.json'))
        self.assertEqual(len(backups), 1)
        self.assertEqual(len(json.loads(backups[0].read_text())['annotations']), 38)

    def test_newer_work_in_the_new_folder_wins(self):
        self.old.write_text(store(38, 'x'))
        self.new.parent.mkdir(parents=True)
        self.new.write_text(store(40, 'x'))
        self.assertEqual(resolve_store(self.new, self.old), self.new)
        self.assertEqual(len(json.loads(self.new.read_text())['annotations']), 40)

    def test_diverged_copies_are_refused_with_both_named(self):
        self.old.write_text(store(40, '2026-11-07T10:00:00Z'))
        self.new.parent.mkdir(parents=True)
        self.new.write_text(store(38, '2026-11-06T17:01:00Z').replace('"criteria": []', '"criteria": [1]'))
        with self.assertRaises(ValueError) as ctx:
            resolve_store(self.new, self.old)
        message = str(ctx.exception)
        self.assertIn('40 trials, last saved 2026-11-07T10:00:00Z', message)
        self.assertIn('38 trials', message)


class AppInstancePath(unittest.TestCase):
    def test_app_uses_the_project_instance_folder(self):
        from app.app import app
        self.assertEqual(Path(app.instance_path), ROOT / 'instance')


if __name__ == '__main__':
    unittest.main()
