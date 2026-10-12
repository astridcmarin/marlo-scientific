import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from intelligence_store.bortezomib_figure_review import build_figure_review
if __name__=='__main__':
    p=argparse.ArgumentParser(description='Provisional aggregate figure comparison; not validation.')
    p.add_argument('--output',type=Path);args=p.parse_args()
    result=build_figure_review()
    if args.output:
        with args.output.open('x') as f:json.dump(result,f,indent=2,allow_nan=False)
    print(result['status'])
    for row in result['rows']:
        print(f"{row['nominal_time_after_dose_h']} h: approximate concentration {row['approximate_concentration_ng_ml']:.2f} ng/mL; activity {row['approximate_observed_activity_percent']:.1f}%; equation {row['equation_activity_at_mean_concentration_percent']:.1f}%")
    print('Independent validation: false; patient simulation ready: false')
