(function () {
  'use strict';

  const TAB_SELECTOR = 'nav a.tabx[href^="#"]';
  const SECTION_IDS = [
    't-market', 't-alloc', 't-port', 't-rotation', 't-rs',
    't-weekly', 't-options', 't-post1', 't-rules'
  ];
  const VIEW_BINDINGS = [
    ['t-alloc', 'positions'], ['t-port', 'core12'],
    ['t-rotation', 'rotation'], ['t-weekly', 'weekly'],
    ['t-options', 'options']
  ];
  const PREFERRED_CARD_TITLES = {
    positions: '保有ポジション',
    core12: '個別株スリーブ Core 12',
    rotation: '主導セクター・業種',
    weekly: '今週の結論',
    options: '0–6 DTE Short Term'
  };

  function targetOf(tab) {
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

  function append(parent, tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    node.textContent = text === null || text === undefined ? '' : String(text);
    parent.appendChild(node);
    return node;
  }

  function rememberCardTitles() {
    document.querySelectorAll('section .card').forEach((card, index) => {
      const title = card.querySelector('h2, .hdr h2, .chd h2');
      card.dataset.v38CardTitle = title
        ? title.childNodes[0].textContent.trim()
        : 'V38 Data ' + String(index + 1);
    });
  }

  function originalTitle(card, fallback) {
    return card && card.dataset.v38CardTitle ? card.dataset.v38CardTitle : fallback;
  }

  function statusNote(parent, status, reason, session) {
    const note = append(parent, 'div', 'v38-bind-note', '');
    note.dataset.v38Status = status || 'DATA_REQUIRED';
    append(note, 'strong', '', status || 'DATA_REQUIRED');
    const details = [session, reason].filter(Boolean).join(' • ');
    if (details) append(note, 'div', '', details);
    return note;
  }

  function resetCard(card, title, status, reason, session) {
    if (!card) return;
    card.replaceChildren();
    card.dataset.v38Status = status || 'DATA_REQUIRED';
    append(card, 'h2', '', title || originalTitle(card, 'V38 Data'));
    statusNote(card, status || 'DATA_REQUIRED', reason || 'AUTHORITATIVE_INPUT_MISSING', session);
  }

  function addKeyValue(parent, label, value) {
    const row = append(parent, 'div', 'v38-live-kv', '');
    append(row, 'span', '', label || '—');
    append(row, 'b', '', value === null || value === undefined || value === '' ? '—' : value);
    return row;
  }

  function metricMap(daily) {
    const out = {};
    const rows = daily && Array.isArray(daily.metrics) ? daily.metrics : [];
    rows.forEach((row) => {
      if (row && typeof row.key === 'string') out[row.key] = row;
    });
    return out;
  }

  function metricDisplay(metrics, key) {
    const row = metrics[key];
    return row && row.status === 'READY' ? row.display : '—';
  }

  function metricLabel(metrics, key) {
    const row = metrics[key];
    if (!row) return key + ': DATA_REQUIRED';
    return row.label + ': ' + (row.status || 'DATA_REQUIRED');
  }

  function findCard(section, text) {
    return Array.from(section.querySelectorAll('.card')).find(
      (card) => originalTitle(card, '').includes(text)
    ) || null;
  }

  function neutralizeCards(section, session, reason) {
    section.querySelectorAll('.card').forEach((card) => {
      resetCard(
        card, originalTitle(card, 'V38 Data'), 'DATA_REQUIRED',
        reason || 'AUTHORITATIVE_CARD_INPUT_NOT_AVAILABLE', session
      );
    });
  }

  function renderDailyCard(card, title, status, reason, session, rows) {
    if (!card) return;
    card.replaceChildren();
    card.dataset.v38Status = status;
    append(card, 'h2', '', title);
    rows.forEach((row) => addKeyValue(card, row[0], row[1]));
    statusNote(card, status, reason, session);
  }

  function renderDaily(view) {
    const section = document.getElementById('t-market');
    const daily = view && view.daily && typeof view.daily === 'object' ? view.daily : null;
    if (!section || !daily) return;
    const session = view.session_date || '—';
    const metrics = metricMap(daily);
    neutralizeCards(section, session, 'AUTHORITATIVE_CARD_INPUT_NOT_AVAILABLE');
    section.dataset.v38Status = daily.status || 'DATA_REQUIRED';

    const nqsar = metrics.nqsar;
    const pill = document.getElementById('sarPill');
    if (pill) {
      pill.classList.remove('sar-blue', 'sar-green', 'sar-yellow', 'sar-red');
      const state = nqsar && nqsar.status === 'READY' ? nqsar.display : null;
      pill.classList.add(state ? 'sar-' + String(state).toLowerCase() : 'sar-yellow');
      const badge = pill.querySelector('#sarBadge');
      const colour = pill.querySelector('#sarCol');
      const judgment = pill.querySelector('#sarJud');
      const lot = pill.querySelector('#sarLot');
      if (badge) badge.textContent = state ? '確定' : 'DATA REQUIRED';
      if (colour) colour.textContent = state || '—';
      if (judgment) judgment.textContent = state ? '正本入力' : 'NQSAR未取得';
      if (lot) lot.textContent = state ? '最新セッション' : '判定不可';
      pill.dataset.v38Status = state ? 'READY' : 'DATA_REQUIRED';
    }

    section.querySelectorAll(':scope > .ribwrap').forEach((ribbon) => {
      ribbon.replaceChildren();
      append(ribbon, 'div', 'riblab', 'レジーム履歴　DATA_REQUIRED（履歴正本未取得）');
      ribbon.dataset.v38Status = 'DATA_REQUIRED';
    });

    const mc57 = metrics.mc57;
    const banner = section.querySelector(':scope > .banner');
    if (banner) {
      banner.replaceChildren();
      banner.classList.remove('b-bull', 'b-bear');
      banner.classList.add('b-bull');
      append(banner, 'div', 'lab', 'マーケットステータス（MC57）');
      append(banner, 'div', 'val', metricDisplay(metrics, 'mc57'));
      append(banner, 'div', 'st', mc57 && mc57.status === 'READY' ? '最新値' : 'DATA REQUIRED');
      const aux = append(banner, 'div', 'aux', '');
      addKeyValue(aux, '50MA Breadth', metricDisplay(metrics, 'breadth50'));
      addKeyValue(aux, 'F2', metricDisplay(metrics, 'f2'));
      banner.dataset.v38Status = mc57 ? mc57.status : 'DATA_REQUIRED';
    }

    renderDailyCard(findCard(section, '今日のマーケット'), '今日のマーケット',
      daily.status || 'DATA_REQUIRED', '各指標は同一セッションの正本値のみ', session, [
        ['Market Mode', metricDisplay(metrics, 'market_mode')],
        ['NQSAR', metricDisplay(metrics, 'nqsar')],
        ['MC57', metricDisplay(metrics, 'mc57')],
        ['50MA Breadth', metricDisplay(metrics, 'breadth50')],
        ['200MA Breadth', metricDisplay(metrics, 'breadth200')],
        ['F1 / F2 / F3', [metricDisplay(metrics, 'f1'), metricDisplay(metrics, 'f2'), metricDisplay(metrics, 'f3')].join(' / ')]
      ]);

    renderDailyCard(findCard(section, 'マーケット・パフォーマンス'), 'マーケット・パフォーマンス',
      ['market_SPY', 'market_QQQ', 'market_TQQQ', 'market_NQ=F'].every((key) => metrics[key] && metrics[key].status === 'READY') ? 'READY' : 'DATA_REQUIRED',
      '当日終値。騰落率は正本計算未接続のため表示しない', session, [
        ['SPY', metricDisplay(metrics, 'market_SPY')],
        ['QQQ', metricDisplay(metrics, 'market_QQQ')],
        ['TQQQ', metricDisplay(metrics, 'market_TQQQ')],
        ['NQ', metricDisplay(metrics, 'market_NQ=F')]
      ]);

    renderDailyCard(findCard(section, 'ブレッドス推移（50'), 'ブレッドス推移（50日線上の割合）',
      metrics.breadth50 ? metrics.breadth50.status : 'DATA_REQUIRED',
      metrics.breadth50 ? metrics.breadth50.reason : 'BREADTH50_MISSING', session, [
        ['50MA Breadth', metricDisplay(metrics, 'breadth50')],
        ['Coverage', daily.breadth_coverage === null || daily.breadth_coverage === undefined ? '—' : (Number(daily.breadth_coverage) * 100).toFixed(1) + '%']
      ]);

    renderDailyCard(findCard(section, 'ブレッドス推移（200'), 'ブレッドス推移（200日線上の割合）',
      metrics.breadth200 ? metrics.breadth200.status : 'DATA_REQUIRED',
      metrics.breadth200 ? metrics.breadth200.reason : 'BREADTH200_MISSING', session, [
        ['200MA Breadth', metricDisplay(metrics, 'breadth200')],
        ['Coverage', daily.breadth_coverage === null || daily.breadth_coverage === undefined ? '—' : (Number(daily.breadth_coverage) * 100).toFixed(1) + '%']
      ]);

    renderDailyCard(findCard(section, 'レジーム警戒灯'), 'レジーム警戒灯',
      ['f1', 'f2', 'f3'].every((key) => metrics[key] && metrics[key].status === 'READY') ? 'READY' : 'DATA_REQUIRED',
      [metricLabel(metrics, 'f1'), metricLabel(metrics, 'f2'), metricLabel(metrics, 'f3')].join(' • '), session, [
        ['F1', metricDisplay(metrics, 'f1')], ['F2', metricDisplay(metrics, 'f2')], ['F3', metricDisplay(metrics, 'f3')]
      ]);

    renderDailyCard(findCard(section, 'VIX反転シーケンス'), 'VIX',
      metrics['market_^VIX'] ? metrics['market_^VIX'].status : 'DATA_REQUIRED',
      metrics['market_^VIX'] ? metrics['market_^VIX'].reason : 'VIX_MISSING', session,
      [['VIX Close', metricDisplay(metrics, 'market_^VIX')]]);
  }

  function renderRsItem(parent, row) {
    const item = append(parent, 'div', 'rsx-item', '');
    item.dataset.v38RsTicker = String(row.ticker || '');
    const top = append(item, 'div', 'rsx-row', '');
    append(top, 'span', 'rsx-rk', row.rank || '—');
    const name = append(top, 'div', 'rsx-name', '');
    const nameLine = append(name, 'div', '', '');
    append(nameLine, 'b', '', row.ticker || '—');
    append(nameLine, 'span', 'rsx-badge sel', 'RS189');
    append(name, 'small', '', row.ddv20_display || 'DDV —');
    const score = append(top, 'div', 'rsx-score', '');
    append(score, 'b', '', row.rs189_display || '—');
    append(score, 'small', '', 'RS189');
    const sub = append(item, 'div', 'rsx-sub', '');
    append(sub, 'span', 'rsx-nums', 'RS63 ' + (row.rs63_display || '—'));
    append(sub, 'span', 'rsx-ret', 'Price ' + (row.price_display || '—'));
  }

  function renderRs(view) {
    const section = document.getElementById('t-rs');
    const rs = view && view.rs && typeof view.rs === 'object' ? view.rs : null;
    if (!section || !rs) return;
    const session = view.session_date || '—';
    neutralizeCards(section, session, rs.reason || 'RS_CARD_INPUT_NOT_AVAILABLE');
    section.dataset.v38Status = rs.status || 'DATA_REQUIRED';
    const intro = section.querySelector('.rsx-intro');
    if (intro) {
      intro.replaceChildren();
      append(intro, 'h2', '', 'RSマルチタイムフレーム比較');
      addKeyValue(intro, '正本ランキング', rs.title || 'RS189 Top 24');
      addKeyValue(intro, 'Coverage', rs.coverage === null || rs.coverage === undefined ? '—' : (Number(rs.coverage) * 100).toFixed(1) + '%');
      statusNote(intro, rs.status || 'DATA_REQUIRED', rs.note || rs.reason, session);
    }
    const listCard = section.querySelector('.rs-cont');
    if (listCard) {
      listCard.replaceChildren();
      append(listCard, 'h2', '', 'RS189 Top 24');
      append(listCard, 'div', 'sub', '正本rs.jsonの順序をそのまま表示。Core 12の適格性・採用順位ではありません。');
      const list = append(listCard, 'div', 'rsc-list', '');
      (Array.isArray(rs.rows) ? rs.rows : []).forEach((row) => renderRsItem(list, row));
      statusNote(listCard, rs.status || 'DATA_REQUIRED', rs.reason || 'CURRENT_SESSION', session);
    }
  }

  function primitiveEntries(row) {
    if (!row || typeof row !== 'object') return [];
    return Object.keys(row).filter((key) => {
      const value = row[key];
      return value === null || ['string', 'number', 'boolean'].includes(typeof value);
    }).slice(0, 8).map((key) => [key, row[key]]);
  }

  function renderGenericRow(parent, row, index) {
    const item = append(parent, 'div', 'rsx-item', '');
    item.dataset.v38Row = String(index + 1);
    const entries = primitiveEntries(row);
    const top = append(item, 'div', 'rsx-row', '');
    append(top, 'span', 'rsx-rk', index + 1);
    const name = append(top, 'div', 'rsx-name', '');
    const lead = entries.length ? entries[0] : ['row', 'Authoritative structured row'];
    append(name, 'b', '', lead[1] === null ? '—' : lead[1]);
    append(name, 'small', '', lead[0]);
    const sub = append(item, 'div', 'rsx-sub', '');
    entries.slice(1).forEach((entry) => {
      append(sub, 'span', 'rsx-nums', entry[0] + ' ' + (entry[1] === null ? '—' : entry[1]));
    });
  }

  function renderGenericSection(view, sectionId, viewKey) {
    const section = document.getElementById(sectionId);
    const data = view && view[viewKey] && typeof view[viewKey] === 'object' ? view[viewKey] : null;
    if (!section || !data) return;
    const session = view.session_date || '—';
    neutralizeCards(section, session, data.reason || 'AUTHORITATIVE_INPUT_MISSING');
    section.dataset.v38Status = data.status || 'DATA_REQUIRED';
    const firstCard = findCard(section, PREFERRED_CARD_TITLES[viewKey] || '') || section.querySelector('.card');
    if (data.status !== 'READY' || !firstCard) return;
    firstCard.replaceChildren();
    append(firstCard, 'h2', '', data.title || viewKey);
    if (data.note) append(firstCard, 'div', 'sub', data.note);
    if (data.state) addKeyValue(firstCard, 'State', data.state);
    const rows = Array.isArray(data.rows) ? data.rows : [];
    const list = append(firstCard, 'div', 'rsc-list', '');
    rows.slice(0, 40).forEach((row, index) => renderGenericRow(list, row, index));
    if (!rows.length && !data.state) addKeyValue(firstCard, 'Rows', '0');
    statusNote(firstCard, data.status, data.reason || 'CURRENT_SESSION', session);
  }

  function renderPublish(view) {
    const section = document.getElementById('t-post1');
    const data = view && view.publish && typeof view.publish === 'object' ? view.publish : null;
    if (!section || !data) return;
    const session = view.session_date || '—';
    section.dataset.v38Status = data.status || 'DATA_REQUIRED';
    const wraps = Array.from(section.querySelectorAll('.postwrap'));
    wraps.forEach((wrap) => {
      wrap.replaceChildren();
      wrap.dataset.v38Status = data.status || 'DATA_REQUIRED';
    });
    if (!wraps[0]) return;
    append(wraps[0], 'h2', '', data.title || 'Publish');
    addKeyValue(wraps[0], 'Full V38 ready', data.full_v38_ready ? 'YES' : 'NO');
    if (data.ready_count !== undefined && data.required_count !== undefined) {
      addKeyValue(wraps[0], 'Dependencies', String(data.ready_count) + ' / ' + String(data.required_count));
    }
    const list = append(wraps[0], 'div', 'rsc-list', '');
    (Array.isArray(data.rows) ? data.rows : []).slice(0, 40).forEach((row, index) => renderGenericRow(list, row, index));
    statusNote(wraps[0], data.status || 'DATA_REQUIRED', data.reason || 'CURRENT_SESSION', session);
    if (wraps[1]) statusNote(wraps[1], 'DATA_REQUIRED', 'ROTATION_PUBLISH_ARTIFACT_NOT_AVAILABLE', session);
  }

  function renderRules(view) {
    const section = document.getElementById('t-rules');
    const data = view && view.rules && typeof view.rules === 'object' ? view.rules : null;
    if (!section || !data) return;
    const session = view.session_date || '—';
    const cards = Array.from(section.querySelectorAll('.card'));
    section.dataset.v38Status = data.status || 'DATA_REQUIRED';
    if (data.status !== 'READY') {
      cards.forEach((card, index) => resetCard(card, index ? 'TQQQ' : '通常個別株', data.status, data.reason, session));
      return;
    }
    const rows = Array.isArray(data.rows) ? data.rows : [];
    const normal = rows.filter((row) => !String(row.key || '').startsWith('tqqq_panic.'));
    const tqqq = rows.filter((row) => String(row.key || '').startsWith('tqqq_panic.'));
    [[cards[0], '通常個別株 / Allocation', normal], [cards[1], 'TQQQ', tqqq]].forEach((group) => {
      const card = group[0];
      if (!card) return;
      card.replaceChildren();
      append(card, 'h2', '', group[1]);
      group[2].forEach((row, index) => {
        const item = append(card, 'div', 'w30exit', '');
        append(item, 'span', 'w30exit-t', index + 1);
        append(item, 'span', 'w30exit-b', String(row.key || '') + ' = ' + String(row.value || ''));
      });
      statusNote(card, 'READY', 'code:adopted-v38-contracts', session);
    });
  }

  function renderHeader(view) {
    const asof = document.querySelector('header .asof');
    if (asof) {
      const generated = view.generated_at ? '　取得 ' + view.generated_at : '';
      asof.textContent = '分析基準日 ' + (view.session_date || '—') + generated + '　｜　LIVE DATA';
    }
    const today = document.querySelector('.todayact');
    const daily = view.daily || {};
    const metrics = metricMap(daily);
    if (today) {
      today.replaceChildren();
      today.classList.remove('ta-blue', 'ta-green', 'ta-yellow', 'ta-red');
      const nqsar = metrics.nqsar && metrics.nqsar.status === 'READY' ? metrics.nqsar.display : null;
      today.classList.add(nqsar ? 'ta-' + String(nqsar).toLowerCase() : 'ta-yellow');
      const top = append(today, 'div', 'ta-top', '');
      append(top, 'span', 'ta-h', '今日の運用');
      append(top, 'span', 'ta-col', metricDisplay(metrics, 'market_mode'));
      append(top, 'span', 'ta-expo', nqsar ? 'NQSAR ' + nqsar : 'Market Mode / NQSAR DATA_REQUIRED');
      today.dataset.v38Status = daily.status || 'DATA_REQUIRED';
    }
  }

  function renderLiveView(view) {
    renderHeader(view);
    renderDaily(view);
    renderRs(view);
    VIEW_BINDINGS.forEach((binding) => renderGenericSection(view, binding[0], binding[1]));
    renderPublish(view);
    renderRules(view);
    document.body.dataset.v38BindingStatus = 'ready';
  }

  function renderAllUnavailable(detail) {
    SECTION_IDS.forEach((id) => {
      const section = document.getElementById(id);
      if (!section) return;
      section.dataset.v38Status = 'DATA_REQUIRED';
      neutralizeCards(section, '—', detail);
      section.querySelectorAll('.postwrap').forEach((wrap) => {
        wrap.replaceChildren();
        statusNote(wrap, 'DATA_REQUIRED', detail, '—');
      });
    });
    renderHeader({daily: {metrics: [], status: 'DATA_REQUIRED'}, session_date: '—'});
    document.body.dataset.v38BindingStatus = 'failed';
  }

  async function loadProductionData() {
    const runtime = window.V38Runtime;
    if (!runtime || typeof runtime.loadJson !== 'function') {
      renderAllUnavailable('RUNTIME_UNAVAILABLE');
      return;
    }
    try {
      const results = await Promise.all([
        runtime.loadJson('data/ui_payload.json'),
        runtime.loadJson('data/ui_view_model.json')
      ]);
      window.V38UiPayload = results[0];
      renderLiveView(results[1]);
    } catch (_) {
      renderAllUnavailable('AUTHORITATIVE_UI_DATA_UNAVAILABLE');
    }
  }

  document.addEventListener('DOMContentLoaded', () => {
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
  });
})();
