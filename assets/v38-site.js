(function () {
  'use strict';

  const TAB_SELECTOR = 'nav a.tabx[href^="#t-"]';
  const SECTION_IDS = [
    't-market', 't-alloc', 't-port', 't-rotation', 't-rs',
    't-weekly', 't-options', 't-post1', 't-rules'
  ];
  const VIEW_BINDINGS = [
    ['t-alloc', 'positions'],
    ['t-port', 'core12'],
    ['t-rotation', 'rotation'],
    ['t-weekly', 'weekly'],
    ['t-options', 'options'],
    ['t-post1', 'publish'],
    ['t-rules', 'rules']
  ];

  function targetOf(tab) {
    const href = tab.getAttribute('href') || '';
    const id = href.charAt(0) === '#' ? href.slice(1) : '';
    return SECTION_IDS.includes(id) ? id : null;
  }

  function activate(targetId) {
    const valid = SECTION_IDS.includes(targetId) ? targetId : 't-market';
    document.querySelectorAll('section').forEach((section) => {
      section.classList.remove('on');
    });
    document.querySelectorAll('nav a.tabx').forEach((tab) => {
      tab.classList.remove('on');
      tab.setAttribute('aria-selected', 'false');
    });

    const section = document.getElementById(valid);
    const tab = Array.from(document.querySelectorAll(TAB_SELECTOR))
      .find((candidate) => targetOf(candidate) === valid);
    if (section) section.classList.add('on');
    if (tab) {
      tab.classList.add('on');
      tab.setAttribute('aria-selected', 'true');
    }
    window.scrollTo(0, 0);
  }

  function root(id) {
    return document.querySelector(
      '[data-v38-live-section="' + id + '"]'
    );
  }

  function node(tag, className, text) {
    const out = document.createElement(tag);
    if (className) out.className = className;
    if (text !== undefined && text !== null) out.textContent = String(text);
    return out;
  }

  function statusClass(status) {
    return status === 'READY' ? 'pos' : (status === 'STALE' ? 'neg' : 'mut');
  }

  function resetRoot(sectionId, title, status, session) {
    const out = root(sectionId);
    if (!out) return null;
    out.replaceChildren();
    out.className = 'card';
    out.dataset.v38Status = status || 'DATA_REQUIRED';

    const head = node('div', 'chd');
    head.appendChild(node('h2', '', title || 'V38'));
    const now = node('div', 'chd-now');
    now.appendChild(node('b', statusClass(out.dataset.v38Status), out.dataset.v38Status));
    now.appendChild(node('span', '', session || '—'));
    head.appendChild(now);
    out.appendChild(head);
    return out;
  }

  function addMessage(parent, text) {
    if (!text) return;
    parent.appendChild(node('div', 'mut', text));
  }

  function addRow(parent, label, value, detail, rowIndex) {
    const row = node('div', 'rrow');
    if (rowIndex !== undefined) row.dataset.v38Row = String(rowIndex);
    const left = node('div', 'lft');
    left.appendChild(node('div', 'nm', label || '—'));
    const right = node('div', 'rgt');
    right.appendChild(node('div', 'big', value === undefined || value === null ? '—' : value));
    row.appendChild(left);
    row.appendChild(right);
    if (detail) row.appendChild(node('div', 'foot', detail));
    parent.appendChild(row);
    return row;
  }

  function sectionDetail(section) {
    if (!section || !Array.isArray(section.components)) {
      return 'Authoritative inputs are unavailable.';
    }
    return section.components.map((item) => {
      const name = item && item.name ? item.name : 'input';
      const status = item && item.status ? item.status : 'DATA_REQUIRED';
      const reason = item && item.reason ? item.reason : 'UNKNOWN';
      return name + ': ' + status + ' (' + reason + ')';
    }).join(' • ');
  }

  function renderPayload(payload) {
    const sections = payload && payload.sections && typeof payload.sections === 'object'
      ? payload.sections : {};
    SECTION_IDS.forEach((id) => {
      const section = sections[id] || null;
      const status = section && typeof section.status === 'string'
        ? section.status : 'DATA_REQUIRED';
      const out = resetRoot(id, 'V38', status, payload && payload.session_date);
      if (out) addMessage(out, sectionDetail(section));
    });
  }

  function renderDaily(view) {
    const daily = view && view.daily && typeof view.daily === 'object'
      ? view.daily : null;
    const status = daily && daily.status ? daily.status : 'DATA_REQUIRED';
    const out = resetRoot('t-market', 'Daily', status, view && view.session_date);
    if (!out) return;
    if (!daily || !Array.isArray(daily.metrics)) {
      addMessage(out, daily && daily.reason ? daily.reason : 'Daily data unavailable.');
      return;
    }
    daily.metrics.forEach((metric) => {
      if (!metric || typeof metric !== 'object') return;
      const detail = [
        metric.status && metric.status !== 'READY' ? metric.status : '',
        metric.severity && metric.severity !== 'NO_JUDGMENT' ? metric.severity : '',
        metric.status !== 'READY' && metric.reason ? metric.reason : ''
      ].filter(Boolean).join(' • ');
      const row = addRow(out, metric.label || metric.key, metric.display || '—', detail);
      row.dataset.v38Metric = String(metric.key || '');
    });
  }

  function renderRs(view) {
    const rs = view && view.rs && typeof view.rs === 'object' ? view.rs : null;
    const status = rs && rs.status ? rs.status : 'DATA_REQUIRED';
    const out = resetRoot('t-rs', (rs && rs.title) || 'RS189 Top 24', status, view && view.session_date);
    if (!out) return;
    addMessage(out, rs && rs.note ? rs.note : 'RS ranking; not Core 12.');
    if (!rs || !Array.isArray(rs.rows) || rs.rows.length === 0) {
      addMessage(out, rs && rs.reason ? rs.reason : 'RS data unavailable.');
      return;
    }
    const list = node('div', 'rsx-card');
    rs.rows.forEach((item) => {
      if (!item || typeof item !== 'object') return;
      const row = node('div', 'rsx-item');
      row.dataset.v38RsTicker = String(item.ticker || '');
      const label = '#' + String(item.rank || '—') + '  ' + String(item.ticker || '—');
      const value = 'RS189 ' + String(item.rs189_display || '—') + '  ·  RS63 ' + String(item.rs63_display || '—');
      row.appendChild(node('div', 'nm', label));
      row.appendChild(node('div', 'big', value));
      row.appendChild(node('div', 'mut', 'Price ' + String(item.price_display || '—') + '  ·  DDV20 ' + String(item.ddv20_display || '—')));
      list.appendChild(row);
    });
    out.appendChild(list);
  }

  function primitiveEntries(item) {
    if (!item || typeof item !== 'object') return [];
    return Object.keys(item).filter((key) => {
      const value = item[key];
      return value === null || ['string', 'number', 'boolean'].includes(typeof value);
    }).slice(0, 8).map((key) => [key, item[key]]);
  }

  function summarizeRow(item, index, viewKey) {
    if (viewKey === 'rules' && item && typeof item.key === 'string') {
      return [item.key, item.value, ''];
    }
    const entries = primitiveEntries(item);
    if (!entries.length) return ['Row ' + index, '—', 'Authoritative structured row'];
    const preferred = ['ticker', 'symbol', 'theme', 'name', 'action', 'state', 'status', 'key'];
    let primary = entries.find(([key]) => preferred.includes(key));
    if (!primary) primary = entries[0];
    const rest = entries.filter(([key]) => key !== primary[0]);
    const detail = rest.map(([key, value]) => key + ': ' + (value === null ? '—' : value)).join(' • ');
    return [primary[0], primary[1] === null ? '—' : primary[1], detail];
  }

  function renderGeneric(view, sectionId, viewKey) {
    const data = view && view[viewKey] && typeof view[viewKey] === 'object'
      ? view[viewKey] : null;
    const status = data && data.status ? data.status : 'DATA_REQUIRED';
    const title = data && data.title ? data.title : viewKey;
    const out = resetRoot(sectionId, title, status, view && view.session_date);
    if (!out) return;
    if (data && data.note) addMessage(out, data.note);
    if (data && data.reason && status !== 'READY') addMessage(out, data.reason);
    if (data && data.state) addRow(out, 'State', data.state, 'Authoritative weekly state');
    if (viewKey === 'publish' && data && data.full_v38_ready !== undefined) {
      const counts = data.ready_count !== undefined && data.required_count !== undefined
        ? String(data.ready_count) + '/' + String(data.required_count) + ' dependencies ready' : '';
      addRow(out, 'Full V38 ready', data.full_v38_ready ? 'YES' : 'NO', counts);
    }
    const rows = data && Array.isArray(data.rows) ? data.rows : [];
    if (!rows.length) {
      if (!(data && data.reason)) addMessage(out, 'No authoritative rows for this session.');
      return;
    }
    rows.slice(0, viewKey === 'rules' ? 80 : 40).forEach((item, i) => {
      const summary = summarizeRow(item, i + 1, viewKey);
      addRow(out, summary[0], summary[1], summary[2], i + 1);
    });
  }

  function renderLiveView(view) {
    renderDaily(view);
    renderRs(view);
    VIEW_BINDINGS.forEach(([sectionId, viewKey]) => renderGeneric(view, sectionId, viewKey));
  }

  function setAllUnavailable(detail) {
    SECTION_IDS.forEach((id) => {
      const out = resetRoot(id, 'V38', 'DATA_REQUIRED', '—');
      if (out) addMessage(out, detail);
    });
  }

  async function loadProductionData() {
    const runtime = window.V38Runtime;
    if (!runtime || typeof runtime.loadJson !== 'function') {
      setAllUnavailable('Runtime unavailable.');
      return;
    }
    try {
      const payload = await runtime.loadJson('data/ui_payload.json');
      renderPayload(payload);
    } catch (_) {
      setAllUnavailable('Authoritative ui_payload.json is unavailable.');
      return;
    }
    try {
      const view = await runtime.loadJson('data/ui_view_model.json');
      renderLiveView(view);
    } catch (_) {
      // ui_payload already left every section fail-closed.
    }
  }

  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll(TAB_SELECTOR).forEach((tab) => {
      tab.addEventListener('click', (event) => {
        const target = targetOf(tab);
        if (!target) return;
        event.preventDefault();
        activate(target);
      });
    });

    const activeTab = Array.from(document.querySelectorAll(TAB_SELECTOR))
      .find((tab) => tab.classList.contains('on'));
    const activeSection = SECTION_IDS.find((id) => {
      const section = document.getElementById(id);
      return section && section.classList.contains('on');
    });
    activate(activeTab ? targetOf(activeTab) : (activeSection || 't-market'));
    loadProductionData();
  });
})();
