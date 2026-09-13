(function () {
  'use strict';

  const MAX_SESSIONS = 504;
  const DEBUG_TEXT = [
    '通常株PIT履歴', '遡及推計なし', 'MC57 Raw', 'MC57 EMA2 Raw', 'MC57 Z',
    'MC57内部 12指標履歴', '日次保存済み履歴', '各指標は同一セッションの正本値のみ'
  ];
  let rendering = false;

  function finite(value) {
    if (value === null || value === undefined || value === '') return null;
    const number = Number(value);
    return Number.isFinite(number) ? number : null;
  }

  function cardByTitle(section, titlePart) {
    return Array.from(section.querySelectorAll('.card')).find((card) => {
      const original = String(card.dataset.v38CardTitle || '');
      const h2 = card.querySelector('h2');
      return original.includes(titlePart) || (h2 && h2.textContent.includes(titlePart));
    }) || null;
  }

  function cleanupTechnicalUi() {
    const daily = document.getElementById('t-market');
    if (daily) {
      daily.querySelectorAll('.v38-mc57-trend').forEach((node) => node.remove());
      daily.querySelectorAll('.v38-bind-note').forEach((note) => {
        const text = note.textContent || '';
        const status = note.dataset.v38Status || '';
        if (status === 'READY' || DEBUG_TEXT.some((token) => text.includes(token))) {
          note.remove();
          return;
        }
        if (status === 'DATA_REQUIRED' || status === 'STALE') {
          const replacement = status === 'STALE' ? '更新待ち' : 'データ未取得';
          if (text.trim() !== replacement) {
            note.replaceChildren();
            const span = document.createElement('span');
            span.className = 'mut';
            span.textContent = replacement;
            note.appendChild(span);
          }
        }
      });
    }

    document.querySelectorAll('.v38-bind-note').forEach((note) => {
      const status = note.dataset.v38Status || '';
      if (status === 'READY') {
        note.remove();
        return;
      }
      if (status === 'DATA_REQUIRED' || status === 'STALE') {
        note.replaceChildren();
        const span = document.createElement('span');
        span.className = 'mut';
        span.textContent = status === 'STALE' ? '更新待ち' : 'データ未取得';
        note.appendChild(span);
      }
    });
  }

  function normalizePoints(points) {
    return (Array.isArray(points) ? points : []).map((point) => {
      if (!point || typeof point !== 'object' || typeof point.date !== 'string') return null;
      const value = finite(point.value !== undefined ? point.value : point.close);
      return value === null ? null : {date: point.date, value: value};
    }).filter(Boolean).slice(-MAX_SESSIONS);
  }

  function ratioSeries(left, right) {
    const rightByDate = {};
    normalizePoints(right).forEach((point) => { rightByDate[point.date] = point.value; });
    return normalizePoints(left).map((point) => {
      const divisor = finite(rightByDate[point.date]);
      return divisor === null || divisor === 0 ? null : {date: point.date, value: point.value / divisor};
    }).filter(Boolean);
  }

  function quarterTicks(points) {
    const values = normalizePoints(points);
    if (!values.length) return [];
    const ticks = [];
    const seen = new Set();
    values.forEach((point, index) => {
      const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(point.date);
      if (!match) return;
      const year = Number(match[1]);
      const month = Number(match[2]);
      const quarter = Math.floor((month - 1) / 3);
      const key = year + '-Q' + quarter;
      if (seen.has(key)) return;
      seen.add(key);
      const quarterMonth = quarter * 3 + 1;
      ticks.push({index: index, label: String(year).slice(2) + '/' + String(quarterMonth)});
    });
    return ticks;
  }

  function drawTrend(chart, points, colour) {
    const values = normalizePoints(points);
    if (!chart || values.length < 2) return false;
    const width = 680;
    const height = 180;
    const padX = 6;
    const padY = 8;
    let low = Math.min.apply(null, values.map((point) => point.value));
    let high = Math.max.apply(null, values.map((point) => point.value));
    if (high === low) {
      high += 1;
      low -= 1;
    }
    const x = (index) => padX + (width - padX * 2) * index / Math.max(1, values.length - 1);
    const y = (value) => padY + (height - padY * 2) * (high - value) / (high - low);
    const coords = values.map((point, index) => [x(index), y(point.value)]);

    chart.replaceChildren();
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('class', 'spark v38-live-spark v38-two-year-trend');
    svg.setAttribute('viewBox', '0 0 ' + width + ' ' + height);
    svg.setAttribute('preserveAspectRatio', 'none');
    svg.setAttribute('role', 'img');
    svg.setAttribute('aria-label', '2年トレンド');
    svg.dataset.v38HistoryPoints = String(values.length);

    const pathText = coords.map((point, index) => (index ? 'L' : 'M') + point[0].toFixed(1) + ',' + point[1].toFixed(1)).join(' ');
    const area = document.createElementNS(svg.namespaceURI, 'path');
    area.setAttribute('d', pathText + ' L' + coords[coords.length - 1][0].toFixed(1) + ',' + (height - padY) + ' L' + coords[0][0].toFixed(1) + ',' + (height - padY) + ' Z');
    area.setAttribute('fill', colour || '#1E7A4D');
    area.setAttribute('opacity', '0.08');
    svg.appendChild(area);

    const line = document.createElementNS(svg.namespaceURI, 'polyline');
    line.setAttribute('points', coords.map((point) => point[0].toFixed(1) + ',' + point[1].toFixed(1)).join(' '));
    line.setAttribute('fill', 'none');
    line.setAttribute('stroke', colour || '#1E7A4D');
    line.setAttribute('stroke-width', '2');
    svg.appendChild(line);

    const last = coords[coords.length - 1];
    const dot = document.createElementNS(svg.namespaceURI, 'circle');
    dot.setAttribute('cx', last[0].toFixed(1));
    dot.setAttribute('cy', last[1].toFixed(1));
    dot.setAttribute('r', '3.2');
    dot.setAttribute('fill', colour || '#1E7A4D');
    svg.appendChild(dot);
    chart.appendChild(svg);

    const ticks = quarterTicks(values);
    if (ticks.length) {
      const axis = document.createElement('div');
      axis.className = 'dax v38-quarter-axis';
      axis.dataset.v38QuarterTicks = String(ticks.length);
      axis.style.display = 'grid';
      axis.style.gridTemplateColumns = 'repeat(' + ticks.length + ', minmax(0, 1fr))';
      ticks.forEach((tick) => {
        const span = document.createElement('span');
        span.textContent = tick.label;
        axis.appendChild(span);
      });
      chart.appendChild(axis);
    }
    return true;
  }

  function marketSeries(daily, symbol) {
    const series = daily && daily.market_series;
    return series && Array.isArray(series[symbol]) ? series[symbol] : [];
  }

  function redrawDaily(view) {
    const daily = view && view.daily;
    const section = document.getElementById('t-market');
    if (!daily || !section) return;

    const history = Array.isArray(daily.history) ? daily.history : [];
    const diagnostics = daily.market_diagnostics && Array.isArray(daily.market_diagnostics.series)
      ? daily.market_diagnostics.series : [];
    const specs = [
      ['ブレッドス推移（50', history.map((row) => ({date: row.date, value: row.breadth50})), '#2c69c9'],
      ['ブレッドス推移（200', history.map((row) => ({date: row.date, value: row.breadth200})), '#7b5c36'],
      ['売買代金 参加度', diagnostics.map((row) => ({date: row.date, value: row.volume_participation})), '#2c69c9'],
      ['集積／分散', diagnostics.map((row) => ({date: row.date, value: row.up_down_dollar_ratio})), '#7b5c36'],
      ['騰落ライン（マクレラン', diagnostics.map((row) => ({date: row.date, value: row.mcclellan})), '#1E7A4D'],
      ['クレジット推移', ratioSeries(marketSeries(daily, 'HYG'), marketSeries(daily, 'IEF')), '#7b5c36'],
      ['攻守ローテーション', ratioSeries(marketSeries(daily, 'XLY'), marketSeries(daily, 'XLP')), '#7b5c36'],
      ['VIX反転シーケンス', marketSeries(daily, '^VIX'), '#B84A42'],
      ['VIX期間構造', ratioSeries(marketSeries(daily, '^VIX'), marketSeries(daily, '^VIX3M')), '#B84A42']
    ];

    specs.forEach((spec) => {
      const card = cardByTitle(section, spec[0]);
      if (!card) return;
      const chart = card.querySelector('.chart');
      if (!chart) return;
      drawTrend(chart, spec[1], spec[2]);
    });
  }

  async function finalPass() {
    if (rendering) return;
    rendering = true;
    try {
      cleanupTechnicalUi();
      const runtime = window.V38Runtime;
      if (runtime && typeof runtime.loadJson === 'function') {
        const view = await runtime.loadJson('data/ui_view_model.json');
        redrawDaily(view);
      }
      cleanupTechnicalUi();
      document.body.dataset.v38FinalUiStatus = 'ready';
    } catch (_) {
      document.body.dataset.v38FinalUiStatus = 'failed';
    } finally {
      rendering = false;
    }
  }

  function start() {
    finalPass();
    window.setTimeout(finalPass, 250);
    window.setTimeout(finalPass, 900);
    window.setTimeout(finalPass, 1800);
  }

  function waitForBinding() {
    if (document.body && document.body.dataset.v38BindingStatus === 'ready') {
      start();
      return;
    }
    window.setTimeout(waitForBinding, 40);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', waitForBinding, {once: true});
  } else {
    waitForBinding();
  }
})();
