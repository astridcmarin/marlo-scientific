/* A numeric educational projection. The archived JSON is the provenance record. */
(function (host) {
  'use strict';
  const VERSION = 'archived-pk-timeline-csv-v1';
  const valueKeys = ['time_h','concentration_ng_ml','auc_ng_h_ml','requested_mg','accounted_mg'];
  const valid = p => p && Array.isArray(p.amounts_mg) && p.amounts_mg.length === 10 &&
    [...p.amounts_mg, ...valueKeys.map(k => p[k])].every(v => typeof v === 'number' && Number.isFinite(v) && v >= 0);
  function build(points, events, metadata, eventsAvailable) {
    const m = metadata;
    if (!m || !['run_id','scenario_id','revision_id'].every(k => Number.isSafeInteger(m[k]) && m[k] > 0) ||
        !['payload_sha256','report_sha256','revision_payload_sha256','execution_contract_sha256'].every(k => /^[a-f0-9]{64}$/.test(m[k])) ||
        m.method_version !== 'hughes-educational-pk-v1.0' ||
        typeof m.solver_method_version !== 'string' || !/^[a-zA-Z0-9._-]{1,100}$/.test(m.solver_method_version))
      throw new Error('Missing supported archived run provenance');
    if (!Array.isArray(points) || !points.length || points.length > 721 || !points.every(valid) ||
        points[0].time_h !== 0 || points.some((p,i) => p.time_h > 72 || (i && p.time_h <= points[i-1].time_h)))
      throw new Error('Unsupported archived points');
    if (typeof eventsAvailable !== 'boolean' || !Array.isArray(events) || events.length > 4 ||
        (!eventsAvailable && events.length) || (eventsAvailable && !events.length)) throw new Error('Unsupported event coverage');
    const eventMap = new Map();
    events.forEach(e => {
      if (!e || !Number.isInteger(e.index) || e.index < 0 || e.index >= points.length || eventMap.has(e.index) ||
          typeof e.amount_mg !== 'number' || !Number.isFinite(e.amount_mg) || e.amount_mg <= 0 ||
          !valid(e.before) || !valid(e.after) || e.time_h !== points[e.index].time_h ||
          e.before.time_h !== e.time_h || e.after.time_h !== e.time_h ||
          valueKeys.some(k => e.after[k] !== points[e.index][k]) ||
          e.after.amounts_mg.some((a,i) => a !== points[e.index].amounts_mg[i]))
        throw new Error('Unsupported archived boundary');
      eventMap.set(e.index, e);
    });
    const headers = ['export_version','purpose','clinical_prediction_validated','patient_simulation_ready',
      'run_id','scenario_id','revision_id','payload_sha256','report_sha256','revision_payload_sha256',
      'execution_contract_sha256','method_version','solver_method_version','boundary_coverage',
      'sampled_point_index_zero_based','state','request_amount_mg','time_h',
      'absorption_amount_mg', ...Array.from({length:7}, (_,i) => `transit_${i+1}_amount_mg`),
      'central_amount_mg','eliminated_amount_mg','concentration_ng_ml','auc_0_t_ng_h_ml',
      'cumulative_requested_amount_mg','accounted_amount_mg'];
    const prefix = [VERSION,'synthetic_educational',false,false,m.run_id,m.scenario_id,m.revision_id,
      m.payload_sha256,m.report_sha256,m.revision_payload_sha256,m.execution_contract_sha256,
      m.method_version,m.solver_method_version,eventsAvailable ? 'available' : 'unavailable'];
    const rows = [headers];
    const row = (p,index,state,amount) => rows.push([...prefix,index,state,amount,p.time_h,
      ...p.amounts_mg,p.concentration_ng_ml,p.auc_ng_h_ml,p.requested_mg,p.accounted_mg]);
    points.forEach((p,index) => {
      const event = eventMap.get(index);
      if (event) row(event.before,index,'boundary_before_request',event.amount_mg);
      row(p,index,event ? 'sampled_after_request' : 'sampled',event ? event.amount_mg : '');
    });
    // All fields are fixed identifiers, validated numerics or restricted metadata.
    const cell = value => '"' + String(value).replace(/"/g, '""') + '"';
    return rows.map(r => r.map(cell).join(',')).join('\r\n') + '\r\n';
  }
  function download(csv, runId, browser) {
    const url = browser.URL.createObjectURL(new browser.Blob([csv], {type:'text/csv;charset=utf-8'}));
    let anchor;
    let clicked = false;
    try {
      anchor = browser.document.createElement('a');
      anchor.href = url; anchor.download = `saved-educational-pk-run-${runId}-timeline.csv`;
      anchor.hidden = true; browser.document.body.appendChild(anchor);
      anchor.click(); clicked = true;
    } finally {
      if (anchor && anchor.parentNode) anchor.parentNode.removeChild(anchor);
      if (clicked) browser.setTimeout(() => browser.URL.revokeObjectURL(url), 10000);
      else browser.URL.revokeObjectURL(url);
    }
  }
  const api = {build, download};
  if (typeof module === 'object' && module.exports) module.exports = api;
  else host.PKTimelineCSV = api;
})(typeof window === 'object' ? window : globalThis);
