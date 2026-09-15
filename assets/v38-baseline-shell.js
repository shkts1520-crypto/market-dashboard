(function () {
  'use strict';

  function openTicker(ticker) {
    if (ticker && window.V38OpenTickerChart) window.V38OpenTickerChart(ticker);
  }

  function bindTickerTargets(root) {
    root.querySelectorAll('[data-tkone]').forEach((target) => {
      target.tabIndex = target.tabIndex >= 0 ? target.tabIndex : 0;
      target.setAttribute('role', 'button');
      const activate = () => openTicker(target.dataset.tkone);
      target.addEventListener('click', activate);
      target.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          activate();
        }
      });
    });
  }

  function bindCopyButtons(root) {
    root.querySelectorAll('button.cp[data-tk]').forEach((button) => {
      button.addEventListener('click', async () => {
        const tickers = String(button.dataset.tk || '').trim();
        if (!tickers) return;
        try {
          await navigator.clipboard.writeText(tickers);
          button.dataset.copied = 'true';
        } catch (_) {
          button.dataset.copied = 'unavailable';
        }
      });
    });
  }

  async function bindSearch() {
    const input = document.getElementById('tksearch');
    const results = document.getElementById('tkresults');
    if (!input || !results) return;
    let rows = [];
    try {
      const response = await fetch('data/search_index.json', {cache: 'no-store'});
      if (!response.ok) throw new Error(String(response.status));
      const payload = await response.json();
      rows = Array.isArray(payload) ? payload : (payload.rows || payload.symbols || []);
    } catch (_) {
      results.textContent = 'SOURCE_UNAVAILABLE';
      results.dataset.v38Status = 'SOURCE_UNAVAILABLE';
      return;
    }
    input.addEventListener('input', () => {
      const query = input.value.trim().toUpperCase();
      results.replaceChildren();
      if (!query) return;
      rows.filter((row) => String(row.ticker || row.symbol || '').toUpperCase().includes(query))
        .slice(0, 12)
        .forEach((row) => {
          const ticker = String(row.ticker || row.symbol || '').toUpperCase();
          const button = document.createElement('button');
          button.type = 'button';
          button.className = 'v38-ticker-link';
          button.textContent = ticker;
          button.addEventListener('click', () => openTicker(ticker));
          results.appendChild(button);
        });
      if (!results.children.length) results.textContent = 'NO_SIGNAL';
    });
  }

  document.addEventListener('DOMContentLoaded', () => {
    bindTickerTargets(document);
    bindCopyButtons(document);
    bindSearch();
  }, {once: true});
})();
