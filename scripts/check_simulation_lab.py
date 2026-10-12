"""Run the consolidated teaching and Patient Lab regression checks."""
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
FILES=(
    'test_simulation_lab.py','test_protein_turnover.py','test_turnover_experiment.py',
    'test_binding_turnover.py','test_site_exposure_response.py',
    'test_transit_kernel.py','test_transit_regimen.py','test_transit_pages.py','test_transit_regimen_pages.py',
    'test_patient_lab_workspace.py','test_patient_directory.py',
    'test_two_scenario_patient_comparison.py','test_patient_comparison_report.py',
)


def main():
    missing=[name for name in FILES if not (ROOT/'tests'/name).is_file()]
    if missing:
        print('Missing prerequisite test files: '+', '.join(missing),file=sys.stderr)
        return 1
    sys.path.insert(0,str(ROOT))
    loader=unittest.TestLoader();suite=unittest.TestSuite()
    for name in FILES:suite.addTests(loader.discover(str(ROOT/'tests'),pattern=name))
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    print('Software/mathematical checks only. Scientific validation status is unchanged.')
    return 0 if result.wasSuccessful() and result.testsRun else 1


if __name__=='__main__':sys.exit(main())
