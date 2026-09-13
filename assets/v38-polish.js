(function () {
  'use strict';

  const TAB_SELECTOR = 'nav a.tabx[href^="#"]';
  const SECTION_IDS = [
    't-market', 't-alloc', 't-port', 't-rotation', 't-rs',
    't-weekly', 't-options', 't-post1', 't-rules'
  ];
  let navReady = false;
  let polishRun = 0;

  function finite(value) {
    if (value === null || value === undefined || value === '') return null;
    const number = Number(value);
    return Number.isFinite(number) ? number : null;
  }

  function append(parent, tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined && text !== null) element.textContent = String(text);
    parent.appendChild(element);
    return element;
  }

  function targetOf(tab) {
    if (!tab) return null;
    const href = tab.getAttribute('href') || '';
    const id = href.charAt(0) === '#' ? href.slice(1) : '';
    return SECTION_IDS.includes(id) ? id : null;
  }

  function activate(targetId, updateHistory) {
    const valid = SECTION_IDS.includes(targetId) ? targetId : 't-market';
    document.querySelectorAll(TAB_SELECTOR).forEach((tab) => {
      const active = targetOf(tab) === valid;
      tab.classList.toggle('on', active);
      tab.setAttribute('aria-selected', active ? 'true' : 'false');
    });
    SECTION_IDS.forEach((id) => {
      const section = document.getElementById(id);
      if (!section) return;
      section.removeAttribute('hidden');
      section.classList.toggle('on', id === valid);
      // Explicitly keep the same visibility contract as v38-site.js. This makes
      // navigation deterministic even if a legacy/cached :target rule is present.
      section.style.display = id === valid ? 'block' : 'none';
      section.setAttribute('aria-hidden', id === valid ? 'false' : 'true');
    });
    if (updateHistory && window.location.hash !== '#' + valid) {
      history.pushState({v38Tab: valid}, '', '#' + valid);
    }
    window.scrollTo(0, 0);
    window.requestAnimationFrame(() => window.scrollTo(0, 0));
  }

  function activateFromLocation() {
    const requested = window.location.hash ? window.location.hash.slice(1) : '';
    activate(SECTION_IDS.includes(requested) ? requested : 't-market', false);
  }

  function initNavigation() {
    if (navReady) return;
    navReady = true;
    document.documentElement.dataset.v38NavReady = 'true';

    document.addEventListener('click', (event) => {
      const node = event.target instanceof Element ? event.target.closest(TAB_SELECTOR) : null;
      if (!node) return;
      const target = targetOf(node);
      if (!target) return;
      event.preventDefault();
      event.stopPropagation();
      activate(target, true);
    }, true);

    window.addEventListener('popstate', activateFromLocation);
    window.addEventListener('hashchange', activateFromLocation);
    window.addEventListener('pageshow', activateFromLocation);
    activateFromLocation();
  }

  function originalTitle(card) {
    return card ? String(card.dataset.v38CardTitle || '') : '';
  }

  function findCard(section, text) {
    return Array.from(section.querySelectorAll('.card')).find((card) => {
      const current = card.querySelector('h2');
      return originalTitle(card).includes(text) || (current && current.textContent.includes(text));
    }) || null;
  }

  function removeRecoveryScaffolding(section) {
    if (!section) return;
    section.querySelectorAll('.v38-mc57-trend').forEach((node) => node.remove());
    section.querySelectorAll('.v38-bind-note').forEach((note) => {
      const text = note.textContent || '';
      const status = note.dataset.v38Status || '';
      if (
        status === 'READY' ||
        text.includes('通常株PIT履歴') ||
        text.includes('遡及推計なし') ||
        text.includes('MC57内部 12指標履歴') ||
        text.includes('日次保存済み履歴') ||
        text.includes('各指標は同一セッションの正本値のみ')
      ) {
        note.remove();
        return;
      }
      if (status === 'DATA_REQUIRED' || status === 'STALE') {
        note.replaceChildren();
        append(note, 'span', 'mut', status === 'STALE' ? '更新待ち' : 'データ未取得');
      }
    });
  }

  function metricMap(daily) {
    const out = {};
    (daily && Array.isArray(daily.metrics) ? daily.metrics : []).forEach((row) => {
      if (row && typeof row.key === 'string') out[row.key] = row;
    });
    return out;
  }

  function stateFor(value, warn, severe) {
    const number = finite(value);
    if (number === null) return {key: 'na', label: '算出不可', cls: 'reg-na'};
    if (number >= severe) return {key: 'bad', label: '警戒', cls: 'reg-bad'};
    if (number >= warn) return {key: 'warn', label: '注意', cls: 'reg-warn'};
    return {key: 'ok', label: '平常', cls: 'reg-ok'};
  }

  function onset(historyRows, key, threshold) {
    const rows = (Array.isArray(historyRows) ? historyRows : []).filter((row) => {
      return row && typeof row.date === 'string' && finite(row[key]) !== null;
    });
    if (!rows.length || finite(rows[rows.length - 1][key]) < threshold) return null;
    let index = rows.length - 1;
    while (index > 0 && finite(rows[index - 1][key]) >= threshold) index -= 1;
    return rows[index].date;
  }

  function shortDate(iso) {
    if (!iso || iso.length < 10) return '';
    return String(Number(iso.slice(5, 7))) + '/' + String(Number(iso.slice(8, 10)));
  }

  function addOnsets(cell, historyRows, key, warn, severe, state) {
    const line = append(cell, 'div', 'reg-onset', '');
    if (state.key === 'na') {
      append(line, 'span', 'onset on-ok', '算出不可');
      return;
    }
    const severeSince = onset(historyRows, key, severe);
    const warnSince = onset(historyRows, key, warn);
    if (severeSince) append(line, 'span', 'onset on-bad', '警戒入り ' + shortDate(severeSince));
    if (warnSince) append(line, 'span', 'onset on-warn', '注意入り ' + shortDate(warnSince));
    if (!severeSince && !warnSince) append(line, 'span', 'onset on-ok', '平常');
  }

  function pctWhole(value) {
    const number = finite(value);
    return number === null ? '—' : Math.round(number * 100) + '%';
  }

  function chips(cell, values, suffix) {
    if (!Array.isArray(values) || !values.length) return;
    const row = append(cell, 'div', 'reg-chips', '');
    values.slice(0, 8).forEach((ticker) => {
      const chip = append(row, 'span', 'rgchip', String(ticker));
      if (suffix) {
        const sup = document.createElement('sup');
        sup.textContent = suffix;
        chip.appendChild(sup);
      }
    });
  }

  function f1Meta(component) {
    const oldCount = Number(component.old_top24_count || 0);
    const observed = Number(component.observable_count || 0);
    const coverage = finite(component.coverage);
    const rankDrops = Number(component.rank_drop_count || 0);
    const eligibilityDrops = Number(component.eligibility_drop_count || 0);
    const drops = Number(component.drop_count || 0);
    const parts = [];
    if (oldCount) parts.push('分母' + oldCount);
    if (coverage !== null) parts.push('観測率' + Math.round(coverage * 100) + '%');
    else if (oldCount && observed) parts.push('観測' + observed);
    if (component.rank_drop_count !== undefined) parts.push('順位落ち' + rankDrops);
    if (component.eligibility_drop_count !== undefined) parts.push('適格脱落' + eligibilityDrops);
    else if (drops) parts.push('脱落' + drops);
    return parts.join('・');
  }

  function f2Meta(component) {
    const parts = [];
    if (component.top24_count !== undefined) parts.push('Top24 ' + component.top24_count);
    if (component.observable_count !== undefined) parts.push('観測' + component.observable_count);
    if (component.weak_count !== undefined) parts.push('RS63<85 ' + component.weak_count);
    return parts.join('・');
  }

  function f3Meta(component) {
    const parts = [];
    if (component.queue_count !== undefined) parts.push('Queue ' + component.queue_count);
    if (component.observable_count !== undefined) parts.push('観測' + component.observable_count);
    if (component.break_count !== undefined) parts.push('崩れ ' + component.break_count);
    return parts.join('・');
  }

  function addRegimeCell(grid, spec, component, historyRows) {
    const value = finite(component && component.value);
    const state = stateFor(value, spec.warn, spec.severe);
    const cell = append(grid, 'div', 'reg-cell ' + state.cls, '');
    const key = append(cell, 'div', 'reg-k', spec.title + ' ');
    append(key, 'span', 'reg-kind ' + spec.kindClass, spec.kind);
    append(cell, 'div', 'reg-role', spec.role);
    addOnsets(cell, historyRows, spec.key, spec.warn, spec.severe, state);
    const meta = spec.meta(component || {});
    if (meta) {
      const metaRow = append(cell, 'div', 'reg-onset', '');
      append(metaRow, 'span', 'onset on-ok', meta);
    }
    append(cell, 'div', 'reg-v', pctWhole(value));
    append(cell, 'div', 'reg-l', state.label);
    chips(cell, component && component[spec.listKey], spec.chipSuffix);
    return state;
  }

  function renderRegimeCard(view) {
    const section = document.getElementById('t-market');
    const daily = view && view.daily;
    if (!section || !daily) return;
    const card = findCard(section, 'レジーム警戒灯');
    if (!card) return;

    const detail = daily.f123_detail && typeof daily.f123_detail === 'object'
      ? daily.f123_detail : {};
    const metrics = metricMap(daily);
    const components = {};
    ['f1', 'f2', 'f3'].forEach((key) => {
      const fromDetail = detail[key] && typeof detail[key] === 'object' ? detail[key] : {};
      components[key] = Object.assign({}, fromDetail);
      if (finite(components[key].value) === null && metrics[key]) components[key].value = finite(metrics[key].value);
    });

    card.replaceChildren();
    card.classList.add('reg-card');
    card.dataset.v38Status = detail.status || daily.status || 'READY';
    const header = append(card, 'div', 'hdr reg-hd', '');
    const h2 = append(header, 'h2', '', 'レジーム警戒灯 ');
    append(h2, 'span', 'h2en', 'Regime Early-Warning');
    const headerState = append(header, 'span', 'reg-hdr', '');
    const body = append(card, 'div', 'reg-body', '');
    const grid = append(body, 'div', 'reg-grid', '');
    const historyRows = Array.isArray(daily.history) ? daily.history : [];

    const specs = [
      {
        key: 'f1', title: 'F1 リーダー脱落率', kind: 'タイミング', kindClass: 'kind-t',
        role: '最速の警報｜20営業日前Top24からの脱落を観測',
        warn: 0.20, severe: 0.30, meta: f1Meta, listKey: 'dropped', chipSuffix: '順'
      },
      {
        key: 'f2', title: 'F2 勢い細り率', kind: 'タイミング', kindClass: 'kind-t',
        role: '現在のRS189 Top24でRS63<85の比率',
        warn: 0.25, severe: 0.40, meta: f2Meta, listKey: 'weak', chipSuffix: ''
      },
      {
        key: 'f3', title: 'F3 キュー崩れ', kind: '深さ', kindClass: 'kind-d',
        role: '強い候補群の20日失速・52週高値からの深押しを観測',
        warn: 0.40, severe: 0.60, meta: f3Meta, listKey: 'broken', chipSuffix: ''
      }
    ];
    const states = specs.map((spec) => addRegimeCell(grid, spec, components[spec.key], historyRows));
    const bad = states.map((state, index) => state.key === 'bad' ? 'F' + (index + 1) : null).filter(Boolean);
    const warn = states.some((state) => state.key === 'warn');
    if (bad.length) {
      headerState.classList.add('reg-hdr-bad');
      headerState.textContent = '⚠ ' + bad.join('・') + ' 点灯';
    } else if (warn) {
      headerState.classList.add('reg-hdr-warn');
      headerState.textContent = '注意域（点灯手前）';
    } else {
      headerState.classList.add('reg-hdr-ok');
      headerState.textContent = '平常（内部は健全）';
    }
  }

  function cleanDaily(view) {
    const section = document.getElementById('t-market');
    if (!section) return;
    removeRecoveryScaffolding(section);
    renderRegimeCard(view);
    removeRecoveryScaffolding(section);
  }

  function cleanGlobalReadyNotes() {
    document.querySelectorAll('.v38-bind-note[data-v38-status="READY"]').forEach((note) => note.remove());
  }

  async function polish() {
    const runtime = window.V38Runtime;
    if (!runtime || typeof runtime.loadJson !== 'function') return;
    try {
      const view = await runtime.loadJson('data/ui_view_model.json');
      cleanDaily(view);
      cleanGlobalReadyNotes();
      document.body.dataset.v38PolishStatus = 'ready';
      polishRun += 1;
    } catch (_) {
      document.body.dataset.v38PolishStatus = 'failed';
    }
  }

  function waitForBinding() {
    const ready = document.body && document.body.dataset.v38BindingStatus;
    if (ready === 'ready' || ready === 'failed') {
      polish();
      window.setTimeout(polish, 180);
      window.setTimeout(polish, 700);
      return;
    }
    window.setTimeout(waitForBinding, 40);
  }

  function init() {
    initNavigation();
    waitForBinding();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init, {once: true});
  } else {
    init();
  }
})();
