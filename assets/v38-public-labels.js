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
