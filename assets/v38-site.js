(function () {
  'use strict';

  const TAB_SELECTOR = 'nav a.tabx[href^="#"]';
  const SECTION_IDS = [
    't-market', 't-alloc', 't-port', 't-rotation', 't-rs',
    't-weekly', 't-options', 't-post1', 't-rules'
  ];
  const VIEW_BINDINGS = [
    ['t-alloc', 'positions'], ['t-port', 'core12'],
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
      // Keep the visibility contract explicit. This makes tab switching reliable
      // even when a cached/legacy stylesheet still contains :target rules.
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

  function finite(value) {
    if (value === null || value === undefined || value === '') return null;
    const number = Number(value);
    return Number.isFinite(number) ? number : null;
  }

  function pct(value, digits) {
    const number = finite(value);
    if (number === null) return '—';
    const sign = number > 0 ? '+' : '';
    return sign + (number * 100).toFixed(digits === undefined ? 1 : digits) + '%';
  }

  function num(value, digits) {
    const number = finite(value);
    return number === null ? '—' : number.toLocaleString(undefined, {
      minimumFractionDigits: digits === undefined ? 1 : digits,
      maximumFractionDigits: digits === undefined ? 1 : digits
    });
  }

  function closePoints(points) {
    return (Array.isArray(points) ? points : []).map((point, index) => {
      if (point && typeof point === 'object') {
        const value = finite(point.close !== undefined ? point.close : point.value);
        return value === null ? null : {x: index, value: value, date: point.date || ''};
      }
      const value = finite(point);
      return value === null ? null : {x: index, value: value, date: ''};
    }).filter(Boolean);
  }

  function sparkline(parent, points, colour, height) {
    const values = closePoints(points);
    if (!values.length) return null;
    const width = 680;
    const chartHeight = height || 68;
    const padX = 6;
    const padY = 6;
    const lows = values.map((point) => point.value);
    let low = Math.min.apply(null, lows);
    let high = Math.max.apply(null, lows);
    if (high === low) {
      high += 1;
      low -= 1;
    }
    const x = (index) => padX + (width - padX * 2) * index / Math.max(1, values.length - 1);
    const y = (value) => padY + (chartHeight - padY * 2) * (high - value) / (high - low);
    const coords = values.map((point, index) => [x(index), y(point.value)]);
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('class', 'spark v38-live-spark');
    svg.setAttribute('viewBox', '0 0 ' + width + ' ' + chartHeight);
    svg.setAttribute('preserveAspectRatio', 'none');
    svg.setAttribute('role', 'img');
    svg.setAttribute('aria-label', 'Live price history');
    const area = document.createElementNS(svg.namespaceURI, 'path');
    const path = coords.map((point, index) => (index ? 'L' : 'M') + point[0].toFixed(1) + ',' + point[1].toFixed(1)).join(' ');
    area.setAttribute('d', path + ' L' + coords[coords.length - 1][0].toFixed(1) + ',' + (chartHeight - padY) + ' L' + coords[0][0].toFixed(1) + ',' + (chartHeight - padY) + ' Z');
    area.setAttribute('fill', colour || '#1E7A4D');
    area.setAttribute('opacity', '0.10');
    svg.appendChild(area);
    const line = document.createElementNS(svg.namespaceURI, 'polyline');
    line.setAttribute('points', coords.map((point) => point[0].toFixed(1) + ',' + point[1].toFixed(1)).join(' '));
    line.setAttribute('fill', 'none');
    line.setAttribute('stroke', colour || '#1E7A4D');
    line.setAttribute('stroke-width', '2');
    svg.appendChild(line);
    const dot = document.createElementNS(svg.namespaceURI, 'circle');
    dot.setAttribute('cx', coords[coords.length - 1][0].toFixed(1));
    dot.setAttribute('cy', coords[coords.length - 1][1].toFixed(1));
    dot.setAttribute('r', '3.2');
    dot.setAttribute('fill', colour || '#1E7A4D');
    svg.appendChild(dot);
    parent.appendChild(svg);
    return svg;
  }

  function tickerLink(parent, ticker, className) {
    const link = append(parent, 'a', className || '', ticker || '—');
    if (ticker) {
      link.href = 'https://www.tradingview.com/chart/?symbol=' + encodeURIComponent(ticker);
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
    }
    return link;
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

  function renderChartCard(card, title, current, label, points, colour, status, reason, session) {
    if (!card) return;
    card.replaceChildren();
    card.dataset.v38Status = status || 'DATA_REQUIRED';
    const header = append(card, 'div', 'chd', '');
    append(header, 'h2', '', title);
    const now = append(header, 'div', 'chd-now', '');
    now.style.color = colour || '#1E7A4D';
    append(now, 'b', '', current || '—');
    append(now, 'span', '', label || '最新');
    const chart = append(card, 'div', 'chart', '');
    sparkline(chart, points, colour || '#1E7A4D', 180);
    statusNote(card, status || 'DATA_REQUIRED', reason || 'CURRENT_SESSION', session);
  }

  function marketSummary(daily, symbol) {
    const summaries = daily && daily.market_summaries;
    return summaries && summaries[symbol] ? summaries[symbol] : {};
  }

  function marketSeries(daily, symbol) {
    const series = daily && daily.market_series;
    return series && Array.isArray(series[symbol]) ? series[symbol] : [];
  }

  function hasMarket(daily, symbols) {
    return symbols.every((symbol) => finite(marketSummary(daily, symbol).close) !== null);
  }

  function performanceBlock(card, name, summary) {
    append(card, 'div', 'ixn', name);
    addKeyValue(card, name + ' Close', num(summary.close, 2));
    const grid = append(card, 'div', 'perf', '');
    [
      ['YTD', summary.change_ytd], ['1週', summary.change_1w],
      ['1カ月', summary.change_1m], ['1年', summary.change_1y],
      ['52週位置', summary.position_52w === null || summary.position_52w === undefined ? null : summary.position_52w - 1]
    ].forEach((entry) => {
      const cell = append(grid, 'div', 'c', '');
      append(cell, 'div', 'k', entry[0]);
      const value = finite(entry[1]);
      append(cell, 'div', 'v ' + (value === null ? 'mut' : value >= 0 ? 'pos' : 'neg'), value === null ? '—' : pct(value));
    });
  }

  function renderPerformanceCard(card, daily, session) {
    if (!card) return;
    card.replaceChildren();
    append(card, 'h2', '', 'マーケット・パフォーマンス Performance');
    performanceBlock(card, 'S&P500', marketSummary(daily, 'SPY'));
    performanceBlock(card, 'NASDAQ100', marketSummary(daily, 'QQQ'));
    append(card, 'div', 'perf-div', '等ウェイト（ブレッドス）');
    performanceBlock(card, 'S&P均等 RSP', marketSummary(daily, 'RSP'));
    performanceBlock(card, 'NDX均等 QQQE', marketSummary(daily, 'QQQE'));
    addKeyValue(card, 'VIX', num(marketSummary(daily, '^VIX').close, 2));
    statusNote(card, hasMarket(daily, ['SPY', 'QQQ']) ? 'READY' : 'DATA_REQUIRED', 'Yahoo completed daily bars; unavailable optional series and horizons remain —', session);
  }

  function ratioSeries(left, right) {
    const byDate = {};
    (Array.isArray(right) ? right : []).forEach((row) => {
      const value = finite(row && row.close);
      if (row && row.date && value !== null) byDate[row.date] = value;
    });
    return (Array.isArray(left) ? left : []).map((row) => {
      const l = finite(row && row.close);
      const r = row && byDate[row.date];
      return l !== null && finite(r) !== null && r !== 0 ? {date: row.date, close: l / r} : null;
    }).filter(Boolean);
  }

  function distributionDays(rows) {
    const recent = (Array.isArray(rows) ? rows : []).slice(-26);
    let count = 0;
    for (let index = 1; index < recent.length; index += 1) {
      const current = recent[index];
      const previous = recent[index - 1];
      const currentClose = finite(current.close);
      const previousClose = finite(previous.close);
      const currentVolume = finite(current.volume);
      const previousVolume = finite(previous.volume);
      if (currentClose !== null && previousClose !== null && currentVolume !== null && previousVolume !== null && currentClose < previousClose && currentVolume > previousVolume) count += 1;
    }
    return count;
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

    renderPerformanceCard(findCard(section, 'マーケット・パフォーマンス'), daily, session);

    const history = Array.isArray(daily.history) ? daily.history : [];
    renderChartCard(findCard(section, 'ブレッドス推移（50'), 'ブレッドス推移（50日線上の割合）',
      metricDisplay(metrics, 'breadth50'), '50日線上', history.map((row) => ({date: row.date, close: row.breadth50})),
      '#2c69c9', metrics.breadth50 ? metrics.breadth50.status : 'DATA_REQUIRED',
      history.length > 1 ? '日次保存済み履歴' : '履歴蓄積開始済み（現在1セッション）', session);
    renderChartCard(findCard(section, 'ブレッドス推移（200'), 'ブレッドス推移（200日線上の割合）',
      metricDisplay(metrics, 'breadth200'), '200日線上', history.map((row) => ({date: row.date, close: row.breadth200})),
      '#7b5c36', metrics.breadth200 ? metrics.breadth200.status : 'DATA_REQUIRED',
      history.length > 1 ? '日次保存済み履歴' : '履歴蓄積開始済み（現在1セッション）', session);

    const diagnostics = daily.market_diagnostics && typeof daily.market_diagnostics === 'object'
      ? daily.market_diagnostics : {};
    const diagnosticSeries = Array.isArray(diagnostics.series) ? diagnostics.series : [];
    const latestDiagnostic = diagnosticSeries.length ? diagnosticSeries[diagnosticSeries.length - 1] : {};
    const diagnosticStatus = diagnostics.status || 'DATA_REQUIRED';
    const diagnosticReason = diagnostics.reason || 'MARKET_DIAGNOSTIC_HISTORY_MISSING';
    renderChartCard(findCard(section, '売買代金 参加度'), '売買代金 参加度 Volume Participation',
      finite(latestDiagnostic.volume_participation) === null ? '—' : num(latestDiagnostic.volume_participation, 2) + '×',
      '全銘柄出来高 / 直前200日平均', diagnosticSeries.map((row) => ({date: row.date, close: row.volume_participation})),
      '#2c69c9', diagnosticStatus, diagnosticReason, session);
    renderChartCard(findCard(section, '集積／分散'), '集積／分散 Accumulation / Distribution',
      finite(latestDiagnostic.up_down_dollar_ratio) === null ? '—' : num(latestDiagnostic.up_down_dollar_ratio, 2) + '×',
      '上昇銘柄売買代金 / 下落銘柄売買代金', diagnosticSeries.map((row) => ({date: row.date, close: row.up_down_dollar_ratio})),
      '#7b5c36', diagnosticStatus, diagnosticReason, session);
    renderChartCard(findCard(section, '騰落ライン（マクレラン'), '騰落ライン（マクレラン）',
      finite(latestDiagnostic.mcclellan) === null ? '—' : num(latestDiagnostic.mcclellan, 1),
      '騰落差 EMA19 − EMA39', diagnosticSeries.map((row) => ({date: row.date, close: row.mcclellan})),
      '#1E7A4D', diagnosticStatus, diagnosticReason, session);

    const changeCard = findCard(section, '前回からの変化');
    if (changeCard) {
      changeCard.replaceChildren();
      append(changeCard, 'h2', '', '前回からの変化 Change Log');
      const previous = history.length > 1 ? history[history.length - 2] : null;
      const list = append(changeCard, 'ul', 'chlog', '');
      if (previous) {
        [['50MA Breadth', 'breadth50'], ['200MA Breadth', 'breadth200'], ['F1', 'f1'], ['F2', 'f2'], ['F3', 'f3']].forEach((entry) => {
          const current = finite(history[history.length - 1][entry[1]]);
          const before = finite(previous[entry[1]]);
          const li = append(list, 'li', '', '');
          li.textContent = entry[0] + ' ' + (current === null ? '—' : num(current, 1)) + (current !== null && before !== null ? '（前回比 ' + (current - before >= 0 ? '+' : '') + num(current - before, 1) + '）' : '');
        });
      } else {
        append(list, 'li', '', '履歴蓄積開始。次の営業日から前回比を表示します。');
      }
      statusNote(changeCard, 'READY', 'data/history/sessions', session);
    }

    const leaders = daily.leader_diagnostics || {};
    renderDailyCard(findCard(section, 'リーダーの強さ'), 'リーダーの強さ Leader Temperature', 'READY',
      '正本RS universeからの診断値（売買ゲートではありません）', session, [
        ['RS63/126/189 全て85以上', leaders.triple_rs85_count],
        ['52週高値まで5%以内', leaders.near_52w_high_count],
        ['当日上昇銘柄比率', finite(leaders.advancing_1d_pct) === null ? '—' : num(leaders.advancing_1d_pct, 1) + '%']
      ]);

    const momentum = findCard(section, '先導株モメンタム');
    if (momentum) {
      momentum.replaceChildren();
      append(momentum, 'h2', '', '先導株モメンタム・ラン Leader Momentum');
      const list = append(momentum, 'div', 'rsc-list', '');
      (Array.isArray(leaders.top_ret20) ? leaders.top_ret20 : []).slice(0, 10).forEach((row) => renderRsItem(list, row, 'rs63'));
      statusNote(momentum, 'READY', '20-session return leaders; diagnostic only', session);
    }

    renderDailyCard(findCard(section, '信用と金利'), '信用と金利 Credit & Rates',
      hasMarket(daily, ['HYG', 'IEF', '^TNX', '^FVX']) ? 'READY' : 'DATA_REQUIRED',
      'Yahoo completed daily bars', session, [
        ['HYG', num(marketSummary(daily, 'HYG').close, 2)],
        ['IEF', num(marketSummary(daily, 'IEF').close, 2)],
        ['米10年金利', num(marketSummary(daily, '^TNX').close, 2) + '%'],
        ['米5年金利', num(marketSummary(daily, '^FVX').close, 2) + '%']
      ]);

    const credit = ratioSeries(marketSeries(daily, 'HYG'), marketSeries(daily, 'IEF'));
    renderChartCard(findCard(section, 'クレジット推移'), 'クレジット推移（HYG / IEF）',
      credit.length ? num(credit[credit.length - 1].close, 3) : '—', 'HYG / IEF', credit,
      '#7b5c36', credit.length ? 'READY' : 'DATA_REQUIRED', 'Yahoo completed daily bars', session);

    const riskOn = ratioSeries(marketSeries(daily, 'XLY'), marketSeries(daily, 'XLP'));
    renderChartCard(findCard(section, '攻守ローテーション'), '攻守ローテーション（XLY / XLP）',
      riskOn.length ? num(riskOn[riskOn.length - 1].close, 3) : '—', 'Risk-on / Defensive', riskOn,
      '#7b5c36', riskOn.length ? 'READY' : 'DATA_REQUIRED', 'Yahoo completed daily bars', session);

    renderChartCard(findCard(section, 'VIX反転シーケンス'), 'VIX反転シーケンス VIX Fear Cycle',
      metricDisplay(metrics, 'market_^VIX'), 'VIX Close', marketSeries(daily, '^VIX'),
      '#B84A42', metrics['market_^VIX'] ? metrics['market_^VIX'].status : 'DATA_REQUIRED', 'Yahoo completed daily bars', session);
    const term = ratioSeries(marketSeries(daily, '^VIX'), marketSeries(daily, '^VIX3M'));
    renderChartCard(findCard(section, 'VIX期間構造'), 'VIX期間構造（1M / 3M）',
      term.length ? num(term[term.length - 1].close, 3) : '—', '1M / 3M', term,
      '#B84A42', term.length ? 'READY' : 'DATA_REQUIRED', 'Yahoo completed daily bars', session);

    const vix = finite(marketSummary(daily, '^VIX').close);
    const vxn = finite(marketSummary(daily, '^VXN').close);
    renderDailyCard(findCard(section, 'オプション想定変動幅'), 'オプション想定変動幅 Expected Move',
      vix !== null || vxn !== null ? 'READY' : 'DATA_REQUIRED', '年率IV÷√12の約1カ月目安', session, [
        ['SPY 約1カ月', vix === null ? '—' : '±' + (vix / Math.sqrt(12)).toFixed(1) + '%'],
        ['QQQ 約1カ月', vxn === null ? '—' : '±' + (vxn / Math.sqrt(12)).toFixed(1) + '%']
      ]);

    renderDailyCard(findCard(section, 'ディストリビューション・デイ'), 'ディストリビューション・デイ（直近25営業日）',
      'READY', '価格下落かつ前日比出来高増の表示用proxy。FTD以降判定ではありません。', session, [
        ['SPY', distributionDays(marketSeries(daily, 'SPY')) + '日'],
        ['QQQ', distributionDays(marketSeries(daily, 'QQQ')) + '日']
      ]);
  }

  function renderRsItem(parent, row, scoreKey) {
    const item = append(parent, 'div', 'rsx-item', '');
    item.dataset.v38RsTicker = String(row.ticker || '');
    const top = append(item, 'div', 'rsx-row', '');
    append(top, 'span', 'rsx-rk', row.rank || '—');
    const name = append(top, 'div', 'rsx-name', '');
    const nameLine = append(name, 'div', '', '');
    tickerLink(nameLine, row.ticker, 'v38-ticker-link');
    const period = scoreKey || 'rs189';
    append(nameLine, 'span', 'rsx-badge sel', period.toUpperCase());
    append(name, 'small', '', [row.industry || row.sector, row.ddv20_display || 'DDV —'].filter(Boolean).join(' • '));
    const score = append(top, 'div', 'rsx-score', '');
    append(score, 'b', '', row[period + '_display'] || '—');
    append(score, 'small', '', period.toUpperCase());
    const sub = append(item, 'div', 'rsx-sub', '');
    append(sub, 'span', 'rsx-nums', '63 ' + (row.rs63_display || '—') + ' / 126 ' + (row.rs126_display || '—') + ' / 189 ' + (row.rs189_display || '—'));
    append(sub, 'span', 'rsx-ret', 'Price ' + (row.price_display || '—') + ' • 1M ' + pct(row.ret20));
    sparkline(item, row.sparkline, (finite(row.ret20) || 0) >= 0 ? '#1E7A4D' : '#B84A42', 68);
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
    const windows = rs.windows || {};
    [[63, 'RS63 Top10', '約3ヶ月'], [126, 'RS126 Top10', '約6ヶ月'], [189, 'RS189 Top10', '約9ヶ月・主指標']].forEach((spec) => {
      const card = findCard(section, spec[1]);
      if (!card) return;
      card.replaceChildren();
      const header = append(card, 'div', 'hdr', '');
      append(header, 'h2', '', spec[1] + ' ' + spec[2]);
      append(card, 'div', 'sub', '取得済み価格から算出した正本RS順位と直近63営業日の価格スパークライン。');
      const list = append(card, 'div', 'rsc-list', '');
      (Array.isArray(windows[String(spec[0])]) ? windows[String(spec[0])] : []).forEach((row) => renderRsItem(list, row, 'rs' + spec[0]));
      statusNote(card, rs.status || 'DATA_REQUIRED', rs.reason || 'CURRENT_SESSION', session);
    });
    const persistence = findCard(section, 'RS189 継続性');
    if (persistence) {
      persistence.replaceChildren();
      append(persistence, 'h2', '', 'RS189 Leadership Persistence');
      append(persistence, 'div', 'sub', 'RS189 Top24。Core 12の適格性・採用順位ではありません。');
      const list = append(persistence, 'div', 'rsc-list', '');
      (Array.isArray(rs.rows) ? rs.rows : []).forEach((row) => renderRsItem(list, row, 'rs189'));
      statusNote(persistence, rs.status || 'DATA_REQUIRED', rs.reason || 'CURRENT_SESSION', session);
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

  function renderRotation(view) {
    const section = document.getElementById('t-rotation');
    const data = view && view.rotation;
    if (!section || !data) return;
    const session = view.session_date || '—';
    neutralizeCards(section, session, data.reason || 'PEER_THEME_AUTHORITY_MISSING');
    section.dataset.v38Status = data.status || 'DATA_REQUIRED';
    const diagnostics = data.diagnostics || {};
    const industries = Array.isArray(diagnostics.industry) ? diagnostics.industry : [];
    const sectors = Array.isArray(diagnostics.sector) ? diagnostics.sector : [];

    const leading = findCard(section, '主導セクター・業種');
    if (leading && industries.length) {
      leading.replaceChildren();
      append(leading, 'h2', '', '主導セクター・業種 Leading Groups');
      append(leading, 'div', 'sub', '現行Universeの20日平均騰落率。Peer Theme Scoreではなく診断表示です。');
      const list = append(leading, 'div', 'bglist', '');
      industries.slice(0, 15).forEach((row) => {
        const item = append(list, 'div', 'bgrow', '');
        append(item, 'div', 'bgname', row.group);
        append(item, 'div', 'bgmeta', pct(row.ret20_avg) + ' • RS63 ' + num(row.rs63_avg, 1) + ' • ' + row.member_count + '銘柄');
      });
      statusNote(leading, 'READY', 'CURRENT_UNIVERSE_DIAGNOSTIC_NOT_PEER_THEME_SCORE', session);
    }

    const leaderCard = findCard(section, '強い業種の主導株');
    if (leaderCard && industries.length) {
      leaderCard.replaceChildren();
      append(leaderCard, 'h2', '', '強い業種の主導株 Leaders in Strong Groups');
      industries.slice(0, 10).forEach((row) => {
        const line = append(leaderCard, 'div', 'slrow', '');
        append(line, 'div', 'slname', row.group);
        const chips = append(line, 'div', 'chips', '');
        (Array.isArray(row.leaders) ? row.leaders : []).forEach((ticker) => tickerLink(chips, ticker, 'chip hot v38-ticker-link'));
      });
      statusNote(leaderCard, 'READY', 'RS63 leaders inside current diagnostic groups', session);
    }

    const heatmap = findCard(section, 'セクター温度マップ');
    if (heatmap && sectors.length) {
      heatmap.replaceChildren();
      append(heatmap, 'h2', '', 'セクター温度マップ Sector Heatmap');
      const grid = append(heatmap, 'div', 'hmgrid', '');
      sectors.slice(0, 11).forEach((row) => {
        const cell = append(grid, 'div', 'hm', '');
        append(cell, 'div', 'hm-n', row.group);
        append(cell, 'div', 'hm-v', pct(row.ret20_avg));
        cell.dataset.v38Direction = (finite(row.ret20_avg) || 0) >= 0 ? 'up' : 'down';
      });
      statusNote(heatmap, 'READY', 'Current-universe 20-session average return', session);
    }

    const etfCard = findCard(section, 'セクターETF強弱');
    if (etfCard) {
      etfCard.replaceChildren();
      append(etfCard, 'h2', '', 'セクターETF強弱 Sector ETF Strength');
      const table = append(etfCard, 'div', 'sectbl', '');
      ['XLB','XLC','XLE','XLF','XLI','XLK','XLP','XLRE','XLU','XLV','XLY'].map((ticker) => {
        return {ticker: ticker, summary: marketSummary(view.daily || {}, ticker)};
      }).sort((a, b) => (finite(b.summary.change_1w) || -1e9) - (finite(a.summary.change_1w) || -1e9)).forEach((item) => {
        const row = append(table, 'div', 'l', '');
        tickerLink(row, item.ticker, 'tk v38-ticker-link');
        append(row, 'span', (finite(item.summary.change_1w) || 0) >= 0 ? 'pos' : 'neg', pct(item.summary.change_1w));
        append(row, 'span', 'mut', '1M ' + pct(item.summary.change_1m));
      });
      statusNote(etfCard, hasMarket(view.daily || {}, ['XLB','XLC','XLE','XLF','XLI','XLK','XLP','XLRE','XLU','XLV','XLY']) ? 'READY' : 'DATA_REQUIRED', 'Yahoo completed daily bars', session);
    }
  }

  function renderWeekly(view) {
    const section = document.getElementById('t-weekly');
    const data = view && view.weekly;
    if (!section || !data) return;
    const session = view.session_date || '—';
    const daily = view.daily || {};
    const metrics = metricMap(daily);
    neutralizeCards(section, session, data.reason || 'NQSAR_AUTHORITATIVE_INPUT_MISSING');
    section.dataset.v38Status = data.status || 'DATA_REQUIRED';

    renderDailyCard(findCard(section, '構造マクロ'), '構造マクロ Structural Macro',
      hasMarket(daily, ['DX-Y.NYB', 'CL=F', 'GC=F']) ? 'READY' : 'DATA_REQUIRED', 'Yahoo completed daily bars', session, [
      ['ドル指数 DXY', num(marketSummary(daily, 'DX-Y.NYB').close, 2) + ' / 1W ' + pct(marketSummary(daily, 'DX-Y.NYB').change_1w)],
      ['WTI', num(marketSummary(daily, 'CL=F').close, 2) + ' / 1W ' + pct(marketSummary(daily, 'CL=F').change_1w)],
      ['Gold', num(marketSummary(daily, 'GC=F').close, 2) + ' / 1W ' + pct(marketSummary(daily, 'GC=F').change_1w)]
    ]);
    renderDailyCard(findCard(section, '金利レジーム'), '金利レジーム Rates',
      hasMarket(daily, ['^TNX', '^FVX', 'IEF']) ? 'READY' : 'DATA_REQUIRED', 'Yahoo completed daily bars', session, [
      ['米10年', num(marketSummary(daily, '^TNX').close, 2) + '%'],
      ['米5年', num(marketSummary(daily, '^FVX').close, 2) + '%'],
      ['IEF 1週', pct(marketSummary(daily, 'IEF').change_1w)]
    ]);
    renderDailyCard(findCard(section, 'マクロ圧力'), 'マクロ圧力 Macro Pressure',
      hasMarket(daily, ['^VIX', '^VXN', 'HYG', 'DX-Y.NYB']) ? 'READY' : 'DATA_REQUIRED', 'Display diagnostics only', session, [
      ['VIX', num(marketSummary(daily, '^VIX').close, 2)],
      ['VXN', num(marketSummary(daily, '^VXN').close, 2)],
      ['HYG 1週', pct(marketSummary(daily, 'HYG').change_1w)],
      ['DXY 1週', pct(marketSummary(daily, 'DX-Y.NYB').change_1w)]
    ]);
    renderDailyCard(findCard(section, '広域ブレッドス'), '広域ブレッドス Market Breadth', 'READY', 'Current-session stock universe', session, [
      ['50MA上', metricDisplay(metrics, 'breadth50')],
      ['200MA上', metricDisplay(metrics, 'breadth200')],
      ['当日上昇比率', finite(daily.leader_diagnostics && daily.leader_diagnostics.advancing_1d_pct) === null ? '—' : num(daily.leader_diagnostics.advancing_1d_pct, 1) + '%']
    ]);
    renderDailyCard(findCard(section, 'データ品質'), 'データ品質 Data Quality', 'READY', 'Fail-closed acquisition contract', session, [
      ['Stock coverage', finite(daily.stock_data_coverage) === null ? '—' : pct(daily.stock_data_coverage)],
      ['Breadth coverage', finite(daily.breadth_coverage) === null ? '—' : pct(daily.breadth_coverage)],
      ['History sessions', Array.isArray(daily.history) ? daily.history.length : 0]
    ]);
    const soxl = marketSummary(daily, 'SOXL');
    renderDailyCard(findCard(section, 'レバレッジ・コンディション'), 'レバレッジ・コンディション（SOXL）',
      finite(soxl.close) === null ? 'DATA_REQUIRED' : 'READY', 'Yahoo completed daily bars', session, [
        ['Close', num(soxl.close, 2)], ['1週', pct(soxl.change_1w)], ['1カ月', pct(soxl.change_1m)], ['3カ月', pct(soxl.change_3m)]
      ]);
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
    renderRotation(view);
    renderWeekly(view);
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
