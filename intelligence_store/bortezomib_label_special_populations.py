"""Phase 4.2e: pinned extract of the 2012 VELCADE label's special-population sections (2.6, 8.5-8.7, 12.3).

Transcribed from the rendered page images of the FDA approval package for NDA 021602 S-027 (the label pages are
scanned). Used by the bortezomib special-population summary; no calculation reads it.
"""
from pathlib import Path

from .covariate_estimation import _load_pinned

EXTRACT_PATH = Path(__file__).parent / 'data' / 'bortezomib_label_special_populations_2012_v1.json'
EXTRACT_SHA256 = 'db8683de99248937a283ea8c0f6d043e9be02a5fb2258b0abff1f55af2bdb1ce'


def load_extract(path=EXTRACT_PATH):
    return _load_pinned(path, EXTRACT_SHA256, 'label-special-populations-v1', 'Bortezomib 2012 label special populations')
