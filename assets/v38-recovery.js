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

  function num(value, digits) {
    const n = finite(value);
    return n === null ? '—' : n.toFixed(digits === undefined ? 0 : digits);
  }

  function tickerLink(parent, ticker) {
    const a = append(parent, 'a', 'chip hot v38-ticker-link', ticker);
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

  async function applyRecovery() {
    const runtime = window.V38Runtime;
    if (!runtime || typeof runtime.loadJson !== 'function') return;
    try {
      const view = await runtime.loadJson('data/ui_view_model.json');
      const apply = function () {
        if (document.body.dataset.v38BindingStatus !== 'ready') {
          window.setTimeout(apply, 40);
          return;
        }
        renderFineThemeRows(view);
        renderEmptyPositions(view);
        document.body.dataset.v38RecoveryStatus = 'ready';
      };
      apply();
    } catch (_) {
      document.body.dataset.v38RecoveryStatus = 'failed';
    }
  }

  document.addEventListener('DOMContentLoaded', applyRecovery);
})();
