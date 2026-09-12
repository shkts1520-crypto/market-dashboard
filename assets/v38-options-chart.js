(function () {
  'use strict';

  const OPTIONS_URL = 'data/options/index.json';
  const STYLE_ID = 'v38-options-chart-style';
  const MODAL_ID = 'v38-options-chart-modal';
  const TICKER_RE = /^[A-Z][A-Z0-9.\-]{0,9}$/;
  let optionsPromise = null;
  let lastTicker = null;

  function finite(value) {
    const n = Number(value);
    return Number.isFinite(n) ? n : null;
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

  function findTickerRow(options, ticker) {
    if (!options || !ticker) return null;
    const buckets = options.buckets && typeof options.buckets === 'object' ? options.buckets : {};
    const order = ['0-45', '22-45', '7-21', '0-6'];
    for (const bucket of order) {
      const rows = Array.isArray(buckets[bucket]) ? buckets[bucket] : [];
      const row = rows.find((item) => item && String(item.ticker || '').toUpperCase() === ticker);
      if (row) return {bucket: bucket, row: row, historical: false};
    }
    const rows = Array.isArray(options.rows) ? options.rows : [];
    const row = rows.find((item) => item && String(item.ticker || '').toUpperCase() === ticker);
    if (row) return {bucket: String(row.bucket || '0-45'), row: row, historical: false};

    // A transient current-chain failure must not erase an already measured wall.
    // Historical values remain explicitly labelled as previous observations and
    // are never presented as current-session positioning.
    const history = options.history && typeof options.history === 'object' ? options.history[ticker] : null;
    if (Array.isArray(history) && history.length) {
      const observed = history.slice().reverse().find((item) => item && typeof item === 'object');
      if (observed) {
        return {
          bucket: 'history',
          historical: true,
          row: Object.assign({ticker: ticker}, observed)
        };
      }
    }
    return null;
  }

  function injectStyle() {
    if (document.getElementById(STYLE_ID)) return;
    const style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent = `
      #${MODAL_ID}{position:fixed;inset:0;z-index:2147483000;background:rgba(18,20,18,.58);display:flex;align-items:center;justify-content:center;padding:12px;box-sizing:border-box}
      #${MODAL_ID}[hidden]{display:none!important}
      .v38-oc-shell{width:min(1180px,100%);height:min(86vh,860px);background:#f7f1e8;border:1px solid rgba(74,63,47,.28);border-radius:18px;box-shadow:0 24px 80px rgba(0,0,0,.28);overflow:hidden;display:flex;flex-direction:column}
      .v38-oc-head{display:flex;align-items:center;gap:10px;padding:11px 14px;border-bottom:1px solid rgba(74,63,47,.18);background:rgba(255,252,247,.94)}
      .v38-oc-title{font-weight:800;font-size:18px;color:#222;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
      .v38-oc-sub{font-size:12px;color:#6a6259;white-space:nowrap}
      .v38-oc-spacer{flex:1}
      .v38-oc-close{appearance:none;border:1px solid rgba(74,63,47,.22);border-radius:10px;background:#fffaf3;color:#332f2a;padding:7px 10px;font:inherit;cursor:pointer;font-weight:800;min-width:38px}
      .v38-oc-body{position:relative;flex:1;min-height:0;background:#fff}
      .v38-oc-tv{position:absolute;inset:0}
      .v38-oc-tv .tradingview-widget-container,.v38-oc-tv .tradingview-widget-container__widget{width:100%;height:100%}
      .v38-oc-levels{position:absolute;left:14px;top:14px;z-index:5;width:min(350px,calc(100% - 28px));background:rgba(255,252,247,.95);backdrop-filter:blur(5px);border:1px solid rgba(74,63,47,.20);border-radius:13px;padding:10px;box-shadow:0 8px 24px rgba(0,0,0,.12);pointer-events:auto}
      .v38-oc-level-head{display:flex;align-items:center;gap:8px;margin-bottom:7px;flex-wrap:wrap}
      .v38-oc-level-head b{font-size:13px;color:#27231f}
      .v38-oc-bucket{font-size:11px;color:#6a6259;border:1px solid rgba(74,63,47,.18);border-radius:999px;padding:2px 7px;background:#fff}
      .v38-oc-history{border-color:#b88a38;color:#765623;background:#fff7e8}
      .v38-oc-level-grid{display:grid;grid-template-columns:1fr auto;column-gap:12px;row-gap:5px;font-size:12px}
      .v38-oc-level-grid span:nth-child(odd){color:#5d554c}.v38-oc-level-grid b{color:#26211c;text-align:right}
      .v38-oc-call{color:#a23d35!important}.v38-oc-put{color:#28704b!important}.v38-oc-flip{color:#9a6c13!important}.v38-oc-range{color:#315f96!important}
      .v38-oc-note{font-size:11px;color:#746c63;margin-top:7px;line-height:1.4}
      .v38-oc-unavailable{font-size:12px;color:#746c63;line-height:1.45}
      .v38-ticker-link,[data-v38-rs-ticker],[data-v38-ticker],.chip,.tk{cursor:pointer}
      @media(max-width:700px){#${MODAL_ID}{padding:0}.v38-oc-shell{height:100dvh;width:100%;border-radius:0}.v38-oc-head{padding:9px 10px}.v38-oc-title{font-size:16px}.v38-oc-sub{display:none}.v38-oc-levels{left:8px;top:8px;width:calc(100% - 16px);padding:8px}.v38-oc-level-grid{font-size:11px}.v38-oc-body{min-height:0}}
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
      <div class="v38-oc-shell" role="dialog" aria-modal="true" aria-label="TradingView chart">
        <div class="v38-oc-head">
          <div class="v38-oc-title">—</div>
          <div class="v38-oc-sub">TradingView • V38 Options positioning</div>
          <div class="v38-oc-spacer"></div>
          <button class="v38-oc-close" type="button" aria-label="閉じる">×</button>
        </div>
        <div class="v38-oc-body">
          <div class="v38-oc-tv"></div>
          <div class="v38-oc-levels"></div>
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

  function renderLevels(host, options, ticker) {
    host.replaceChildren();
    const found = findTickerRow(options, ticker);
    if (!found) {
      const head = document.createElement('div');
      head.className = 'v38-oc-level-head';
      head.innerHTML = '<b>V38 Options Levels</b><span class="v38-oc-bucket">未取得</span>';
      host.appendChild(head);
      const note = document.createElement('div');
      note.className = 'v38-oc-unavailable';
      note.textContent = 'この銘柄は現在のOptions取得対象外、またはチェーン取得不能です。TradingViewチャートはこの画面内に表示します。';
      host.appendChild(note);
      return;
    }
    const row = found.row;
    const spot = finite(row.spot);
    const move = finite(row.expected_move) !== null
      ? finite(row.expected_move)
      : (spot !== null && finite(row.expected_move_pct) !== null ? spot * finite(row.expected_move_pct) : null);
    const lower = spot !== null && move !== null ? Math.max(0, spot - move) : null;
    const upper = spot !== null && move !== null ? spot + move : null;
    const head = document.createElement('div');
    head.className = 'v38-oc-level-head';
    const title = document.createElement('b');
    title.textContent = 'V38 Options Levels';
    const bucket = document.createElement('span');
    bucket.className = 'v38-oc-bucket' + (found.historical ? ' v38-oc-history' : '');
    bucket.textContent = found.historical
      ? '前回実測 ' + String(row.date || '日付不明')
      : found.bucket + ' DTE';
    head.append(title, bucket);
    host.appendChild(head);
    const grid = document.createElement('div');
    grid.className = 'v38-oc-level-grid';
    const entries = [
      ['Call Wall', row.call_wall, 'v38-oc-call'],
      ['Expected Upper', upper, 'v38-oc-range'],
      ['Spot', spot, ''],
      ['Gamma Flip', row.gamma_flip, 'v38-oc-flip'],
      ['Expected Lower', lower, 'v38-oc-range'],
      ['Put Wall', row.put_wall, 'v38-oc-put']
    ];
    entries.forEach((entry) => {
      const label = document.createElement('span');
      label.textContent = entry[0];
      if (entry[2]) label.className = entry[2];
      const value = document.createElement('b');
      value.textContent = money(entry[1]);
      if (entry[2]) value.className = entry[2];
      grid.append(label, value);
    });
    host.appendChild(grid);
    const note = document.createElement('div');
    note.className = 'v38-oc-note';
    const expiry = row.expected_move_expiry ? ' • EM expiry ' + row.expected_move_expiry : '';
    const quality = row.quality ? ' • ' + row.quality : '';
    const source = options && options.risk_free_rate_source ? ' • rate ' + options.risk_free_rate_source : '';
    const historical = found.historical ? ' • 現行チェーン未取得のため前回実測値を表示' : '';
    note.textContent = 'Expected Range ' + money(lower) + ' – ' + money(upper) + ' (' + pct(row.expected_move_pct) + ')' + expiry + quality + source + historical + '。Direction/Confidenceは推測表示しません。';
    host.appendChild(note);
  }

  function openTicker(ticker) {
    ticker = cleanTicker(ticker);
    if (!ticker) return;
    const modal = ensureModal();
    lastTicker = ticker;
    modal.hidden = false;
    modal.querySelector('.v38-oc-title').textContent = ticker;
    renderTradingView(modal.querySelector('.v38-oc-tv'), ticker);
    const levelHost = modal.querySelector('.v38-oc-levels');
    levelHost.textContent = 'Options levels loading…';
    loadOptions().then((options) => {
      if (!modal.hidden && lastTicker === ticker) renderLevels(levelHost, options, ticker);
    });
  }

  function tickerFromTradingViewHref(link) {
    if (!link || !link.href) return null;
    try {
      const url = new URL(link.href, window.location.href);
      if (!/tradingview\.com$/i.test(url.hostname) && !/\.tradingview\.com$/i.test(url.hostname)) return null;
      const symbol = url.searchParams.get('symbol');
      return cleanTicker(symbol);
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

    // Known ticker-only visual atoms may safely use their own text. This avoids
    // the previous bug that treated arbitrary uppercase prose as a symbol.
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

  window.V38OpenTickerChart = openTicker;
})();
