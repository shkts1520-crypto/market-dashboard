(function () {
  'use strict';

  const SOURCE = 'build_dashboard(2).py';

  function norm(value) {
    return String(value || '').replace(/\s+/g, ' ').trim();
  }

  function originalTitle(card) {
    if (!card) return '';
    if (card.dataset.v38CardTitle) return norm(card.dataset.v38CardTitle);
    const heading = card.querySelector('h2,.hdr h2,.chd h2');
    return heading ? norm(heading.textContent) : '';
  }

  function sourceHeading(label, english, question) {
    const wrap = document.createElement('div');
    wrap.className = 'msec';
    wrap.dataset.v38PySource = '1';
    const line = document.createElement('div');
    const left = document.createElement('span');
    left.className = 'msec-l';
    left.textContent = label;
    line.appendChild(left);
    if (english) {
      const en = document.createElement('span');
      en.className = 'msec-en';
      en.textContent = english;
      line.appendChild(en);
    }
    wrap.appendChild(line);
    if (question) {
      const q = document.createElement('div');
      q.className = 'msec-q';
      q.textContent = question;
      wrap.appendChild(q);
    }
    return wrap;
  }

  function findCard(section, needle) {
    return Array.from(section.querySelectorAll('.card')).find((card) => originalTitle(card).includes(needle)) || null;
  }

  function reveal(card) {
    if (!card) return null;
    card.hidden = false;
    card.removeAttribute('hidden');
    card.classList.remove('v38-py-unbound');
    card.dataset.v38UiSource = SOURCE;
    return card;
  }

  function applyPositionsSourceLayout() {
    const section = document.getElementById('t-alloc');
    if (!section) return;

    const holdings = reveal(findCard(section, '保有ポジション'));
    const expected = reveal(findCard(section, '現在の想定ポジション'));
    const recovery = reveal(findCard(section, 'マーケット回復後'));
    const equity = reveal(findCard(section, 'エクイティカーブ×21日EMA'));

    section.querySelectorAll(':scope > .msec[data-v38-py-source="1"]').forEach((node) => node.remove());

    const fragment = document.createDocumentFragment();
    fragment.appendChild(sourceHeading(
      'トレード計画・保有記録',
      'Plan & Holdings',
      '現在の保有と、次の寄りで必要なアクションを確認'
    ));
    if (holdings) fragment.appendChild(holdings);

    fragment.appendChild(sourceHeading(
      '① 配分計算',
      'Position Sizing',
      '現在の市場モードから、新規枠と候補を確認'
    ));
    if (expected) fragment.appendChild(expected);

    fragment.appendChild(sourceHeading(
      '② 次回補充候補',
      'Next Entries',
      '空き枠は当日引け後判定→翌寄り。隔週の強制入替はしない'
    ));
    if (recovery) fragment.appendChild(recovery);

    fragment.appendChild(sourceHeading(
      '資産推移・口座',
      'Equity & Account',
      '口座資産の時系列は、正本データが接続されている場合だけ表示'
    ));
    if (equity) fragment.appendChild(equity);

    section.appendChild(fragment);
    section.dataset.v38UiSource = SOURCE;
    section.dataset.v38PositionsSource = 'ready';
  }

  async function afterAuthority() {
    try {
      await fetch('data/py_source_display.json', {cache: 'no-store'});
    } catch (_) {}
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    applyPositionsSourceLayout();
  }

  document.addEventListener('v38:view-ready', () => { void afterAuthority(); }, {once: true});
})();
