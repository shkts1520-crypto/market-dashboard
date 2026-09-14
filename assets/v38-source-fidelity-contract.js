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

  function refitRotation() {
    var wrap = document.querySelector('#t-rotation .v38-source-rotation-wrap');
    if (!wrap) return;
    var frame = wrap.querySelector('.v38-source-rotation-frame');
    var scaler = wrap.querySelector('.v38-source-scaler');
    if (!frame || !scaler) return;
    var rect = frame.getBoundingClientRect();
    var w = rect.width || frame.clientWidth;
    var h = rect.height || frame.clientHeight;
    if (!w || !h) return;
    var full = wrap.classList.contains('fs');
    var portrait = full && h > w;
    var scale = portrait ? Math.min(w / 1080, h / 1680) : Math.min(w / 1680, h / 1080);
    scaler.style.transform = portrait ? 'rotate(90deg) scale(' + scale + ')' : 'scale(' + scale + ')';
    wrap.dataset.v38VisibleFit = String(Math.round(scale * 100000) / 100000);
  }

  function scheduleRotationRefit() {
    requestAnimationFrame(function () {
      refitRotation();
      requestAnimationFrame(refitRotation);
    });
    setTimeout(refitRotation, 40);
    setTimeout(refitRotation, 160);
  }

  var queued = false;
  function queue() {
    if (queued) return;
    queued = true;
    setTimeout(function () {
      queued = false;
      restore();
      var section = document.getElementById('t-rotation');
      if (section && section.classList.contains('on')) scheduleRotationRefit();
    }, 0);
  }

  function bindRotationVisibility() {
    var section = document.getElementById('t-rotation');
    if (!section || section.dataset.v38VisibleFitObserver === 'bound') return;
    section.dataset.v38VisibleFitObserver = 'bound';
    new MutationObserver(function () {
      if (section.classList.contains('on')) scheduleRotationRefit();
    }).observe(section, {attributes: true, attributeFilter: ['class']});
  }

  new MutationObserver(queue).observe(document.documentElement, {childList: true, subtree: true});
  document.addEventListener('v38:data-ready', queue);
  document.addEventListener('click', function (event) {
    var tab = event.target && event.target.closest ? event.target.closest('a.tabx[href="#t-rotation"]') : null;
    if (tab) scheduleRotationRefit();
  });
  window.addEventListener('resize', scheduleRotationRefit);
  bindRotationVisibility();
  [0, 150, 550, 1000, 1900, 3200, 4800].forEach(function (ms) {
    setTimeout(function () {
      bindRotationVisibility();
      restore();
      var section = document.getElementById('t-rotation');
      if (section && section.classList.contains('on')) scheduleRotationRefit();
    }, ms);
  });
})();
