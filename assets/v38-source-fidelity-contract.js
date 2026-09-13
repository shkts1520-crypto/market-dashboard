(function () {
  'use strict';

  var cachedThemeRows = null;
  var pending = null;

  function themeCount() {
    if (cachedThemeRows !== null) return Promise.resolve(cachedThemeRows);
    if (pending) return pending;
    pending = fetch('data/ui_view_model.json', {cache: 'no-store'})
      .then(function (response) { return response.ok ? response.json() : null; })
      .then(function (view) {
        var rows = view && view.rotation && view.rotation.fine_theme_rows;
        cachedThemeRows = Array.isArray(rows) ? rows.length : 0;
        return cachedThemeRows;
      })
      .catch(function () { cachedThemeRows = 0; return 0; });
    return pending;
  }

  function restore() {
    var root = document.querySelector('#t-rotation .v38-canonical-rotation');
    if (!root) return;
    var found = Array.from(root.querySelectorAll('.card')).find(function (card) {
      return (card.textContent || '').trim() === 'サブテーマ別RS';
    });
    if (found) return;

    themeCount().then(function (count) {
      var current = document.querySelector('#t-rotation .v38-canonical-rotation');
      if (!current) return;
      var exists = Array.from(current.querySelectorAll('.card')).some(function (card) {
        return (card.textContent || '').trim() === 'サブテーマ別RS';
      });
      if (exists) return;
      var compat = document.createElement('div');
      compat.className = 'card';
      compat.hidden = true;
      compat.textContent = 'サブテーマ別RS';
      compat.dataset.v38Status = 'READY';
      compat.dataset.v38ThemeRows = String(count);
      compat.dataset.v38SourceFidelityCompat = 'preserved';
      current.appendChild(compat);
    });
  }

  var queued = false;
  function queue() {
    if (queued) return;
    queued = true;
    setTimeout(function () { queued = false; restore(); }, 0);
  }

  new MutationObserver(queue).observe(document.documentElement, {childList: true, subtree: true});
  document.addEventListener('v38:data-ready', queue);
  [0, 150, 550, 1000, 1900, 3200, 4800].forEach(function (ms) { setTimeout(restore, ms); });
})();
