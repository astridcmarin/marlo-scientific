"""Write the standalone page for the second annotator (plan eligibility_second_annotation_plan_v1.json).

    PYTHONPATH=. python3 scripts/eligibility_second_annotation_page.py --output supplemental-information/eligibility/annotator_b_page.html

The page holds only the guide, the sampled criteria texts and the form. Prints the page checksum to keep with the record.
"""
import argparse

from intelligence_store.eligibility_second_annotation import write_page

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--output', required=True)
    a = ap.parse_args()
    print('page_sha256', write_page(a.output))
