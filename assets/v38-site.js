(function () {
  'use strict';

  const TAB_SELECTOR =
    'a.tabx[href^="#"]';

  const SECTION_IDS = [
    't-market',
    't-alloc',
    't-port',
    't-rotation',
    't-rs',
    't-weekly',
    't-options',
    't-post1',
    't-rules'
  ];

  function targetOf(tab) {
    const href =
      tab.getAttribute('href') || '';

    if (
      href.length > 1 &&
      href.charAt(0) === '#'
    ) {
      const id = href.slice(1);
      if (SECTION_IDS.includes(id)) {
        return id;
      }
    }

    return null;
  }

  function suppressMockContent() {
    SECTION_IDS.forEach(
      (id) => {
        const section =
          document.getElementById(id);

        if (!section) {
          return;
        }

        Array.from(section.children)
          .forEach(
            (child) => {
              if (
                !child.classList.contains(
                  'v38-production-state'
                )
              ) {
                child.hidden = true;
                child.setAttribute(
                  'aria-hidden',
                  'true'
                );
              }
            }
          );
      }
    );
  }

  function activate(
    targetId,
    updateHash
  ) {
    const tabs = Array.from(
      document.querySelectorAll(
        TAB_SELECTOR
      )
    );

    const valid =
      SECTION_IDS.includes(targetId)
        ? targetId
        : 't-market';

    tabs.forEach(
      (tab) => {
        const active =
          targetOf(tab) === valid;

        tab.classList.toggle(
          'on',
          active
        );

        tab.setAttribute(
          'aria-selected',
          active ? 'true' : 'false'
        );
      }
    );

    SECTION_IDS.forEach(
      (id) => {
        const section =
          document.getElementById(id);

        if (!section) {
          return;
        }

        const active =
          id === valid;

        section.classList.toggle(
          'on',
          active
        );

        section.hidden = !active;
      }
    );

    if (
      updateHash &&
      window.location.hash !==
        '#' + valid
    ) {
      history.replaceState(
        null,
        '',
        '#' + valid
      );
    }
  }

  function sectionDetail(section) {
    if (
      !section ||
      !Array.isArray(section.components)
    ) {
      return (
        'Authoritative inputs are unavailable. ' +
        'Mock values remain shielded.'
      );
    }

    const parts =
      section.components.map(
        (row) => {
          const status =
            typeof row.status === 'string'
              ? row.status
              : 'DATA_REQUIRED';

          const reason =
            typeof row.reason === 'string'
              ? row.reason
              : 'UNKNOWN';

          return (
            row.name +
            ': ' +
            status +
            ' (' +
            reason +
            ')'
          );
        }
      );

    return parts.join(' • ');
  }

  function stateNode(id) {
    return document.querySelector(
      '.v38-production-state' +
      '[data-v38-section="' +
      id +
      '"]'
    );
  }

  function renderPayload(payload) {
    const sections =
      payload &&
      payload.sections &&
      typeof payload.sections === 'object'
        ? payload.sections
        : {};

    SECTION_IDS.forEach(
      (id) => {
        const node = stateNode(id);

        if (!node) {
          return;
        }

        const section =
          sections[id] || null;

        const status =
          section &&
          typeof section.status === 'string'
            ? section.status
            : 'DATA_REQUIRED';

        const title =
          node.querySelector('b');

        const body =
          node.querySelector('span');

        if (title) {
          title.textContent = status;
        }

        if (body) {
          body.textContent =
            sectionDetail(section);
        }

        node.dataset.v38Status = status;
      }
    );
  }

  function setAllUnavailable(detail) {
    document
      .querySelectorAll(
        '.v38-production-state'
      )
      .forEach(
        (node) => {
          const title =
            node.querySelector('b');
          const body =
            node.querySelector('span');

          if (title) {
            title.textContent =
              'DATA_REQUIRED';
          }

          if (body) {
            body.textContent = detail;
          }

          node.dataset.v38Status =
            'DATA_REQUIRED';
        }
      );
  }

  function ensureLiveStyles() {
    if (
      document.getElementById(
        'v38-live-binding-style'
      )
    ) {
      return;
    }

    const style =
      document.createElement('style');

    style.id =
      'v38-live-binding-style';

    style.textContent = [
      '.v38-production-state.v38-live-bound{justify-content:flex-start;gap:8px}',
      '.v38-live-head{display:flex;justify-content:space-between;align-items:baseline;gap:8px;flex-wrap:wrap}',
      '.v38-live-head strong{font-size:14px}',
      '.v38-live-status{font-size:10px;opacity:.7}',
      '.v38-live-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px 12px;width:100%}',
      '.v38-live-metric{min-width:0}',
      '.v38-live-metric-label,.v38-live-metric-value,.v38-live-metric-meta{display:block;min-width:0;overflow-wrap:anywhere}',
      '.v38-live-metric-label{font-size:10px;opacity:.7}',
      '.v38-live-metric-value{font-size:14px;font-weight:700;font-variant-numeric:tabular-nums}',
      '.v38-live-metric-meta{font-size:9px;opacity:.6}',
      '.v38-live-note{font-size:10px;opacity:.7}',
      '.v38-rs-list{display:grid;gap:4px;width:100%}',
      '.v38-rs-row{display:grid;grid-template-columns:2rem minmax(3.8rem,1fr) minmax(4rem,.9fr) minmax(3.5rem,.75fr) minmax(3.5rem,.75fr);gap:5px;align-items:center;min-width:0;font-size:10px}',
      '.v38-rs-row>span{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}',
      '.v38-rs-row .v38-num{text-align:right;font-variant-numeric:tabular-nums}',
      '@media(min-width:700px){.v38-live-grid{grid-template-columns:repeat(4,minmax(0,1fr))}}'
    ].join('');

    document.head.appendChild(style);
  }

  function appendText(
    parent,
    tag,
    className,
    text
  ) {
    const node =
      document.createElement(tag);

    if (className) {
      node.className = className;
    }

    node.textContent =
      text === null || text === undefined
        ? ''
        : String(text);

    parent.appendChild(node);
    return node;
  }

  function renderDaily(view) {
    const node = stateNode('t-market');
    const daily =
      view && view.daily &&
      typeof view.daily === 'object'
        ? view.daily
        : null;

    if (
      !node ||
      !daily ||
      !Array.isArray(daily.metrics)
    ) {
      return;
    }

    node.replaceChildren();
    node.classList.add('v38-live-bound');
    node.dataset.v38Status =
      typeof daily.status === 'string'
        ? daily.status
        : 'DATA_REQUIRED';

    const head =
      document.createElement('div');
    head.className = 'v38-live-head';
    appendText(
      head,
      'strong',
      '',
      'Daily • ' + String(view.session_date || '—')
    );
    appendText(
      head,
      'span',
      'v38-live-status',
      node.dataset.v38Status
    );
    node.appendChild(head);

    const grid =
      document.createElement('div');
    grid.className = 'v38-live-grid';

    daily.metrics.forEach(
      (metric) => {
        if (!metric || typeof metric !== 'object') {
          return;
        }

        const item =
          document.createElement('div');
        item.className = 'v38-live-metric';
        item.dataset.v38Metric =
          String(metric.key || '');

        appendText(
          item,
          'span',
          'v38-live-metric-label',
          metric.label || metric.key || '—'
        );
        appendText(
          item,
          'span',
          'v38-live-metric-value',
          metric.display || '—'
        );

        const status =
          typeof metric.status === 'string'
            ? metric.status
            : 'DATA_REQUIRED';
        const severity =
          typeof metric.severity === 'string' &&
          metric.severity !== 'NO_JUDGMENT'
            ? metric.severity
            : '';

        if (status !== 'READY' || severity) {
          const reason =
            status !== 'READY' &&
            typeof metric.reason === 'string'
              ? metric.reason
              : '';
          appendText(
            item,
            'span',
            'v38-live-metric-meta',
            [severity, reason]
              .filter(Boolean)
              .join(' • ')
          );
        }

        grid.appendChild(item);
      }
    );

    node.appendChild(grid);
  }

  function renderRs(view) {
    const node = stateNode('t-rs');
    const rs =
      view && view.rs &&
      typeof view.rs === 'object'
        ? view.rs
        : null;

    if (!node || !rs) {
      return;
    }

    node.replaceChildren();
    node.classList.add('v38-live-bound');
    node.dataset.v38Status =
      typeof rs.status === 'string'
        ? rs.status
        : 'DATA_REQUIRED';

    const head =
      document.createElement('div');
    head.className = 'v38-live-head';
    appendText(
      head,
      'strong',
      '',
      String(rs.title || 'RS189 Top 24') +
        ' • ' +
        String(view.session_date || '—')
    );
    appendText(
      head,
      'span',
      'v38-live-status',
      node.dataset.v38Status
    );
    node.appendChild(head);

    appendText(
      node,
      'div',
      'v38-live-note',
      rs.note || ''
    );

    if (
      !Array.isArray(rs.rows) ||
      rs.rows.length === 0
    ) {
      appendText(
        node,
        'div',
        'v38-live-note',
        rs.reason || 'RS data unavailable.'
      );
      return;
    }

    const list =
      document.createElement('div');
    list.className = 'v38-rs-list';

    const header =
      document.createElement('div');
    header.className = 'v38-rs-row';
    appendText(header, 'span', '', '#');
    appendText(header, 'span', '', 'Ticker');
    appendText(header, 'span', 'v38-num', 'Price');
    appendText(header, 'span', 'v38-num', 'RS189');
    appendText(header, 'span', 'v38-num', 'RS63');
    list.appendChild(header);

    rs.rows.forEach(
      (row) => {
        if (!row || typeof row !== 'object') {
          return;
        }

        const line =
          document.createElement('div');
        line.className = 'v38-rs-row';
        line.dataset.v38RsTicker =
          String(row.ticker || '');

        appendText(line, 'span', '', row.rank);
        appendText(line, 'span', '', row.ticker || '—');
        appendText(line, 'span', 'v38-num', row.price_display || '—');
        appendText(line, 'span', 'v38-num', row.rs189_display || '—');
        appendText(line, 'span', 'v38-num', row.rs63_display || '—');
        list.appendChild(line);
      }
    );

    node.appendChild(list);
  }

  function renderLiveView(view) {
    ensureLiveStyles();
    renderDaily(view);
    renderRs(view);
  }

  async function loadProductionData() {
    const runtime =
      window.V38Runtime;

    if (
      !runtime ||
      typeof runtime.loadJson !==
        'function'
    ) {
      setAllUnavailable(
        'Runtime unavailable. ' +
        'Mock values remain shielded.'
      );
      return;
    }

    try {
      const payload =
        await runtime.loadJson(
          'data/ui_payload.json'
        );

      renderPayload(payload);
    } catch (_) {
      setAllUnavailable(
        'Authoritative ui_payload.json ' +
        'is unavailable. ' +
        'Mock values remain shielded.'
      );
      return;
    }

    try {
      const view =
        await runtime.loadJson(
          'data/ui_view_model.json'
        );

      renderLiveView(view);
    } catch (_) {
      // Keep the already rendered fail-closed payload state.
    }
  }

  document.addEventListener(
    'DOMContentLoaded',
    () => {
      suppressMockContent();

      document
        .querySelectorAll(
          TAB_SELECTOR
        )
        .forEach(
          (tab) => {
            tab.addEventListener(
              'click',
              (event) => {
                const target =
                  targetOf(tab);

                if (!target) {
                  return;
                }

                event.preventDefault();

                activate(
                  target,
                  true
                );
              }
            );
          }
        );

      const requested =
        window.location.hash
          ? window.location.hash.slice(1)
          : '';

      const initiallyActive =
        Array.from(
          document.querySelectorAll(
            TAB_SELECTOR
          )
        ).find(
          (tab) =>
            tab.classList.contains(
              'on'
            )
        );

      activate(
        SECTION_IDS.includes(requested)
          ? requested
          : (
              initiallyActive
                ? targetOf(
                    initiallyActive
                  )
                : 't-market'
            ),
        false
      );

      loadProductionData();
    }
  );
})();
