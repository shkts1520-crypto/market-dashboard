(function () {
  'use strict';

  var queued = false;
  var viewPromise = null;

  function loadView() {
    if (!viewPromise) {
      viewPromise = fetch('data/ui_view_model.json', {cache: 'no-store'})
        .then(function (response) { return response.ok ? response.json() : null; })
        .catch(function () { return null; });
    }
    return viewPromise;
  }

  function repair() {
    queued = false;
    loadView().then(function (view) {
      var obs = view && view.daily && view.daily.display_observations;
      var regime = obs && obs.regime_history;
      if (!regime || regime.status !== 'READY') return;
      var records = Array.isArray(regime.records) ? regime.records : [];
      var latest = records.length ? records[records.length - 1] : null;
      var labels = Array.from(document.querySelectorAll('#t-market .riblab'));
      labels.forEach(function (label) {
        var text = String(label.textContent || '');
        if (!text.includes('レジーム履歴')) return;
        label.textContent = 'レジーム履歴　' +
          (latest && latest.state ? String(latest.state) + ' / ' : '') +
          '正本観測 ' + String(regime.observation_count || records.length) + '件';
        label.dataset.v38Status = 'READY';
        label.dataset.v38BindingKey = 'daily.display_observations.regime_history';
      });
    });
  }

  function queue() {
    if (queued) return;
    queued = true;
    requestAnimationFrame(repair);
  }

  document.addEventListener('v38:data-ready', queue);
  new MutationObserver(queue).observe(document.documentElement, {
    childList: true,
    subtree: true,
    characterData: true
  });
  [0, 250, 900, 1800, 3500].forEach(function (ms) { setTimeout(queue, ms); });
})();
