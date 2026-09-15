(function () {
  'use strict';

  function cards(sectionId) {
    const section = document.getElementById(sectionId);
    return section ? Array.from(section.querySelectorAll(':scope > .card')) : [];
  }

  function cardByTitle(sectionId, title) {
    return cards(sectionId).find((card) => {
      const heading = card.querySelector('h2');
      return heading && heading.textContent.includes(title);
    });
  }

  function setText(root, selector, value) {
    const node = root && root.querySelector(selector);
    if (node && value !== undefined && value !== null) node.textContent = String(value);
  }

  function metricMap(daily) {
    return Object.fromEntries((daily.metrics || []).map((row) => [row.key, row]));
  }

  function bindDaily(view) {
    const daily = view.daily || {};
    const metrics = metricMap(daily);
    const display = (key) => metrics[key] && metrics[key].display;
    const summary = cardByTitle('t-market', '今日のマーケット');
    setText(summary, '.mkt20-score b', display('mc57'));
    const mc57 = cardByTitle('t-market', 'MC57推移');
    setText(mc57, '.chd-now b', display('mc57'));
    const breadth50 = cardByTitle('t-market', 'ブレッドス推移（50');
    const breadth200 = cardByTitle('t-market', 'ブレッドス推移（200');
    setText(breadth50, '.chd-now b', display('breadth50'));
    setText(breadth200, '.chd-now b', display('breadth200'));
    [summary, mc57, breadth50, breadth200].filter(Boolean).forEach((card) => {
      card.dataset.v38Status = 'READY';
      card.dataset.v38BoundSession = view.session_date || '';
    });
  }

  function bindRankItems(card, rows, scoreKey) {
    if (!card || !Array.isArray(rows)) return;
    const items = Array.from(card.querySelectorAll('.rsx-item'));
    items.forEach((item, index) => {
      const row = rows[index];
      item.hidden = !row;
      if (!row) return;
      item.dataset.v38Ticker = row.ticker || '';
      setText(item, '.rsx-rk', row.rank || index + 1);
      setText(item, '.rsx-name b', row.ticker || '—');
      setText(item, '.rsx-name small', row.industry || row.sector || '—');
      setText(item, '.rsx-score b', row[scoreKey + '_display'] || row[scoreKey] || '—');
      setText(item, '.rsx-nums', `63 ${row.rs63_display || '—'}・126 ${row.rs126_display || '—'}・189 ${row.rs189_display || '—'}`);
      setText(item, '.rsx-ret', `Price ${row.price_display || '—'}・${row.ddv20_display || 'DDV —'}`);
    });
    card.dataset.v38Status = 'READY';
    card.dataset.v38Rows = String(rows.length);
  }

  function bindRs(view) {
    const rs = view.rs || {};
    const windows = rs.windows || {};
    bindRankItems(cardByTitle('t-rs', 'RS63 Top10'), windows['63'] || [], 'rs63');
    bindRankItems(cardByTitle('t-rs', 'RS126 Top10'), windows['126'] || [], 'rs126');
    bindRankItems(cardByTitle('t-rs', 'RS189 Top10'), windows['189'] || [], 'rs189');
    bindRankItems(cardByTitle('t-rs', 'RS189 継続性'), rs.rows || [], 'rs189');
  }

  function bindMoverRow(item, row, key) {
    item.hidden = !row;
    if (!row) return;
    item.dataset.tkone = row.ticker || '';
    setText(item, '.mvr-t', row.ticker || '—');
    setText(item, '.mvr-th', row.theme || row.industry || row.sector || '—');
    const value = Number(row[key]);
    setText(item, '.mvr-v', Number.isFinite(value) ? `${value >= 0 ? '+' : ''}${(value * 100).toFixed(1)}%` : '—');
    const badges = item.querySelectorAll('.mvr-e');
    if (badges[0]) badges[0].textContent = row.rvol == null ? 'RVOL —' : `RVOL${Number(row.rvol).toFixed(1)}`;
    if (badges[1]) badges[1].textContent = row.rs189 == null ? 'RS189 —' : `RS189 ${Number(row.rs189).toFixed(0)}`;
  }

  function bindMovers(view) {
    const movers = view.movers || {};
    const blocks = Array.from(document.querySelectorAll('#t-movers .mv-per'));
    ['1d', '1w', '1m'].forEach((period, index) => {
      const block = blocks[index];
      const data = (movers.periods || {})[period];
      if (!block || !data) return;
      const columns = block.querySelectorAll('.mv-col');
      [[columns[0], data.gainers], [columns[1], data.losers]].forEach(([column, rows]) => {
        if (!column) return;
        Array.from(column.querySelectorAll('.mvr')).forEach((item, rowIndex) => bindMoverRow(item, rows[rowIndex], data.key));
      });
    });
    const section = document.getElementById('t-movers');
    if (section) section.dataset.v38Status = movers.status || 'SOURCE_UNAVAILABLE';
  }

  function bindPositions(view) {
    const positions = view.positions || {};
    if (positions.status !== 'READY' || (positions.rows || []).length) return;
    const card = cardByTitle('t-alloc', '現在の保有') || cards('t-alloc')[0];
    if (!card) return;
    card.querySelectorAll('.rsx-item,[data-tkone]').forEach((row) => { row.hidden = true; });
    let empty = card.querySelector('.v38-empty-positions');
    if (!empty) {
      empty = document.createElement('div');
      empty.className = 'empty v38-empty-positions';
      card.appendChild(empty);
    }
    empty.textContent = '現在保有なし';
    card.dataset.v38Status = 'READY';
  }

  function bind(view) {
    if (!view) return;
    bindDaily(view);
    bindRs(view);
    bindMovers(view);
    bindPositions(view);
    document.body.dataset.v38LiveBinder = 'ready';
  }

  document.addEventListener('v38:view-ready', (event) => bind(event.detail), {once: true});
  if (window.V38UiViewModel) bind(window.V38UiViewModel);
})();
