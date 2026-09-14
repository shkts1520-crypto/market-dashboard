(function () {
  'use strict';

  const OPTIONS_URL = 'data/options/index.json';
  const SEARCH_URL = 'data/search_index.json';
  const UI_URL = 'data/ui_view_model.json';
  const TV_WIDGET = 'https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js';
  const NO_CONTRACT = 'NO_VALID_0_45_DTE_CONTRACTS';
  let metadataPromise = null;
  let scheduled = false;

  function loadMetadata() {
    if (!metadataPromise) {
      metadataPromise = Promise.all([
        fetch(OPTIONS_URL, {cache: 'no-store'}).then((response) => response.ok ? response.json() : null).catch(() => null),
        fetch(SEARCH_URL, {cache: 'no-store'}).then((response) => response.ok ? response.json() : null).catch(() => null),
        fetch(UI_URL, {cache: 'no-store'}).then((response) => response.ok ? response.json() : null).catch(() => null)
      ]).then(([options, search, view]) => ({options, search, view}));
    }
    return metadataPromise;
  }

  function esc(value) {
    return String(value == null ? '' : value)
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;');
  }

  function tickerFromModal(modal) {
    const title = modal && modal.querySelector('.v38-rc-title,.v38-oc-title');
    return title ? String(title.textContent || '').trim().toUpperCase() : '';
  }

  function tradingViewSymbol(search, ticker) {
    const rows = search && Array.isArray(search.rows) ? search.rows : [];
    const row = rows.find((item) => item && String(item.ticker || '').trim().toUpperCase() === ticker);
    const exchange = row ? String(row.exchange || '').trim().toUpperCase() : '';
    return exchange ? exchange + ':' + ticker : ticker;
  }

  function installTradingView(host, symbol) {
    if (!host || !symbol || host.dataset.v38ChartSource === 'tradingview-live') return;
    host.replaceChildren();
    host.dataset.v38ChartSource = 'tradingview-live';
    host.dataset.v38TradingviewSymbol = symbol;
    const container = document.createElement('div');
    container.className = 'tradingview-widget-container v38-live-chart-fallback';
    container.style.height = '100%';
    container.style.width = '100%';
    const widget = document.createElement('div');
    widget.className = 'tradingview-widget-container__widget';
    widget.style.height = '100%';
    widget.style.width = '100%';
    container.appendChild(widget);
    const script = document.createElement('script');
    script.type = 'text/javascript';
    script.src = TV_WIDGET;
    script.async = true;
    script.textContent = JSON.stringify({
      autosize: true,
      symbol: symbol,
      interval: 'D',
      timezone: 'exchange',
      theme: 'light',
      backgroundColor: 'rgba(255,255,255,1)',
      style: '1',
      withdateranges: true,
      hide_side_toolbar: false,
      allow_symbol_change: false,
      save_image: false,
      locale: 'en',
      calendar: false,
      support_host: 'https://www.tradingview.com'
    });
    container.appendChild(script);
    host.appendChild(container);
  }

  function markOptionSemantics(modal, options, ticker) {
    if (!modal || !options || !ticker) return;
    const status = modal.querySelector('.v38-rc-status,.v38-oc-status');
    if (!status) return;
    const failure = options.failures && options.failures[ticker];
    if (failure === NO_CONTRACT && !status.dataset.v38ContractSemantics) {
      status.dataset.v38ContractSemantics = 'no-valid-0-45-dte-contracts';
      status.textContent = 'Options: 0–45 DTE 有効契約なし • ' + String(status.textContent || '');
    }
  }

  function repairModal() {
    const modal = document.getElementById('v38-options-chart-modal');
    if (!modal || modal.hidden) return;
    const ticker = tickerFromModal(modal);
    if (!ticker) return;
    const empty = Array.from(modal.querySelectorAll('.v38-rc-empty')).find((node) =>
      /ローソク足履歴は未取得/.test(String(node.textContent || ''))
    );
    loadMetadata().then(({options, search}) => {
      if (!modal || modal.hidden || tickerFromModal(modal) !== ticker) return;
      if (empty && document.documentElement.contains(empty)) {
        const host = modal.querySelector('.v38-rc-chart,.v38-oc-chart');
        installTradingView(host, tradingViewSymbol(search, ticker));
        const status = modal.querySelector('.v38-rc-status,.v38-oc-status');
        if (status) {
          status.dataset.v38ChartFallback = 'tradingview-live';
          status.textContent = 'TradingView 実チャート • ローカル優先履歴外はライブ表示へ自動切替';
        }
      }
      markOptionSemantics(modal, options, ticker);
    });
  }

  function findDailyCard(needles) {
    const section = document.getElementById('t-market');
    if (!section) return null;
    return Array.from(section.querySelectorAll('.card')).find((card) => {
      const heading = card.querySelector('h2,.hdr h2,.chd h2');
      const text = String(heading ? heading.textContent : '').replace(/\s+/g, ' ').trim();
      return needles.some((needle) => text.includes(needle));
    }) || null;
  }

  function readyCard(card, key, html) {
    if (!card || card.dataset.v38ObservationBound === key) return;
    card.innerHTML = html;
    card.dataset.v38Status = 'READY';
    card.dataset.v38BindingKey = 'daily.display_observations.' + key;
    card.dataset.v38ObservationBound = key;
  }

  function sparkline(series) {
    const rows = Array.isArray(series) ? series.filter((row) => row && Number.isFinite(Number(row.value_t != null ? row.value_t : row.value))) : [];
    if (rows.length < 2) return '';
    const values = rows.map((row) => Number(row.value_t != null ? row.value_t : row.value));
    const min = Math.min.apply(null, values);
    const max = Math.max.apply(null, values);
    const span = Math.max(1e-9, max - min);
    const width = 320, height = 78, pad = 5;
    const points = values.map((value, index) => {
      const x = pad + index * (width - pad * 2) / Math.max(1, values.length - 1);
      const y = pad + (max - value) / span * (height - pad * 2);
      return x.toFixed(1) + ',' + y.toFixed(1);
    }).join(' ');
    return '<svg viewBox="0 0 ' + width + ' ' + height + '" aria-hidden="true" style="width:100%;height:78px;display:block"><polyline points="' + points + '" fill="none" stroke="currentColor" stroke-width="2" vector-effect="non-scaling-stroke"></polyline></svg>';
  }

  function renderRegime(obs) {
    const card = findDailyCard(['マーケットステータス推移', 'Regime History']);
    if (!card || !obs || obs.status !== 'READY') return;
    const records = Array.isArray(obs.records) ? obs.records : [];
    const chips = records.slice(-30).map((row) => '<span class="chip">' + esc(row.date) + ' ' + esc(row.state) + '</span>').join('');
    const current = records.length ? records[records.length - 1] : null;
    readyCard(card, 'regime_history',
      '<h2>マーケットステータス推移 <span class="h2en">Regime History</span></h2>' +
      '<div class="sub">正本NQSARラベルだけを保存。価格から過去色を推定しない。</div>' +
      '<div style="font-size:26px;font-weight:800;margin:10px 0">' + esc(current ? current.state : '') + '</div>' +
      '<div class="mut">正本観測 ' + esc(obs.observation_count) + '件・以後セッションごとに追記</div>' +
      '<div class="chips" style="margin-top:9px">' + chips + '</div>');
  }

  function signed(value, digits) {
    const number = Number(value);
    return Number.isFinite(number) ? (number >= 0 ? '+' : '') + number.toFixed(digits) : '';
  }

  function renderLiquidity(obs) {
    const card = findDailyCard(['ネット流動性', 'Net Liquidity']);
    if (!card || !obs || obs.status !== 'READY') return;
    const d4 = Number(obs.change_4w_t);
    const d13 = Number(obs.change_13w_t);
    readyCard(card, 'net_liquidity',
      '<h2>ネット流動性 <span class="h2en">Net Liquidity</span></h2>' +
      '<div class="sub">FRB総資産 − RRP − TGA。公式単位で換算し、欠けた成分の0埋めはしない。</div>' +
      '<div style="display:flex;gap:16px;align-items:end;flex-wrap:wrap;margin-top:8px">' +
        '<div><div class="mut">現在</div><div style="font-size:26px;font-weight:800">$' + Number(obs.current_t).toFixed(2) + 'T</div></div>' +
        '<div><div class="mut">4週</div><b class="' + (d4 >= 0 ? 'pos' : 'neg') + '">' + signed(d4, 2) + 'T</b></div>' +
        '<div><div class="mut">13週</div><b class="' + (d13 >= 0 ? 'pos' : 'neg') + '">' + signed(d13, 2) + 'T</b></div>' +
      '</div>' + sparkline(obs.series) +
      '<div class="mut">FRED観測日 ' + esc(obs.latest_observation) + '</div>');
  }

  function renderSentiment(obs) {
    const card = findDailyCard(['センチメント', 'Sentiment']);
    if (!card || !obs || obs.status !== 'READY') return;
    const rows = Array.isArray(obs.components) ? obs.components : [];
    const body = rows.map((row) =>
      '<div style="display:grid;grid-template-columns:minmax(0,1fr) auto auto;gap:8px;padding:6px 0;border-bottom:1px solid rgba(0,0,0,.06)">' +
        '<span>' + esc(row.label) + (row.in_composite ? '' : ' <span class="mut">参考</span>') + '</span>' +
        '<span class="mut">' + esc(row.raw_display) + '</span>' +
        '<b>' + (Number.isFinite(Number(row.percentile)) ? Number(row.percentile).toFixed(0) : '') + '</b>' +
      '</div>'
    ).join('');
    readyCard(card, 'sentiment',
      '<h2>センチメント <span class="h2en">Sentiment</span></h2>' +
      '<div class="sub">旧仕様どおり、利用可能な正本成分だけを同率平均。NAAIM等を遅延値で代用しない。</div>' +
      '<div style="display:flex;align-items:baseline;gap:10px;margin:9px 0"><span style="font-size:28px;font-weight:800">' + Number(obs.current).toFixed(0) + '</span><b>' + esc(obs.band) + '</b><span class="mut">合成 ' + esc(obs.component_count) + '成分</span></div>' +
      body + sparkline(obs.series));
  }

  function renderReversal(obs) {
    const card = findDailyCard(['転換初動リーダーボード', 'Reversal Leaders']);
    if (!card || !obs || obs.status !== 'READY') return;
    const active = !!obs.active;
    const status = active
      ? '● 回復初動が進行中（安値から +' + (Number(obs.off_low) * 100).toFixed(0) + '%・DD最深 ' + (Number(obs.dd_at_low) * 100).toFixed(0) + '%）'
      : '○ 待機中（QQQは高値から ' + (Number(obs.dd_now) * 100).toFixed(0) + '%・−10%DDからの+5%回復トリガー未成立）';
    const leaders = Array.isArray(obs.leaders) ? obs.leaders : [];
    const chips = leaders.map((row) => {
      const mark = row.reclaim21 && row.volume_recovered ? '◎奪回+出来高' : row.reclaim21 ? '○21EMA奪回' : '・待ち';
      return '<span class="chip" data-tkone="' + esc(row.ticker) + '">' + esc(row.ticker) + ' <span class="mut">' + esc(mark) + '</span></span>';
    }).join('');
    readyCard(card, 'reversal_leaders',
      '<h2>転換初動リーダーボード <span class="h2en">Reversal Leaders</span></h2>' +
      '<div class="sub">QQQの−10%DD→安値から+5%回復時だけ、約42営業日前のRS63上位20を観測。売買ゲートには使わない。</div>' +
      '<div style="font-weight:800;margin:9px 0">' + esc(status) + '</div>' +
      (active ? '<div class="mut">旧リーダー基準日 ' + esc(obs.old_leader_date) + '・奪回+出来高 ' + esc(obs.ready_count) + '/20</div><div class="chips" style="margin-top:8px">' + chips + '</div>' : '<div class="mut">トリガー成立までは候補銘柄を生成しない。</div>'));
  }

  function renderFtd(obs) {
    const card = findDailyCard(['フォロースルー・デイ', 'Follow-Through Day', 'FTD']);
    if (!card || !obs || obs.status !== 'READY') return;
    const rows = Array.isArray(obs.rows) ? obs.rows : [];
    const body = rows.map((row) =>
      '<div style="padding:8px 0;border-bottom:1px solid rgba(0,0,0,.06)">' +
        '<div style="display:flex;justify-content:space-between;gap:8px"><b>' + esc(row.ticker) + '</b><span>' + esc(row.state) + '</span></div>' +
        '<div class="mut" style="margin-top:3px">' + esc(row.display) + '</div>' +
      '</div>'
    ).join('');
    readyCard(card, 'ftd_proxy',
      '<h2>フォロースルー・デイ <span class="h2en">FTD (proxy)</span></h2>' +
      '<div class="sub">調整局面→Day1→Day4以降に+1.25%以上かつ出来高増。FTD日安値の終値割れ、または回復後の新規調整入りで無効化。時間だけでは失効しない。</div>' + body);
  }

  function repairDailyCards() {
    loadMetadata().then(({view}) => {
      const observations = view && view.daily && view.daily.display_observations;
      if (!observations || observations.status !== 'READY') return;
      renderRegime(observations.regime_history);
      renderLiquidity(observations.net_liquidity);
      renderSentiment(observations.sentiment);
      renderReversal(observations.reversal_leaders);
      renderFtd(observations.ftd_proxy);
    });
  }

  function queue() {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(function () {
      scheduled = false;
      repairModal();
      repairDailyCards();
    });
  }

  new MutationObserver(queue).observe(document.documentElement, {
    childList: true,
    subtree: true,
    characterData: true,
    attributes: true,
    attributeFilter: ['hidden']
  });
  document.addEventListener('click', function () {
    setTimeout(repairModal, 50);
    setTimeout(repairModal, 250);
    setTimeout(repairModal, 900);
    setTimeout(repairDailyCards, 80);
  });
  document.addEventListener('v38:data-ready', queue);
  [0, 300, 1200, 3000].forEach((ms) => setTimeout(function () {
    repairModal();
    repairDailyCards();
  }, ms));
})();