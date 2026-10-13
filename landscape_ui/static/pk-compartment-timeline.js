/* Retained points and before/after boundaries only. No interpolation or model calls. */
(() => {
  'use strict';
  document.querySelectorAll('[data-pk-timeline]').forEach(root => {
    const q = selector => root.querySelector(selector);
    const validPoint = p => p && Array.isArray(p.amounts_mg) && p.amounts_mg.length === 10 &&
      [...p.amounts_mg, p.time_h, p.concentration_ng_ml, p.auc_ng_h_ml, p.requested_mg, p.accounted_mg]
        .every(v => typeof v === 'number' && Number.isFinite(v) && v >= 0);
    let points;
    try {
      points = JSON.parse(q('[data-pk-points]').textContent);
      if (!Array.isArray(points) || !points.length || points.length > 721 || !points.every(validPoint)) return;
    } catch (_) { return; }
    let events = [];
    try {
      const source = q('[data-pk-events]');
      const supplied = source ? JSON.parse(source.textContent) : [];
      if (Array.isArray(supplied) && supplied.length <= 4 && supplied.every(e => e &&
        Number.isInteger(e.index) && e.index >= 0 && e.index < points.length &&
        typeof e.amount_mg === 'number' && Number.isFinite(e.amount_mg) && e.amount_mg > 0 &&
        e.time_h === points[e.index].time_h && validPoint(e.before) && validPoint(e.after))) events = supplied;
    } catch (_) { /* Keep sampled-point navigation available. */ }
    const eventMap = new Map(events.map(e => [e.index, e]));
    // Use coordinates from the existing archived curve, never interpolate.
    const chartMarkers = [];
    document.querySelectorAll('[data-pk-archive-chart]').forEach(svg => {
      const unit = svg.getAttribute('data-pk-archive-chart');
      const key = unit === 'ng/mL' ? 'concentration_ng_ml' : unit === 'ng·h/mL' ? 'auc_ng_h_ml' : null;
      if (!key || svg.getAttribute('viewBox') !== '0 0 780 305' || points.length < 2) return;
      const curves = svg.querySelectorAll('polyline');
      if (curves.length !== 1 || svg.querySelector('[data-pk-chart-marker]')) return;
      const raw = curves[0].getAttribute('points');
      if (!raw) return;
      const coordinates = raw.trim().split(/\s+/).map(pair => pair.split(',').map(Number));
      const horizon = points[points.length - 1].time_h;
      const top = (Math.max(...points.map(p => p[key])) || 1) * 1.1;
      if (!(horizon > 0) || !Number.isFinite(top) || coordinates.length !== points.length ||
          coordinates.some((xy, i) => xy.length !== 2 || !xy.every(Number.isFinite) ||
            Math.abs(xy[0] - (70 + 670 * points[i].time_h / horizon)) > .001 ||
            Math.abs(xy[1] - (250 - 220 * points[i][key] / top)) > .001)) return;
      const make = (tag, attributes) => {
        const node = document.createElementNS('http://www.w3.org/2000/svg', tag);
        Object.entries(attributes).forEach(([name, value]) => node.setAttribute(name, String(value)));
        return node;
      };
      const group = make('g', {'data-pk-chart-marker':'', 'aria-hidden':'true', 'pointer-events':'none'});
      const line = make('line', {y1:30, y2:250, stroke:'#a63d16', 'stroke-width':1.5, 'stroke-dasharray':'5 4'});
      const dot = make('circle', {r:5, fill:'#a63d16', stroke:'#fff', 'stroke-width':2});
      group.appendChild(line); group.appendChild(dot); svg.appendChild(group);
      chartMarkers.push({coordinates, line, dot});
    });
    const chartNote = q('[data-pk-chart-note]');
    if (chartNote) chartNote.hidden = chartMarkers.length === 0;
    const slider = q('[data-pk-position]');
    const prev = q('[data-pk-prev]');
    const next = q('[data-pk-next]');
    const phase = q('[data-pk-phase]');
    const number = new Intl.NumberFormat('en-US', {maximumFractionDigits: 6});
    function show(index, requestedPhase = 'after') {
      index = Math.max(0, Math.min(points.length - 1, Math.trunc(index)));
      if (!Number.isFinite(index)) return;
      const event = eventMap.get(index);
      const before = Boolean(event && requestedPhase === 'before');
      const p = event ? (before ? event.before : event.after) : points[index];
      const state = event ? `${before ? 'Before' : 'After'} ${number.format(event.amount_mg)} mg synthetic request` : 'Archived sampled point';
      slider.value = String(index);
      slider.setAttribute('aria-valuetext', `${p.time_h.toFixed(3)} hours; ${state}; point ${index + 1} of ${points.length}`);
      q('[data-pk-time]').textContent = `${p.time_h.toFixed(3)} h`;
      q('[data-pk-status]').textContent = `Point ${index + 1} of ${points.length} · ${state}`;
      if (phase) { phase.disabled = !event; phase.value = before ? 'before' : 'after'; }
      for (const [name, key] of [['concentration','concentration_ng_ml'], ['auc','auc_ng_h_ml'], ['requested','requested_mg'], ['accounted','accounted_mg']])
        q(`[data-pk-${name}]`).textContent = number.format(p[key]);
      p.amounts_mg.forEach((amount, i) => {
        q(`[data-pk-amount="${i}"]`).textContent = number.format(amount);
        const meter = q(`[data-pk-meter="${i}"]`);
        meter.max = p.requested_mg > 0 ? p.requested_mg : 1;
        meter.value = amount;
      });
      chartMarkers.forEach(({coordinates, line, dot}) => {
        const [x, y] = coordinates[index];
        line.setAttribute('x1', String(x)); line.setAttribute('x2', String(x));
        dot.setAttribute('cx', String(x)); dot.setAttribute('cy', String(y));
      });
      prev.disabled = index === 0;
      next.disabled = index === points.length - 1;
    }
    const play = q('[data-pk-play]');
    const speed = q('[data-pk-speed]');
    const playbackStatus = q('[data-pk-playback-status]');
    let timer = null;
    function stop(message = 'Playback paused.') {
      if (timer !== null) { clearInterval(timer); timer = null; }
      if (play) { play.textContent = 'Play archived timeline'; play.setAttribute('aria-pressed', 'false'); }
      if (playbackStatus) playbackStatus.textContent = message;
      q('[data-pk-status]').setAttribute('aria-live', 'polite');
    }
    function intervalMs() {
      const rate = Number(speed.value);
      return 1000 / ([1, 4, 10].includes(rate) ? rate : 4);
    }
    function tick() {
      if (document.hidden) { stop('Playback paused while the page is hidden.'); return; }
      const index = Number(slider.value);
      if (index >= points.length - 1) { stop('Playback complete.'); return; }
      show(index + 1);
      if (index + 1 === points.length - 1) stop('Playback complete.');
    }
    if (play && speed) {
      play.disabled = points.length < 2;
      play.addEventListener('click', () => {
        if (timer !== null) { stop(); return; }
        if (points.length < 2 || document.hidden) return;
        const index = Number(slider.value);
        show(index >= points.length - 1 ? 0 : index); // Playback uses archived after-request points.
        q('[data-pk-status]').setAttribute('aria-live', 'off');
        play.textContent = 'Pause'; play.setAttribute('aria-pressed', 'true');
        if (playbackStatus) playbackStatus.textContent = 'Playing archived points.';
        timer = setInterval(tick, intervalMs());
      });
      speed.addEventListener('change', () => {
        if (timer !== null) { clearInterval(timer); timer = setInterval(tick, intervalMs()); }
      });
      document.addEventListener('visibilitychange', () => {
        if (document.hidden && timer !== null) stop('Playback paused while the page is hidden.');
      });
      window.addEventListener('pagehide', () => stop());
    }
    const csvButton = q('[data-pk-csv]');
    const csvStatus = q('[data-pk-csv-status]');
    if (csvButton) csvButton.disabled = true;
    if (csvButton && csvStatus && window.PKTimelineCSV && window.Blob && window.URL &&
        typeof window.URL.createObjectURL === 'function' && typeof window.URL.revokeObjectURL === 'function') {
      try {
        const metadata = JSON.parse(q('[data-pk-csv-metadata]').textContent);
        const coverage = JSON.parse(q('[data-pk-boundary-coverage]').textContent);
        const csv = window.PKTimelineCSV.build(points, events, metadata, coverage);
        csvButton.disabled = false;
        csvStatus.textContent = coverage ? 'Archived timeline CSV ready.' : 'CSV ready; request boundary snapshots are unavailable.';
        csvButton.addEventListener('click', () => {
          stop();
          try {
            window.PKTimelineCSV.download(csv, metadata.run_id, window);
            csvStatus.textContent = 'CSV download requested. Keep the archived JSON with it for full provenance.';
          } catch (_) { csvStatus.textContent = 'CSV download could not be started. Use the archived JSON download instead.'; }
        });
      } catch (_) { csvStatus.textContent = 'CSV withheld: supported archive provenance or numerical data are unavailable. Use the archived JSON download.'; }
    }
    slider.max = String(points.length - 1);
    slider.addEventListener('input', () => { stop(); show(Number(slider.value)); });
    prev.addEventListener('click', () => { stop(); show(Number(slider.value) - 1); });
    next.addEventListener('click', () => { stop(); show(Number(slider.value) + 1); });
    q('[data-pk-reset]').addEventListener('click', () => { stop(); show(0); });
    if (phase) phase.addEventListener('change', () => { stop(); show(Number(slider.value), phase.value); });
    root.querySelectorAll('[data-pk-jump]').forEach(button => {
      const index = Number(button.getAttribute('data-pk-jump'));
      button.disabled = !eventMap.has(index);
      button.addEventListener('click', () => { stop(); if (eventMap.has(index)) show(index); });
    });
    const eventControls = q('[data-pk-event-controls]');
    if (eventControls) eventControls.hidden = events.length === 0;
    show(0);
    q('[data-pk-controls]').hidden = false;
    q('[data-pk-fallback]').hidden = true;
  });
})();
