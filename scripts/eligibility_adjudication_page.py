"""Write the standalone adjudication page (plan eligibility_second_annotation_plan_v1.json, `adjudication`).

    PYTHONPATH=. python3 scripts/eligibility_adjudication_page.py --output supplemental-information/eligibility/adjudication_page.html

The page holds only annotation guide v2, the criteria texts of the disagreeing pairs, both readings and the form.
Prints the view checksum to keep with the record.
"""
import argparse

from intelligence_store.eligibility_adjudication import write_page

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--output', required=True)
    a = ap.parse_args()
    print('view_sha256', write_page(a.output))
