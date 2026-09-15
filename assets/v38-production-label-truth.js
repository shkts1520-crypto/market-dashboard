(function(){
  'use strict';

  const SECTION_IDS = [
    't-market', 't-alloc', 't-port', 't-today', 't-rotation',
    't-movers', 't-rs', 't-weekly', 't-options', 't-post1'
  ];

  const replacements = [
    ['回復時点の順位で再計算する前提のモック。', '回復時点の順位で再計算する前提。現行正本producer未復元。'],
    ['MOCK DATA', ''],
    ['Mock Data', ''],
    ['モックデータ', '旧表示値は使用しません'],
    ['モック', '旧表示値']
  ];

  function scrubText(root) {
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    nodes.forEach((textNode) => {
      let text = String(textNode.nodeValue || '');
      let next = text;
      replacements.forEach(([from, to]) => {
        next = next.split(from).join(to);
      });
      if (next !== text) textNode.nodeValue = next;
    });
  }

  function apply() {
    SECTION_IDS.forEach((id) => {
      const section = document.getElementById(id);
      if (section) scrubText(section);
    });
    document.body.dataset.v38LegacyMockLabels = '0';
  }

  function start() {
    window.setTimeout(apply, 350);
  }

  document.addEventListener('v38:view-ready', start, {once: true});
  if (window.V38UiViewModel) start();
})();
