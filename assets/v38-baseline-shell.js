(function () {
  'use strict';

  const cardSpecs = [
    ['発火前', 'Pre-Breakout'],
    ['支えへの接触', 'Put Wall Touch'],
    ['エントリー候補ボード', 'Confluence'],
    ['ポケットピボット（10D）', 'Pocket Pivots (10D)'],
    ["本日のピックアップ", "Today's Setups"],
    ['テクニカル・パターン別', 'Chart Patterns'],
    ['圧縮コイル（VCP）', 'VCP Watch'],
    ['21EMAタッチ', '21EMA Touch'],
    ['Multi VWAPセットアップ', '63 / 252 / All-time VWAP'],
    ['底打ち（構造ピボット）', 'Structure Pivot'],
    ['ブレイク一覧', 'Signals'],
    ['運用ルール（確定版）', 'Playbook'],
    ['定義・グレード・格付け', 'Grades'],
    ['状態の凡例', 'Status'],
    ['コホート分析', 'Cohort'],
    ['入り方', 'Entries'],
    ['手仕舞いの目安', 'Exits'],
    ['リーダー監視', 'Leaders']
  ];

  function node(tag, className, text) {
    const out = document.createElement(tag);
    if (className) out.className = className;
    if (text !== undefined) out.textContent = String(text);
    return out;
  }

  function heading(title, english) {
    const h2 = node('h2', '', title);
    h2.appendChild(node('span', 'h2en', english));
    return h2;
  }

  function statusHost(reason) {
    const host = node('div', 'v38-baseline-card-body', 'SOURCE_UNAVAILABLE');
    host.dataset.v38Status = 'DATA_REQUIRED';
    host.dataset.v38Reason = reason;
    return host;
  }

  function insertTab(beforeHref, href, label) {
    const nav = document.querySelector('nav');
    if (!nav || nav.querySelector(`a[href="${href}"]`)) return;
    const tab = node('a', 'tabx', label);
    tab.href = href;
    const before = nav.querySelector(`a[href="${beforeHref}"]`);
    nav.insertBefore(tab, before || null);
  }

  function buildSetups() {
    let section = document.getElementById('t-today');
    if (section && section.children.length) return;
    if (!section) { section = node('section'); section.id = 't-today'; }
    section.dataset.v38Baseline = '0905';

    const intro = node('div', 'msec');
    const left = node('div', 'msec-l', 'セットアップ');
    left.appendChild(node('span', 'msec-en', 'Setups'));
    intro.append(left, node('div', 'msec-q', '発火前・支え・重なり・トリガーを元画面の順序で確認'));
    section.appendChild(intro);

    const search = node('div', 'card v38-baseline-search');
    search.id = 'v38-universe-search';
    search.append(heading('銘柄検索', 'Ticker Search'), node('div', 'sub', 'ティッカーで全ユニバースを検索（タップで詳細）'));
    const input = node('input', 'tksearch');
    input.type = 'search'; input.placeholder = '例: NVDA'; input.setAttribute('aria-label', '銘柄検索');
    search.append(input, node('div', 'tkresults'));
    section.appendChild(search);

    cardSpecs.forEach(([title, english]) => {
      const card = node('div', 'card');
      card.dataset.v38CardTitle = title;
      if (title === 'Multi VWAPセットアップ') card.classList.add('v38-vwap-card');
      card.append(heading(title, english), statusHost('BASELINE_CARD_SOURCE_UNAVAILABLE'));
      section.appendChild(card);
    });
    if (!section.parentNode) {
      const rotation = document.getElementById('t-rotation');
      rotation.parentNode.insertBefore(section, rotation);
    }
  }

  function buildMovers() {
    let section = document.getElementById('t-movers');
    if (section && section.children.length) return;
    if (!section) { section = node('section'); section.id = 't-movers'; }
    section.dataset.v38Baseline = '0905';
    const intro = node('div', 'msec');
    const left = node('div', 'msec-l', '値動き 上位・下位');
    left.appendChild(node('span', 'msec-en', 'Movers'));
    intro.append(left, node('div', 'msec-q', '日次騰落・RS変化・期間リターン'));
    const card = node('div', 'card'); card.dataset.v38CardTitle = '値動き 上位・下位';
    card.appendChild(heading('値動き 上位・下位', 'Movers'));
    const grid = node('div', 'v38-movers-grid');
    ['gainers', 'losers'].forEach((kind) => {
      const block = node('div', `v38-movers-${kind}`);
      block.append(node('h3', '', kind === 'gainers' ? '日次上昇' : '日次下落'), node('div', 'v38-movers-rows', 'DATA_REQUIRED'));
      grid.appendChild(block);
    });
    card.appendChild(grid); section.append(intro, card);
    if (!section.parentNode) {
      const rs = document.getElementById('t-rs'); rs.parentNode.insertBefore(section, rs);
    }
  }

  function restoreRotationInventory() {
    const section = document.getElementById('t-rotation');
    if (!section) return;
    const cards = Array.from(section.querySelectorAll(':scope > .card'));
    const text = section.textContent || '';
    const first = cards[0] || null;
    if (!/RRG|資金フロー/.test(text) && first) first.prepend(heading('RRG・資金フロー', 'GICS / Style Flow'));
    if (!/指数と中身の乖離|Index vs Breadth/.test(text)) {
      const card = node('div', 'card'); card.dataset.v38CardTitle = '指数と中身の乖離';
      card.append(heading('指数と中身の乖離', 'Index vs Breadth'), statusHost('ROTATION_INDEX_BREADTH_SOURCE_UNAVAILABLE'));
      section.insertBefore(card, cards[2] || null);
    }
    section.dataset.v38Baseline = '0905';
  }

  function paintMoverRows(host, rows) {
    if (!host) return;
    host.replaceChildren();
    (rows || []).forEach((row, index) => {
      const line = node('div', 'mrow');
      const ticker = node('button', 'v38-ticker-link', row.ticker || '—');
      ticker.type = 'button';
      ticker.addEventListener('click', () => window.V38OpenTickerChart && window.V38OpenTickerChart(row.ticker));
      line.append(node('span', 'rk', index + 1), ticker);
      const value = Number(row.ret1);
      line.appendChild(node('b', value >= 0 ? 'pos' : 'neg', Number.isFinite(value) ? `${value >= 0 ? '+' : ''}${(value * 100).toFixed(1)}%` : '—'));
      host.appendChild(line);
    });
    host.dataset.v38Status = rows && rows.length ? 'READY' : 'DATA_REQUIRED';
  }

  async function bindSearch() {
    const card = document.getElementById('v38-universe-search');
    if (!card) return;
    const input = card.querySelector('input');
    const results = card.querySelector('.tkresults');
    if (!input || !results) return;
    let rows = [];
    try {
      const payload = await fetch('data/search_index.json', {cache: 'no-store'}).then((response) => response.ok ? response.json() : Promise.reject());
      rows = Array.isArray(payload) ? payload : (payload.rows || payload.symbols || []);
    } catch (_) {
      results.textContent = 'SOURCE_UNAVAILABLE';
      results.dataset.v38Status = 'DATA_REQUIRED';
    }
    const render = () => {
      const query = input.value.trim().toUpperCase();
      results.replaceChildren();
      if (!query) return;
      rows.filter((row) => String(row.ticker || row.symbol || '').toUpperCase().includes(query)).slice(0, 12).forEach((row) => {
        const ticker = String(row.ticker || row.symbol || '').toUpperCase();
        const button = node('button', 'v38-ticker-link', ticker);
        button.type = 'button';
        button.addEventListener('click', () => window.V38OpenTickerChart && window.V38OpenTickerChart(ticker));
        results.appendChild(button);
      });
      results.dataset.v38Status = results.children.length ? 'READY' : 'NO_SIGNAL';
      if (!results.children.length) results.textContent = 'NO_SIGNAL';
    };
    input.addEventListener('input', render);
  }

  async function bind() {
    try {
      const view = await fetch('data/ui_view_model.json', {cache: 'no-store'}).then((r) => r.ok ? r.json() : Promise.reject());
      const movers = view.movers || {};
      paintMoverRows(document.querySelector('.v38-movers-gainers .v38-movers-rows'), movers.gainers);
      paintMoverRows(document.querySelector('.v38-movers-losers .v38-movers-rows'), movers.losers);
      document.getElementById('t-movers').dataset.v38Status = movers.status || 'DATA_REQUIRED';
      document.getElementById('t-today').dataset.v38Status = (view.setups || {}).status || 'DATA_REQUIRED';
    } catch (_) {
      document.getElementById('t-movers').dataset.v38Status = 'DATA_REQUIRED';
      document.getElementById('t-today').dataset.v38Status = 'DATA_REQUIRED';
    }
  }

  function keepVwapInSetups() {
    const setups = document.getElementById('t-today');
    const rs = document.getElementById('t-rs');
    if (!setups || !rs) return;
    const observer = new MutationObserver(() => {
      const card = rs.querySelector('.v38-vwap-card');
      if (!card) return;
      const placeholder = setups.querySelector('.v38-vwap-card');
      if (placeholder && placeholder !== card) placeholder.replaceWith(card);
      else if (!setups.contains(card)) setups.appendChild(card);
    });
    observer.observe(rs, {childList: true});
  }

  buildSetups(); buildMovers(); restoreRotationInventory();
  insertTab('#t-rotation', '#t-today', 'Setups');
  insertTab('#t-rs', '#t-movers', 'Movers');
  keepVwapInSetups();
  document.addEventListener('DOMContentLoaded', () => { bind(); bindSearch(); }, {once: true});
})();
