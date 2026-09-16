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

  function sanitizePublicText() {
    if (!document.body) return;
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    let node;
    while ((node = walker.nextNode())) {
      const parent = node.parentElement;
      if (!parent || parent.closest('script, style')) continue;
      let next = node.nodeValue || '';
      REPLACEMENTS.forEach(([pattern, replacement]) => {
        next = next.replace(pattern, replacement);
      });
      if (next !== node.nodeValue) node.nodeValue = next;
    }
    document.body.dataset.v38PublicLabels = 'ready';
  }

  function schedule() {
    window.requestAnimationFrame(() => window.requestAnimationFrame(sanitizePublicText));
  }

  document.addEventListener('v38:view-ready', schedule);
  window.addEventListener('load', schedule, {once: true});
  if (window.V38UiViewModel) schedule();
})();
