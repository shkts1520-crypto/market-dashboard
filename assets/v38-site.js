(function () {
  'use strict';

  const TAB_SELECTOR = 'a.tabx[href^="#"]';
  const SECTION_IDS = [
    't-market', 't-alloc', 't-port', 't-today', 't-rotation', 't-movers',
    't-rs', 't-weekly', 't-options', 't-post1', 't-rules'
  ];

  function targetOf(tab) {
    const href = tab && tab.getAttribute('href');
    return href && href.startsWith('#') ? href.slice(1) : '';
  }

  function forceTop() {
    const top = () => window.scrollTo(0, 0);
    top();
    requestAnimationFrame(() => {
      top();
      requestAnimationFrame(top);
    });
    setTimeout(top, 0);
    setTimeout(top, 80);
  }

  function activate(targetId, updateHistory) {
    if (!SECTION_IDS.includes(targetId)) targetId = SECTION_IDS[0];
    document.querySelectorAll('section').forEach((section) => {
      section.classList.toggle('on', section.id === targetId);
    });
    document.querySelectorAll(TAB_SELECTOR).forEach((tab) => {
      const active = targetOf(tab) === targetId;
      tab.classList.toggle('on', active);
      tab.setAttribute('aria-selected', active ? 'true' : 'false');
    });
    if (updateHistory) {
      const hash = '#' + targetId;
      if (location.hash !== hash) history.pushState({v38Tab: targetId}, '', hash);
    }
    forceTop();
  }

  function activateFromLocation() {
    activate((location.hash || '#t-market').slice(1), false);
  }

  function rememberCardTitles() {
    document.querySelectorAll('section .card').forEach((card) => {
      if (card.dataset.v38CardTitle) return;
      const heading = card.querySelector('h2,.hdr h2,.chd h2');
      if (heading) card.dataset.v38CardTitle = String(heading.textContent || '').replace(/\s+/g, ' ').trim();
    });
  }

  function renderHeader(view) {
    const asof = document.querySelector('header .asof');
    if (asof) {
      const generated = view.generated_at ? '　取得 ' + view.generated_at : '';
      asof.textContent = '分析基準日 ' + (view.session_date || '—') + generated + '　｜　LIVE DATA';
    }
  }

  function markSections(view) {
    const bindings = [
      ['t-market', 'daily'], ['t-alloc', 'positions'], ['t-port', 'core12'],
      ['t-today', 'setups'], ['t-rotation', 'rotation'], ['t-movers', 'movers'],
      ['t-rs', 'rs'], ['t-weekly', 'weekly'], ['t-options', 'options'],
      ['t-post1', 'publish'], ['t-rules', 'rules']
    ];
    bindings.forEach(([sectionId, key]) => {
      const section = document.getElementById(sectionId);
      const data = view && view[key];
      if (section) section.dataset.v38Status = (data && data.status) || 'SOURCE_UNAVAILABLE';
    });
  }

  function renderLiveView(view) {
    renderHeader(view);
    markSections(view);
    window.V38UiViewModel = view;
    document.dispatchEvent(new CustomEvent('v38:view-ready', {detail: view}));
    document.body.dataset.v38BindingStatus = 'ready';
  }

  function renderAllUnavailable(detail) {
    SECTION_IDS.forEach((id) => {
      const section = document.getElementById(id);
      if (!section) return;
      section.dataset.v38Status = 'SOURCE_UNAVAILABLE';
      section.dataset.v38Reason = detail;
    });
    document.body.dataset.v38BindingStatus = 'failed';
  }

  async function loadProductionData() {
    const runtime = window.V38Runtime;
    if (!runtime || typeof runtime.loadJson !== 'function') {
      renderAllUnavailable('RUNTIME_UNAVAILABLE');
      return;
    }
    try {
      const [payload, view] = await Promise.all([
        runtime.loadJson('data/ui_payload.json'),
        runtime.loadJson('data/ui_view_model.json')
      ]);
      window.V38UiPayload = payload;
      renderLiveView(view);
    } catch (_) {
      renderAllUnavailable('AUTHORITATIVE_UI_DATA_UNAVAILABLE');
    }
  }

  document.addEventListener('DOMContentLoaded', () => {
    if ('scrollRestoration' in history) history.scrollRestoration = 'manual';
    rememberCardTitles();
    document.querySelectorAll(TAB_SELECTOR).forEach((tab) => {
      tab.addEventListener('click', (event) => {
        const target = targetOf(tab);
        if (!target) return;
        event.preventDefault();
        activate(target, true);
      });
    });
    window.addEventListener('popstate', activateFromLocation);
    window.addEventListener('hashchange', activateFromLocation);
    activateFromLocation();
    loadProductionData();
  }, {once: true});
})();
