"""Offline HTML view of an audited comparison; no embedded patient-input editor."""
from html import escape
import math
import json
from .patient_state import digest
from .educational_pk_comparison import compare_pk_runs


def _text(value):
    return escape(str(value),quote=True)


def _curve_svg(comparison):
    points=comparison['points']
    if not points:
        return '<p>No compatible archived concentration curves are available.</p>'
    maximum=max(max(p['left_concentration_ng_ml'],p['right_concentration_ng_ml']) for p in points)
    start,end=points[0]['time_h'],points[-1]['time_h']
    if maximum<=0 or end<=start or not math.isfinite(maximum):
        return '<p>The archived plotting range is unavailable.</p>'
    top=maximum*1.1
    width,height,left,bottom=820,290,80,60
    plot_w,plot_h=width-left-30,height-bottom-30
    def x(t):return left+plot_w*(t-start)/(end-start)
    def y(c):return 30+plot_h*(1-c/top)
    elements=['<svg viewBox="0 0 820 290" role="img" aria-labelledby="curve-title curve-description">',
      '<title id="curve-title">Archived educational concentration curves</title>',
      '<desc id="curve-description">Two archived sampled concentration curves on common linear axes. Lines connect stored samples; they are not new simulation outputs.</desc>']
    for fraction in (0,.25,.5,.75,1):
        yy=y(top*fraction);xx=x(start+(end-start)*fraction)
        elements.append(f'<line x1="{left}" x2="790" y1="{yy:.3f}" y2="{yy:.3f}" stroke="#dfe5e8"/>')
        elements.append(f'<text x="70" y="{yy+4:.3f}" text-anchor="end">{top*fraction:.4g}</text>')
        elements.append(f'<text x="{xx:.3f}" y="250" text-anchor="middle">{start+(end-start)*fraction:.4g}</text>')
    for code,color in (('left','#2563eb'),('right','#d97706')):
        xy=' '.join(f"{x(p['time_h']):.3f},{y(p[code+'_concentration_ng_ml']):.3f}" for p in points)
        elements.append(f'<polyline class="curve-{code}" fill="none" stroke="{color}" stroke-width="2.5" points="{xy}"/>')
    elements.extend(['<text x="430" y="278" text-anchor="middle">Hours from window start</text>',
      '<text transform="translate(18 145) rotate(-90)" text-anchor="middle">Concentration (ng/mL)</text>','</svg>'])
    return ''.join(elements)


def render_comparison_html(summary):
    """Verify the current comparison binds to the audited summary before rendering."""
    if digest({k:v for k,v in summary.items() if k!='report_sha256'}) != summary['report_sha256']:
        raise ValueError('Comparison summary digest differs; no HTML generated.')
    comparison=compare_pk_runs(summary['left_run_id'],summary['right_run_id'],revision_id=summary['revision_id'])
    if comparison['report_sha256']!=summary['source_comparison_sha256']:
        raise ValueError('The archived comparison differs from the audited summary; no HTML generated.')
    available=summary['status']=='educational_comparison_summary_available'
    context=summary['comparison_context']
    labels={'single_declared_covariate_value_changed':'One declared covariate value changed',
      'multiple_covariate_values_changed':'Multiple declared covariate values changed',
      'treatment_values_changed_do_not_isolate_covariate_effect':'Treatment values changed; covariate effects are not isolated',
      'no_declared_numeric_input_change':'No declared numerical input change'}
    head='Comparison available' if available else 'Numerical comparison withheld'
    plot=_curve_svg(comparison) if available else '<p>Curves and numerical differences are withheld.</p>'
    covariates=''.join('<tr><th scope="row">'+_text(r['field'].replace('_',' '))+'</th><td>'+_text(r['left']['value'])+' '+_text(r['left']['unit'])+'</td><td>'+_text(r['right']['value'])+' '+_text(r['right']['unit'])+'</td><td>'+('Changed' if r['value_changed'] else 'Same')+'</td></tr>' for r in summary['covariate_changes'])
    def number(value):return '—' if value is None else f'{value:.6g}'
    metrics=''.join('<tr><th scope="row">'+_text(r['label'])+'</th><td>'+number(r['left'])+'</td><td>'+number(r['right'])+'</td><td>'+number(r['right_minus_left'])+'</td><td>'+number(r['percent_relative_to_left'])+'</td><td>'+_text(r['unit'])+'</td></tr>' for r in summary['metrics'] or [])
    sources=''.join('<tr><th scope="row">'+side.title()+'</th><td>Run #'+_text(summary[side+'_run_id'])+' · '+_text(summary[side+'_source']['title'])+'</td><td class="hash">'+_text(summary[side+'_source']['payload_sha256'])+'</td></tr>' for side in ('left','right'))
    requests=''.join('<details><summary>'+side.title()+' declared treatment request</summary><pre>'+_text(json.dumps(summary[side+'_source']['request'],indent=2,ensure_ascii=False))+'</pre></details>' for side in ('left','right'))
    blockers=''.join('<li>'+_text(b.get('code',str(b)))+': '+_text(b.get('message',''))+'</li>' for side in ('left','right') for b in summary[side+'_source']['clinical_review_blockers'])
    withheld=''.join('<li>'+_text(reason)+'</li>' for reason in summary['withheld_reasons'])
    peaks=''
    if available:
        for side in ('left','right'):
            peak=summary['sampled_peak_context'][side]
            peaks+='<li>'+side.title()+': '+_text(peak['sampling_step_h'])+' h sample interval; '+_text(peak['sample_count'])+' samples; boundary maximum: '+_text(peak['maximum_on_window_boundary'])+'. Equal-maximum sample times: '+_text(peak['equal_maximum_times_h'])+' h.</li>'
    return '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Educational PK comparison</title><style>
