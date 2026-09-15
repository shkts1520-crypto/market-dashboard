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

  function finite(value) {
    if (value === null || value === undefined || value === '') return null;
    const number = Number(value);
    return Number.isFinite(number) ? number : null;
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

  function injectOptionsUpwardStyle() {
    if (document.getElementById('v38-options-upward-style')) return;
    const style = document.createElement('style');
    style.id = 'v38-options-upward-style';
    style.textContent = `
      .v38-options-upward-card .sub{margin-bottom:8px}
      .v38-opt-scan{display:flex;flex-wrap:wrap;gap:6px 10px;font-size:10px;margin:4px 0 9px;color:#625b53}
      .v38-opt-period{border-top:1px solid rgba(74,63,47,.14);padding:8px 0 2px}
      .v38-opt-period:first-of-type{border-top:0}
      .v38-opt-period summary{cursor:pointer;font-weight:900;font-size:12px;display:flex;justify-content:space-between;gap:8px}
      .v38-opt-list{display:flex;flex-direction:column;margin-top:6px}
      .v38-opt-row{display:grid;grid-template-columns:34px 64px minmax(0,1fr) auto;align-items:center;gap:6px;padding:6px 0;border-bottom:1px solid rgba(74,63,47,.08);font-size:10px}
      .v38-opt-row:last-child{border-bottom:0}
      .v38-opt-rank{font-variant-numeric:tabular-nums;color:#7a7268}
      .v38-opt-ticker{font-weight:950;cursor:pointer;text-decoration:underline;text-decoration-thickness:1px;text-underline-offset:2px}
      .v38-opt-why{min-width:0;color:#5f5951;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
      .v38-opt-score{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-weight:900;white-space:nowrap}
      @media(max-width:430px){.v38-opt-row{grid-template-columns:28px 54px minmax(0,1fr) auto;gap:4px;font-size:9px}.v38-opt-why{white-space:normal;line-height:1.25}}
    `;
    document.head.appendChild(style);
  }

  function optionNumber(value, digits) {
    const number = finite(value);
    return number === null ? '—' : number.toFixed(digits == null ? 2 : digits);
  }

  function optionRatio(value) {
    const number = finite(value);
    if (number === null) return '—';
    if (!Number.isFinite(number)) return '∞';
    return number.toFixed(2) + 'x';
  }

  function upwardReason(row) {
    const checks = row.upward_structure_checks || {};
    const parts = [];
    if (checks.spot_above_gamma_flip === true) parts.push('Spot>Flip');
    if (checks.call_wall_above_spot === true) parts.push('CallWall>Spot');
    if (checks.put_wall_below_spot === true) parts.push('PutWall<Spot');
    if (checks.call_gex_dominant === true) parts.push('CallGEX優勢');
    return parts.join('・') || '—';
  }

  async function bindOptionsUpward() {
    const section = document.getElementById('t-options');
    if (!section) return;
    let options = null;
    try {
      const response = await fetch('data/options/index.json', {cache: 'no-store'});
      if (response.ok) options = await response.json();
    } catch (_) {}
    if (!options || !options.upward_rankings) return;

    injectOptionsUpwardStyle();
    let card = section.querySelector('.v38-options-upward-card');
    if (!card) {
      card = document.createElement('div');
      card.className = 'card v38-options-upward-card';
      const firstCard = section.querySelector(':scope > .card');
      if (firstCard) section.insertBefore(card, firstCard);
      else section.appendChild(card);
    }
    card.replaceChildren();
    const heading = document.createElement('h2');
    heading.textContent = '上向きOptions配置';
    const sub = document.createElement('div');
    sub.className = 'sub';
    sub.textContent = '全Active Universeを走査。Direction/Confidence予測ではなく、実測のWall / Gamma Flip / GEX配置で期間別に抽出。';
    card.append(heading, sub);

    const scan = options.universe_scan || {};
    const scanLine = document.createElement('div');
    scanLine.className = 'v38-opt-scan';
    const targetCount = scan.target_count == null ? '—' : scan.target_count;
    const resolved = scan.resolved_count == null ? '—' : scan.resolved_count;
    const coverage = finite(scan.resolution_coverage);
    const positioning = scan.positioning_count == null ? '—' : scan.positioning_count;
    scanLine.textContent = `Universe ${targetCount} / 解決 ${resolved}${coverage === null ? '' : ` (${(coverage * 100).toFixed(1)}%)`} / Options配置 ${positioning} / Scan ${scan.status || '—'}`;
    card.appendChild(scanLine);

    const order = ['0-6', '7-21', '22-45', '0-45'];
    order.forEach((bucket, bucketIndex) => {
      const rows = Array.isArray(options.upward_rankings[bucket]) ? options.upward_rankings[bucket] : [];
      const details = document.createElement('details');
      details.className = 'v38-opt-period';
      details.open = bucketIndex === 0 || bucket === '0-45';
      const summary = document.createElement('summary');
      const label = document.createElement('span');
      label.textContent = `${bucket} DTE`;
      const count = document.createElement('span');
      count.textContent = `${rows.length}銘柄`;
      summary.append(label, count);
      details.appendChild(summary);
      const list = document.createElement('div');
      list.className = 'v38-opt-list';
      rows.forEach((row, index) => {
        const line = document.createElement('div');
        line.className = 'v38-opt-row';
        const rank = document.createElement('span');
        rank.className = 'v38-opt-rank';
        rank.textContent = String(row.upward_rank || index + 1);
        const ticker = document.createElement('span');
        ticker.className = 'v38-opt-ticker';
        ticker.dataset.v38Ticker = row.ticker || '';
        ticker.textContent = row.ticker || '—';
        const why = document.createElement('span');
        why.className = 'v38-opt-why';
        why.textContent = `${upwardReason(row)} / Spot ${optionNumber(row.spot)} / Flip ${optionNumber(row.gamma_flip)} / CW ${optionNumber(row.call_wall)} / PW ${optionNumber(row.put_wall)}`;
        const score = document.createElement('span');
        score.className = 'v38-opt-score';
        score.textContent = `${row.upward_structure_score || 0}/${row.upward_structure_observed || 0} · GEX ${optionRatio(row.call_put_gex_ratio)}`;
        line.append(rank, ticker, why, score);
        list.appendChild(line);
      });
      if (!rows.length) {
        const empty = document.createElement('div');
        empty.className = 'empty';
        empty.textContent = '該当なし';
        list.appendChild(empty);
      }
      details.appendChild(list);
      card.appendChild(details);
    });
    card.dataset.v38TruthSource = 'data/options/index.json.upward_rankings';
    card.dataset.v38Status = 'READY';
    card.dataset.v38Rows = String(Object.values(options.upward_rankings).reduce((sum, rows) => sum + (Array.isArray(rows) ? rows.length : 0), 0));
    section.dataset.v38Status = options.status || 'READY';
  }

  function bind(view) {
    if (!view) return;
    bindDaily(view);
    bindRs(view);
    bindMovers(view);
    bindPositions(view);
    bindOptionsUpward();
    document.body.dataset.v38LiveBinder = 'ready';
  }

  document.addEventListener('v38:view-ready', (event) => bind(event.detail), {once: true});
  if (window.V38UiViewModel) bind(window.V38UiViewModel);
})();
