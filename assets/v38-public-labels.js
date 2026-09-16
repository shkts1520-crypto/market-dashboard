(function () {
  'use strict';

  const REPLACEMENTS = [
    [/DATA_REQUIRED/g, '未取得'],
    [/DATA REQUIRED/g, '未取得'],
    [/SOURCE_UNAVAILABLE/g, '未取得'],
    [/producer未復元/g, '未取得'],
    [/正本publish shard/g, '公開データ'],
    [/full_v38_ready:/g, '公開準備:'],
    [/blockers:/g, '未解決項目:'],
    [/MOCK DATA/g, ''],
    [/正本producer/g, '取得元']
  ];

  let sanitizing = false;

  function ensureVisualFidelityStyle() {
    if (document.getElementById('v38-public-fidelity-style')) return;
    const style = document.createElement('style');
    style.id = 'v38-public-fidelity-style';
    style.textContent = [
      '@media(max-width:600px){',
      '.v38-theme-bar small{display:block!important;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}',
      '.v38-theme-bar{grid-template-columns:20px minmax(78px,.95fr) minmax(62px,1.15fr) 34px minmax(72px,.9fr)!important;gap:5px!important}',
      '}'
    ].join('');
    document.head.appendChild(style);
  }

  function polishDteHeadings(root) {
    const scope = root && root.querySelectorAll ? root : document;
    scope.querySelectorAll('#t-options .card h2').forEach((heading) => {
      const text = String(heading.textContent || '').trim();
      const match = text.match(/^DTE\s+(\d+)-(\d+)$/);
      if (match) heading.textContent = `${match[1]}–${match[2]} DTE`;
    });
  }

  function sanitizeTextNode(node) {
    const parent = node && node.parentElement;
    if (!parent || parent.closest('script, style')) return;
    let next = node.nodeValue || '';
    REPLACEMENTS.forEach(([pattern, replacement]) => {
      next = next.replace(pattern, replacement);
    });
    if (next !== node.nodeValue) node.nodeValue = next;
  }

  function sanitizePublicText(root) {
    if (!document.body || sanitizing) return;
    sanitizing = true;
    try {
      const target = root && root.nodeType ? root : document.body;
      if (target.nodeType === Node.TEXT_NODE) {
        sanitizeTextNode(target);
      } else {
        const walker = document.createTreeWalker(target, NodeFilter.SHOW_TEXT);
        let node;
        while ((node = walker.nextNode())) sanitizeTextNode(node);
      }
      ensureVisualFidelityStyle();
      polishDteHeadings(target.nodeType === Node.ELEMENT_NODE ? target : document);
      document.body.dataset.v38PublicLabels = 'ready';
    } finally {
      sanitizing = false;
    }
  }

  function schedule() {
    window.requestAnimationFrame(() => sanitizePublicText(document.body));
  }

  function observe() {
    if (!document.body) return;
    sanitizePublicText(document.body);
    const observer = new MutationObserver((mutations) => {
      mutations.forEach((mutation) => {
        if (mutation.type === 'characterData') {
          sanitizePublicText(mutation.target);
          return;
        }
        mutation.addedNodes.forEach((node) => sanitizePublicText(node));
      });
    });
    observer.observe(document.body, {subtree: true, childList: true, characterData: true});
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', observe, {once: true});
  } else {
    observe();
  }
  document.addEventListener('v38:view-ready', schedule);
  window.addEventListener('load', schedule, {once: true});
})();
