(function () {
  'use strict';
  const TV_WIDGET = 'https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js';
  const NO_CONTRACT = 'NO_VALID_0_45_DTE_CONTRACTS';
  let metadata;

  function load() {
    if (!metadata) metadata = Promise.all([
      fetch('data/options/index.json', {cache: 'no-store'}).then((r) => r.ok ? r.json() : null),
      fetch('data/search_index.json', {cache: 'no-store'}).then((r) => r.ok ? r.json() : null),
    ]).then(([options, search]) => ({options, search}));
    return metadata;
  }

  function ticker(modal) {
    const title = modal && modal.querySelector('.v38-rc-title,.v38-oc-title');
    return title ? title.textContent.trim().toUpperCase() : '';
  }

  function symbol(search, value) {
    const row = ((search && search.rows) || []).find((x) => String(x.ticker || '').toUpperCase() === value);
    const exchange = row && String(row.exchange || '').toUpperCase();
    return exchange ? `${exchange}:${value}` : value;
  }

  function install(host, value) {
    if (!host || host.dataset.v38ChartSource === 'tradingview-live') return;
    host.replaceChildren();
    host.dataset.v38ChartSource = 'tradingview-live';
    host.dataset.v38TradingviewSymbol = value;
    const container = document.createElement('div');
    container.className = 'tradingview-widget-container v38-live-chart-fallback';
    container.style.cssText = 'height:100%;width:100%';
    const widget = document.createElement('div');
    widget.className = 'tradingview-widget-container__widget';
    container.appendChild(widget);
    const script = document.createElement('script');
    script.src = TV_WIDGET;
    script.async = true;
    script.textContent = JSON.stringify({autosize:true,symbol:value,interval:'D',theme:'light',style:'1',locale:'en'});
    container.appendChild(script);
    host.appendChild(container);
  }

  function apply() {
    const modal = document.getElementById('v38-options-chart-modal');
    if (!modal || modal.hidden) return;
    const value = ticker(modal);
    if (!value) return;
    load().then(({options, search}) => {
      if (modal.hidden || ticker(modal) !== value) return;
      const empty = Array.from(modal.querySelectorAll('.v38-rc-empty')).some((node) => /ローソク足履歴は未取得/.test(node.textContent));
      const status = modal.querySelector('.v38-rc-status,.v38-oc-status');
      if (empty) {
        install(modal.querySelector('.v38-rc-chart,.v38-oc-chart'), symbol(search, value));
        if (status) status.textContent = 'TradingView 実チャート • ローカル優先履歴外はライブ表示へ自動切替';
      }
      if (status && options && options.failures && options.failures[value] === NO_CONTRACT) {
        status.dataset.v38ContractSemantics = 'no-valid-0-45-dte-contracts';
        status.textContent = `Options: 0–45 DTE 有効契約なし • ${status.textContent}`;
      }
    });
  }

  document.addEventListener('click', () => setTimeout(apply, 0), true);
  if (window.V38OpenTickerChart) {
    const openTickerChart = window.V38OpenTickerChart;
    window.V38OpenTickerChart = function () {
      const result = openTickerChart.apply(this, arguments);
      setTimeout(apply, 0);
      return result;
    };
  }
  window.V38ApplyTradingViewFallback = apply;
})();
