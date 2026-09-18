(function () {
  'use strict';

  const OPTIONS_URL = 'data/options/index.json';
  const TAB_ID = 't-options';
  const BUCKETS = ['0-6', '7-21', '22-45', '0-45'];
  let optionsPromise = null;

  function finite(value) {
    if (value === null || value === undefined || value === '') return null;
    const number = Number(value);
    return Number.isFinite(number) ? number : null;
  }

  function price(value) {
    const number = finite(value);
    return number === null ? '—' : number.toFixed(2);
  }

  function netGexText(value) {
    const number = finite(value);
    if (number === null) return '—';
    const abs = Math.abs(number);
    if (abs >= 1e9) return (number < 0 ? '-' : '') + (abs / 1e9).toFixed(1) + 'B';
    if (abs >= 1e6) return (number < 0 ? '-' : '') + (abs / 1e6).toFixed(1) + 'M';
    if (abs >= 1e3) return (number < 0 ? '-' : '') + (abs / 1e3).toFixed(1) + 'K';
    return number.toFixed(0);
  }

  function el(parent, tag, cls, text) {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined) node.textContent = String(text);
    if (parent) parent.appendChild(node);
    return node;
  }

  function optionRows(options, bucket) {
    const raw = options && options.buckets ? options.buckets[bucket] : null;
    if (Array.isArray(raw)) return raw.slice(0, 24);
    if (raw && Array.isArray(raw.rows)) return raw.rows.slice(0, 24);
    return [];
  }

  function injectStyle() {
    if (document.getElementById('source-mc57-options-style')) return;
    const style = document.createElement('style');
    style.id = 'source-mc57-options-style';
    style.textContent =
      '#t-options .v38-source-options-ticker{' +
      'appearance:none;border:0;background:transparent;padding:0;margin:0;' +
      'font:inherit;font-size:13px;font-weight:800;color:#2c69c9;cursor:pointer;text-align:left}' +
      '#t-options .v38-source-options-ticker:active{opacity:.65}' +
      '#t-options .v38-empty{font-size:11px;color:#575242;padding:8px 2px}' +
      '#t-options .v38-options-list{display:grid;grid-template-columns:1fr;gap:12px}' +
      '@media(min-width:760px){#t-options .v38-options-list{grid-template-columns:repeat(2,minmax(0,1fr))}}';
    document.head.appendChild(style);
  }

  function ensureTabAndSection() {
    injectStyle();
    const nav = document.querySelector('nav');
    if (!nav) return null;

    let tabLink = nav.querySelector('a.tabx[href="#' + TAB_ID + '"]');
    if (!tabLink) {
      tabLink = document.createElement('a');
      tabLink.className = 'tabx';
      tabLink.href = '#' + TAB_ID;
      tabLink.textContent = 'Options';
      tabLink.setAttribute('onclick', "tab('t-options',this);return false;");
      const publish = nav.querySelector('a.tabx[href="#t-post1"]');
      nav.insertBefore(tabLink, publish || null);
    }

    let section = document.getElementById(TAB_ID);
    if (!section) {
      section = document.createElement('section');
      section.id = TAB_ID;
      const publishSection = document.getElementById('t-post1');
      if (publishSection && publishSection.parentNode) {
        publishSection.parentNode.insertBefore(section, publishSection);
      } else {
        const wrap = nav.parentElement || document.body;
        wrap.appendChild(section);
      }
    }
    return section;
  }

  function renderUnavailable(section) {
    section.replaceChildren();
    const msec = el(section, 'div', 'msec');
    const left = el(msec, 'div', 'msec-l', 'Options Intelligence');
    el(left, 'span', 'msec-en', 'DTE Matrix');
    el(msec, 'div', 'msec-q', '期間別に全銘柄を走査。Wall配置とExpected Moveを比較。');
    const card = el(section, 'div', 'card rsx-card');
    el(card, 'h2', '', 'Options');
    el(card, 'div', 'v38-empty', 'Optionsデータ未取得');
    section.dataset.v38Status = 'DATA_REQUIRED';
  }

  function renderOptions(options) {
    const section = ensureTabAndSection();
    if (!section) return;

    section.replaceChildren();
    const root = el(section, 'div', 'v38-canonical-options');
    root.dataset.v38CanonicalVisual = 'options-v5';

    const msec = el(root, 'div', 'msec');
    const left = el(msec, 'div', 'msec-l', 'Options Intelligence');
    el(left, 'span', 'msec-en', 'DTE Matrix');
    el(msec, 'div', 'msec-q', '期間別に全銘柄を走査。Wall配置とExpected Moveを比較。');

    const list = el(root, 'div', 'v38-options-list');

    BUCKETS.forEach(function (bucket) {
      const rows = optionRows(options, bucket);
      const card = el(list, 'div', 'card rsx-card');
      const title = bucket.replace('-', '–') + ' DTE';
      card.dataset.v38Status = 'READY';
      card.dataset.v38OptionBucket = bucket;
      card.dataset.v38OptionRows = String(rows.length);

      const hdr = el(card, 'div', 'hdr');
      const h2 = el(hdr, 'h2', '', title);
      el(
        h2,
        'span',
        'h2en',
        bucket === '0-6' ? 'Short Term' :
        bucket === '7-21' ? 'Swing' :
        bucket === '22-45' ? 'Medium Term' : 'All 0–45'
      );
      el(
        card,
        'div',
        'sub',
        'ランキングは期間ごとに独立。Spot・Wall・Flip・Expected Move・Qualityを同じ行で確認。'
      );

      if (!rows.length) {
        el(card, 'div', 'v38-empty', '該当データなし');
        return;
      }

      rows.forEach(function (rowData, index) {
        const ticker = String(rowData.ticker || '').trim().toUpperCase();
        const item = el(card, 'div', 'rsx-item');
        if (ticker) item.dataset.v38Ticker = ticker;

        const row = el(item, 'div', 'rsx-row');
        el(row, 'span', 'rsx-rk', index + 1);

        const name = el(row, 'div', 'rsx-name');
        const nameLine = el(name, 'div');
        const button = el(nameLine, 'button', 'v38-source-options-ticker', ticker || '—');
        button.type = 'button';
        if (ticker) button.dataset.v38Ticker = ticker;
        el(name, 'small', '', rowData.theme || rowData.sector || rowData.expiry || 'Options');

        const score = el(row, 'div', 'rsx-score');
        el(score, 'b', '', netGexText(rowData.net_gex));
        el(score, 'small', '', 'Net GEX');

        const sub = el(item, 'div', 'rsx-sub');
        const nums = el(sub, 'span', 'rsx-nums', 'Spot ');
        el(nums, 'b', '', price(rowData.spot));
        nums.append(' ・ Call / Flip / Put ');
        el(
          nums,
          'b',
          '',
          price(rowData.call_wall) + ' / ' +
          price(rowData.gamma_flip) + ' / ' +
          price(rowData.put_wall)
        );

        const ret = el(sub, 'span', 'rsx-ret', 'Expected Move ');
        const expectedMove = finite(rowData.expected_move_pct);
        el(ret, 'b', '', expectedMove === null ? '—' : '±' + (100 * expectedMove).toFixed(1) + '%');
        ret.append(' ・ Quality ');
        el(ret, 'b', '', String(rowData.quality || 'READY'));
      });
    });

    section.dataset.v38Status = options.status || 'READY';
    section.dataset.v38OptionsRestoreStatus = 'canonical-v5-layout-ready';
  }

  function loadOptions() {
    if (!optionsPromise) {
      optionsPromise = fetch(OPTIONS_URL, {cache: 'no-store'})
        .then(function (response) {
          if (!response.ok) throw new Error('options HTTP ' + response.status);
          return response.json();
        });
    }
    return optionsPromise;
  }

  function start() {
    const section = ensureTabAndSection();
    if (!section) return;
    loadOptions().then(renderOptions).catch(function () {
      renderUnavailable(section);
    });
  }

  document.readyState === 'loading'
    ? document.addEventListener('DOMContentLoaded', start, {once: true})
    : start();
})();