(function () {
  'use strict';

  const SECTOR_ETFS = [
    ['XLB', '素材'], ['XLC', '通信'], ['XLE', 'エネルギー'], ['XLF', '金融'],
    ['XLI', '資本財'], ['XLK', 'IT'], ['XLP', '生活必需品'], ['XLRE', '不動産'],
    ['XLU', '公益'], ['XLV', 'ヘルスケア'], ['XLY', '一般消費財']
  ];
  const PERIODS = [21, 63, 126, 189];
  let running = false;

  function finite(value) {
    if (value === null || value === undefined || value === '') return null;
    const number = Number(value);
    return Number.isFinite(number) ? number : null;
  }

  function pct(value, digits) {
    const number = finite(value);
    if (number === null) return '—';
    const sign = number > 0 ? '+' : '';
    return sign + (number * 100).toFixed(digits === undefined ? 1 : digits) + '%';
  }

  function score(value) {
    const number = finite(value);
    return number === null ? '—' : number.toFixed(1);
  }

  function compactDollar(value) {
    const number = finite(value);
    if (number === null) return '—';
    if (Math.abs(number) >= 1e12) return '$' + (number / 1e12).toFixed(2) + 'T';
    if (Math.abs(number) >= 1e9) return '$' + (number / 1e9).toFixed(2) + 'B';
    if (Math.abs(number) >= 1e6) return '$' + (number / 1e6).toFixed(1) + 'M';
    return '$' + number.toFixed(0);
  }

  function add(parent, tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    parent.appendChild(node);
    return node;
  }

  function tickerLink(parent, ticker) {
    const clean = String(ticker || '').trim().toUpperCase();
    const link = add(parent, 'a', 'v38-ticker-link v38-rot-ticker', clean || '—');
    if (clean) {
      link.href = 'https://www.tradingview.com/chart/?symbol=' + encodeURIComponent(clean);
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      link.dataset.v38Ticker = clean;
    }
    return link;
  }

  function findCard(section, title) {
    if (!section) return null;
    return Array.from(section.querySelectorAll('.card')).find((card) => {
      const original = String(card.dataset.v38CardTitle || '');
      const heading = card.querySelector('h2, .hdr h2, .chd h2');
      const current = heading ? String(heading.textContent || '') : '';
      return original.includes(title) || current.includes(title);
    }) || null;
  }

  function header(card, title, subtitle) {
    card.replaceChildren();
    const hd = add(card, 'div', 'v38-rot-head', '');
    add(hd, 'h2', '', title);
    if (subtitle) add(card, 'div', 'sub v38-rot-sub', subtitle);
    return hd;
  }

  function note(card, text) {
    add(card, 'div', 'v38-rot-note', text);
  }

  function injectStyle() {
    if (document.getElementById('v38-detail-restore-style')) return;
    const style = document.createElement('style');
    style.id = 'v38-detail-restore-style';
    style.textContent = `
      .v38-vix-conditions{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:6px;margin:9px 0 8px}
      .v38-vix-condition{border:1px solid rgba(27,29,28,.10);border-radius:8px;padding:7px 6px;background:rgba(27,29,28,.025);min-width:0}
      .v38-vix-condition b{display:block;font-size:10px;letter-spacing:.02em;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
      .v38-vix-condition span{display:block;font-size:9px;color:#575242;margin-top:2px;white-space:nowrap}
      .v38-vix-condition.on{background:rgba(39,117,84,.10);border-color:rgba(39,117,84,.30)}
      .v38-vix-condition.on b{color:#1f6d4c}.v38-vix-condition.current{box-shadow:inset 0 0 0 1px rgba(44,105,201,.28)}
      .v38-vix-condition.rearm.on{background:rgba(44,105,201,.08);border-color:rgba(44,105,201,.26)}
      .v38-vix-condition.rearm.on b{color:#315f9f}
      .v38-rot-head{display:flex;justify-content:space-between;align-items:baseline;gap:8px}.v38-rot-head h2{margin:0}
      .v38-rot-sub{margin-top:3px}.v38-rot-note{font-size:9.5px;color:#575242;line-height:1.45;margin-top:8px;padding-top:6px;border-top:1px solid rgba(27,29,28,.07)}
      .v38-rot-table-wrap{overflow-x:auto;-webkit-overflow-scrolling:touch;margin-top:7px}.v38-rot-table{width:100%;border-collapse:collapse;font-size:10.5px;min-width:520px}
      .v38-rot-table th{font-size:9px;color:#575242;text-align:right;padding:5px 5px;border-bottom:1px solid rgba(27,29,28,.10);white-space:nowrap}.v38-rot-table th:first-child{text-align:left}
      .v38-rot-table td{padding:6px 5px;border-bottom:1px solid rgba(27,29,28,.055);text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}.v38-rot-table td:first-child{text-align:left;font-weight:700;color:#2b2925}
      .v38-rot-up{color:#1f734c;font-weight:800}.v38-rot-down{color:#a43b36;font-weight:800}.v38-rot-flat{color:#68645b}
      .v38-rot-flow{margin-top:10px}.v38-rot-flow-title{display:flex;justify-content:space-between;gap:8px;align-items:baseline;font-size:10px;color:#575242;margin-bottom:4px}.v38-rot-flow-title b{font-size:11px;color:#34322e}
      .v38-rot-flow svg{width:100%;height:210px;display:block;background:rgba(27,29,28,.018);border-radius:8px}
      .v38-fine-list{display:grid;gap:6px;margin-top:7px}.v38-fine-row{padding:8px 9px;border-radius:8px;background:rgba(27,29,28,.028);border:1px solid rgba(27,29,28,.045)}
      .v38-fine-top{display:grid;grid-template-columns:minmax(0,1fr) repeat(4,auto);gap:7px;align-items:baseline}.v38-fine-name{font-size:11px;font-weight:800;min-width:0}.v38-fine-name small{display:block;color:#575242;font-size:8.5px;font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;margin-top:1px}.v38-fine-metric{font-size:9px;text-align:right;color:#575242}.v38-fine-metric b{display:block;font-size:11px;color:#2b2925}
      .v38-fine-leaders{display:flex;gap:5px;align-items:center;flex-wrap:wrap;margin-top:5px}.v38-fine-leaders>span{font-size:8.5px;color:#575242}.v38-rot-ticker{font-size:10px;font-weight:800;text-decoration:none;color:#2c69c9;border-radius:5px;background:rgba(44,105,201,.07);padding:1px 5px}
      .v38-major-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px;margin-top:7px}.v38-major-cell{border-radius:8px;border:1px solid rgba(27,29,28,.06);padding:8px 9px;background:rgba(27,29,28,.025)}.v38-major-cell.hot{background:rgba(39,117,84,.09)}.v38-major-cell.cold{background:rgba(164,59,54,.065)}
      .v38-major-cell b{display:block;font-size:10.5px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.v38-major-cell .v{font-size:17px;font-weight:850;margin-top:2px}.v38-major-cell small{display:block;font-size:8.5px;color:#575242;margin-top:2px;line-height:1.35}
      .v38-money{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px;margin-top:9px}.v38-money>div{padding:7px 8px;border-radius:7px;background:rgba(27,29,28,.025);border:1px solid rgba(27,29,28,.05)}.v38-money span{display:block;font-size:8.5px;color:#575242}.v38-money b{display:block;font-size:13px;margin-top:2px}
      .v38-period-leaders{margin-top:9px}.v38-period-leaders>div{display:grid;grid-template-columns:42px minmax(0,1fr);gap:6px;align-items:start;padding:4px 0;border-bottom:1px solid rgba(27,29,28,.045)}.v38-period-leaders>div>span{font-size:9px;font-weight:800;color:#575242}.v38-period-leaders .links{display:flex;gap:4px;flex-wrap:wrap}
      @media(max-width:620px){.v38-vix-conditions{grid-template-columns:repeat(2,minmax(0,1fr))}.v38-vix-condition:last-child{grid-column:1/-1}.v38-fine-top{grid-template-columns:minmax(0,1fr) repeat(2,auto)}.v38-fine-metric.hide-mobile{display:none}.v38-major-grid{grid-template-columns:1fr}.v38-money{grid-template-columns:1fr 1fr}.v38-rot-flow svg{height:190px}}
    `;
    document.head.appendChild(style);
  }

  function vixProgress(state) {
    const order = ['EVENT', 'ROLLOVER', 'BOTTOM', 'RE-EXTREME'];
    const index = order.indexOf(state);
    return {
      EVENT: index >= 0,
      ROLLOVER: index >= 1,
      BOTTOM: index >= 2,
      'RE-EXTREME': state === 'RE-EXTREME',
      REARM: state === 'NORMAL'
    };
  }

  function renderVixConditions(view) {
    const market = document.getElementById('t-market');
    const card = findCard(market, 'VIX反転シーケンス');
    const payload = view && view.daily && view.daily.vix_fear_cycle;
    if (!card || !payload || payload.status !== 'READY') return;
    const existing = card.querySelector('.v38-vix-conditions');
    if (existing) existing.remove();
    const values = payload.current || {};
    const high = finite(values.high), p1 = finite(values.plus1_sigma), p2 = finite(values.plus2_sigma);
    const state = String(payload.state || 'NORMAL').toUpperCase();
    const reached = vixProgress(state);
    const conditions = [
      ['EVENT', 'High ≥ +2σ', reached.EVENT, high !== null && p2 !== null && high >= p2],
      ['ROLLOVER', 'EVENT後 LWMA5↓', reached.ROLLOVER, state === 'ROLLOVER'],
      ['BOTTOM', 'LWMA5 < LWMA10', reached.BOTTOM, state === 'BOTTOM'],
      ['RE-EXTREME', 'BOTTOM後 +2σ', reached['RE-EXTREME'], state === 'RE-EXTREME'],
      ['REARM', 'High ≤ +1σ', reached.REARM, high !== null && p1 !== null && high <= p1]
    ];
    const box = document.createElement('div');
    box.className = 'v38-vix-conditions';
    box.setAttribute('aria-label', 'VIX Fear Cycle current sequence conditions');
    conditions.forEach((item) => {
      const cell = add(box, 'div', 'v38-vix-condition' + (item[2] ? ' on' : '') + (item[3] ? ' current' : '') + (item[0] === 'REARM' ? ' rearm' : ''), '');
      add(cell, 'b', '', item[0]);
      add(cell, 'span', '', item[2] ? (item[0] === 'REARM' ? '再武装済' : '到達済') : '未到達');
      cell.title = item[1];
      cell.dataset.v38Condition = item[0];
      cell.dataset.v38Reached = item[2] ? 'true' : 'false';
      cell.dataset.v38CurrentTrigger = item[3] ? 'true' : 'false';
    });
    const anchor = card.querySelector('.v38-vix-values');
    if (anchor && anchor.nextSibling) card.insertBefore(box, anchor.nextSibling); else if (anchor) anchor.after(box); else card.prepend(box);
  }

  function returnOver(series, sessions) {
    const rows = Array.isArray(series) ? series.filter((row) => finite(row && row.close) !== null) : [];
    if (rows.length <= sessions) return null;
    const latest = finite(rows[rows.length - 1].close), prior = finite(rows[rows.length - 1 - sessions].close);
    return latest !== null && prior !== null && prior > 0 ? latest / prior - 1 : null;
  }

  function sectorRows(view) {
    const seriesMap = view && view.daily && view.daily.market_series || {};
    const rows = SECTOR_ETFS.map((spec) => {
      const row = {ticker: spec[0], label: spec[1], returns: {}, scores: {}, ranks: {}};
      PERIODS.forEach((period) => { row.returns[period] = returnOver(seriesMap[spec[0]], period); });
      return row;
    });
    PERIODS.forEach((period) => {
      const valid = rows.filter((row) => finite(row.returns[period]) !== null).sort((a, b) => b.returns[period] - a.returns[period]);
      valid.forEach((row, index) => {
        row.ranks[period] = index + 1;
        row.scores[period] = valid.length <= 1 ? 50 : 100 * (valid.length - 1 - index) / (valid.length - 1);
      });
    });
    return rows;
  }

  function rankDelta(row, period) {
    const current = finite(row.ranks[period]), longRank = finite(row.ranks[189]);
    if (current === null || longRank === null) return null;
    return longRank - current;
  }

  function deltaText(delta) {
    if (delta === null) return '—';
    if (delta > 0) return '▲' + delta;
    if (delta < 0) return '▼' + Math.abs(delta);
    return '•0';
  }

  function drawRankFlow(host, rows) {
    const width = 760, height = 230, left = 86, right = 70, top = 26, bottom = 24;
    const xs = PERIODS.map((_, i) => left + (width - left - right) * i / (PERIODS.length - 1));
    const y = (rank) => top + (height - top - bottom) * (Math.max(1, Math.min(SECTOR_ETFS.length, rank)) - 1) / (SECTOR_ETFS.length - 1);
    const ns = 'http://www.w3.org/2000/svg';
    const svg = document.createElementNS(ns, 'svg'); svg.setAttribute('viewBox', `0 0 ${width} ${height}`); svg.setAttribute('preserveAspectRatio', 'none');
    PERIODS.forEach((period, i) => {
      const line = document.createElementNS(ns, 'line'); line.setAttribute('x1', xs[i]); line.setAttribute('x2', xs[i]); line.setAttribute('y1', top); line.setAttribute('y2', height - bottom); line.setAttribute('stroke', '#ddd9d1'); line.setAttribute('stroke-width', '1'); svg.appendChild(line);
      const text = document.createElementNS(ns, 'text'); text.setAttribute('x', xs[i]); text.setAttribute('y', 14); text.setAttribute('text-anchor', 'middle'); text.setAttribute('font-size', '10'); text.setAttribute('fill', '#575242'); text.textContent = 'RS' + period; svg.appendChild(text);
    });
    const palette = ['#2c69c9','#2f7560','#b27a1f','#9b4c46','#675b86','#507b87','#7c6a48','#50704e','#8a6b7f','#6a7480','#8b6142'];
    rows.forEach((row, index) => {
      const points = PERIODS.map((p, i) => finite(row.ranks[p]) === null ? null : [xs[i], y(row.ranks[p])]).filter(Boolean);
      if (points.length < 2) return;
      const poly = document.createElementNS(ns, 'polyline'); poly.setAttribute('points', points.map((p) => p[0] + ',' + p[1]).join(' ')); poly.setAttribute('fill', 'none'); poly.setAttribute('stroke', palette[index % palette.length]); poly.setAttribute('stroke-width', row.ranks[21] <= 3 || row.ranks[189] <= 3 ? '2.2' : '1.1'); poly.setAttribute('stroke-opacity', row.ranks[21] <= 5 || row.ranks[189] <= 5 ? '.85' : '.38'); svg.appendChild(poly);
      const start = points[0], end = points[points.length - 1];
      const l = document.createElementNS(ns, 'text'); l.setAttribute('x', left - 5); l.setAttribute('y', start[1] + 3); l.setAttribute('text-anchor', 'end'); l.setAttribute('font-size', '8.5'); l.setAttribute('fill', palette[index % palette.length]); l.textContent = row.label; svg.appendChild(l);
      const r = document.createElementNS(ns, 'text'); r.setAttribute('x', width - right + 5); r.setAttribute('y', end[1] + 3); r.setAttribute('font-size', '8.5'); r.setAttribute('fill', palette[index % palette.length]); r.textContent = row.label; svg.appendChild(r);
    });
    host.replaceChildren(svg);
  }

  function renderMajor(card, view, rows) {
    if (!card || !rows.length) return;
    header(card, '主導セクター・業種 Leading Groups', '大分類 — 期間ごとランキング / Major Sectors · Rank by Period');
    const wrap = add(card, 'div', 'v38-rot-table-wrap', '');
    const table = add(wrap, 'table', 'v38-rot-table', '');
    const thead = add(table, 'thead', '', ''); const hr = add(thead, 'tr', '', '');
    ['Sector','RS21','RS63','RS126','RS189','Δ vs 189'].forEach((h) => add(hr, 'th', '', h));
    const body = add(table, 'tbody', '', '');
    rows.slice().sort((a, b) => (a.ranks[21] || 999) - (b.ranks[21] || 999)).forEach((row) => {
      const tr = add(body, 'tr', '', '');
      const name = add(tr, 'td', '', row.label + ' '); tickerLink(name, row.ticker);
      PERIODS.forEach((p) => add(tr, 'td', '', finite(row.scores[p]) === null ? '—' : row.scores[p].toFixed(0)));
      const delta = rankDelta(row, 21); const td = add(tr, 'td', delta > 0 ? 'v38-rot-up' : delta < 0 ? 'v38-rot-down' : 'v38-rot-flat', deltaText(delta));
      td.title = 'RS21 rank vs RS189 rank';
    });
    const flow = add(card, 'div', 'v38-rot-flow', '');
    const ft = add(flow, 'div', 'v38-rot-flow-title', ''); add(ft, 'b', '', '順位推移（大分類） Rank Flow'); add(ft, 'span', '', 'RS21 → RS189（1=上位）');
    const svgHost = add(flow, 'div', '', ''); drawRankFlow(svgHost, rows);
    note(card, '11セクターETFの取得済み終値から各期間騰落率を算出し、当日横断でRS percentile化。観察表示で、Core 12のEligibility/Rankingには使用しません。');
    card.dataset.v38RotationRestore = 'major-rank-flow';
  }

  function renderFine(card, rotation) {
    if (!card) return;
    const groups = Array.isArray(rotation && rotation.fine_theme_groups) ? rotation.fine_theme_groups.slice(0, 6) : [];
    header(card, '強い業種の主導株 Leaders in Strong Groups', '細分類 — Sub-theme RS Rank / 上位6テーマと構成リーダー');
    const list = add(card, 'div', 'v38-fine-list', '');
    groups.forEach((row, index) => {
      const item = add(list, 'div', 'v38-fine-row', '');
      const top = add(item, 'div', 'v38-fine-top', '');
      const name = add(top, 'div', 'v38-fine-name', (index + 1) + '. ' + String(row.group || '—'));
      add(name, 'small', '', String(row.major_theme || '') + ' • ' + String(row.member_count || 0) + '銘柄');
      [['Theme RS', row.theme_rs, ''], ['RS63', row.rs63_avg, ''], ['RS189', row.rs189_avg, 'hide-mobile']].forEach((spec) => {
        const metric = add(top, 'div', 'v38-fine-metric ' + spec[2], ''); add(metric, 'span', '', spec[0]); add(metric, 'b', '', score(spec[1]));
      });
      const mom = add(top, 'div', 'v38-fine-metric hide-mobile', ''); add(mom, 'span', '', '20D'); add(mom, 'b', '', pct(row.ret20_avg));
      const leaders = add(item, 'div', 'v38-fine-leaders', ''); add(leaders, 'span', '', 'Leaders');
      (Array.isArray(row.leaders) ? row.leaders.slice(0, 5) : []).forEach((ticker) => tickerLink(leaders, ticker));
    });
    if (!groups.length) add(card, 'div', 'sub', 'Fine Themeデータ未取得');
    note(card, 'Fine Themeは復旧済みテーマ分類。表示中のリーダーはRS189≥85かつ200MA上を優先。Themeは観察・加点情報で、単独ハードゲートではありません。');
    card.dataset.v38RotationRestore = 'fine-theme-leaders';
  }

  function latestDiagnostic(view) {
    const series = view && view.daily && view.daily.market_diagnostics && view.daily.market_diagnostics.series;
    return Array.isArray(series) && series.length ? series[series.length - 1] : null;
  }

  function periodLeaders(view) {
    const out = {};
    const ret20 = view && view.daily && view.daily.leader_diagnostics && view.daily.leader_diagnostics.top_ret20;
    out[21] = (Array.isArray(ret20) ? ret20 : []).slice(0, 5).map((row) => row && row.ticker).filter(Boolean);
    const windows = view && view.rs && view.rs.windows || {};
    [63,126,189].forEach((p) => { out[p] = (Array.isArray(windows[String(p)]) ? windows[String(p)] : []).slice(0,5).map((row) => row && row.ticker).filter(Boolean); });
    return out;
  }

  function renderHeatMoney(card, view) {
    if (!card) return;
    const rotation = view.rotation || {};
    const majors = Array.isArray(rotation.major_theme_groups) ? rotation.major_theme_groups.slice(0, 10) : [];
    header(card, 'セクター温度マップ Sector Heatmap', 'Major Themeの現在強度 + Money Flow / 期間別リーダー');
    const grid = add(card, 'div', 'v38-major-grid', '');
    majors.forEach((row) => {
      const themeRs = finite(row.theme_rs), ret20 = finite(row.ret20_avg);
      const cell = add(grid, 'div', 'v38-major-cell' + (themeRs !== null && themeRs >= 70 ? ' hot' : themeRs !== null && themeRs <= 30 ? ' cold' : ''), '');
      add(cell, 'b', '', String(row.group || '—'));
      add(cell, 'div', 'v', themeRs !== null ? themeRs.toFixed(1) : '—');
      add(cell, 'small', '', 'RS63 ' + score(row.rs63_avg) + ' / RS189 ' + score(row.rs189_avg) + ' / 20D ' + pct(ret20));
    });
    const diag = latestDiagnostic(view) || {};
    const adv = finite(diag.advance_count), dec = finite(diag.decline_count), up = finite(diag.advance_dollar_volume), down = finite(diag.decline_dollar_volume), ratio = finite(diag.up_down_dollar_ratio);
    const money = add(card, 'div', 'v38-money', '');
    let m = add(money, 'div', '', ''); add(m, 'span', '', 'Dollar-Vol (Adv+Dec)'); add(m, 'b', '', up === null && down === null ? '—' : compactDollar((up || 0) + (down || 0)));
    m = add(money, 'div', '', ''); add(m, 'span', '', 'Up/Down $Vol'); add(m, 'b', '', ratio === null ? '—' : ratio.toFixed(2));
    m = add(money, 'div', '', ''); add(m, 'span', '', 'Breadth (Adv/Dec)'); add(m, 'b', '', adv === null || dec === null ? '—' : adv.toFixed(0) + '/' + dec.toFixed(0));
    const leaders = periodLeaders(view); const leaderBox = add(card, 'div', 'v38-period-leaders', '');
    [21,63,126,189].forEach((p) => { const row = add(leaderBox, 'div', '', ''); add(row, 'span', '', 'RS' + p); const links = add(row, 'div', 'links', ''); (leaders[p] || []).forEach((ticker) => tickerLink(links, ticker)); });
    note(card, 'Money Flowは現行Universeの実測集計。RS21欄は20営業日リターン上位、RS63/126/189は各RSランキング上位。');
    card.dataset.v38RotationRestore = 'heat-money-flow';
  }

  function renderEtf(card, rows) {
    if (!card) return;
    header(card, 'セクターETF強弱 Sector ETF Strength', '11セクターETF — 期間別の実測騰落率と順位');
    const wrap = add(card, 'div', 'v38-rot-table-wrap', ''); const table = add(wrap, 'table', 'v38-rot-table', '');
    const thead = add(table, 'thead', '', ''), hr = add(thead, 'tr', '', ''); ['ETF','21D','63D','126D','189D','21D順位'].forEach((h)=>add(hr,'th','',h));
    const body = add(table, 'tbody', '', '');
    rows.slice().sort((a,b)=>(a.ranks[21]||999)-(b.ranks[21]||999)).forEach((row)=>{
      const tr=add(body,'tr','',''); const name=add(tr,'td','',row.label+' ');tickerLink(name,row.ticker);
      PERIODS.forEach((p)=>{const v=finite(row.returns[p]);add(tr,'td',v>0?'v38-rot-up':v<0?'v38-rot-down':'v38-rot-flat',pct(v));}); add(tr,'td','',finite(row.ranks[21])===null?'—':'#'+row.ranks[21]);
    });
    note(card, '価格データはDailyタブと同じ取得済みcompleted daily bars。推測値ではありません。');
    card.dataset.v38RotationRestore = 'sector-etf-strength';
  }

  function renderRotation(view) {
    const section = document.getElementById('t-rotation');
    const rotation = view && view.rotation;
    if (!section || !rotation) return;
    const rows = sectorRows(view);
    renderMajor(findCard(section, '主導セクター・業種'), view, rows);
    renderFine(findCard(section, '強い業種の主導株'), rotation);
    renderHeatMoney(findCard(section, 'セクター温度マップ'), view);
    renderEtf(findCard(section, 'セクターETF強弱'), rows);
    section.dataset.v38RotationRestoreStatus = 'ready';
  }

  async function loadView() {
    const runtime = window.V38Runtime;
    if (runtime && typeof runtime.loadJson === 'function') return runtime.loadJson('data/ui_view_model.json');
    const response = await fetch('data/ui_view_model.json', {cache: 'no-store'});
    if (!response.ok) throw new Error('ui_view_model unavailable');
    return response.json();
  }

  async function apply() {
    if (running) return;
    running = true;
    try {
      injectStyle();
      const view = await loadView();
      renderVixConditions(view);
      renderRotation(view);
      document.body.dataset.v38DetailRestoreStatus = 'ready';
    } catch (_) {
      document.body.dataset.v38DetailRestoreStatus = 'failed';
    } finally {
      running = false;
    }
  }

  function start() {
    apply();
    [450, 1400, 2100, 2800, 3600, 4300].forEach((ms) => window.setTimeout(apply, ms));
    document.addEventListener('v38:data-ready', apply);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, {once: true}); else start();
})();
