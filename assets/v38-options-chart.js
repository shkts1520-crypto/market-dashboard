(function () {
  'use strict';

  const OPTIONS_URL = 'data/options/index.json';
  const LIGHTWEIGHT_URL = 'https://cdn.jsdelivr.net/npm/lightweight-charts@4.2.3/dist/lightweight-charts.standalone.production.js';
  const STYLE_ID = 'v38-options-chart-style';
  const MODAL_ID = 'v38-options-chart-modal';
  const TICKER_RE = /^[A-Z][A-Z0-9.\-]{0,9}$/;
  const BUCKETS = ['0-45', '22-45', '7-21', '0-6'];

  let optionsPromise = null;
  let libraryPromise = null;
  let lastTicker = null;
  let currentChart = null;
  let currentObserver = null;

  function finite(value) {
    if (value === null || value === undefined || value === '') return null;
    const number = Number(value);
    return Number.isFinite(number) ? number : null;
  }

  function cleanTicker(value) {
    const ticker = String(value || '').trim().toUpperCase();
    return TICKER_RE.test(ticker) ? ticker : null;
  }

  function money(value) {
    const number = finite(value);
    if (number === null) return '—';
    return Math.abs(number) >= 1000
      ? number.toLocaleString(undefined, {maximumFractionDigits: 2})
      : number.toFixed(2);
  }

  function pct(value) {
    const number = finite(value);
    return number === null ? '—' : (number * 100).toFixed(1) + '%';
  }

  function firstFinite(row, keys) {
    if (!row) return null;
    for (const key of keys) {
      const number = finite(row[key]);
      if (number !== null) return number;
    }
    return null;
  }

  function loadOptions() {
    if (!optionsPromise) {
      optionsPromise = fetch(OPTIONS_URL, {cache: 'no-store'})
        .then((response) => {
          if (!response.ok) throw new Error('options HTTP ' + response.status);
          return response.json();
        })
        .catch(() => null);
    }
    return optionsPromise;
  }

  function loadLightweightCharts() {
    if (window.LightweightCharts) return Promise.resolve(window.LightweightCharts);
    if (!libraryPromise) {
      libraryPromise = new Promise((resolve) => {
        const script = document.createElement('script');
        script.src = LIGHTWEIGHT_URL;
        script.async = true;
        script.onload = () => resolve(window.LightweightCharts || null);
        script.onerror = () => resolve(null);
        document.head.appendChild(script);
      });
    }
    return libraryPromise;
  }

  function rowsForBucket(options, bucket) {
    const buckets = options && options.buckets && typeof options.buckets === 'object'
      ? options.buckets : {};
    return Array.isArray(buckets[bucket]) ? buckets[bucket] : [];
  }

  function rowForBucket(options, ticker, bucket) {
    return rowsForBucket(options, bucket).find((row) =>
      row && String(row.ticker || '').toUpperCase() === ticker
    ) || null;
  }

  function availableBuckets(options, ticker) {
    return BUCKETS.filter((bucket) => rowForBucket(options, ticker, bucket));
  }

  function fallbackRow(options, ticker) {
    const rows = options && Array.isArray(options.rows) ? options.rows : [];
    const current = rows.find((row) => row && String(row.ticker || '').toUpperCase() === ticker);
    if (current) return {bucket: String(current.bucket || '0-45'), row: current, historical: false};

    const history = options && options.history && typeof options.history === 'object'
      ? options.history[ticker] : null;
    if (Array.isArray(history) && history.length) {
      const observed = history.slice().reverse().find((row) => row && typeof row === 'object');
      if (observed) return {bucket: 'history', row: Object.assign({ticker}, observed), historical: true};
    }
    return null;
  }

  function resolveRow(options, ticker, bucket) {
    if (!options || !ticker) return null;
    if (bucket && BUCKETS.includes(bucket)) {
      const row = rowForBucket(options, ticker, bucket);
      if (row) return {bucket, row, historical: false};
    }
    const buckets = availableBuckets(options, ticker);
    if (buckets.length) {
      return {bucket: buckets[0], row: rowForBucket(options, ticker, buckets[0]), historical: false};
    }
    return fallbackRow(options, ticker);
  }

  function levelsFromRow(row) {
    const spot = firstFinite(row, ['spot', 'underlying_price', 'underlying']);
    const expectedMove = firstFinite(row, ['expected_move', 'expected_move_abs', 'em_abs']);
    const expectedPct = firstFinite(row, ['expected_move_pct', 'em_pct']);
    const move = expectedMove !== null
      ? expectedMove
      : (spot !== null && expectedPct !== null ? spot * expectedPct : null);
    const upperDirect = firstFinite(row, ['expected_upper', 'expected_move_upper', 'em_upper']);
    const lowerDirect = firstFinite(row, ['expected_lower', 'expected_move_lower', 'em_lower']);
    const upper = upperDirect !== null ? upperDirect : (spot !== null && move !== null ? spot + move : null);
    const lower = lowerDirect !== null ? lowerDirect : (spot !== null && move !== null ? Math.max(0, spot - move) : null);

    return [
      {key: 'call', label: 'Call Wall', value: firstFinite(row, ['call_wall', 'call_wall_price']), color: '#b63d34', style: 'solid'},
      {key: 'upper', label: 'Expected Upper', value: upper, color: '#2f64a2', style: 'dashed'},
      {key: 'spot', label: 'Spot', value: spot, color: '#4b4b4b', style: 'dotted'},
      {key: 'flip', label: 'Gamma Flip', value: firstFinite(row, ['gamma_flip', 'gamma_flip_price']), color: '#9b6c0d', style: 'solid'},
      {key: 'lower', label: 'Expected Lower', value: lower, color: '#2f64a2', style: 'dashed'},
      {key: 'put', label: 'Put Wall', value: firstFinite(row, ['put_wall', 'put_wall_price']), color: '#23724b', style: 'solid'}
    ].filter((item) => item.value !== null);
  }

  function candlesFor(options, ticker) {
    const rows = options && options.chart_ohlc && typeof options.chart_ohlc === 'object'
      ? options.chart_ohlc[ticker] : null;
    return (Array.isArray(rows) ? rows : []).map((row) => {
      const open = finite(row.open);
      const high = finite(row.high);
      const low = finite(row.low);
      const close = finite(row.close);
      if (!row.time || [open, high, low, close].some((value) => value === null)) return null;
      return {time: String(row.time), open, high, low, close};
    }).filter(Boolean);
  }

  function injectStyle() {
    if (document.getElementById(STYLE_ID)) return;
    const style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent = `
      #${MODAL_ID}{position:fixed;inset:0;z-index:2147483000;background:rgba(18,20,18,.62);display:flex;align-items:center;justify-content:center;padding:10px;box-sizing:border-box}
      #${MODAL_ID}[hidden]{display:none!important}
      .v38-oc-shell{width:min(1080px,100%);height:min(90vh,820px);background:#f8f7f3;border:1px solid rgba(74,63,47,.28);border-radius:18px;box-shadow:0 24px 80px rgba(0,0,0,.34);overflow:hidden;display:flex;flex-direction:column}
      .v38-oc-head{display:flex;align-items:center;gap:9px;padding:8px 11px;border-bottom:1px solid rgba(74,63,47,.16);background:#f8f7f3;min-height:52px}
      .v38-oc-title{font-weight:900;font-size:18px;color:#222;min-width:44px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
      .v38-oc-buckets{display:flex;align-items:center;gap:5px;overflow-x:auto;scrollbar-width:none}.v38-oc-buckets::-webkit-scrollbar{display:none}
      .v38-oc-bucket-btn{appearance:none;border:1px solid rgba(74,63,47,.18);border-radius:999px;background:#fff;color:#5d554c;padding:5px 9px;font:800 10px/1 -apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;cursor:pointer;white-space:nowrap}
      .v38-oc-bucket-btn[aria-pressed="true"]{background:#282722;color:#fff;border-color:#282722}.v38-oc-bucket-btn:disabled{opacity:.35;cursor:default}
      .v38-oc-spacer{flex:1}.v38-oc-close{appearance:none;border:1px solid rgba(74,63,47,.22);border-radius:10px;background:#fffaf3;color:#332f2a;padding:7px 10px;font:inherit;cursor:pointer;font-weight:900;min-width:38px}
      .v38-oc-body{position:relative;flex:1;min-height:0;background:#fff;overflow:hidden}.v38-oc-tv{position:absolute;inset:0}.v38-oc-tv .tradingview-widget-container{position:absolute;inset:0}.v38-oc-chart{position:absolute;inset:0}
      .v38-oc-levels{position:absolute;z-index:5;left:9px;top:8px;right:56px;display:flex;flex-wrap:wrap;gap:5px 9px;pointer-events:none;padding:5px 7px;border-radius:8px;background:rgba(250,249,246,.88);backdrop-filter:blur(4px);box-shadow:0 2px 10px rgba(0,0,0,.08);font-size:9px;font-weight:850;color:#4b4742}
      .v38-oc-legend-item{display:inline-flex;align-items:center;gap:4px}.v38-oc-legend-swatch{display:inline-block;width:13px;height:2px;border-radius:2px;background:currentColor}
      .v38-oc-status{position:absolute;z-index:5;left:9px;right:9px;bottom:8px;padding:6px 8px;border-radius:8px;background:rgba(250,249,246,.9);backdrop-filter:blur(4px);font-size:9px;line-height:1.35;color:#625b53;box-shadow:0 2px 10px rgba(0,0,0,.07);pointer-events:none}
      .v38-oc-unavailable{position:absolute;z-index:6;left:50%;top:50%;transform:translate(-50%,-50%);padding:9px 12px;border-radius:9px;background:rgba(250,249,246,.94);font-size:11px;font-weight:800;color:#6b645d;box-shadow:0 2px 12px rgba(0,0,0,.10)}
      .v38-oc-fallback{width:100%;height:100%;display:block}
      .v38-ticker-link,[data-v38-rs-ticker],[data-v38-ticker],.chip,.tk,.mvr-t{cursor:pointer}
      @media(max-width:700px){#${MODAL_ID}{padding:0}.v38-oc-shell{height:100dvh;width:100%;border-radius:0}.v38-oc-head{padding:7px 8px;gap:6px;min-height:48px}.v38-oc-title{font-size:16px}.v38-oc-bucket-btn{padding:5px 8px;font-size:9px}.v38-oc-levels{left:6px;top:6px;right:44px;font-size:8px;gap:4px 7px}.v38-oc-status{left:6px;right:6px;bottom:6px;font-size:8px}}
    `;
    document.head.appendChild(style);
  }

  function ensureModal() {
    let modal = document.getElementById(MODAL_ID);
    if (modal) return modal;
    injectStyle();
    modal = document.createElement('div');
    modal.id = MODAL_ID;
    modal.hidden = true;
    modal.innerHTML = `
      <div class="v38-oc-shell" role="dialog" aria-modal="true" aria-label="ローソク足とV38 Options水準">
        <div class="v38-oc-head">
          <div class="v38-oc-title">—</div>
          <div class="v38-oc-buckets"></div>
          <div class="v38-oc-spacer"></div>
          <button type="button" class="v38-oc-close" aria-label="閉じる">×</button>
        </div>
        <div class="v38-oc-body">
          <div class="v38-oc-tv"><div class="tradingview-widget-container"><div class="v38-oc-chart"></div></div></div>
          <div class="v38-oc-levels">V38 Options</div>
          <div class="v38-oc-status">ローソク足を読み込み中…</div>
        </div>
      </div>`;
    document.body.appendChild(modal);
    modal.querySelector('.v38-oc-close').addEventListener('click', closeModal);
    modal.addEventListener('click', (event) => {
      if (event.target === modal) closeModal();
    });
    return modal;
  }

  function disposeChart() {
    if (currentObserver) {
      currentObserver.disconnect();
      currentObserver = null;
    }
    if (currentChart && typeof currentChart.remove === 'function') {
      try { currentChart.remove(); } catch (_) {}
    }
    currentChart = null;
  }

  function fallbackCandles(host, candles, levels) {
    host.replaceChildren();
    if (!candles.length) return;

    const width = 760;
    const height = 520;
    const px = 44;
    const py = 26;
    const lows = candles.map((c) => c.low).concat(levels.map((l) => l.value));
    const highs = candles.map((c) => c.high).concat(levels.map((l) => l.value));
    let low = Math.min.apply(null, lows);
    let high = Math.max.apply(null, highs);
    const margin = Math.max((high - low) * 0.06, high * 0.005);
    low -= margin;
    high += margin;
    const x = (index) => px + (width - 2 * px) * (index + 0.5) / candles.length;
    const y = (value) => py + (high - value) / Math.max(1e-9, high - low) * (height - 2 * py);
    const step = (width - 2 * px) / candles.length;
    const bodyWidth = Math.max(1.2, Math.min(8, step * 0.58));

    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('class', 'v38-oc-fallback');
    svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
    svg.setAttribute('preserveAspectRatio', 'none');

    candles.forEach((candle, index) => {
      const xx = x(index);
      const up = candle.close >= candle.open;
      const colour = up ? '#2c9a7b' : '#d9534f';
      const wick = document.createElementNS(svg.namespaceURI, 'line');
      wick.setAttribute('x1', xx.toFixed(1));
      wick.setAttribute('x2', xx.toFixed(1));
      wick.setAttribute('y1', y(candle.high).toFixed(1));
      wick.setAttribute('y2', y(candle.low).toFixed(1));
      wick.setAttribute('stroke', colour);
      wick.setAttribute('stroke-width', '1');
      svg.appendChild(wick);

      const rect = document.createElementNS(svg.namespaceURI, 'rect');
      rect.setAttribute('x', (xx - bodyWidth / 2).toFixed(1));
      rect.setAttribute('y', Math.min(y(candle.open), y(candle.close)).toFixed(1));
      rect.setAttribute('width', bodyWidth.toFixed(1));
      rect.setAttribute('height', Math.max(1, Math.abs(y(candle.open) - y(candle.close))).toFixed(1));
      rect.setAttribute('fill', up ? colour : '#fff');
      rect.setAttribute('stroke', colour);
      rect.setAttribute('stroke-width', '1');
      svg.appendChild(rect);
    });

    levels.forEach((level) => {
      const yy = y(level.value);
      const line = document.createElementNS(svg.namespaceURI, 'line');
      line.setAttribute('x1', String(px));
      line.setAttribute('x2', String(width - px));
      line.setAttribute('y1', yy.toFixed(1));
      line.setAttribute('y2', yy.toFixed(1));
      line.setAttribute('stroke', level.color);
      line.setAttribute('stroke-width', '1.3');
      if (level.style !== 'solid') line.setAttribute('stroke-dasharray', '5 4');
      svg.appendChild(line);

      const text = document.createElementNS(svg.namespaceURI, 'text');
      text.setAttribute('x', String(width - px));
      text.setAttribute('y', (yy - 3).toFixed(1));
      text.setAttribute('fill', level.color);
      text.setAttribute('font-size', '11');
      text.setAttribute('font-weight', '800');
      text.setAttribute('text-anchor', 'end');
      text.textContent = level.label + ' ' + money(level.value);
      svg.appendChild(text);
    });

    host.appendChild(svg);
  }

  function lineStyle(lib, style) {
    if (!lib || !lib.LineStyle) return 0;
    if (style === 'dashed') return lib.LineStyle.Dashed;
    if (style === 'dotted') return lib.LineStyle.Dotted;
    return lib.LineStyle.Solid;
  }

  async function renderCandles(modal, options, ticker, row) {
    disposeChart();
    const host = modal.querySelector('.v38-oc-chart');
    host.replaceChildren();
    const candles = candlesFor(options, ticker);
    const levels = levelsFromRow(row || {});

    if (!candles.length) {
      const unavailable = document.createElement('div');
      unavailable.className = 'v38-oc-unavailable';
      unavailable.textContent = 'ローソク足履歴未取得';
      host.appendChild(unavailable);
      return;
    }

    try {
      const lib = await loadLightweightCharts();
      if (modal.hidden || lastTicker !== ticker) return;
      if (!lib || typeof lib.createChart !== 'function') {
        fallbackCandles(host, candles, levels);
        return;
      }

      const chart = lib.createChart(host, {
        width: host.clientWidth || 760,
        height: host.clientHeight || 520,
        layout: {background: {type: 'solid', color: '#ffffff'}, textColor: '#494640', fontSize: 11},
        grid: {vertLines: {color: '#eceae5'}, horzLines: {color: '#eceae5'}},
        rightPriceScale: {borderColor: '#dedbd4', scaleMargins: {top: 0.08, bottom: 0.08}},
        timeScale: {borderColor: '#dedbd4', rightOffset: 3, barSpacing: 8, minBarSpacing: 3, timeVisible: false},
        handleScroll: {mouseWheel: true, pressedMouseMove: true, horzTouchDrag: true, vertTouchDrag: false},
        handleScale: {axisPressedMouseMove: true, mouseWheel: true, pinch: true}
      });

      const series = chart.addCandlestickSeries({
        upColor: '#2c9a7b',
        downColor: '#d9534f',
        borderUpColor: '#2c9a7b',
        borderDownColor: '#d9534f',
        wickUpColor: '#2c9a7b',
        wickDownColor: '#d9534f',
        priceLineVisible: false
      });
      series.setData(candles);
      levels.forEach((level) => {
        series.createPriceLine({
          price: level.value,
          color: level.color,
          lineWidth: level.key === 'spot' ? 1 : 2,
          lineStyle: lineStyle(lib, level.style),
          axisLabelVisible: true,
          title: level.label
        });
      });
      chart.timeScale().fitContent();
      currentChart = chart;

      if (window.ResizeObserver) {
        currentObserver = new ResizeObserver(() => {
          if (currentChart === chart) {
            try {
              chart.applyOptions({width: host.clientWidth, height: host.clientHeight});
            } catch (_) {}
          }
        });
        currentObserver.observe(host);
      }
    } catch (_) {
      disposeChart();
      if (!modal.hidden && lastTicker === ticker) {
        fallbackCandles(host, candles, levels);
      }
    }
  }

  function renderLegend(modal, row) {
    const host = modal.querySelector('.v38-oc-levels');
    host.replaceChildren();
    const label = document.createElement('span');
    label.textContent = 'V38 Options';
    host.appendChild(label);

    levelsFromRow(row || {}).forEach((level) => {
      const item = document.createElement('span');
      item.className = 'v38-oc-legend-item';
      item.style.color = level.color;
      const swatch = document.createElement('i');
      swatch.className = 'v38-oc-legend-swatch';
      const text = document.createElement('span');
      text.textContent = level.label + ' ' + money(level.value);
      item.appendChild(swatch);
      item.appendChild(text);
      host.appendChild(item);
    });
  }

  function renderStatus(modal, found) {
    const host = modal.querySelector('.v38-oc-status');
    if (!found || !found.row) {
      host.textContent = '現行チェーン未取得';
      return;
    }
    const row = found.row;
    const parts = [found.historical ? '前回実測' : String(found.bucket || '0-45') + ' DTE'];
    const expectedMove = finite(row.expected_move_pct);
    if (expectedMove !== null) parts.push('Expected Move ' + pct(expectedMove));
    if (row.expected_move_expiry) parts.push('EM expiry ' + String(row.expected_move_expiry));
    if (row.quality) parts.push(String(row.quality));
    parts.push('推測方向・信頼度は表示しません');
    host.textContent = parts.join(' • ');
  }

  function renderBucketButtons(modal, options, ticker, selected) {
    const host = modal.querySelector('.v38-oc-buckets');
    host.replaceChildren();
    const available = new Set(availableBuckets(options, ticker));

    BUCKETS.forEach((bucket) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'v38-oc-bucket-btn';
      button.textContent = bucket;
      button.disabled = !available.has(bucket);
      button.setAttribute('aria-pressed', bucket === selected ? 'true' : 'false');
      button.addEventListener('click', () => {
        if (button.disabled) return;
        const found = resolveRow(options, ticker, bucket);
        renderBucketButtons(modal, options, ticker, bucket);
        renderLegend(modal, found && found.row);
        renderStatus(modal, found);
        void renderCandles(modal, options, ticker, found && found.row);
      });
      host.appendChild(button);
    });
  }

  function openTicker(ticker) {
    ticker = cleanTicker(ticker);
    if (!ticker) return;

    const modal = ensureModal();
    lastTicker = ticker;
    modal.hidden = false;
    modal.querySelector('.v38-oc-title').textContent = ticker;
    modal.querySelector('.v38-oc-levels').textContent = 'V38 Options';
    modal.querySelector('.v38-oc-status').textContent = 'ローソク足・Options水準を読み込み中…';
    modal.querySelector('.v38-oc-chart').replaceChildren();

    loadOptions().then((options) => {
      if (modal.hidden || lastTicker !== ticker) return;
      const found = resolveRow(options, ticker, null);
      const selected = found && !found.historical && BUCKETS.includes(found.bucket)
        ? found.bucket : null;
      renderBucketButtons(modal, options, ticker, selected);
      renderLegend(modal, found && found.row);
      renderStatus(modal, found);
      void renderCandles(modal, options, ticker, found && found.row);
    }).catch(() => {
      if (!modal.hidden && lastTicker === ticker) {
        modal.querySelector('.v38-oc-status').textContent = '現行チェーン未取得';
      }
    });
  }

  function closeModal() {
    const modal = document.getElementById(MODAL_ID);
    if (modal) modal.hidden = true;
    disposeChart();
    lastTicker = null;
  }

  function tickerFromTradingViewHref(link) {
    if (!link || !link.href) return null;
    try {
      const url = new URL(link.href, window.location.href);
      if (!/tradingview\.com$/i.test(url.hostname) && !/\.tradingview\.com$/i.test(url.hostname)) return null;
      return cleanTicker(url.searchParams.get('symbol'));
    } catch (_) {
      return null;
    }
  }

  function tickerFromGenericRow(item) {
    if (!item) return null;
    const name = item.querySelector('.rsx-name');
    if (name) {
      const key = String(name.querySelector('small') && name.querySelector('small').textContent || '').trim().toLowerCase();
      const value = cleanTicker(name.querySelector('b') && name.querySelector('b').textContent);
      if ((key === 'ticker' || key === 'symbol') && value) return value;
      const link = name.querySelector('.v38-generic-ticker');
      const linked = cleanTicker(link && link.textContent);
      if (linked) return linked;
    }
    const spans = Array.from(item.querySelectorAll('.rsx-sub .rsx-nums'));
    for (const span of spans) {
      const match = String(span.textContent || '').trim().match(/^(?:ticker|symbol)\s+([A-Z][A-Z0-9.\-]{0,9})$/i);
      if (match) return cleanTicker(match[1]);
    }
    const text = String(item.textContent || '').toUpperCase();
    const explicit = text.match(/(?:TICKER|SYMBOL)\s+([A-Z][A-Z0-9.\-]{0,9})/);
    return explicit ? cleanTicker(explicit[1]) : null;
  }

  function tickerFromElement(target) {
    if (!(target instanceof Element)) return null;
    const explicitData = target.closest('[data-v38-ticker],[data-v38-rs-ticker],[data-ticker],[data-symbol]');
    if (explicitData) {
      const value = explicitData.getAttribute('data-v38-ticker')
        || explicitData.getAttribute('data-v38-rs-ticker')
        || explicitData.getAttribute('data-ticker')
        || explicitData.getAttribute('data-symbol');
      const ticker = cleanTicker(value);
      if (ticker) return ticker;
    }
    const link = target.closest('a');
    if (link) {
      if (link.classList.contains('v38-ticker-link')) {
        const ticker = cleanTicker(link.textContent);
        if (ticker) return ticker;
      }
      const ticker = tickerFromTradingViewHref(link);
      if (ticker) return ticker;
    }
    const genericTicker = tickerFromGenericRow(target.closest('.rsx-item'));
    if (genericTicker) return genericTicker;
    const atom = target.closest('.mvr-t,.tk,.chip');
    if (atom) return cleanTicker(atom.textContent);
    return null;
  }

  function isTickerActionTarget(target) {
    if (!(target instanceof Element)) return false;
    return Boolean(target.closest('a.v38-ticker-link,a[href*="tradingview.com/chart"],[data-v38-ticker],[data-v38-rs-ticker],[data-ticker],[data-symbol],.rsx-item,.mvr-t,.chip,.tk'));
  }

  document.addEventListener('click', (event) => {
    if (!isTickerActionTarget(event.target)) return;
    const ticker = tickerFromElement(event.target);
    if (!ticker) return;
    event.preventDefault();
    event.stopPropagation();
    openTicker(ticker);
  }, true);

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') closeModal();
  });

  window.V38OpenTickerChart = openTicker;
})();
