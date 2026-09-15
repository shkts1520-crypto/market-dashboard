(function () {
  'use strict';

  const BASELINE_REASON = 'BASELINE_CARD_SOURCE_UNAVAILABLE';
  const ROTATION_REASON = 'ROTATION_INDEX_BREADTH_SOURCE_UNAVAILABLE';
  const GENERIC_REASON = 'AUTHORITATIVE_CARD_INPUT_NOT_AVAILABLE';
  const SECTION_STATUS = {
    't-market': 'daily',
    't-alloc': 'positions',
    't-port': 'core12',
    't-today': 'setups',
    't-rotation': 'rotation',
    't-movers': 'movers',
    't-rs': 'rs',
    't-weekly': 'weekly',
    't-options': 'options',
    't-post1': 'publish',
    't-rules': 'rules'
  };

  function titleOf(card) {
    return String(card && (card.dataset.v38CardTitle || (card.querySelector('h2') || {}).textContent) || '').trim();
  }

  function tickerButton(ticker) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'v38-ticker-link';
    button.textContent = ticker;
    button.addEventListener('click', function () {
      if (window.V38OpenTickerChart) window.V38OpenTickerChart(ticker);
    });
    return button;
  }

  function fillLeaderWatch(card, rows) {
    const host = card && card.querySelector('.v38-baseline-card-body');
    if (!host) return false;
    const leaders = (Array.isArray(rows) ? rows : [])
      .filter(function (row) { return row && row.ticker && Number.isFinite(Number(row.rs189)); })
      .slice()
      .sort(function (a, b) { return Number(b.rs189) - Number(a.rs189); })
      .slice(0, 16);
    if (!leaders.length) return false;
    host.replaceChildren();
    host.dataset.v38Status = 'READY';
    host.dataset.v38Reason = 'SETUPS_READY_RS189_LEADERS';
    const list = document.createElement('div');
    list.className = 'chips';
    leaders.forEach(function (row) {
      const wrap = document.createElement('span');
      wrap.className = 'chip';
      wrap.appendChild(tickerButton(String(row.ticker).toUpperCase()));
      const meta = document.createElement('span');
      meta.className = 'mut';
      meta.textContent = ' RS189 ' + Number(row.rs189).toFixed(0);
      wrap.appendChild(meta);
      list.appendChild(wrap);
    });
    host.appendChild(list);
    card.dataset.v38Status = 'READY';
    card.dataset.v38BindingKey = 'setups-leader-watch';
    return true;
  }

  function suppressUnboundBaselineCards(view) {
    const setups = view && view.setups;
    if (!setups || setups.status !== 'READY') return;
    const rows = Array.isArray(setups.rows) ? setups.rows : [];
    document.querySelectorAll('#t-today .card').forEach(function (card) {
      const host = card.querySelector('.v38-baseline-card-body');
      if (!host || host.dataset.v38Reason !== BASELINE_REASON) return;
      const title = titleOf(card);
      if (title.indexOf('リーダー監視') >= 0 && fillLeaderWatch(card, rows)) return;
      if (title.indexOf('Multi VWAP') >= 0) return;
      card.hidden = true;
      card.dataset.v38PlaceholderSuppressed = 'true';
      card.dataset.v38SuppressedReason = 'UNBOUND_BASELINE_SCAFFOLD';
    });
  }

  function suppressFalseRotationPlaceholder(view) {
    const rotation = view && view.rotation;
    if (!rotation || rotation.status !== 'READY') return;
    document.querySelectorAll('#t-rotation .v38-baseline-card-body').forEach(function (host) {
      if (host.dataset.v38Reason !== ROTATION_REASON) return;
      const card = host.closest('.card');
      if (card) {
        card.hidden = true;
        card.dataset.v38PlaceholderSuppressed = 'true';
        card.dataset.v38SuppressedReason = 'UNBOUND_ROTATION_SCAFFOLD';
      }
    });
  }

  function sectionReady(view, section) {
    const key = SECTION_STATUS[section.id];
    const payload = key && view && view[key];
    return Boolean(payload && payload.status === 'READY');
  }

  function suppressGenericReadyScaffolds(view) {
    Object.keys(SECTION_STATUS).forEach(function (id) {
      const section = document.getElementById(id);
      if (!section || !sectionReady(view, section)) return;
      section.querySelectorAll('.card[data-v38-status="DATA_REQUIRED"]').forEach(function (card) {
        const note = card.querySelector('.v38-bind-note[data-v38-status="DATA_REQUIRED"]');
        const text = String(note && note.textContent || '');
        if (!text.includes(GENERIC_REASON)) return;
        card.hidden = true;
        card.dataset.v38PlaceholderSuppressed = 'true';
        card.dataset.v38SuppressedReason = 'GENERIC_RENDER_SCAFFOLD';
      });
    });
  }

  function removeStaleReadyNotes() {
    document.querySelectorAll('.card[data-v38-status="READY"] .v38-bind-note').forEach(function (note) {
      const status = note.dataset.v38Status;
      if (status === 'DATA_REQUIRED' || status === 'STALE' || status === 'SOURCE_UNAVAILABLE') note.remove();
    });
  }

  function cleanPublish(view) {
    if (!view || !view.publish || view.publish.status !== 'READY') return;
    const wraps = Array.from(document.querySelectorAll('#t-post1 .postwrap'));
    wraps.slice(1).forEach(function (wrap) {
      const text = String(wrap.textContent || '');
      if (/ROTATION_PUBLISH_ARTIFACT_NOT_AVAILABLE|SOURCE_UNAVAILABLE|データ未取得/.test(text)) {
        wrap.hidden = true;
        wrap.dataset.v38PlaceholderSuppressed = 'true';
        wrap.dataset.v38SuppressedReason = 'UNBOUND_PUBLISH_SCAFFOLD';
      }
    });
  }

  async function run() {
    if (!window.V38Runtime || typeof window.V38Runtime.loadJson !== 'function') return;
    let view;
    try {
      view = await window.V38Runtime.loadJson('data/ui_view_model.json');
    } catch (_) {
      return;
    }
    suppressUnboundBaselineCards(view);
    suppressFalseRotationPlaceholder(view);
    suppressGenericReadyScaffolds(view);
    cleanPublish(view);
    removeStaleReadyNotes();
    document.body.dataset.v38StatusTruth = 'applied';
  }

  function schedule() {
    let attempts = 0;
    const timer = setInterval(function () {
      attempts += 1;
      if (document.body && document.body.dataset.v38BindingStatus === 'ready') {
        clearInterval(timer);
        run();
      } else if (attempts >= 40) {
        clearInterval(timer);
      }
    }, 100);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', schedule, {once: true});
  } else {
    schedule();
  }
})();
