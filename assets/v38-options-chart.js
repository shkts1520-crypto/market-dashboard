(function () {
  'use strict';

  const OPTIONS_URL = 'data/options/index.json';
  const STYLE_ID = 'v38-options-chart-style';
  const UI_STYLE_ID = 'v38-options-ui-polish-style';
  const MODAL_ID = 'v38-options-chart-modal';
  const TICKER_RE = /^[A-Z][A-Z0-9.\-]{0,9}$/;
  const BUCKETS = ['0-45', '22-45', '7-21', '0-6'];
  let optionsPromise = null;
  let lastTicker = null;
  let activeBucket = null;
  let activeOptions = null;

  function finite(value) {
    if (value === null || value === undefined || value === '') return null;
    const n = Number(value);
    return Number.isFinite(n) ? n : null;
  }

  function firstFinite(row, keys) {
    if (!row) return null;
    for (const key of keys) {
      const n = finite(row[key]);
      if (n !== null) return n;
    }
    return null;
  }

  function money(value) {
    const n = finite(value);
    if (n === null) return '—';
    if (Math.abs(n) >= 1000) return n.toLocaleString(undefined, {maximumFractionDigits: 2});
    return n.toFixed(2);
  }

  function pct(value) {
    const n = finite(value);
    return n === null ? '—' : (n * 100).toFixed(1) + '%';
  }

  function cleanTicker(value) {
    const ticker = String(value || '').trim().toUpperCase();
    return TICKER_RE.test(ticker) ? ticker : null;
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

  function rowsForBucket(options, bucket) {
    const buckets = options && options.buckets && typeof options.buckets === 'object' ? options.buckets : {};
    return Array.isArray(buckets[bucket]) ? buckets[bucket] : [];
  }

  function rowForBucket(options, ticker, bucket) {
    return rowsForBucket(options, bucket).find((item) => item && String(item.ticker || '').toUpperCase() === ticker) || null;
  }

  function availableBuckets(options, ticker) {
    return BUCKETS.filter((bucket) => rowForBucket(options, ticker, bucket));
  }

  function fallbackRow(options, ticker) {
    const rows = options && Array.isArray(options.rows) ? options.rows : [];
    const row = rows.find((item) => item && String(item.ticker || '').toUpperCase() === ticker);
    if (row) return {bucket: String(row.bucket || '0-45'), row: row, historical: false};

    const history = options && options.history && typeof options.history === 'object' ? options.history[ticker] : null;
    if (Array.isArray(history) && history.length) {
      const observed = history.slice().reverse().find((item) => item && typeof item === 'object');
      if (observed) {
        return {
          bucket: 'history',
          row: Object.assign({ticker: ticker}, observed),
          historical: true
        };
      }
    }
    return null;
  }

  function resolveRow(options, ticker, bucket) {
    if (!options || !ticker) return null;
    if (bucket && BUCKETS.includes(bucket)) {
      const row = rowForBucket(options, ticker, bucket);
      if (row) return {bucket: bucket, row: row, historical: false};
    }
    const buckets = availableBuckets(options, ticker);
    if (buckets.length) {
      const selected = buckets[0];
      return {bucket: selected, row: rowForBucket(options, ticker, selected), historical: false};
    }
    return fallbackRow(options, ticker);
  }

  function levelsFromRow(row) {
    const spot = firstFinite(row, ['spot', 'underlying_price', 'underlying']);
    const expectedMove = firstFinite(row, ['expected_move', 'expected_move_abs', 'em_abs']);
    const expectedPct = firstFinite(row, ['expected_move_pct', 'em_pct']);
    const move = expectedMove !== null ? expectedMove : (spot !== null && expectedPct !== null ? spot * expectedPct : null);
    const upperDirect = firstFinite(row, ['expected_upper', 'expected_move_upper', 'em_upper']);
    const lowerDirect = firstFinite(row, ['expected_lower', 'expected_move_lower', 'em_lower']);
    const upper = upperDirect !== null ? upperDirect : (spot !== null && move !== null ? spot + move : null);
    const lower = lowerDirect !== null ? lowerDirect : (spot !== null && move !== null ? Math.max(0, spot - move) : null);
    return [
      {key: 'call', label: 'Call Wall', value: firstFinite(row, ['call_wall', 'call_wall_price']), cls: 'v38-oc-call'},
      {key: 'upper', label: 'Expected Upper', value: upper, cls: 'v38-oc-range'},
      {key: 'spot', label: 'Spot', value: spot, cls: 'v38-oc-spot'},
      {key: 'flip', label: 'Gamma Flip', value: firstFinite(row, ['gamma_flip', 'gamma_flip_price']), cls: 'v38-oc-flip'},
      {key: 'lower', label: 'Expected Lower', value: lower, cls: 'v38-oc-range'},
      {key: 'put', label: 'Put Wall', value: firstFinite(row, ['put_wall', 'put_wall_price']), cls: 'v38-oc-put'}
    ].filter((item) => item.value !== null);
  }

  function injectStyle() {
    if (document.getElementById(STYLE_ID)) return;
    const style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent = `
      #${MODAL_ID}{position:fixed;inset:0;z-index:2147483000;background:rgba(18,20,18,.62);display:flex;align-items:center;justify-content:center;padding:10px;box-sizing:border-box}
      #${MODAL_ID}[hidden]{display:none!important}
      .v38-oc-shell{width:min(1240px,100%);height:min(90vh,900px);background:#111;border:1px solid rgba(74,63,47,.28);border-radius:18px;box-shadow:0 24px 80px rgba(0,0,0,.34);overflow:hidden;display:flex;flex-direction:column}
      .v38-oc-head{display:flex;align-items:center;gap:10px;padding:9px 12px;border-bottom:1px solid rgba(74,63,47,.18);background:rgba(255,252,247,.97);min-height:52px}
      .v38-oc-title{font-weight:900;font-size:18px;color:#222;min-width:44px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
      .v38-oc-sub{font-size:11px;color:#6a6259;white-space:nowrap}
      .v38-oc-buckets{display:flex;align-items:center;gap:5px;overflow-x:auto;scrollbar-width:none;margin-left:4px}.v38-oc-buckets::-webkit-scrollbar{display:none}
      .v38-oc-bucket-btn{appearance:none;border:1px solid rgba(74,63,47,.18);border-radius:999px;background:#fff;color:#5d554c;padding:5px 9px;font:700 10px/1 -apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;cursor:pointer;white-space:nowrap}
      .v38-oc-bucket-btn[aria-pressed="true"]{background:#282722;color:#fff;border-color:#282722}
      .v38-oc-bucket-btn:disabled{opacity:.35;cursor:default}
      .v38-oc-spacer{flex:1}
      .v38-oc-close{appearance:none;border:1px solid rgba(74,63,47,.22);border-radius:10px;background:#fffaf3;color:#332f2a;padding:7px 10px;font:inherit;cursor:pointer;font-weight:900;min-width:38px}
      .v38-oc-body{position:relative;flex:1;min-height:0;background:#fff;overflow:hidden}
      .v38-oc-tv{position:absolute;inset:0;z-index:1}
      .v38-oc-tv .tradingview-widget-container,.v38-oc-tv .tradingview-widget-container__widget{width:100%;height:100%}
      .v38-oc-overlay{position:absolute;inset:0;z-index:4;pointer-events:none;overflow:hidden}
      .v38-oc-legend{position:absolute;left:12px;top:10px;display:flex;flex-wrap:wrap;gap:5px 10px;max-width:calc(100% - 120px);padding:5px 7px;border-radius:8px;background:rgba(255,255,255,.84);backdrop-filter:blur(4px);font-size:10px;font-weight:800;color:#45413b;box-shadow:0 2px 10px rgba(0,0,0,.09)}
      .v38-oc-legend-item{display:inline-flex;align-items:center;gap:4px}.v38-oc-legend-swatch{width:13px;height:2px;border-radius:2px;background:currentColor;display:inline-block}
      .v38-oc-line{position:absolute;left:0;right:0;height:0;border-top:2px solid currentColor;opacity:.92}
      .v38-oc-line.v38-oc-spot{border-top-style:dashed;border-top-width:1px;opacity:.75}
      .v38-oc-price{position:absolute;right:6px;transform:translateY(-50%);display:flex;align-items:center;gap:6px;border-radius:7px;padding:3px 6px;background:rgba(255,255,255,.94);box-shadow:0 1px 6px rgba(0,0,0,.12);font:800 10px/1.15 ui-monospace,SFMono-Regular,Menlo,monospace;white-space:nowrap}
      .v38-oc-price strong{font-weight:900}.v38-oc-price span{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;font-weight:800;opacity:.78}
      .v38-oc-call{color:#b63d34}.v38-oc-put{color:#23724b}.v38-oc-flip{color:#9b6c0d}.v38-oc-range{color:#2f64a2}.v38-oc-spot{color:#373737}
      .v38-oc-status{position:absolute;left:12px;bottom:10px;max-width:min(620px,calc(100% - 24px));padding:5px 8px;border-radius:8px;background:rgba(255,255,255,.88);backdrop-filter:blur(4px);font-size:10px;line-height:1.35;color:#625b53;box-shadow:0 2px 10px rgba(0,0,0,.08)}
      .v38-oc-unavailable{position:absolute;left:12px;top:12px;padding:7px 9px;border-radius:8px;background:rgba(255,255,255,.92);font-size:11px;font-weight:800;color:#6b645d;box-shadow:0 2px 10px rgba(0,0,0,.08)}
      .v38-ticker-link,[data-v38-rs-ticker],[data-v38-ticker],.chip,.tk,.mvr-t{cursor:pointer}
      @media(max-width:700px){#${MODAL_ID}{padding:0}.v38-oc-shell{height:100dvh;width:100%;border-radius:0}.v38-oc-head{padding:7px 8px;gap:6px;min-height:48px}.v38-oc-title{font-size:16px}.v38-oc-sub{display:none}.v38-oc-bucket-btn{padding:5px 8px;font-size:9px}.v38-oc-legend{left:7px;top:7px;max-width:calc(100% - 82px);font-size:9px;gap:4px 7px}.v38-oc-price{right:4px;font-size:9px;padding:2px 4px}.v38-oc-price span{display:none}.v38-oc-status{left:7px;bottom:7px;font-size:9px;max-width:calc(100% - 14px)}}
    `;
    document.head.appendChild(style);
  }

  function injectUiPolishStyle() {
    if (document.getElementById(UI_STYLE_ID)) return;
    const style = document.createElement('style');
    style.id = UI_STYLE_ID;
    style.textContent = `
      #t-market .card.v38-ui-focus{padding-top:13px;padding-bottom:13px}
      #t-market .card.v38-ui-focus>.hdr,#t-market .card.v38-ui-focus .hdr{margin-bottom:8px;padding-bottom:6px;border-bottom:1px solid rgba(27,29,28,.07)}
      #t-market .card.v38-ui-focus h2{font-weight:850;letter-spacing:-.015em}
      #t-market .card.v38-ui-focus .big,#t-market .card.v38-ui-focus .pbig,#t-market .card.v38-ui-focus .mbval,#t-market .card.v38-ui-focus .reg-v,#t-market .card.v38-ui-focus .chd-now b{font-weight:900;font-variant-numeric:tabular-nums;letter-spacing:-.02em}
      #t-market .card.v38-ui-focus .spark{margin-top:7px;height:38px}
      #t-market .card.v38-ui-focus .mut,#t-market .card.v38-ui-focus small{line-height:1.45}
      @media(max-width:620px){#t-market .card.v38-ui-focus{padding-top:11px;padding-bottom:11px}#t-market .card.v38-ui-focus>.hdr,#t-market .card.v38-ui-focus .hdr{margin-bottom:6px}}
    `;
    document.head.appendChild(style);
  }

  function normalizeFDecimals() {
    const section = document.getElementById('t-market');
    if (!section || !document.createTreeWalker) return;
    const walker = document.createTreeWalker(section, NodeFilter.SHOW_TEXT);
    const nodes = [];
    let node;
    while ((node = walker.nextNode())) nodes.push(node);
    nodes.forEach((textNode) => {
      const parent = textNode.parentElement;
      if (!parent || parent.closest('script,style')) return;
      const original = textNode.nodeValue || '';
      const replaced = original.replace(/\b(F[123])\s+(0(?:\.\d+)?|1(?:\.0+)?)\b(?!\s*%)/g, (all, key, raw) => {
        const n = Number(raw);
        if (!Number.isFinite(n) || n < 0 || n > 1) return all;
        return key + ' ' + Math.round(n * 100) + '%';
      });
      if (replaced !== original) textNode.nodeValue = replaced;
    });
  }

  function applyUiPolish() {
    injectUiPolishStyle();
    const section = document.getElementById('t-market');
    if (!section) return;
    const focusWords = ['今日のマーケット', '前回からの変化', 'MC57'];
    section.querySelectorAll('.card').forEach((card) => {
      const heading = card.querySelector('h2');
      const text = (heading ? heading.textContent : card.textContent || '').trim();
      if (focusWords.some((word) => text.includes(word))) card.classList.add('v38-ui-focus');
    });
    normalizeFDecimals();
    document.body.dataset.v38UiHotfix = 'ready';
  }

  function ensureModal() {
    let modal = document.getElementById(MODAL_ID);
    if (modal) return modal;
    injectStyle();
    modal = document.createElement('div');
    modal.id = MODAL_ID;
    modal.hidden = true;
    modal.innerHTML = `
      <div class="v38-oc-shell" role="dialog" aria-modal="true" aria-label="TradingView chart with V38 options levels">
        <div class="v38-oc-head">
          <div class="v38-oc-title">—</div>
          <div class="v38-oc-sub">TradingView • V38 Options</div>
          <div class="v38-oc-buckets" aria-label="Options DTE bucket"></div>
          <div class="v38-oc-spacer"></div>
          <button class="v38-oc-close" type="button" aria-label="閉じる">×</button>
        </div>
        <div class="v38-oc-body">
          <div class="v38-oc-tv"></div>
          <div class="v38-oc-overlay v38-oc-levels" aria-live="polite"></div>
        </div>
      </div>`;
    document.body.appendChild(modal);
    modal.querySelector('.v38-oc-close').addEventListener('click', closeModal);
    modal.addEventListener('click', (event) => {
      if (event.target === modal) closeModal();
    });
    return modal;
  }

  function closeModal() {
    const modal = document.getElementById(MODAL_ID);
    if (!modal) return;
    modal.hidden = true;
    const host = modal.querySelector('.v38-oc-tv');
    if (host) host.replaceChildren();
    lastTicker = null;
    activeBucket = null;
    activeOptions = null;
  }

  function renderTradingView(host, ticker) {
    host.replaceChildren();
    const wrap = document.createElement('div');
    wrap.className = 'tradingview-widget-container';
    const widget = document.createElement('div');
    widget.className = 'tradingview-widget-container__widget';
    wrap.appendChild(widget);
    const script = document.createElement('script');
    script.type = 'text/javascript';
    script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js';
    script.async = true;
    script.text = JSON.stringify({
      autosize: true,
      symbol: ticker,
      interval: 'D',
      timezone: 'America/New_York',
      theme: 'light',
      style: '1',
      locale: 'ja',
      allow_symbol_change: true,
      withdateranges: true,
      hide_side_toolbar: false,
      calendar: false,
      support_host: 'https://www.tradingview.com'
    });
    wrap.appendChild(script);
    host.appendChild(wrap);
  }

  function renderBucketButtons(modal, options, ticker, selectedBucket) {
    const host = modal.querySelector('.v38-oc-buckets');
    host.replaceChildren();
    const available = availableBuckets(options, ticker);
    BUCKETS.forEach((bucket) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'v38-oc-bucket-btn';
      button.textContent = bucket;
      button.disabled = !available.includes(bucket);
      button.setAttribute('aria-pressed', selectedBucket === bucket ? 'true' : 'false');
      button.addEventListener('click', () => {
        if (button.disabled || !lastTicker || !activeOptions) return;
        activeBucket = bucket;
        renderBucketButtons(modal, activeOptions, lastTicker, bucket);
        renderOverlay(modal.querySelector('.v38-oc-levels'), activeOptions, lastTicker, bucket);
      });
      host.appendChild(button);
    });
  }

  function renderOverlay(host, options, ticker, bucket) {
    host.replaceChildren();
    const found = resolveRow(options, ticker, bucket);
    if (!found) {
      const empty = document.createElement('div');
      empty.className = 'v38-oc-unavailable';
      empty.textContent = 'V38 Options • この銘柄は現在のOptions取得対象外、またはチェーン取得不能です。';
      host.appendChild(empty);
      return;
    }

    const levels = levelsFromRow(found.row);
    const legend = document.createElement('div');
    legend.className = 'v38-oc-legend';
    const legendTitle = document.createElement('span');
    legendTitle.className = 'v38-oc-legend-item';
    legendTitle.textContent = 'V38 Options';
    legend.appendChild(legendTitle);
    levels.forEach((item) => {
      const entry = document.createElement('span');
      entry.className = 'v38-oc-legend-item ' + item.cls;
      const swatch = document.createElement('i');
      swatch.className = 'v38-oc-legend-swatch';
      const label = document.createElement('span');
      label.textContent = item.label;
      entry.append(swatch, label);
      legend.appendChild(entry);
    });
    host.appendChild(legend);

    if (!levels.length) {
      const empty = document.createElement('div');
      empty.className = 'v38-oc-unavailable';
      empty.textContent = 'V38 Options • 水平ライン用の価格データがありません。';
      host.appendChild(empty);
      return;
    }

    const values = levels.map((item) => item.value).filter((value) => Number.isFinite(value));
    let min = Math.min.apply(null, values);
    let max = Math.max.apply(null, values);
    if (!(max > min)) {
      min -= 1;
      max += 1;
    }
    const padding = (max - min) * 0.12;
    min -= padding;
    max += padding;

    levels.forEach((item) => {
      const ratio = (item.value - min) / (max - min);
      const top = 91 - ratio * 78;
      const line = document.createElement('div');
      line.className = 'v38-oc-line ' + item.cls;
      line.style.top = top.toFixed(2) + '%';
      const price = document.createElement('div');
      price.className = 'v38-oc-price ' + item.cls;
      price.style.top = top.toFixed(2) + '%';
      const label = document.createElement('span');
      label.textContent = item.label;
      const value = document.createElement('strong');
      value.textContent = money(item.value);
      price.append(label, value);
      host.append(line, price);
    });

    const status = document.createElement('div');
    status.className = 'v38-oc-status';
    const expiry = found.row.expected_move_expiry ? ' • EM expiry ' + found.row.expected_move_expiry : '';
    const expectedPct = firstFinite(found.row, ['expected_move_pct', 'em_pct']);
    const expectedText = expectedPct !== null ? ' • Expected Move ' + pct(expectedPct) : '';
    const quality = found.row.quality ? ' • ' + found.row.quality : '';
    const historyText = found.historical
      ? ' • 前回実測 • 現行チェーン未取得のため前回実測値を表示'
      : ' • ' + found.bucket + ' DTE';
    status.textContent = 'Options Wall Overlay' + historyText + expectedText + expiry + quality + ' • 推測方向・信頼度は表示しません。';
    host.appendChild(status);
  }

  function openTicker(ticker) {
    ticker = cleanTicker(ticker);
    if (!ticker) return;
    const modal = ensureModal();
    lastTicker = ticker;
    activeBucket = null;
    activeOptions = null;
    modal.hidden = false;
    modal.querySelector('.v38-oc-title').textContent = ticker;
    renderTradingView(modal.querySelector('.v38-oc-tv'), ticker);
    const overlay = modal.querySelector('.v38-oc-levels');
    overlay.textContent = 'V38 Options loading…';
    loadOptions().then((options) => {
      if (modal.hidden || lastTicker !== ticker) return;
      activeOptions = options;
      const found = resolveRow(options, ticker, null);
      activeBucket = found && !found.historical && BUCKETS.includes(found.bucket) ? found.bucket : null;
      renderBucketButtons(modal, options, ticker, activeBucket);
      renderOverlay(overlay, options, ticker, activeBucket);
    });
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

    const generic = target.closest('.rsx-item');
    const genericTicker = tickerFromGenericRow(generic);
    if (genericTicker) return genericTicker;

    const atom = target.closest('.mvr-t,.tk,.chip');
    if (atom) {
      const ticker = cleanTicker(atom.textContent);
      if (ticker) return ticker;
    }

    const item = target.closest('.slrow,.l');
    if (item) {
      const text = String(item.textContent || '').toUpperCase();
      const explicit = text.match(/(?:TICKER|SYMBOL)\s+([A-Z][A-Z0-9.\-]{0,9})/);
      if (explicit) return cleanTicker(explicit[1]);
    }
    return null;
  }

  function isTickerActionTarget(target) {
    if (!(target instanceof Element)) return false;
    return Boolean(target.closest(
      'a.v38-ticker-link,a[href*="tradingview.com/chart"],[data-v38-ticker],[data-v38-rs-ticker],[data-ticker],[data-symbol],.rsx-item,.mvr-t,.chip,.tk'
    ));
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

  function initUiPolish() {
    applyUiPolish();
    window.setTimeout(applyUiPolish, 180);
    window.setTimeout(applyUiPolish, 700);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initUiPolish, {once: true});
  else initUiPolish();

  window.V38OpenTickerChart = openTicker;
})();
