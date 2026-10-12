import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from intelligence_store.bortezomib_timecourse import build_timecourse
if __name__=='__main__':
    p=argparse.ArgumentParser(description='Fixed study-regimen reproduction candidate.')
    p.add_argument('--output',type=Path);args=p.parse_args();r=build_timecourse()
    if args.output:
        with args.output.open('x') as f:json.dump(r,f,indent=2,allow_nan=False)
    print('Status:',r['status'])
    print('Dose events: 4; elimination relaxation: assumed 1/h; clock continuous')
    print('Maximum mass-balance error (mg):',r['maximum_mass_balance_error_mg'])
    print('Source reproduction established: false; patient simulation ready: false')
