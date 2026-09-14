(function () {
  'use strict';

  const TICKER_RE = /^[A-Z][A-Z0-9.\-]{0,9}$/;
  const CARD_TEMPLATES = new WeakMap();
  let running = false;

  function canonicalTitleFromHeading(heading) {
    if (!heading) return '';
    const first = heading.childNodes && heading.childNodes.length ? heading.childNodes[0] : null;
    return first && first.textContent ? first.textContent.trim() : heading.textContent.trim();
  }

  function captureCanonicalCards() {
    document.querySelectorAll('section .card').forEach((card) => {
      const heading = card.querySelector('h2');
      if (!heading) return;
      const parent = heading.parentElement;
      CARD_TEMPLATES.set(card, {
        heading: heading.cloneNode(true),
        wrapperTag: parent && parent !== card ? parent.tagName.toLowerCase() : null,
        wrapperClass: parent && parent !== card ? parent.className : ''
      });
      card.dataset.v38CanonicalTitle = canonicalTitleFromHeading(heading);
    });
  }

  captureCanonicalCards();

  function finite(value) {
    if (value === null || value === undefined || value === '') return null;
    const number = Number(value);
    return Number.isFinite(number) ? number : null;
  }

  function num(value, digits) {
    const number = finite(value);
    if (number === null) return '—';
    const d = digits === undefined ? 1 : digits;
    return number.toLocaleString(undefined, {minimumFractionDigits: d, maximumFractionDigits: d});
  }

  function pct(value) {
    const number = finite(value);
    if (number === null) return '—';
    return (number > 0 ? '+' : '') + (number * 100).toFixed(1) + '%';
  }

  function cleanTicker(value) {
    const text = String(value || '').trim().toUpperCase();
    return TICKER_RE.test(text) ? text : null;
  }

  function cardByTitle(sectionId, titlePart) {
    const section = document.getElementById(sectionId);
    if (!section) return null;
    return Array.from(section.querySelectorAll('.card')).find((card) => {
      const canonical = String(card.dataset.v38CanonicalTitle || card.dataset.v38CardTitle || '');
      if (canonical.includes(titlePart)) return true;
      const template = CARD_TEMPLATES.get(card);
      return Boolean(template && template.heading && template.heading.textContent.includes(titlePart));
    }) || null;
  }

  function appendCanonicalHeading(card) {
    const template = CARD_TEMPLATES.get(card);
    if (!template || !template.heading) return null;
    const heading = template.heading.cloneNode(true);
    if (template.wrapperTag) {
      const wrapper = document.createElement(template.wrapperTag);
      wrapper.className = template.wrapperClass || '';
      wrapper.appendChild(heading);
      card.appendChild(wrapper);
    } else {
      card.appendChild(heading);
    }
    return heading;
  }

  function readyCard(card, bindingKey, subtitle) {
    if (!card) return null;
    card.replaceChildren();
    card.dataset.v38Status = 'READY';
    card.dataset.v38BindingKey = bindingKey;
    appendCanonicalHeading(card);
    if (subtitle) {
      const sub = document.createElement('div');
      sub.className = 'sub';
      sub.textContent = subtitle;
      card.appendChild(sub);
    }
    return card;
  }

  function unavailableCard(card, bindingKey, subtitle) {
    if (!card) return null;
    card.replaceChildren();
    card.dataset.v38Status = 'SOURCE_UNAVAILABLE';
    card.dataset.v38BindingKey = bindingKey;
    appendCanonicalHeading(card);
    if (subtitle) {
      const sub = document.createElement('div');
      sub.className = 'sub';
      sub.textContent = subtitle;
      card.appendChild(sub);
    }
    return card;
  }

  function restoreCanonicalHeading(card) {
    const template = CARD_TEMPLATES.get(card);
    if (!template || !template.heading) return;
    const current = card.querySelector('h2');
    if (!current) return;
    current.replaceWith(template.heading.cloneNode(true));
  }

  function restoreAllCanonicalHeadings() {
    document.querySelectorAll('section .card').forEach(restoreCanonicalHeading);
  }

  function kv(parent, label, value) {
    const row = document.createElement('div');
    row.className = 'v38-live-kv';
    const left = document.createElement('span');
    left.textContent = label;
    const right = document.createElement('b');
    right.textContent = value === null || value === undefined || value === '' ? '—' : String(value);
    row.appendChild(left);
    row.appendChild(right);
    parent.appendChild(row);
    return row;
  }

  function tickerLink(value, extraClass) {
    const symbol = cleanTicker(value);
    const link = document.createElement('a');
    link.className = 'v38-ticker-link v38-generic-ticker' + (extraClass ? ' ' + extraClass : '');
    link.textContent = symbol || String(value || '—');
    if (symbol) {
      link.href = 'https://www.tradingview.com/chart/?symbol=' + encodeURIComponent(symbol);
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      link.dataset.v38Ticker = symbol;
    }
    return link;
  }

  function addSub(parent, leftText, rightText) {
    const sub = document.createElement('div');
    sub.className = 'rsx-sub';
    const left = document.createElement('span');
    left.className = 'rsx-nums';
    left.textContent = leftText || '—';
    const right = document.createElement('span');
    right.className = 'rsx-ret';
    right.textContent = rightText || '—';
    sub.appendChild(left);
    sub.appendChild(right);
    parent.appendChild(sub);
  }

  function sourceRows(parent, rows, describe, score, limit, badgeText) {
    const values = Array.isArray(rows) ? rows : [];
    values.slice(0, limit || 20).forEach((row, index) => {
      const item = document.createElement('div');
      item.className = 'rsx-item';
      const symbol = cleanTicker(row && (row.ticker || row.symbol));
      if (symbol) item.dataset.v38Ticker = symbol;
      const top = document.createElement('div');
      top.className = 'rsx-row';
      const rank = document.createElement('span');
      rank.className = 'rsx-rk';
      rank.textContent = String(index + 1);
      const name = document.createElement('div');
      name.className = 'rsx-name';
      const line = document.createElement('div');
      line.appendChild(tickerLink(symbol));
      if (badgeText) {
        const badge = document.createElement('span');
        badge.className = 'rsx-badge sel';
        badge.textContent = typeof badgeText === 'function' ? badgeText(row || {}) : badgeText;
        line.appendChild(badge);
      }
      name.appendChild(line);
      const small = document.createElement('small');
      small.textContent = String((row && (row.theme_name || row.industry || row.sector || row.quality)) || '');
      if (small.textContent) name.appendChild(small);
      const scoreBox = document.createElement('div');
      scoreBox.className = 'rsx-score';
      const scoreValue = document.createElement('b');
      const scoreData = score ? score(row || {}) : null;
      scoreValue.textContent = scoreData && scoreData.value !== undefined ? String(scoreData.value) : '—';
      const scoreLabel = document.createElement('small');
      scoreLabel.textContent = scoreData && scoreData.label ? scoreData.label : '';
      scoreBox.appendChild(scoreValue);
      scoreBox.appendChild(scoreLabel);
      top.appendChild(rank);
      top.appendChild(name);
      top.appendChild(scoreBox);
      item.appendChild(top);
      const detail = describe ? describe(row || {}) : null;
      if (detail) addSub(item, detail.left, detail.right);
      parent.appendChild(item);
    });
  }

  function metricMap(daily) {
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
    const values = (Array.isArray(points) ? points : []).map((point) => {
      const value = finite(point && (point.value !== undefined ? point.value : point.close));
      return point && point.date && value !== null ? {date: point.date, value: value} : null;
    }).filter(Boolean);
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
    line.setAttribute('stroke', 'currentColor');
    line.setAttribute('stroke-width', '2');
    svg.appendChild(line);
    parent.appendChild(svg);
  }

  function repairMc57(view) {
    const detail = view && view.daily && view.daily.mc57_detail;
    const series = detail && detail.series && detail.series.mc57;
    const card = cardByTitle('t-market', 'MC57推移');
    if (!card || !detail || detail.status !== 'READY' || !Array.isArray(series) || !series.length) return;
    readyCard(card, 'daily-mc57-history', '取得済み固定57ETF履歴。');
    const current = detail.current || {};
    const row = document.createElement('div');
    row.className = 'eqrow';
    [['MC57', num(current.mc57, 1)], ['Raw', num(current.raw, 1)], ['EMA2 Raw', num(current.ema2_raw, 1)], ['Z', num(current.z, 2)]].forEach((item) => {
      const cell = document.createElement('span');
      cell.className = 'eqkv';
      cell.textContent = item[0] + ' ';
      const b = document.createElement('b');
      b.textContent = item[1];
      cell.appendChild(b);
      row.appendChild(cell);
    });
    card.appendChild(row);
    const chart = document.createElement('div');
    chart.className = 'chart';
    card.appendChild(chart);
    spark(chart, series);
    card.dataset.v38HistoryPoints = String(series.length);
  }

  function repairOptions(options) {
    if (!options || options.status !== 'READY' || !options.buckets) return;
    [
      ['0–6 DTE', '0-6'],
      ['7–21 DTE', '7-21'],
      ['22–45 DTE', '22-45'],
      ['0–45 DTE', '0-45']
    ].forEach((spec) => {
      const card = cardByTitle('t-options', spec[0]);
      const rows = Array.isArray(options.buckets[spec[1]]) ? options.buckets[spec[1]] : [];
      if (!card || !rows.length) return;
      readyCard(card, 'options-' + spec[1], '期間別の実Optionsチェーン。Direction / Confidenceは推測せず表示しません。');
      const targets = options.target_policy && Array.isArray(options.target_policy.targets) ? options.target_policy.targets.length : rows.length;
      const good = rows.filter((row) => row && row.quality === 'GOOD').length;
      const summary = document.createElement('div');
      summary.className = 'eqrow';
      card.appendChild(summary);
      [['取得銘柄', String(rows.length) + ' / ' + String(targets)], ['Quality', 'GOOD ' + String(good) + ' / PARTIAL ' + String(rows.length - good)]].forEach((item) => {
        const cell = document.createElement('span');
        cell.className = 'eqkv';
        cell.textContent = item[0] + ' ';
        const b = document.createElement('b');
        b.textContent = item[1];
        cell.appendChild(b);
        summary.appendChild(cell);
      });
      sourceRows(card, rows,
        (row) => ({
          left: 'Spot ' + num(row.spot, 2) + ' ・ Call / Flip / Put ' + [num(row.call_wall, 2), num(row.gamma_flip, 2), num(row.put_wall, 2)].join(' / '),
          right: 'Expected Move ' + pct(row.expected_move_pct) + ' ・ Quality ' + String(row.quality || '—')
        }),
        (row) => ({value: String(row.quality || '—'), label: 'Quality'}), 20);
      card.dataset.v38OptionBucket = spec[1];
      card.dataset.v38OptionRows = String(rows.length);
    });
  }

  function repairThemes(view) {
    const rotation = view && view.rotation;
    const rows = rotation && Array.isArray(rotation.fine_theme_rows) ? rotation.fine_theme_rows : [];
    const card = cardByTitle('t-rotation', 'サブテーマ別RS');
    if (!card || !rotation || rotation.status !== 'READY' || !rows.length) return;
    readyCard(card, 'rotation-subtheme-rs', '取得済み細粒度Theme入力。');
    const coverage = finite(rotation.fine_theme_coverage);
    kv(card, 'Theme coverage', coverage === null ? '—' : (coverage * 100).toFixed(1) + '%');
    const list = document.createElement('div');
    list.className = 'bglist';
    card.appendChild(list);
    rows.slice(0, 20).forEach((row) => {
      const item = document.createElement('div');
      item.className = 'bgrow';
      const name = document.createElement('div');
      name.className = 'bgname';
      name.textContent = row.theme_name || row.theme_id || '—';
      const meta = document.createElement('div');
      meta.className = 'bgmeta';
      const members = row.member_count === null || row.member_count === undefined ? '—' : String(row.member_count);
      meta.textContent = 'Theme RS ' + num(row.theme_rs, 1) + ' ・ 1M中央値 ' + pct(row.ret20_median) + ' ・ RS63 ' + num(row.rs63_median, 1) + ' ・ ' + members + '銘柄';
      item.appendChild(name);
      item.appendChild(meta);
      const chips = document.createElement('div');
      chips.className = 'chips';
      (Array.isArray(row.leaders) ? row.leaders : []).slice(0, 5).forEach((value) => chips.appendChild(tickerLink(value, 'chip hot')));
      item.appendChild(chips);
      list.appendChild(item);
    });
    card.dataset.v38ThemeRows = String(rows.length);
  }

  function rsSet(windows, key) {
    return new Set((windows && Array.isArray(windows[key]) ? windows[key] : []).map((row) => cleanTicker(row.ticker)).filter(Boolean));
  }

  function repairRs(view, history) {
    const rs = view && view.rs;
    if (!rs || rs.status !== 'READY') return;
    const windows = rs.windows || {};
    const a = rsSet(windows, '63');
    const b = rsSet(windows, '126');
    const c = rsSet(windows, '189');
    const triple = Array.from(a).filter((value) => b.has(value) && c.has(value));
    let card = cardByTitle('t-rs', 'RSマルチタイムフレーム比較');
    if (card) {
      readyCard(card, 'rs-multiframe', '取得済みRS63 / RS126 / RS189 Top10の重複。');
      kv(card, 'RS63 Top10', String(a.size) + '銘柄');
      kv(card, 'RS126 Top10', String(b.size) + '銘柄');
      kv(card, 'RS189 Top10', String(c.size) + '銘柄');
      kv(card, '三窓Top10一致', String(triple.length) + '銘柄');
      const chips = document.createElement('div');
      chips.className = 'chips';
      triple.forEach((value) => chips.appendChild(tickerLink(value)));
      card.appendChild(chips);
    }
    card = cardByTitle('t-rs', '三窓一致リーダー');
    if (card) {
      readyCard(card, 'rs-triple-leaders', 'RS63 / 126 / 189のTop10すべてに入る銘柄。');
      const chips = document.createElement('div');
      chips.className = 'chips';
      if (!triple.length) kv(card, '一致銘柄', '0');
      triple.forEach((value) => chips.appendChild(tickerLink(value)));
      if (triple.length) card.appendChild(chips);
    }
    const snapshots = history && Array.isArray(history.snapshots) ? history.snapshots : [];
    card = cardByTitle('t-rs', 'Top10 IN / OUT履歴');
    if (card && history && history.status === 'READY' && snapshots.length >= 2) {
      const latest = snapshots[snapshots.length - 1];
      const previous = snapshots[snapshots.length - 2];
      const latestRows = latest.windows && latest.windows['189'] || [];
      const previousRows = previous.windows && previous.windows['189'] || [];
      const latestSet = new Set(latestRows.slice(0, 10).map((row) => cleanTicker(row.ticker)).filter(Boolean));
      const previousSet = new Set(previousRows.slice(0, 10).map((row) => cleanTicker(row.ticker)).filter(Boolean));
      const entered = Array.from(latestSet).filter((value) => !previousSet.has(value));
      const exited = Array.from(previousSet).filter((value) => !latestSet.has(value));
      readyCard(card, 'rs-top10-in-out', 'RS189 Top10の直近2観測日比較（表示用再構築履歴）。');
      kv(card, '比較', String(previous.date || '—') + ' → ' + String(latest.date || '—'));
      kv(card, 'IN', entered.join(', ') || 'なし');
      kv(card, 'OUT', exited.join(', ') || 'なし');
    }
  }

  function renderCoreTable(card, rows, startRank, limit) {
    const table = document.createElement('table');
    const header = document.createElement('tr');
    ['#', '銘柄', 'RS189', 'RS63', '200MA乖離', 'DDV20'].forEach((label, index) => {
      const th = document.createElement('th');
      if (index < 2) th.className = 'l';
      th.textContent = label;
      header.appendChild(th);
    });
    table.appendChild(header);
    (Array.isArray(rows) ? rows : []).slice(0, limit || 12).forEach((row, index) => {
      const tr = document.createElement('tr');
      tr.dataset.v38Ddv20 = finite(row.ddv20) === null ? '' : String(row.ddv20);
      const symbol = cleanTicker(row.ticker || row.symbol);
      if (symbol) tr.dataset.v38Ticker = symbol;
      const rank = document.createElement('td');
      rank.className = 'l mut';
      rank.textContent = String((startRank || 1) + index);
      const tickerCell = document.createElement('td');
      tickerCell.className = 'l tk';
      tickerCell.appendChild(tickerLink(symbol));
      const badges = document.createElement('div');
      badges.className = 'rowbadges';
      const status = document.createElement('span');
      status.className = 'stb';
      status.textContent = String(row.eligibility_status || 'ELIGIBLE');
      badges.appendChild(status);
      tickerCell.appendChild(badges);
      const rs189 = document.createElement('td');
      rs189.className = 'rsc';
      rs189.textContent = num(row.rs189, 1);
      const rs63 = document.createElement('td');
      rs63.textContent = num(row.rs63, 1);
      const vs200 = document.createElement('td');
      const price = finite(row.price), sma200 = finite(row.sma200);
      vs200.textContent = price !== null && sma200 !== null && sma200 > 0 ? pct(price / sma200 - 1) : '—';
      const ddv = document.createElement('td');
      const ddv20 = finite(row.ddv20);
      ddv.textContent = ddv20 === null ? '—' : '$' + num(ddv20 / 1000000, 1) + 'M';
      tr.appendChild(rank); tr.appendChild(tickerCell); tr.appendChild(rs189); tr.appendChild(rs63); tr.appendChild(vs200); tr.appendChild(ddv);
      table.appendChild(tr);
    });
    card.appendChild(table);
  }

  function repairCore(view) {
    const core = view && view.core12;
    if (!core || core.status !== 'READY') return;
    const rows = Array.isArray(core.rows) ? core.rows : [];
    const map = metricMap(view.daily || {});

    const liquidity = document.querySelector('#t-port .card.liqstick');
    if (liquidity) {
      liquidity.dataset.v38Status = 'READY';
      liquidity.dataset.v38BindingKey = 'core12-liquidity-filter';
      const buttons = Array.from(liquidity.querySelectorAll('button'));
      buttons.forEach((button) => {
        button.onclick = () => {
          const match = String(button.textContent || '').match(/\$([0-9]+)M/);
          const threshold = match ? Number(match[1]) * 1000000 : 0;
          buttons.forEach((item) => item.classList.toggle('active', item === button));
          document.querySelectorAll('#t-port tr[data-v38-ddv20]').forEach((row) => {
            const value = finite(row.dataset.v38Ddv20);
            row.hidden = value === null || value < threshold;
          });
        };
      });
    }

    let card = cardByTitle('t-port', 'レジーム警戒灯');
    if (card) {
      readyCard(card, 'core-regime', 'Current Session正本値。F1/F2/F3・MC57は通常株Hard Gateへ追加しません。');
      const grid = document.createElement('div');
      grid.className = 'reg-grid';
      [['Market Mode', core.market_mode || metricText(map, 'market_mode')], ['NQSAR', metricText(map, 'nqsar')], ['Breadth 50MA', metricText(map, 'breadth50')], ['MC57', metricText(map, 'mc57')], ['新規上限', core.max_new_total_slots]].forEach((item) => {
        const cell = document.createElement('div');
        cell.className = 'reg-cell';
        const label = document.createElement('span');
        label.textContent = item[0];
        const value = document.createElement('b');
        value.textContent = item[1] === null || item[1] === undefined || item[1] === '' ? '—' : String(item[1]);
        cell.appendChild(label); cell.appendChild(value); grid.appendChild(cell);
      });
      card.appendChild(grid);
    }

    card = cardByTitle('t-port', '個別株スリーブ');
    if (card && rows.length) {
      readyCard(card, 'core12-main', '現行V38 Core12 ranking。空席は無理に埋めず、現行Eligibilityを満たす候補だけを表示。');
      const alloc = document.createElement('div');
      alloc.className = 'alloc';
      const individual = document.createElement('div');
      individual.className = 'a-ind'; individual.style.width = '70%'; individual.textContent = '個別 最大70';
      const lev = document.createElement('div');
      lev.className = 'a-lev'; lev.style.width = '30%'; lev.textContent = 'TQQQ 通常30';
      alloc.appendChild(individual); alloc.appendChild(lev); card.appendChild(alloc);
      const note = document.createElement('div');
      note.className = 'note rk-note';
      note.textContent = 'Eligibility: Price≥$5、DDV20≥$10M、SMA50>SMA200、Close>SMA200、RS189≥85、RS63≥85、構造的小型Clinical Biotech除外。AttackはStock RS189 70%＋Peer Theme 30%、SelectiveはRS189中心。';
      card.appendChild(note);
      renderCoreTable(card, rows, 1, 12);
      card.dataset.v38CoreRows = String(Math.min(12, rows.length));
    }

    card = cardByTitle('t-port', 'RSリーダー控え');
    if (card && rows.length > 12) {
      readyCard(card, 'core12-bench', '現行Core12 ranking 13–24位。採用ポジションではありません。');
      renderCoreTable(card, rows.slice(12, 24), 13, 12);
    }

    const entrants = core.new_entrants;
    card = cardByTitle('t-port', '新規参入（ポート候補36位圏）');
    if (card && entrants && entrants.status === 'READY') {
      readyCard(card, 'core12-new-entrants', '20営業日前はRS189 36位圏外、現在30位以内へ入った銘柄。');
      const meta = document.createElement('div');
      meta.className = 'mut';
      meta.textContent = String(entrants.baseline_session || '—') + ' → ' + String(entrants.current_session || '—');
      card.appendChild(meta);
      const chips = document.createElement('div');
      chips.className = 'chips';
      (Array.isArray(entrants.rows) ? entrants.rows : []).forEach((row) => {
        const chip = tickerLink(row.ticker, 'chip hot');
        chip.prepend(document.createTextNode(String(row.rank) + '位 '));
        chip.dataset.v38Ddv20 = finite(row.ddv20) === null ? '' : String(row.ddv20);
        chips.appendChild(chip);
      });
      if (!chips.children.length) chips.textContent = '該当なし';
      card.appendChild(chips);
    }
  }

  function repairPositions(view) {
    const positions = view && view.positions;
    const core = view && view.core12;
    if (!positions || positions.status !== 'READY') return;
    const rows = Array.isArray(positions.rows) ? positions.rows : [];
    const isEmpty = rows.length === 0;

    let card = cardByTitle('t-alloc', '現在の想定ポジション');
    if (card) {
      readyCard(card, 'positions-current-expected', isEmpty ? 'Positions正本はEMPTY。保有を捏造しません。' : 'Positions正本の現在保有。');
      if (isEmpty) {
        kv(card, 'Current holdings', '0');
        kv(card, 'Portfolio state', 'EMPTY');
      } else {
        sourceRows(card, rows,
          (row) => ({left: 'Entry ' + num(row.entry_price, 2) + ' ・ Close ' + num(row.close, 2), right: 'Action ' + String(row.action || '—')}),
          (row) => ({value: pct(row.pnl_pct), label: '損益'}), 20);
      }
    }

    card = cardByTitle('t-alloc', 'マーケット回復後のポジション入り銘柄');
    const candidates = core && Array.isArray(core.rows) ? core.rows.filter((row) => row.eligibility_status === 'ELIGIBLE').slice(0, 12) : [];
    if (card && candidates.length) {
      readyCard(card, 'positions-recovery-candidates', '現行Core12上位。現在の保有ではなく、回復時点に再評価する候補。');
      sourceRows(card, candidates,
        (row) => ({left: 'RS189 / RS63 ' + num(row.rs189, 1) + ' / ' + num(row.rs63, 1), right: '翌寄り候補ではなく再評価候補'}),
        (row) => ({value: num(row.rs189, 1), label: 'RS189'}), 12, '候補');
    }

    card = cardByTitle('t-alloc', 'エクイティカーブ×21日EMA');
    if (card && isEmpty) {
      readyCard(card, 'positions-equity-curve', 'Positionsが明示的EMPTYのため現在は対象外。口座資産データを捏造しません。');
      const row = document.createElement('div');
      row.className = 'eqrow';
      const state = document.createElement('span');
      state.className = 'dd';
      const badge = document.createElement('span');
      badge.className = 'st';
      badge.textContent = 'Portfolio EMPTY';
      state.appendChild(badge); row.appendChild(state); card.appendChild(row);
    }
  }

  function repairWeekly(view) {
    const weekly = view && view.weekly;
    const daily = view && view.daily;
    if (!weekly || weekly.status !== 'READY' || !daily) return;
    const map = metricMap(daily);
    const summaries = daily.market_summaries || {};
    let card = cardByTitle('t-weekly', '今週の結論');
    if (card) {
      readyCard(card, 'weekly-conclusion', '取得済みWeekly NQSARとCurrent Session指標。');
      kv(card, 'NQSAR', weekly.state || '—');
      kv(card, 'Market Mode', metricText(map, 'market_mode'));
      kv(card, 'Breadth 50MA', metricText(map, 'breadth50'));
      kv(card, 'MC57', metricText(map, 'mc57'));
      kv(card, 'QQQ 1週', pct(summaries.QQQ && summaries.QQQ.change_1w));
    }
    const history = Array.isArray(daily.history) ? daily.history : [];
    card = cardByTitle('t-weekly', '今週の変化');
    if (card && history.length >= 6) {
      readyCard(card, 'weekly-diff', '直近5営業日前との取得済み指標比較。');
      const now = history[history.length - 1], before = history[history.length - 6];
      [['Breadth50', 'breadth50'], ['Breadth200', 'breadth200'], ['F1', 'f1'], ['F2', 'f2'], ['F3', 'f3']].forEach((spec) => {
        const oldValue = finite(before[spec[1]]), newValue = finite(now[spec[1]]);
        kv(card, spec[0], oldValue === null || newValue === null ? '—' : num(oldValue, 1) + ' → ' + num(newValue, 1));
      });
    }
    const sectorTickers = ['XLB','XLC','XLE','XLF','XLI','XLK','XLP','XLRE','XLU','XLV','XLY'];
    const movers = sectorTickers.map((symbol) => ({ticker: symbol, change_1w: summaries[symbol] && summaries[symbol].change_1w})).filter((row) => finite(row.change_1w) !== null).sort((a, b) => b.change_1w - a.change_1w);
    card = cardByTitle('t-weekly', '週次騰落ボード');
    if (card && movers.length) {
      readyCard(card, 'weekly-movers', '取得済みGICS11セクターETFの1週間騰落率。');
      sourceRows(card, movers, (row) => ({left: '1W ' + pct(row.change_1w), right: ''}), (row) => ({value: pct(row.change_1w), label: '1W'}), 11);
    }

    const observations = daily.display_observations || {};
    const regime = observations.regime_history || {};
    const regimeRows = Array.isArray(regime.records) ? regime.records : [];
    card = cardByTitle('t-weekly', '地合いの帯');
    if (card && regime.status === 'READY' && regimeRows.length) {
      readyCard(card, 'weekly-regime-history', '正本NQSAR観測履歴。価格から過去の色を推定しません。');
      const shown = regimeRows.slice(-60);
      const label = document.createElement('div');
      label.className = 'riblab';
      label.textContent = 'レジーム履歴 ' + String(shown[0].date || '—') + ' → ' + String(shown[shown.length - 1].date || '—') + '（正本 ' + String(regime.observation_count || regimeRows.length) + '件）';
      card.appendChild(label);
      const ribbon = document.createElement('div');
      ribbon.className = 'ribbon';
      shown.forEach((row) => {
        const state = String(row.state || '').toLowerCase();
        const chip = document.createElement('span');
        chip.className = 'rb ' + ({blue: 'c-bl', green: 'c-gr', yellow: 'c-yl', red: 'c-rd'}[state] || 'c-yl');
        chip.title = String(row.date || '') + ' ' + String(row.state || '');
        ribbon.appendChild(chip);
      });
      card.appendChild(ribbon);
    }

    card = cardByTitle('t-weekly', '来週の経済指標');
    if (card) {
      unavailableCard(card, 'weekly-economic-calendar-source', 'Yahoo価格APIは経済イベント日程を提供しません。正本カレンダー未接続のため、日付や指標を推測表示しません。');
      kv(card, '取得判定', 'SOURCE_UNAVAILABLE');
      kv(card, '利用可能な正本', 'なし');
    }

    const positions = view.positions || {};
    card = cardByTitle('t-weekly', '自分 vs QQQ円建て');
    if (card && positions.status === 'READY' && Array.isArray(positions.rows) && positions.rows.length === 0) {
      readyCard(card, 'weekly-self-vs-qqq', 'PositionsはEMPTY。架空のポートフォリオ成績は作りません。');
      kv(card, 'My portfolio', '保有なし / 比較対象外');
      kv(card, 'QQQ 1週', pct(summaries.QQQ && summaries.QQQ.change_1w));
    }
  }

  async function loadJson(path) {
    if (window.V38Runtime && typeof window.V38Runtime.loadJson === 'function') {
      return window.V38Runtime.loadJson(path);
    }
    const response = await fetch(path, {cache: 'no-store'});
    if (!response.ok) throw new Error('HTTP ' + response.status + ' for ' + path);
    return response.json();
  }

  async function repairPublishedCards() {
    if (running || !document.body || document.body.dataset.v38BindingStatus !== 'ready') return false;
    running = true;
    try {
      const view = await loadJson('data/ui_view_model.json');
      let options = null, history = null;
      try { options = await loadJson('data/options/index.json'); } catch (_) { options = null; }
      try { history = await loadJson('data/rs_history.json'); } catch (_) { history = null; }
      repairMc57(view);
      // Options owns its production DOM in v38-restored-experience.js. Keep the
      // frozen Options cards intact instead of rebuilding them a second time.
      repairThemes(view);
      repairRs(view, history);
      repairCore(view);
      repairPositions(view);
      repairWeekly(view);
      restoreAllCanonicalHeadings();
      document.body.dataset.v38DataRepairStatus = 'ready';
      return true;
    } catch (_) {
      document.body.dataset.v38DataRepairStatus = 'failed';
      return false;
    } finally {
      running = false;
    }
  }

  function scheduleRepair() {
    let attempts = 0;
    const run = async () => {
      attempts += 1;
      const ready = document.body && document.body.dataset.v38FinalUiStatus === 'ready';
      if (ready && await repairPublishedCards()) return;
      if (attempts < 80) window.setTimeout(run, 75);
    };
    window.setTimeout(run, 75);
    window.setTimeout(repairPublishedCards, 1200);
    window.setTimeout(repairPublishedCards, 2400);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', scheduleRepair, {once: true});
  } else {
    scheduleRepair();
  }
})();
