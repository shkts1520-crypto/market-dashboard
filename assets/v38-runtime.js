(function (global) {
  'use strict';

  const REQUIRED_META = [
    'session_date', 'generated_at', 'coverage', 'source',
    'schema_version', 'calculation_version'
  ];
  const TICKER_RE = /^[A-Z][A-Z0-9.\-]{0,9}$/;

  function missing(value) {
    return value === null ||
      value === undefined ||
      value === '' ||
      (typeof value === 'number' && !Number.isFinite(value));
  }

  function display(value, decimals) {
    if (missing(value)) return '—';
    if (typeof value === 'number' && Number.isInteger(decimals)) {
      return value.toFixed(decimals);
    }
    return String(value);
  }

  function assessShard(obj, targetSession) {
    if (!obj || typeof obj !== 'object' || Array.isArray(obj)) {
      return {status: 'DATA_REQUIRED', reason: 'EXPECTED_JSON_OBJECT'};
    }
    const absent = REQUIRED_META.filter((key) => !(key in obj));
    if (absent.length) {
      return {status: 'DATA_REQUIRED', reason: 'MISSING_METADATA', missing: absent};
    }
    if (obj.session_date !== targetSession) {
      return {
        status: 'STALE', reason: 'SESSION_MISMATCH',
        session_date: obj.session_date
      };
    }
    return {status: 'READY', reason: 'CURRENT_SESSION'};
  }

  async function loadJson(path) {
    const response = await fetch(path, {cache: 'no-store'});
    if (!response.ok) throw new Error('HTTP ' + response.status + ' for ' + path);
    return response.json();
  }

  function appendExtension(src, name) {
    const script = document.createElement('script');
    script.src = src;
    script.async = false;
    script.dataset.v38Extension = name;
    document.head.appendChild(script);
  }

  function loadDisplayExtensions() {
    appendExtension('assets/v38-observables.js', 'observables');
    appendExtension('assets/v38-polish.js', 'polish');
    appendExtension('assets/v38-final-ui.js', 'final-ui');
  }

  function finite(value) {
    const number = Number(value);
    return value === null || value === undefined || value === '' || !Number.isFinite(number) ? null : number;
  }

  function pct(value) {
    const number = finite(value);
    if (number === null) return '—';
    return (number > 0 ? '+' : '') + (number * 100).toFixed(1) + '%';
  }

  function num(value, digits) {
    const number = finite(value);
    return number === null ? '—' : number.toLocaleString(undefined, {
      minimumFractionDigits: digits === undefined ? 1 : digits,
      maximumFractionDigits: digits === undefined ? 1 : digits
    });
  }

  function ticker(value) {
    const text = String(value || '').trim().toUpperCase();
    return TICKER_RE.test(text) ? text : null;
  }

  function card(sectionId, titlePart, index) {
    const section = document.getElementById(sectionId);
    if (!section) return null;
    const cards = Array.from(section.querySelectorAll('.card'));
    if (Number.isInteger(index)) return cards[index] || null;
    return cards.find((node) => {
      const original = String(node.dataset.v38CardTitle || '');
      const h2 = node.querySelector('h2');
      return original.includes(titlePart) || (h2 && h2.textContent.includes(titlePart));
    }) || null;
  }

  function readyCard(node, title, subtitle) {
    if (!node) return null;
    node.replaceChildren();
    node.dataset.v38Status = 'READY';
    const h2 = document.createElement('h2');
    h2.textContent = title;
    node.appendChild(h2);
    if (subtitle) {
      const sub = document.createElement('div');
      sub.className = 'sub';
      sub.textContent = subtitle;
      node.appendChild(sub);
    }
    return node;
  }

  function kv(parent, label, value) {
    const row = document.createElement('div');
    row.className = 'v38-live-kv';
    const left = document.createElement('span');
    const right = document.createElement('b');
    left.textContent = label;
    right.textContent = value === null || value === undefined || value === '' ? '—' : String(value);
    row.appendChild(left);
    row.appendChild(right);
    parent.appendChild(row);
  }

  function tickerLink(value) {
    const symbol = ticker(value);
    const link = document.createElement('a');
    link.className = 'v38-ticker-link';
    link.textContent = symbol || String(value || '—');
    if (symbol) {
      link.href = 'https://www.tradingview.com/chart/?symbol=' + encodeURIComponent(symbol);
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      link.dataset.v38Ticker = symbol;
    }
    return link;
  }

  function tickerRows(parent, rows, describe, limit) {
    const list = document.createElement('div');
    list.className = 'rsc-list';
    parent.appendChild(list);
    const values = Array.isArray(rows) ? rows : [];
    values.slice(0, limit || 20).forEach((row, index) => {
      const item = document.createElement('div');
      item.className = 'rsx-item';
      const symbol = ticker(row && (row.ticker || row.symbol));
      if (symbol) item.dataset.v38Ticker = symbol;
      const top = document.createElement('div');
      top.className = 'rsx-row';
      const rank = document.createElement('span');
      rank.className = 'rsx-rk';
      rank.textContent = String(index + 1);
      const name = document.createElement('div');
      name.className = 'rsx-name';
      name.appendChild(tickerLink(symbol));
      top.appendChild(rank);
      top.appendChild(name);
      item.appendChild(top);
      const text = describe ? describe(row || {}) : '';
      if (text) {
        const sub = document.createElement('div');
        sub.className = 'rsx-sub';
        sub.textContent = text;
        item.appendChild(sub);
      }
      list.appendChild(item);
    });
    if (values.length > (limit || 20)) {
      const more = document.createElement('div');
      more.className = 'mut';
      more.textContent = '表示 ' + String(limit || 20) + ' / ' + String(values.length) + '件';
      parent.appendChild(more);
    }
  }

  function metrics(daily) {
    const out = {};
    (daily && Array.isArray(daily.metrics) ? daily.metrics : []).forEach((row) => {
      if (row && typeof row.key === 'string') out[row.key] = row;
    });
    return out;
  }

  function metricText(map, key) {
    const row = map[key];
    return row && row.status === 'READY' ? String(row.display || '—') : '—';
  }

  function spark(parent, points) {
    const values = (Array.isArray(points) ? points : []).map((point) => ({
      date: point && point.date,
      value: finite(point && (point.value !== undefined ? point.value : point.close))
    })).filter((point) => point.date && point.value !== null);
    if (values.length < 2) return;
    const width = 680, height = 180, pad = 8;
    let low = Math.min.apply(null, values.map((point) => point.value));
    let high = Math.max.apply(null, values.map((point) => point.value));
    if (low === high) { low -= 1; high += 1; }
    const x = (index) => pad + (width - pad * 2) * index / Math.max(1, values.length - 1);
    const y = (value) => pad + (height - pad * 2) * (high - value) / (high - low);
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('class', 'spark v38-live-spark');
    svg.setAttribute('viewBox', '0 0 ' + width + ' ' + height);
    svg.setAttribute('preserveAspectRatio', 'none');
    const line = document.createElementNS(svg.namespaceURI, 'polyline');
    line.setAttribute('points', values.map((point, index) => x(index).toFixed(1) + ',' + y(point.value).toFixed(1)).join(' '));
    line.setAttribute('fill', 'none');
    line.setAttribute('stroke', '#1E7A4D');
    line.setAttribute('stroke-width', '2');
    svg.appendChild(line);
    parent.appendChild(svg);
  }

  function repairMc57(view) {
    const detail = view && view.daily && view.daily.mc57_detail;
    const node = card('t-market', 'MC57推移');
    const series = detail && detail.series && detail.series.mc57;
    if (!node || !detail || detail.status !== 'READY' || !Array.isArray(series) || !series.length) return;
    readyCard(node, 'MC57推移 Market Status History', '取得済み固定57ETF履歴。');
    const current = detail.current || {};
    kv(node, 'MC57', num(current.mc57, 1));
    kv(node, 'Raw', num(current.raw, 1));
    kv(node, 'EMA2 Raw', num(current.ema2_raw, 1));
    kv(node, 'Z', num(current.z, 2));
    const chart = document.createElement('div');
    chart.className = 'chart';
    node.appendChild(chart);
    spark(chart, series);
    node.dataset.v38HistoryPoints = String(series.length);
  }

  function repairOptions(options) {
    if (!options || options.status !== 'READY' || !options.buckets) return;
    [
      ['0–6 DTE Short Term', '0-6'],
      ['7–21 DTE Swing', '7-21'],
      ['22–45 DTE Medium Term', '22-45'],
      ['0–45 DTE Multi-expiry', '0-45']
    ].forEach((spec) => {
      const node = card('t-options', spec[0]);
      const rows = Array.isArray(options.buckets[spec[1]]) ? options.buckets[spec[1]] : [];
      if (!node || !rows.length) return;
      readyCard(node, spec[0], '実Optionsチェーン。Direction / Confidenceは推測せず表示しません。');
      const targets = options.target_policy && Array.isArray(options.target_policy.targets) ? options.target_policy.targets.length : rows.length;
      const good = rows.filter((row) => row && row.quality === 'GOOD').length;
      kv(node, '取得銘柄', String(rows.length) + ' / ' + String(targets));
      kv(node, 'Quality', 'GOOD ' + String(good) + ' / PARTIAL ' + String(rows.length - good));
      tickerRows(node, rows, (row) => 'Spot ' + num(row.spot, 2) + ' • Call ' + num(row.call_wall, 2) + ' • Put ' + num(row.put_wall, 2) + ' • Flip ' + num(row.gamma_flip, 2) + ' • EM ' + pct(row.expected_move_pct) + ' • ' + String(row.quality || '—'), 20);
      node.dataset.v38OptionBucket = spec[1];
      node.dataset.v38OptionRows = String(rows.length);
    });
  }

  function repairThemes(view) {
    const rotation = view && view.rotation;
    const rows = rotation && Array.isArray(rotation.fine_theme_rows) ? rotation.fine_theme_rows : [];
    const node = card('t-rotation', 'サブテーマ別RS');
    if (!node || !rotation || rotation.status !== 'READY' || !rows.length) return;
    readyCard(node, 'サブテーマ別RS（ユニバース内）', '取得済み細粒度Theme入力。');
    kv(node, 'Theme coverage', finite(rotation.fine_theme_coverage) === null ? '—' : (finite(rotation.fine_theme_coverage) * 100).toFixed(1) + '%');
    const list = document.createElement('div');
    list.className = 'bglist';
    node.appendChild(list);
    rows.slice(0, 20).forEach((row) => {
      const item = document.createElement('div');
      item.className = 'bgrow';
      const name = document.createElement('div');
      name.className = 'bgname';
      name.textContent = row.theme_name || row.theme_id || '—';
      const meta = document.createElement('div');
      meta.className = 'bgmeta';
      meta.textContent = 'Theme RS ' + num(row.theme_rs, 1) + ' • 1M中央値 ' + pct(row.ret20_median) + ' • RS63 ' + num(row.rs63_median, 1) + ' • ' + String(row.member_count || 0) + '銘柄';
      item.appendChild(name);
      item.appendChild(meta);
      const chips = document.createElement('div');
      chips.className = 'chips';
      (Array.isArray(row.leaders) ? row.leaders : []).slice(0, 5).forEach((value) => {
        const link = tickerLink(value);
        link.className += ' chip hot';
        chips.appendChild(link);
      });
      item.appendChild(chips);
      list.appendChild(item);
    });
    node.dataset.v38ThemeRows = String(rows.length);
  }

  function rsSet(windows, key) {
    return new Set((windows && Array.isArray(windows[key]) ? windows[key] : []).map((row) => ticker(row.ticker)).filter(Boolean));
  }

  function repairRs(view, history) {
    const rs = view && view.rs;
    if (!rs || rs.status !== 'READY') return;
    const windows = rs.windows || {};
    const a = rsSet(windows, '63'), b = rsSet(windows, '126'), c = rsSet(windows, '189');
    const triple = Array.from(a).filter((value) => b.has(value) && c.has(value));
    let node = card('t-rs', 'RSマルチタイムフレーム比較');
    if (node) {
      readyCard(node, 'RSマルチタイムフレーム比較', '取得済みRS63 / RS126 / RS189 Top10の重複。');
      kv(node, 'RS63 Top10', String(a.size) + '銘柄');
      kv(node, 'RS126 Top10', String(b.size) + '銘柄');
      kv(node, 'RS189 Top10', String(c.size) + '銘柄');
      kv(node, '三窓Top10一致', String(triple.length) + '銘柄');
      const chips = document.createElement('div');
      chips.className = 'chips';
      triple.forEach((value) => chips.appendChild(tickerLink(value)));
      node.appendChild(chips);
    }
    node = card('t-rs', '三窓一致リーダー');
    if (node) {
      readyCard(node, '三窓一致リーダー', 'RS63 / 126 / 189のTop10すべてに入る銘柄。');
      triple.forEach((value) => {
        const line = document.createElement('div');
        line.className = 'slrow';
        line.appendChild(tickerLink(value));
        node.appendChild(line);
      });
      if (!triple.length) kv(node, '一致銘柄', '0');
    }
    const snapshots = history && Array.isArray(history.snapshots) ? history.snapshots : [];
    node = card('t-rs', 'Top10 IN / OUT履歴');
    if (node && history && history.status === 'READY' && snapshots.length >= 2) {
      const latest = snapshots[snapshots.length - 1], previous = snapshots[snapshots.length - 2];
      const latestRows = latest.windows && latest.windows['189'] || [];
      const previousRows = previous.windows && previous.windows['189'] || [];
      const latestSet = new Set(latestRows.slice(0, 10).map((row) => ticker(row.ticker)).filter(Boolean));
      const previousSet = new Set(previousRows.slice(0, 10).map((row) => ticker(row.ticker)).filter(Boolean));
      const entered = Array.from(latestSet).filter((value) => !previousSet.has(value));
      const exited = Array.from(previousSet).filter((value) => !latestSet.has(value));
      readyCard(node, 'Top10 IN / OUT履歴', 'RS189 Top10の直近2観測日比較（表示用再構築履歴）。');
      kv(node, '比較', String(previous.date || '—') + ' → ' + String(latest.date || '—'));
      kv(node, 'IN', entered.join(', ') || 'なし');
      kv(node, 'OUT', exited.join(', ') || 'なし');
    }
  }

  function repairCore(view) {
    const core = view && view.core12;
    if (!core || core.status !== 'READY') return;
    const rows = Array.isArray(core.rows) ? core.rows : [];
    const map = metrics(view.daily || {});
    let node = card('t-port', 'レジーム警戒灯');
    if (node) {
      readyCard(node, 'レジーム警戒灯 Regime Early-Warning', '取得済みCurrent Session正本値。');
      kv(node, 'Market Mode', metricText(map, 'market_mode'));
      kv(node, 'NQSAR', metricText(map, 'nqsar'));
      kv(node, 'Breadth 50MA', metricText(map, 'breadth50'));
      kv(node, 'MC57', metricText(map, 'mc57'));
      kv(node, '新規上限', core.max_new_total_slots === null || core.max_new_total_slots === undefined ? '—' : core.max_new_total_slots);
    }
    node = card('t-port', '', 1);
    if (node && rows.length) {
      readyCard(node, '流動性 / DDV20', 'Core12 rankingの取得済みDDV20分布。');
      [10, 20, 50].forEach((million) => kv(node, '≥$' + million + 'M', rows.filter((row) => finite(row.ddv20) !== null && finite(row.ddv20) >= million * 1000000).length + ' / ' + rows.length));
    }
    node = card('t-port', 'RSリーダー控え');
    if (node && rows.length > 12) {
      readyCard(node, 'RSリーダー控え Bench', '現行Core12 ranking 13–24位。採用ポジションではありません。');
      tickerRows(node, rows.slice(12, 24), (row) => 'RS189 ' + num(row.rs189, 1) + ' • Final ' + num(row.final_score, 1) + ' • DDV20 $' + num((finite(row.ddv20) || 0) / 1000000, 1) + 'M', 12);
    }
  }

  function repairPositions(view) {
    const positions = view && view.positions;
    const core = view && view.core12;
    if (!positions || positions.status !== 'READY' || !Array.isArray(positions.rows) || positions.rows.length || !String(positions.source || '').includes('user-confirmed-empty')) return;
    let node = card('t-alloc', '現在の想定ポジション');
    if (node) {
      readyCard(node, '現在の想定ポジション Current Expected 12', 'Positionsはユーザー指定EMPTY。保有を捏造しません。');
      kv(node, 'Current holdings', '0');
      kv(node, 'Market Mode', core && core.market_mode || '—');
      kv(node, '新規枠', core && core.max_new_total_slots !== undefined ? core.max_new_total_slots : '—');
    }
    node = card('t-alloc', 'マーケット回復後のポジション入り銘柄');
    const ranking = core && Array.isArray(core.rows) ? core.rows.filter((row) => row.eligibility_status === 'ELIGIBLE').slice(0, 12) : [];
    if (node && ranking.length) {
      readyCard(node, 'マーケット回復後のポジション入り銘柄 Recovery Candidates', '現行Core12上位。現在の保有ではなく回復時の再評価候補。');
      tickerRows(node, ranking, (row) => 'Final ' + num(row.final_score, 1) + ' • RS189 ' + num(row.rs189, 1), 12);
    }
    node = card('t-alloc', 'エクイティカーブ');
    if (node) {
      readyCard(node, 'エクイティカーブ×21日EMA Equity Curve', 'Positionsが明示的EMPTYのため現在は対象外。');
      kv(node, 'Portfolio state', 'EMPTY');
      kv(node, 'Equity curve', '対象外（保有なし）');
    }
  }

  function repairWeekly(view) {
    const weekly = view && view.weekly;
    const daily = view && view.daily;
    if (!weekly || weekly.status !== 'READY' || !daily) return;
    const map = metrics(daily);
    const summaries = daily.market_summaries || {};
    let node = card('t-weekly', '今週の結論');
    if (node) {
      readyCard(node, '今週の結論 This Week', '取得済みWeekly NQSARとCurrent Session指標。');
      kv(node, 'NQSAR', weekly.state || '—');
      kv(node, 'Market Mode', metricText(map, 'market_mode'));
      kv(node, 'Breadth 50MA', metricText(map, 'breadth50'));
      kv(node, 'MC57', metricText(map, 'mc57'));
      kv(node, 'QQQ 1週', pct(summaries.QQQ && summaries.QQQ.change_1w));
    }
    const history = Array.isArray(daily.history) ? daily.history : [];
    node = card('t-weekly', '今週の変化');
    if (node && history.length >= 6) {
      const now = history[history.length - 1], before = history[history.length - 6];
      readyCard(node, '今週の変化 Weekly Diff', '直近5営業日前との取得済み指標比較。');
      [['Breadth50', 'breadth50'], ['Breadth200', 'breadth200'], ['F1', 'f1'], ['F2', 'f2'], ['F3', 'f3']].forEach((spec) => {
        const oldValue = finite(before[spec[1]]), newValue = finite(now[spec[1]]);
        kv(node, spec[0], oldValue === null || newValue === null ? '—' : num(oldValue, 1) + ' → ' + num(newValue, 1));
      });
    }
    const sectorTickers = ['XLB','XLC','XLE','XLF','XLI','XLK','XLP','XLRE','XLU','XLV','XLY'];
    const movers = sectorTickers.map((value) => ({ticker: value, change_1w: summaries[value] && summaries[value].change_1w})).filter((row) => finite(row.change_1w) !== null).sort((a, b) => b.change_1w - a.change_1w);
    node = card('t-weekly', '週次騰落ボード');
    if (node && movers.length) {
      readyCard(node, '週次騰落ボード Weekly Movers', '取得済みGICS11セクターETFの1週間騰落率。');
      tickerRows(node, movers, (row) => '1W ' + pct(row.change_1w), 11);
    }
    const positions = view.positions || {};
    node = card('t-weekly', '自分 vs QQQ円建て');
    if (node && positions.status === 'READY' && Array.isArray(positions.rows) && positions.rows.length === 0 && String(positions.source || '').includes('user-confirmed-empty')) {
      readyCard(node, '自分 vs QQQ円建て My Week', 'Positionsはユーザー指定EMPTY。架空の成績は作りません。');
      kv(node, 'My portfolio', '保有なし / 比較対象外');
      kv(node, 'QQQ 1週', pct(summaries.QQQ && summaries.QQQ.change_1w));
    }
  }

  async function repairPublishedCards() {
    if (!document.body || document.body.dataset.v38BindingStatus !== 'ready') return false;
    try {
      const view = await loadJson('data/ui_view_model.json');
      let options = null, history = null;
      try { options = await loadJson('data/options/index.json'); } catch (_) { options = null; }
      try { history = await loadJson('data/rs_history.json'); } catch (_) { history = null; }
      repairMc57(view);
      repairOptions(options);
      repairThemes(view);
      repairRs(view, history);
      repairCore(view);
      repairPositions(view);
      repairWeekly(view);
      document.body.dataset.v38DataRepairStatus = 'ready';
      return true;
    } catch (_) {
      document.body.dataset.v38DataRepairStatus = 'failed';
      return false;
    }
  }

  function schedulePublishedCardRepair() {
    let attempts = 0;
    const run = async () => {
      attempts += 1;
      const finalReady = document.body && document.body.dataset.v38FinalUiStatus === 'ready';
      if (finalReady && await repairPublishedCards()) return;
      if (attempts < 80) global.setTimeout(run, 75);
    };
    global.setTimeout(run, 75);
    global.setTimeout(repairPublishedCards, 1200);
    global.setTimeout(repairPublishedCards, 2400);
  }

  global.V38Runtime = Object.freeze({
    missing,
    display,
    assessShard,
    loadJson
  });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', loadDisplayExtensions, {once: true});
    document.addEventListener('DOMContentLoaded', schedulePublishedCardRepair, {once: true});
  } else {
    loadDisplayExtensions();
    schedulePublishedCardRepair();
  }
})(window);
