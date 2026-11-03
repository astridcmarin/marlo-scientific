/* Keep the reader's place when a control reloads the same page (3 November 2026).
 *
 * Many controls are plain links or forms that reload the page they are on (a slider value, a filter, a tab,
 * "Show"). Without this, the browser opens the new page at the top. When a link or form (GET or POST) leads back to the same path,
 * the scroll position is remembered for up to a minute and restored once the new page has loaded. Links to other pages,
 * downloads, new tabs and in-page anchors behave as before. Uses sessionStorage only; nothing leaves the browser.
 */
(function () {
  'use strict';
  var KEY = 'marlo-scroll';
  var MAX_AGE_MS = 60000;  // generous: a slow network can hold the page before its scripts run

  function remember() {
    try {
      sessionStorage.setItem(KEY, JSON.stringify({ path: location.pathname, y: window.scrollY, at: Date.now() }));
    } catch (e) { /* storage unavailable: the page simply opens at the top */ }
  }

  function samePath(url) {
    try {
      var u = new URL(url, location.href);
      return u.origin === location.origin && u.pathname === location.pathname;
    } catch (e) { return false; }
  }

  document.addEventListener('click', function (ev) {
    if (ev.defaultPrevented || ev.button !== 0 || ev.metaKey || ev.ctrlKey || ev.shiftKey || ev.altKey) return;
    var a = ev.target.closest && ev.target.closest('a[href]');
    if (!a || a.target || a.hasAttribute('download')) return;
    var href = a.getAttribute('href');
    if (!href || href.charAt(0) === '#') return;
    if (/[?&]format=(json|csv)/.test(href)) return;
    if (samePath(a.href)) remember();
  }, true);

  document.addEventListener('submit', function (ev) {
    var form = ev.target;
    if (form.target) return;
    if (samePath(form.getAttribute('action') ? form.action : location.href)) remember();
  }, true);

  function restore() {
    var saved = null;
    try { saved = JSON.parse(sessionStorage.getItem(KEY) || 'null'); } catch (e) { return; }
    if (!saved || saved.path !== location.pathname || Date.now() - saved.at > MAX_AGE_MS) return;
    if (location.hash) return;
    window.scrollTo(0, saved.y);
    // Pages that finish laying out after load (charts, the 3D view) get a second try, then the memory is cleared.
    window.addEventListener('load', function () {
      window.scrollTo(0, saved.y);
      try { sessionStorage.removeItem(KEY); } catch (e) { /* ignore */ }
    });
  }
  if ('scrollRestoration' in history) history.scrollRestoration = 'auto';
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', restore); else restore();
}());
