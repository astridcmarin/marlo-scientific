"""Narrow local source-to-project comparison; never independent reviewer sign-off."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import sys
from xml.etree import ElementTree as ET
from zipfile import ZipFile

# Run from either the installed scripts directory or a merge patch directory.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SOURCE_SHA = '261734ad9632f1a0f19156b8b4b6cd88d6637cbefe89be4363791caeeda11849'
MAX_SOURCE_BYTES = 2 * 1024 * 1024
MAX_XML_BYTES = 8 * 1024 * 1024


def extract_source(path):
    with Path(path).open('rb') as handle:
        raw = handle.read(MAX_SOURCE_BYTES + 1)
    if len(raw) > MAX_SOURCE_BYTES:
        raise ValueError('Source file exceeds the bounded DOCX size.')
    actual = hashlib.sha256(raw).hexdigest()
    if actual != SOURCE_SHA:
        raise ValueError('Supplement SHA256 differs from the reviewed source; no comparison performed.')
    with ZipFile(path) as archive:
        member = archive.getinfo('word/document.xml')
        if member.file_size > MAX_XML_BYTES:
            raise ValueError('Document XML exceeds the extraction budget.')
        root = ET.fromstring(archive.read(member))
    ns = {'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    paragraphs = [''.join(t.text or '' for t in p.findall('.//w:t',ns))
                  for p in root.findall('.//w:p',ns)]
    return parse_final_stream(paragraphs), actual


def parse_final_stream(paragraphs):
    starts = [i for i,p in enumerate(paragraphs) if p.strip() == 'Supplementary Material 2: NONMEM Control Stream']
    ends = [i for i,p in enumerate(paragraphs) if p.strip().startswith('Supplementary Material 3:')]
    if len(starts) != 1 or len(ends) != 1 or ends[0] <= starts[0]:
        raise ValueError('Cannot uniquely isolate the final Material 2 control stream.')
    block = paragraphs[starts[0]+1:ends[0]]
    lines = [re.sub(r'\s+','',p.split(';',1)[0]).upper() for p in block if p.strip()]
    def one(pattern):
        found = [re.fullmatch(pattern,line) for line in lines]
        found = [m for m in found if m]
        if len(found) != 1:
            raise ValueError('Source expression is missing or ambiguous: ' + pattern)
        return found[0]
    one(r'TVCL=THETA\(1\)\*\(FFM/WTS\)\*\*0\.75')
    one(r'TVV=THETA\(2\)\*\(FFM/WTS\)\*\*1')
    for expected in ('TVKTR=THETA(3)','GRPCL=TVCL*RF**THETA(5)','CL=GRPCL*EXP(ETA(1))',
                     'V2=TVV*EXP(ETA(2))','KTR=TVKTR*EXP(ETA(3))','K=CL/V2','S2=V2','CP=A(2)/V2'):
        one(re.escape(expected))
    theta_start = lines.index('$THETA')
    theta_end = next(i for i in range(theta_start+1,len(lines)) if lines[i].startswith('$'))
    theta=[]
    for line in lines[theta_start+1:theta_end]:
        if not re.fullmatch(r'\([0-9.,]+\)',line):
            raise ValueError('Unsupported THETA declaration.')
        nums=[float(n) for n in line[1:-1].split(',') if n]
        theta.append(nums[1] if len(nums)>1 else nums[0])
    if len(theta)!=5 or any(not math.isfinite(x) for x in theta):
        raise ValueError('Expected five finite THETA declarations.')
    ffm=float(one(r'WTS=([0-9.]+)').group(1))
    crcl=float(one(r'RF=CRCL2/([0-9.]+)').group(1))
    order=re.findall(r'COMP=\(([^)]+)\)',''.join(lines))
    expected_order=['ABS','CEN']+[f'TRANS{i}' for i in range(1,8)]
    if order!=expected_order:
        raise ValueError('Unexpected source compartment order.')
    expected_des={1:'-KTR*A(1)',2:'KTR*A(9)-K*A(2)',3:'KTR*A(1)-KTR*A(3)'}
    expected_des.update({i:f'KTR*A({i-1})-KTR*A({i})' for i in range(4,10)})
    actual_des={}
    for line in lines:
        if line.startswith('DADT'):
            m=re.fullmatch(r'DADT\(([1-9])\)=(.+)',line)
            if m is None or int(m[1]) in actual_des:
                raise ValueError('Unexpected or duplicate DADT equation.')
            actual_des[int(m[1])]=m[2]
    if actual_des!=expected_des:
        raise ValueError('The source DADT graph differs from the recognized serial topology.')
    return {'source_paragraph_start':starts[0]+1,'source_paragraph_end_exclusive':ends[0]+1,
            'values':{'apparent_clearance':theta[0],'apparent_volume':theta[1],
                      'transit_rate':theta[2],'crcl_exponent':theta[4],
                      'ffm_clearance_exponent':0.75,'ffm_volume_exponent':1.,
                      'reference_ffm':ffm,'reference_crcl':crcl},
            'source_order':order,'precentral_order':['ABS']+order[2:],
            'dadt_expressions':actual_des,'observation_proportional_factor':theta[3]}


def assess(path):
    from intelligence_store.patient_state import digest
    from intelligence_store.pk_parameter_reference import load_parameter_extract, _parameter_math
    from intelligence_store.published_transit_reference import load_structure_contract
    import intelligence_store.pk_parameter_reference as parameter_module
    import intelligence_store.transit_kernel as kernel_module
    import intelligence_store.educational_pk as execution_module
    source,actual_sha=extract_source(path)
    extract=load_parameter_extract();structure=load_structure_contract()
    checks=[]
    def check(code, expected, actual):
        checks.append({'code':code,'source_expected':expected,'project_actual':actual,
                       'status':'matches' if expected==actual else 'differs'})
    for name,value in source['values'].items():
        check('parameter_'+name,value,extract['parameters'][name]['value'])
    check('source_order',source['source_order'],structure['structure']['source_compartment_order'])
    check('precentral_order',source['precentral_order'],structure['structure']['serial_precentral_order'])
    check('stage_count',len(source['precentral_order']),structure['structure']['precentral_stage_count'])
    check('central_source_index',2,structure['structure']['central_source_index'])
    check('central_inflow_source_index',9,structure['structure']['central_inflow_source_index'])
    check('unit_conversion_mg_l_to_ng_ml',1000,structure['units']['conversion_factor'])
    algebra=[];p=source['values']
    for ffm,crcl in ((55,90),(55,45),(50,90),(70,60)):
        expected_cl=p['apparent_clearance']*(ffm/p['reference_ffm'])**p['ffm_clearance_exponent']*(crcl/p['reference_crcl'])**p['crcl_exponent']
        expected_v=p['apparent_volume']*(ffm/p['reference_ffm'])**p['ffm_volume_exponent']
        actual=_parameter_math(ffm,crcl,extract['parameters'])
        expected={'apparent_clearance_l_h':expected_cl,'apparent_volume_l':expected_v,
                  'elimination_rate_h':expected_cl/expected_v,'transit_rate_h':p['transit_rate']}
        agrees=all(math.isclose(actual[k],v,rel_tol=1e-12,abs_tol=1e-12) for k,v in expected.items())
        algebra.append({'ffm_kg':ffm,'crcl_ml_min':crcl,'source_derived_typical_values':expected,
                        'project_values':actual,'status':'matches' if agrees else 'differs'})
    report={'schema_version':'hughes-assisted-source-assessment-v1',
        'status':'assisted_source_comparison_matches' if all(c['status']=='matches' for c in checks+algebra) else 'assisted_source_discrepancy',
        'source_sha256':actual_sha,'source_section':'Supplementary Material 2',
        'source_extraction':source,'contract_checks':checks,'parameter_algebra_cases':algebra,
        'code_sha256':{Path(m.__file__).name:hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest()
                       for m in (parameter_module,kernel_module,execution_module)},
        'review_type':'automated_assisted_comparison_not_independent_signoff',
        'independent_review_completed':False,'clinical_prediction_validated':False,
        'ready_for_patient_simulation':False,'ode_solver_rerun':False,'database_writes_performed':False,
        'not_verified':['Generic kernel derivative execution by this tool (code hash is identification only)',
                        'NONMEM estimation or source dataset reproduction','Random-effects covariance and observation-error reproduction',
                        'Predictive accuracy, uncertainty, individual applicability or clinical endpoints'],
        'limitation':'Narrow recognized-source grammar and four fixed algebra cases. Agreement is not empirical validation, proof for all inputs, or a qualified independent reviewer decision.'}
    report['report_sha256']=digest(report)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-file',type=Path,required=True)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    try:
        report=assess(args.source_file)
        if args.output:
            with args.output.open('x',encoding='utf-8') as handle:
                json.dump(report,handle,indent=2,ensure_ascii=False,allow_nan=False);handle.write('\n')
            print('Saved',args.output)
        print(report['status'],'|',len(report['contract_checks']),'contract checks |',len(report['parameter_algebra_cases']),'algebra cases')
        print('Independent review completed: false | Clinical prediction validated: false')
        return 0 if report['status']=='assisted_source_comparison_matches' else 1
    except (ValueError,OSError,KeyError,ET.ParseError) as exc:
        print(str(exc),file=sys.stderr);return 1


if __name__=='__main__':raise SystemExit(main())
