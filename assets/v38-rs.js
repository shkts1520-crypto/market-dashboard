(function () {
  'use strict';

  function node(tag, className, text) {
    const out = document.createElement(tag);
    if (className) out.className = className;
    if (text !== undefined && text !== null) out.textContent = String(text);
    return out;
  }

  function finite(value) {
    if (value === null || value === undefined || value === '') return null;
    const number = Number(value);
    return Number.isFinite(number) ? number : null;
  }

  function signed(value, decimals) {
    const number = finite(value);
    if (number === null) return '—';
    const places = Number.isInteger(decimals) ? decimals : 0;
    return (number > 0 ? '+' : '') + number.toFixed(places);
  }

  function findCard(section, fragments) {
    const parts = Array.isArray(fragments) ? fragments : [fragments];
    return Array.from(section.querySelectorAll('.card')).find((card) => {
      const title = String(card.dataset.v38CardTitle || card.querySelector('h2')?.textContent || '');
      return parts.some((part) => title.includes(part));
    }) || null;
  }

  function tickerLink(ticker) {
    const link = node('a', 'v38-ticker-link', ticker);
    link.href = 'https://www.tradingview.com/chart/?symbol=' + encodeURIComponent(ticker);
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    return link;
  }

  function chip(parent, ticker, extraClass) {
    const item = node('span', 'chip' + (extraClass ? ' ' + extraClass : ''), '');
    item.appendChild(tickerLink(ticker));
    parent.appendChild(item);
  }

  function note(card, status, detail, session) {
    const line = node('div', 'v38-bind-note', status + ' • ' + detail + ' • ' + session);
    card.appendChild(line);
  }

  function renderTurnover(section, data, session) {
    const card = findCard(section, ['Top10 IN / OUT', 'IN / OUT履歴', 'IN / OUT']);
    if (!card) return false;
    card.replaceChildren();
    card.appendChild(node('h2', '', 'Top10 IN / OUT履歴'));
    card.appendChild(node('div', 'sub', '前営業日・約5営業日前・約21営業日前のTop10と比較。価格履歴から再計算。'));

    const comparison = data.comparison && typeof data.comparison === 'object' ? data.comparison : {};
    ['63', '126', '189'].forEach((period) => {
      const block = node('div', 'rsx-item', '');
      block.dataset.v38RsPeriod = period;
      block.appendChild(node('b', '', 'RS' + period + ' Top10'));
      const detail = comparison[period] && typeof comparison[period] === 'object' ? comparison[period] : {};
      const windows = Array.isArray(detail.windows) ? detail.windows : [];
      windows.forEach((window) => {
        const row = node('div', 'rscg', '');
        const label = String(window.label || '') + ' ' + String(window.period_label || '');
        row.appendChild(node('b', '', label));
        const overlap = finite(window.overlap);
        const turnover = finite(window.turnover);
        row.appendChild(node('span', '', overlap === null ? 'DATA_REQUIRED' : '継続 ' + Math.trunc(overlap) + '/10・入替 ' + Math.trunc(turnover || 0)));

        const entered = Array.isArray(window.in) ? window.in : [];
        const exited = Array.isArray(window.out) ? window.out : [];
        const inWrap = node('div', 'chips', '');
        inWrap.appendChild(node('small', '', 'IN ' + entered.length));
        entered.forEach((ticker) => chip(inWrap, ticker, 'hot'));
        if (!entered.length) inWrap.appendChild(node('span', 'mut', 'なし'));
        row.appendChild(inWrap);
        const outWrap = node('div', 'chips', '');
        outWrap.appendChild(node('small', '', 'OUT ' + exited.length));
        exited.forEach((ticker) => chip(outWrap, ticker, ''));
        if (!exited.length) outWrap.appendChild(node('span', 'mut', 'なし'));
        row.appendChild(outWrap);
        block.appendChild(row);
      });
      card.appendChild(block);
    });
    note(card, 'READY', 'RS history identity verified', session);
    card.dataset.v38RsHistory = 'ready';
    return true;
  }

  function tagClass(tag) {
    return {
      '定着': 'stable',
      '新規急浮上': 'surge',
      '再浮上': 'return',
      '失速中': 'fade',
      '一日急騰型': 'spike',
      '継続': 'hold'
    }[tag] || 'hold';
  }

  function renderPersistence(section, data, session) {
    const card = findCard(section, 'RS189 継続性');
    if (!card) return false;
    const persistence = data.persistence && typeof data.persistence === 'object' ? data.persistence : {};
    const rows = Array.isArray(persistence.rows) ? persistence.rows : [];
    const groups = Array.isArray(persistence.groups) ? persistence.groups : [];
    card.replaceChildren();
    card.appendChild(node('h2', '', 'RS189 継続性 Leadership Persistence'));
    card.appendChild(node('div', 'sub', 'Top10滞在、Top24滞在率、連続日数、21営業日の順位・RS変化。表示専用で選定ルールには不使用。'));

    if (groups.length) {
      const groupWrap = node('div', 'rsc-groups', '');
      groups.forEach((group) => {
        const tickers = Array.isArray(group.tickers) ? group.tickers : [];
        const item = node('div', 'rscg', '');
        item.appendChild(node('b', '', group.tag || '—'));
        item.appendChild(node('span', '', tickers.length));
        const chips = node('div', 'chips', '');
        tickers.forEach((ticker) => chip(chips, ticker, ''));
        item.appendChild(chips);
        groupWrap.appendChild(item);
      });
      card.appendChild(groupWrap);
    }

    const body = node('div', 'rsc-list', '');
    rows.forEach((row) => {
      const item = node('div', 'rsc-row', '');
      item.dataset.v38RsPersistenceTicker = String(row.ticker || '');
      const head = node('div', 'rsc-head', '');
      head.appendChild(node('span', 'rsc-rk', '#' + String(row.rank || '—')));
      head.appendChild(tickerLink(String(row.ticker || '—')));
      head.appendChild(node('span', 'rsc-tag ' + tagClass(row.tag), row.tag || '継続'));
      const rs189 = finite(row.rs189);
      head.appendChild(node('span', 'rsc-rs', 'RS ' + (rs189 === null ? '—' : rs189.toFixed(1))));
      item.appendChild(head);

      const meta = node('div', 'rsc-meta', '');
      const rate = finite(row.top24_rate);
      const move = finite(row.rank_move_21);
      const moveText = move === null ? '—' : (move > 0 ? '↑' + Math.round(move) : move < 0 ? '↓' + Math.abs(Math.round(move)) : '→');
      meta.textContent =
        'Top10 ' + String(row.top10_days_21 ?? '—') + '/' + String(row.valid21 ?? '—') + '日' +
        ' • Top24 ' + (rate === null ? '—' : (rate * 100).toFixed(0) + '%') +
        ' • 連続Top10 ' + String(row.top10_streak ?? '—') + '日' +
        ' • 順位21D ' + moveText +
        ' • ΔRS 63 ' + signed(row.rs63_change_21, 1) +
        ' / 126 ' + signed(row.rs126_change_21, 1) +
        ' / 189 ' + signed(row.rs189_change_21, 1);
      item.appendChild(meta);
      body.appendChild(item);
    });
    card.appendChild(body);
    note(card, 'READY', 'display-only recovered persistence', session);
    card.dataset.v38RsHistory = 'ready';
    return true;
  }

  function decorate(data) {
    const section = document.getElementById('t-rs');
    if (!section || !data || typeof data !== 'object') return;
    const session = String(data.session_date || '—');
    if (data.status !== 'READY') {
      section.dataset.v38RsHistoryStatus = 'data-required';
      return;
    }
    const turnover = renderTurnover(section, data, session);
    const persistence = renderPersistence(section, data, session);
    if (turnover || persistence) section.dataset.v38RsHistoryStatus = 'ready';
  }

  async function run() {
    const runtime = window.V38Runtime;
    if (!runtime || typeof runtime.loadJson !== 'function') return;
    try {
      const data = await runtime.loadJson('data/rs_history.json');
      decorate(data);
    } catch (_) {
      const section = document.getElementById('t-rs');
      if (section) section.dataset.v38RsHistoryStatus = 'unavailable';
    }
  }

  let attempts = 0;
  function waitForBinding() {
    attempts += 1;
    if (document.body && document.body.dataset.v38BindingStatus === 'ready') {
      run();
      return;
    }
    if (attempts < 200) window.setTimeout(waitForBinding, 50);
  }

  waitForBinding();
})();
