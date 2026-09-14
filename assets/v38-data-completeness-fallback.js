(function () {
  'use strict';

  const OPTIONS_URL = 'data/options/index.json';
  const TV_WIDGET = 'https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js';
  const NO_CONTRACT = 'NO_VALID_0_45_DTE_CONTRACTS';
  let optionsPromise = null;
  let scheduled = false;

  function loadOptions() {
    if (!optionsPromise) {
      optionsPromise = fetch(OPTIONS_URL, {cache: 'no-store'})
        .then((response) => response.ok ? response.json() : null)
        .catch(() => null);
    }
    return optionsPromise;
  }

  function tickerFromModal(modal) {
    const title = modal && modal.querySelector('.v38-rc-title,.v38-oc-title');
    return title ? String(title.textContent || '').trim().toUpperCase() : '';
  }

  function installTradingView(host, ticker) {
    if (!host || !ticker || host.dataset.v38ChartSource === 'tradingview-live') return;
    host.replaceChildren();
    host.dataset.v38ChartSource = 'tradingview-live';
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
      symbol: ticker,
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
    if (empty) {
      const host = modal.querySelector('.v38-rc-chart,.v38-oc-chart');
      installTradingView(host, ticker);
      const status = modal.querySelector('.v38-rc-status,.v38-oc-status');
      if (status) {
        status.dataset.v38ChartFallback = 'tradingview-live';
        status.textContent = 'TradingView 実チャート • ローカル優先履歴外はライブ表示へ自動切替';
      }
    }
    loadOptions().then((options) => markOptionSemantics(modal, options, ticker));
  }

  function queue() {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(function () {
      scheduled = false;
      repairModal();
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
  });
  document.addEventListener('v38:data-ready', queue);
  [0, 300, 1200, 3000].forEach((ms) => setTimeout(repairModal, ms));
})();
