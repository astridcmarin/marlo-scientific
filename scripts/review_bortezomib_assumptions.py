import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from intelligence_store.bortezomib_assumption_sensitivity import build_assumption_sensitivity
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path);a=p.parse_args();r=build_assumption_sensitivity()
    if a.output:
        with a.output.open('x') as f:json.dump(r,f,indent=2,allow_nan=False)
    print(r['status'])
    for s in r['scenarios']:print(s['assumed_relaxation_rate_per_h'],'/h:',s['maximum_sampled_absolute_difference_from_1_per_h'])
    print('Assumptions only; Equation 4 unresolved; no validation or uncertainty intervals.')
