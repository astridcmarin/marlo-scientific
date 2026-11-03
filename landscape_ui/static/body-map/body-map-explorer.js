// Digital human 1.0, step 1.4: keeps the explorer's slider and number box in step, and shows the new value when the
// slider is released. The form works without this script (type a number and press Show).
(function () {
  'use strict';
  var form = document.querySelector('.bm-explorer');
  if (!form) return;
  var range = form.querySelector('[data-role="crcl-range"]');
  var number = form.querySelector('[data-role="crcl-number"]');
  if (!range || !number) return;
  range.addEventListener('input', function () { number.value = range.value; });
  range.addEventListener('change', function () { form.submit(); });
  number.addEventListener('input', function () {
    var v = parseFloat(number.value);
    if (isFinite(v) && v >= parseFloat(range.min) && v <= parseFloat(range.max)) range.value = String(v);
  });
}());
