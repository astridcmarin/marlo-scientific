"""Rebuild intelligence_store/data/body_map_flow_paths_v1.json from the committed route model (step 1.3c).

    PYTHONPATH=. python scripts/build_body_map_flow_paths.py

Prints the new file's SHA-256. If the route model or the rules change, the new checksum goes into
intelligence_store/body_map_paths.py (PATHS_SHA256) after review; tests/test_body_map_paths.py checks that the committed
file is exactly what the committed model gives.
"""
from intelligence_store.body_map_paths import write_paths

if __name__ == '__main__':
    print(write_paths())
