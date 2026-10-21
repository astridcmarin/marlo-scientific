"""Checkpoint 2026-10-16, finding 1: every reference file is pinned by its loader."""
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from intelligence_store import (assay_evidence, drug_aliases, interactions, mechanism_evidence, mechanisms,
                                patient_scenarios, safety)

DATA = Path(__file__).resolve().parents[1] / 'intelligence_store' / 'data'


def aliases():
    return drug_aliases.load_alias_catalog()


# (module, path constant, checksum constant, loader taking the path or None for module-level paths)
PINS = [
    (drug_aliases, 'CATALOG_PATH', 'CATALOG_SHA256', lambda p: drug_aliases.load_alias_catalog(p)),
    (drug_aliases, 'FORMATTING_MAP_PATH', 'FORMATTING_MAP_SHA256', lambda p: drug_aliases.load_formatting_group_mappings(p)),
    (safety, 'CATALOG_PATH', 'CATALOG_SHA256', lambda p: safety.load_safety_catalog(aliases(), p)),
    (interactions, 'CATALOG_PATH', 'CATALOG_SHA256', lambda p: interactions.load_interaction_catalog(aliases(), p)),
    (mechanisms, 'ANNOTATION_PATH', 'ANNOTATION_SHA256', lambda p: mechanisms.load_annotation_catalog(aliases(), p)),
    (patient_scenarios, 'PRESETS_PATH', 'PRESETS_SHA256', lambda p: patient_scenarios.load_scenario_presets(p)),
    (assay_evidence, 'REVIEW_PATH', 'REVIEW_SHA256', None),
    (mechanism_evidence, 'PLAN_PATH', 'PLAN_SHA256', None),
]


class ReferencePins(unittest.TestCase):
    def test_pins_match_the_committed_files(self):
        for module, path_name, sha_name, _ in PINS:
            path = getattr(module, path_name)
            self.assertEqual(hashlib.sha256(Path(path).read_bytes()).hexdigest(), getattr(module, sha_name), path)

    def test_a_changed_file_is_refused(self):
        for module, path_name, sha_name, loader in PINS:
            with self.subTest(file=Path(getattr(module, path_name)).name), tempfile.TemporaryDirectory() as tmp:
                changed = Path(tmp) / Path(getattr(module, path_name)).name
                changed.write_bytes(Path(getattr(module, path_name)).read_bytes() + b' ')
                with self.assertRaises(Exception) as caught:
                    if loader is None:
                        with patch.object(module, path_name, changed):
                            (module.build_assay_review if module is assay_evidence else module.build_mechanism_map)()
                    else:
                        loader(changed)
                chain, e = [], caught.exception
                while e is not None:
                    chain.append(str(e))
                    e = e.__cause__ or e.__context__
                self.assertTrue(any('pinned checksum' in m for m in chain), chain)


if __name__ == '__main__':
    unittest.main()


class ReviewPacketsAreFrozen(unittest.TestCase):
    """Checkpoint 2026-10-21: two review packets are not loaded as reference data (one is read by a review script that
    reports its checksum, one is documentation), so they have no loader pin; this test still refuses a silent edit."""
    FROZEN = {
        'lenalidomide_assay_metadata_v2.json': 'af1970a3109070f552474064d2df7a0be4c86f9ff449cff6ebca8c16f928a644',
        'lenalidomide_assay_quality_review_v1.json': '0bdd76d923cfb02bf817f4e00f7aa088fdf6ea270d6e13de90488b5ae0b8efac',
    }

    def test_review_packets_unchanged(self):
        for name, sha in self.FROZEN.items():
            self.assertEqual(hashlib.sha256((DATA / name).read_bytes()).hexdigest(), sha, name)
