(function () {
  'use strict';

  function finite(value) {
    if (value === null || value === undefined || value === '') return null;
    const n = Number(value);
    return Number.isFinite(n) ? n : null;
  }

  function append(parent, tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    node.textContent = text === null || text === undefined ? '' : String(text);
    parent.appendChild(node);
    return node;
  }

  function pctFraction(value) {
    const n = finite(value);
    if (n === null) return '—';
    return (n > 0 ? '+' : '') + (n * 100).toFixed(1) + '%';
  }

  function signed(value, digits) {
    const n = finite(value);
    if (n === null) return '—';
    return (n > 0 ? '+' : '') + n.toFixed(digits === undefined ? 0 : digits);
  }

  function num(value, digits) {
    const n = finite(value);
    return n === null ? '—' : n.toFixed(digits === undefined ? 0 : digits);
  }

  function tickerLink(parent, ticker, className) {
    const a = append(parent, 'a', className || 'chip hot v38-ticker-link', ticker);
    a.href = 'https://www.tradingview.com/chart/?symbol=' + encodeURIComponent(ticker);
    a.target = '_blank';
    a.rel = 'noopener noreferrer';
    return a;
  }

  function findCard(sectionId, text) {
    const section = document.getElementById(sectionId);
    if (!section) return null;
    return Array.from(section.querySelectorAll('.card')).find((card) => {
      const original = card.dataset.v38CardTitle || '';
      const current = card.querySelector('h2') ? card.querySelector('h2').textContent : '';
      return original.includes(text) || current.includes(text);
    }) || null;
  }

  function statusNote(parent, status, detail) {
    const note = append(parent, 'div', 'v38-bind-note', '');
    note.dataset.v38Status = status;
    append(note, 'strong', '', status);
    if (detail) append(note, 'div', '', detail);
  }

  function renderFineThemeRows(view) {
    const rotation = view && view.rotation;
    if (!rotation || rotation.fine_theme_status !== 'READY') return;
    const card = findCard('t-rotation', 'サブテーマ別RS');
    if (!card) return;
    const rows = (Array.isArray(rotation.fine_theme_rows) ? rotation.fine_theme_rows : [])
      .filter((row) => Number(row.member_count || 0) >= 2 && finite(row.theme_rs) !== null)
      .sort((a, b) => Number(b.theme_rs) - Number(a.theme_rs));

    card.replaceChildren();
    append(card, 'h2', '', 'サブテーマ別RS（ユニバース内） Sub-Theme RS');
    append(card, 'div', 'sub', '構成銘柄の63日RS×189日RS（中央値・均等ブレンド）をサブテーマ単位で0-100ランク（2社以上）。元Command Center定義を復元。');

    const summary = append(card, 'div', 'v38-live-kv', '');
    append(summary, 'span', '', '復元Theme / Tag coverage');
    append(summary, 'b', '', String(rows.length) + ' / ' + (finite(rotation.fine_theme_coverage) === null ? '—' : (Number(rotation.fine_theme_coverage) * 100).toFixed(1) + '%'));

    const list = append(card, 'div', 'rsc-list', '');
    rows.forEach((row, index) => {
      const item = append(list, 'details', 'rsx-item', '');
      const head = append(item, 'summary', 'rsx-row', '');
      append(head, 'span', 'rsx-rk', index + 1);
      const name = append(head, 'div', 'rsx-name', '');
      append(name, 'b', '', row.theme_name || row.theme_id || '—');
      append(name, 'small', '', [row.major_theme || '', String(row.member_count || 0) + '社'].filter(Boolean).join(' • '));
      const score = append(head, 'div', 'rsx-score', '');
      append(score, 'b', '', num(row.theme_rs, 0));
      append(score, 'small', '', 'Theme RS');

      const stats = append(item, 'div', 'rsx-sub', '');
      append(stats, 'span', 'rsx-nums', 'RS63中央値 ' + num(row.rs63_median, 0));
      append(stats, 'span', 'rsx-nums', 'RS189中央値 ' + num(row.rs189_median, 0));
      append(stats, 'span', 'rsx-ret', '1M中央値 ' + pctFraction(row.ret20_median));

      const projected = (Array.isArray(rotation.fine_theme_groups) ? rotation.fine_theme_groups : [])
        .find((group) => group.group === (row.theme_name || row.theme_id));
      const leaders = projected && Array.isArray(projected.leaders) ? projected.leaders : row.leaders;
      if (Array.isArray(leaders) && leaders.length) {
        const chips = append(item, 'div', 'chips', '');
        leaders.slice(0, 5).forEach((ticker) => tickerLink(chips, String(ticker)));
      }
    });
    statusNote(card, 'READY', rotation.fine_theme_reason || 'RECOVERED_LEGACY_367_THEME_MAP');
  }

  function renderEmptyPositions(view) {
    const positions = view && view.positions;
    if (!positions || positions.status !== 'READY' || !Array.isArray(positions.rows) || positions.rows.length) return;
    const section = document.getElementById('t-alloc');
    if (!section) return;
    const card = section.querySelector('.card');
    if (!card) return;
    card.replaceChildren();
    append(card, 'h2', '', '保有ポジション Positions');
    append(card, 'div', 'empty', '現在ポジションなし');
    statusNote(card, 'READY', 'USER_CONFIRMED_EMPTY_PORTFOLIO');
  }

  function renderChipSet(parent, label, tickers) {
    const row = append(parent, 'div', 'rsx-sub', '');
    append(row, 'span', 'rsx-nums', label + ' ' + String((tickers || []).length));
    const chips = append(row, 'span', 'chips', '');
    (Array.isArray(tickers) ? tickers : []).forEach((ticker) => tickerLink(chips, String(ticker), 'chip v38-ticker-link'));
    if (!tickers || !tickers.length) append(chips, 'span', 'mut', 'なし');
  }

  function renderRsInOut(history) {
    if (!history || history.status !== 'READY') return;
    const card = findCard('t-rs', 'Top10 IN / OUT履歴');
    if (!card) return;
    card.replaceChildren();
    append(card, 'h2', '', 'Top10 IN / OUT履歴');
    append(card, 'div', 'sub', '現在のTop10を、実際に保存された前営業日・約1週間前・約1か月前と比較。存在しない過去履歴は補完しません。');

    const labels = {'63': 'RS63 約3ヶ月', '126': 'RS126 約6ヶ月', '189': 'RS189 約9ヶ月・主指標'};
    ['63', '126', '189'].forEach((period) => {
      const data = history.windows && history.windows[period];
      const group = append(card, 'div', 'rsx-item', '');
      append(group, 'h3', '', labels[period]);
      append(group, 'div', 'sub', '保存済み ' + String(data && data.available_sessions || 0) + ' セッション');
      (data && Array.isArray(data.comparisons) ? data.comparisons : []).forEach((cmp) => {
        const block = append(group, 'div', 'rsx-item', '');
        const title = cmp.status === 'READY'
          ? cmp.label + '　継続 ' + cmp.continuing + '/10・入替 ' + cmp.replacement_count
          : cmp.label + '　蓄積中 ' + cmp.available_sessions + '/' + cmp.required_sessions;
        append(block, 'b', '', title);
        append(block, 'small', '', cmp.status === 'READY' ? (cmp.detail + ' (' + cmp.target_session + ')') : cmp.detail);
        if (cmp.status === 'READY') {
          renderChipSet(block, 'IN', cmp.in);
          renderChipSet(block, 'OUT', cmp.out);
        }
      });
    });
    statusNote(card, 'READY', 'OBSERVED_ARCHIVE_ONLY • first ' + (history.first_observed_session || '—'));
  }

  function renderRsPersistence(history) {
    if (!history || history.status !== 'READY') return;
    const data = history.persistence;
    const card = findCard('t-rs', 'RS189 継続性');
    if (!card || !data) return;
    card.replaceChildren();
    append(card, 'h2', '', 'RS189 継続性 Leadership Persistence');
    append(card, 'div', 'sub', 'Top10滞在、Top24滞在率、連続日数、順位・RS変化。保存開始前の履歴は推測しません。');
    const observed = Number(data.observed_sessions || 0);
    const required = Number(data.required_sessions || 21);
    const summary = append(card, 'div', 'v38-live-kv', '');
    append(summary, 'span', '', '判定履歴');
    append(summary, 'b', '', observed + '/' + required + '営業日' + (data.classification_ready ? '' : '（蓄積中）'));

    const list = append(card, 'div', 'rsc-list', '');
    (Array.isArray(data.rows) ? data.rows : []).forEach((row) => {
      const item = append(list, 'div', 'rsc-row', '');
      const head = append(item, 'div', 'rsc-head', '');
      append(head, 'span', 'rsc-rk', '#' + row.rank);
      tickerLink(head, String(row.ticker || ''), 'v38-ticker-link');
      append(head, 'span', 'rsc-tag hold', row.classification || '蓄積中');
      append(head, 'span', 'rsc-rs', 'RS ' + num(row.rs189, 1));

      const metrics = append(item, 'div', 'rsc-metrics', '');
      append(metrics, 'span', '', 'Top10 ' + row.top10_days + '/' + row.window_sessions + '日');
      append(metrics, 'span', '', 'Top24 ' + num(row.top24_pct, 0) + '%');
      append(metrics, 'span', '', '連続Top10 ' + row.consecutive_top10_observed + '日（観測）');
      const rankChange = finite(row.rank_change);
      append(metrics, 'span', '', (row.rank_change_sessions || 0) + '日順位 ' + (rankChange === null ? '—' : rankChange > 0 ? '↑' + rankChange : rankChange < 0 ? '↓' + Math.abs(rankChange) : '→'));

      const slopes = append(item, 'div', 'rsc-slopes', '');
      slopes.textContent = '観測期間変化: 63 ' + signed(row.delta_rs63, 0) + ' / 126 ' + signed(row.delta_rs126, 0) + ' / 189 ' + signed(row.delta_rs189, 1);
    });
    statusNote(card, data.classification_ready ? 'READY' : 'ACCUMULATING', data.classification_ready ? '21-session original persistence definitions enabled' : '21営業日そろうまで分類は「蓄積中」');
  }

  async function applyRecovery() {
    const runtime = window.V38Runtime;
    if (!runtime || typeof runtime.loadJson !== 'function') return;
    try {
      const results = await Promise.all([
        runtime.loadJson('data/ui_view_model.json'),
        runtime.loadJson('data/rs_history.json')
      ]);
      const view = results[0];
      const rsHistory = results[1];
      const apply = function () {
        if (document.body.dataset.v38BindingStatus !== 'ready') {
          window.setTimeout(apply, 40);
          return;
        }
        renderFineThemeRows(view);
        renderEmptyPositions(view);
        renderRsInOut(rsHistory);
        renderRsPersistence(rsHistory);
        document.body.dataset.v38RecoveryStatus = 'ready';
      };
      apply();
    } catch (_) {
      document.body.dataset.v38RecoveryStatus = 'failed';
    }
  }

  document.addEventListener('DOMContentLoaded', applyRecovery);
})();
