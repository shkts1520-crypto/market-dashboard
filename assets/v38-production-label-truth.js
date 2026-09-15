(function(){
  'use strict';

  const SECTION_IDS = [
    't-market', 't-alloc', 't-port', 't-today', 't-rotation',
    't-movers', 't-rs', 't-weekly', 't-options', 't-post1'
  ];
  const TREND_SPECS = [
    {key:'mc57', title:'MC57推移', source:'data/ui_view_model.json.daily.mc57_detail.series.mc57'},
    {key:'breadth50', title:'ブレッドス推移（50', source:'data/ui_view_model.json.daily.history.breadth50'},
    {key:'breadth200', title:'ブレッドス推移（200', source:'data/ui_view_model.json.daily.history.breadth200'}
  ];
  const snapshots = {trend:{}, publish:[]};

  const replacements = [
    ['回復時点の順位で再計算する前提のモック。', '回復時点の順位で再計算する前提。現行正本producer未復元。'],
    ['全Active Universeを走査。Direction/Confidence予測ではなく、実測のWall / Gamma Flip / GEX配置で期間別に抽出。', 'RS21・63・189上位50の重複除外対象を走査。実測のWall / Gamma Flip / GEX配置で期間別に抽出。'],
    ['SOURCE_UNAVAILABLE', 'DATA_REQUIRED'],
    ['MOCK DATA', ''],
    ['Mock Data', ''],
    ['モックデータ', '旧表示値は使用しません'],
    ['モック', '旧表示値']
  ];

  function title(card) {
    const h = card && card.querySelector('h2,.hdr h2,.chd h2');
    return h ? String(h.textContent || '').replace(/\s+/g, ' ').trim() : '';
  }

  function marketCards() {
    const section = document.getElementById('t-market');
    return section ? Array.from(section.querySelectorAll(':scope > .card')) : [];
  }

  function findTrendCard(spec) {
    return marketCards().find((card) => title(card).includes(spec.title)) || null;
  }

  function captureLiveBoundOriginals() {
    if (document.body?.dataset?.v38BindingStatus !== 'ready') return;
    TREND_SPECS.forEach((spec) => {
      if (snapshots.trend[spec.key]) return;
      const card = findTrendCard(spec);
      if (card) snapshots.trend[spec.key] = card.cloneNode(true);
    });
    if (!snapshots.publish.length) {
      const wraps = Array.from(document.querySelectorAll('#t-post1 .postwrap'));
      if (wraps.length >= 2 && wraps.every((wrap) => wrap.querySelector('iframe.postframe'))) {
        snapshots.publish = wraps.map((wrap) => wrap.cloneNode(true));
      }
    }
  }

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

  function removeInternalPublicLabels(root) {
    const leaves = Array.from(root.querySelectorAll('*')).filter((el) => el.children.length === 0);
    leaves.forEach((el) => {
      const text = String(el.textContent || '').replace(/\s+/g, ' ').trim();
      if (!text) return;
      if (text === '実データ' || text === '正本の実データ' || text === '正本publish shard') {
        el.remove();
        return;
      }
      if (/^full_v38_ready:\s*(?:true|false)\s*\/\s*blockers:\s*\d+$/i.test(text)) {
        el.remove();
        return;
      }
      if (text === '正本データ') el.textContent = 'LIVE DATA';
    });
  }

  function valuesFor(vm, key) {
    const daily = (vm && vm.daily) || {};
    if (key === 'mc57') {
      const detail = daily.mc57_detail || {};
      const series = (detail.series && detail.series.mc57) || detail.history || [];
      return series.map((row) => Number(row && row.value)).filter(Number.isFinite);
    }
    const field = key === 'breadth50' ? 'breadth50' : 'breadth200';
    return (daily.history || []).map((row) => Number(row && row[field])).filter(Number.isFinite);
  }

  function renderLiveSpark(card, values, spec) {
    if (!card) return false;
    const clean = values.filter(Number.isFinite).slice(-504);
    if (clean.length < 2) {
      card.dataset.v38LiveSeries = 'DATA_REQUIRED';
      card.dataset.v38Status = 'DATA_REQUIRED';
      const missing = document.createElement('div');
      missing.className = 'mut v38-live-series-missing';
      missing.dataset.v38Status = 'DATA_REQUIRED';
      missing.textContent = 'DATA_REQUIRED · 推移データ不足';
      card.appendChild(missing);
      return false;
    }

    let svg = card.querySelector('svg');
    if (!svg) {
      svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
      svg.classList.add('v38-live-spark');
      svg.style.width = '100%';
      svg.style.height = '64px';
      svg.style.display = 'block';
      card.appendChild(svg);
    }
    svg.replaceChildren();
    svg.setAttribute('viewBox', '0 0 100 28');
    svg.setAttribute('preserveAspectRatio', 'none');
    svg.dataset.v38LiveSpark = spec.key;
    svg.setAttribute('aria-label', `${spec.title} 504-session live history`);

    const min = Math.min(...clean);
    const max = Math.max(...clean);
    const span = max - min || 1;
    const points = clean.map((value, index) => {
      const x = clean.length === 1 ? 0 : (index / (clean.length - 1)) * 100;
      const y = 26 - ((value - min) / span) * 24;
      return `${x.toFixed(3)},${y.toFixed(3)}`;
    }).join(' ');
    const line = document.createElementNS('http://www.w3.org/2000/svg', 'polyline');
    line.setAttribute('points', points);
    line.setAttribute('fill', 'none');
    line.setAttribute('stroke', 'currentColor');
    line.setAttribute('stroke-width', '1.7');
    line.setAttribute('vector-effect', 'non-scaling-stroke');
    svg.appendChild(line);

    card.dataset.v38LiveSeries = spec.key;
    card.dataset.v38TruthSource = spec.source;
    card.dataset.v38Status = 'READY';
    return true;
  }

  function restoreTrends(vm) {
    TREND_SPECS.forEach((spec) => {
      const snap = snapshots.trend[spec.key];
      const current = findTrendCard(spec);
      if (!snap || !current) return;
      const restored = snap.cloneNode(true);
      current.replaceWith(restored);
      renderLiveSpark(restored, valuesFor(vm, spec.key), spec);
    });
  }

  function restorePublish() {
    if (snapshots.publish.length < 2) return;
    const current = Array.from(document.querySelectorAll('#t-post1 .postwrap'));
    if (current.length < 2) return;
    snapshots.publish.forEach((snap, index) => {
      if (!current[index]) return;
      const restored = snap.cloneNode(true);
      restored.dataset.v38TruthSource = 'canonical-publish-card';
      restored.dataset.v38Status = 'READY';
      restored.dataset.v38PublishCard = String(index + 1);
      current[index].replaceWith(restored);
    });
    const section = document.getElementById('t-post1');
    if (section) {
      section.dataset.v38TruthSource = 'canonical-publish-cards';
      section.dataset.v38Status = 'READY';
      section.dataset.v38PublishCards = 'ready';
    }
  }

  function markSections(root) {
    SECTION_IDS.forEach((id) => {
      const section = root.getElementById(id);
      if (!section) return;
      if (!section.dataset.v38TruthSource) section.dataset.v38TruthSource = `data/ui_view_model.json#${id}`;
      if (!section.dataset.v38Status) section.dataset.v38Status = 'READY';
    });
  }

  function preserveOptionsUpward(root) {
    const upward = root.querySelector('#t-options .v38-options-upward-card');
    if (!upward) return;
    upward.dataset.v38TruthSource = 'data/options/index.json.upward_rankings';
    upward.dataset.v38Status = 'READY';
  }

  function finalize(vm) {
    restoreTrends(vm || window.V38UiViewModel || {});
    restorePublish();
    SECTION_IDS.forEach((id) => {
      const section = document.getElementById(id);
      if (!section) return;
      scrubText(section);
      removeInternalPublicLabels(section);
    });
    markSections(document);
    preserveOptionsUpward(document);
    document.body.dataset.v38LegacyMockLabels = '0';
    document.body.dataset.v38PublicRenderContract = 'ready';
  }

  function reconcile(vm) {
    let attempts = 0;
    const poll = () => {
      if (document.body?.dataset?.v38TruthBinding === 'ready') {
        finalize(vm);
        window.setTimeout(() => finalize(vm), 120);
        return;
      }
      attempts += 1;
      if (attempts < 80) window.setTimeout(poll, 50);
    };
    poll();
  }

  function start(event) {
    captureLiveBoundOriginals();
    reconcile((event && event.detail) || window.V38UiViewModel || {});
  }

  document.addEventListener('v38:view-ready', start, {once: true});
  if (window.V38UiViewModel) start({detail: window.V38UiViewModel});
})();