:root{color-scheme:light}*{box-sizing:border-box}body{margin:0;background:#f3f6f7;color:#172d38;font:16px/1.6 system-ui,sans-serif}main{max-width:1120px;margin:auto;padding:32px 22px}header{margin-bottom:25px}h1{font-size:30px;line-height:1.25}h2{font-size:21px;margin-top:0}.eyebrow{font-weight:700;letter-spacing:.1em;text-transform:uppercase;font-size:12px;color:#42616b}.notice{background:#fff4d9;border-left:4px solid #b7791f;padding:15px 20px}.card{background:white;border:1px solid #dce4e6;padding:24px;margin-top:20px}.table-scroll{overflow:auto}table{width:100%;border-collapse:collapse;font-size:14px}th,td{text-align:left;padding:11px;border-bottom:1px solid #e2e8eb;vertical-align:top}thead{background:#f4f7f8}th{font-weight:600}svg{display:block;width:100%;height:auto}svg text{font:12px system-ui,sans-serif;fill:#40525e}.legend{display:flex;gap:24px;flex-wrap:wrap}.left{color:#2563eb}.right{color:#b45309}.hash{overflow-wrap:anywhere;font-family:monospace;font-size:12px}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f4f7f8;padding:16px;font-size:12px}summary{cursor:pointer;padding:8px 0}small{color:#49606a}a{color:#245166}@media print{body{background:white}main{padding:0}.card{break-inside:avoid}details{display:block}}
</style></head><body><main><header><div class="eyebrow">Patient Lab · educational archive</div><h1>Saved PK comparison</h1><p>Revision #'''+_text(summary['revision_id'])+' · Left run #'+_text(summary['left_run_id'])+' · Right run #'+_text(summary['right_run_id'])+'''</p><div class="notice"><strong>Educational model outputs</strong><br>Clinical prediction validated: false · Patient simulation ready: false<br>These curves do not establish individual efficacy, toxicity or dose suitability.</div></header>
<section class="card"><h2>'''+head+'</h2><p>'+_text(labels.get(context['status'],context['status']))+'</p><p>Changed covariate values: '+_text(', '.join(context['changed_covariate_values']) or 'none')+'. Changed covariate metadata: '+_text(', '.join(context['changed_covariate_metadata']) or 'none')+'.</p><p>Treatment values changed: '+_text(context['treatment_values_changed'])+' · Full request metadata/values changed: '+_text(context['full_treatment_request_changed'])+'</p><ul>'+withheld+'</ul><div class="table-scroll"><table><thead><tr><th>Covariate</th><th>Left</th><th>Right</th><th>Numerical change</th></tr></thead><tbody>'+covariates+'</tbody></table></div>'+requests+'''</section>
<section class="card"><h2>Concentration over the archived window</h2><p class="legend"><strong class="left">Blue: left run</strong><strong class="right">Orange: right run</strong></p>'''+plot+'''<small>Lines connect archived samples on common linear axes. No interpolation model or simulation was executed for this export. Compartments are mathematical states, not anatomical organs.</small></section>
<section class="card"><h2>Exposure and parameter differences</h2><p>Direction: right minus left. Percentages use the left value as reference. No dose normalization.</p><div class="table-scroll"><table><thead><tr><th>Metric</th><th>Left</th><th>Right</th><th>Difference</th><th>Change (%)</th><th>Unit</th></tr></thead><tbody>'''+metrics+'''</tbody></table></div><p>AUC covers the common recorded window. Peak values are maxima among archived samples, not exact continuous Cmax/Tmax, per-dose peaks or steady-state values.</p><ul>'''+peaks+'''</ul></section>
<section class="card"><h2>Source traceability</h2><div class="table-scroll"><table><thead><tr><th>Side</th><th>Archive</th><th>Payload SHA256</th></tr></thead><tbody>'''+sources+'</tbody></table></div><p>Summary report SHA256:</p><p class="hash">'+_text(summary['report_sha256'])+'</p><p>Source comparison SHA256:</p><p class="hash">'+_text(summary['source_comparison_sha256'])+'</p><p>Method: '+_text(summary['method_version'])+'''</p><p>This document is a snapshot. It is not digitally signed; its displayed hashes do not authenticate edits to the HTML. Preserve the original JSON report for integrity verification.</p></section>
<section class="card"><h2>Unresolved clinical review</h2><ul>'''+blockers+'</ul><p>'+_text(summary['limitation'])+'''</p></section></main></body></html>'''
