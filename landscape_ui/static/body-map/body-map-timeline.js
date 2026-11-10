// Digital human 1.1e: the timeline slider. Stepped by the user only; nothing moves on its own.
(function () {
  var data = document.getElementById('bm-timeline-data');
  var slider = document.getElementById('bm-tl-slider');
  if (!data || !slider) return;
  var rows = JSON.parse(data.textContent);
  var marker = document.getElementById('bm-tl-marker');
  var out = document.getElementById('bm-tl-time');
  var cells = {};
  document.querySelectorAll('#bm-tl-amounts td[data-k]').forEach(function (td) { cells[td.dataset.k] = td; });
  var pct = function (v) { return (v < 0.05 ? 0 : v).toFixed(v >= 10 ? 0 : 1) + '%'; };
  function show(i) {
    var r = rows[i];
    out.textContent = r.t + ' h';
    marker.setAttribute('x1', r.x); marker.setAttribute('x2', r.x);
    ['gut', 'body', 'urine', 'non_renal'].forEach(function (k) { cells[k].textContent = pct(r.p[k]); });
    cells.plasma.textContent = Math.round(r.c) + ' ng/mL';
  }
  slider.addEventListener('input', function () { show(+slider.value); });
  show(+slider.value);
})();
