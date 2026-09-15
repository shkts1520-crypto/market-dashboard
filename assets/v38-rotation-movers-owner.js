(function () {
  'use strict';

  let rotationSnapshot = null;
  let moversSnapshot = null;
  let captured = false;

  function cardByText(section, token) {
    if (!section) return null;
    return Array.from(section.querySelectorAll('.card')).find(function (card) {
      return String(card.textContent || '').includes(token);
    }) || null;
  }

  function stampThemeRows(section) {
    const card = cardByText(section, 'サブテーマ別RS');
    if (!card) return;
    const rows = card.querySelectorAll('tbody tr').length;
    card.dataset.v38Status = rows > 0 ? 'READY' : 'DATA_REQUIRED';
    card.dataset.v38ThemeRows = String(rows);
  }

  function bindTickerButtons(root) {
    root.querySelectorAll('button.v38-ticker-link').forEach(function (button) {
      button.onclick = function () {
        const ticker = String(button.textContent || '').trim();
        if (ticker && window.V38OpenTickerChart) window.V38OpenTickerChart(ticker);
      };
    });
  }

  function bindRotationControls(section) {
    section.querySelectorAll('.rrgtog').forEach(function (toggle) {
      const buttons = Array.from(toggle.querySelectorAll('button'));
      const card = toggle.closest('.card');
      if (!card) return;
      const rrgViews = Array.from(card.querySelectorAll('.rrgview.rrg-per'));
      const heatmaps = Array.from(card.querySelectorAll('.hmgrid'));
      buttons.forEach(function (button, index) {
        button.onclick = function () {
          buttons.forEach(function (item) { item.classList.remove('on'); });
          button.classList.add('on');
          if (rrgViews.length) {
            rrgViews.forEach(function (view, viewIndex) {
              view.style.display = viewIndex === index ? '' : 'none';
            });
          }
          if (heatmaps.length) {
            heatmaps.forEach(function (grid, gridIndex) {
              grid.style.display = gridIndex === index ? '' : 'none';
            });
          }
        };
      });
    });
    bindTickerButtons(section);
  }

  function capture() {
    if (captured) return true;
    if (!document.body || document.body.dataset.v38RotationMoversVisual !== 'applied') return false;
    const rotation = document.getElementById('t-rotation');
    const movers = document.getElementById('t-movers');
    if (!rotation || !movers || !cardByText(rotation, 'サブテーマ別RS') || !movers.querySelector('.mv-wrap')) return false;
    stampThemeRows(rotation);
    rotationSnapshot = rotation.outerHTML;
    moversSnapshot = movers.outerHTML;
    captured = true;
    document.body.dataset.v38RotationMoversOwner = 'captured';
    return true;
  }

  function restore(id, markup) {
    const current = document.getElementById(id);
    if (!current || !markup) return null;
    const active = current.classList.contains('on') || current.getAttribute('aria-hidden') === 'false' || current.style.display === 'block';
    const holder = document.createElement('div');
    holder.innerHTML = markup;
    const restored = holder.firstElementChild;
    if (!restored) return null;
    restored.classList.toggle('on', active);
    restored.style.display = active ? 'block' : 'none';
    restored.setAttribute('aria-hidden', active ? 'false' : 'true');
    current.replaceWith(restored);
    return restored;
  }

  function enforce() {
    if (!capture()) return;
    let rotation = document.getElementById('t-rotation');
    if (rotation && (rotation.querySelector('.v38-canonical-rotation') || !cardByText(rotation, 'サブテーマ別RS'))) {
      rotation = restore('t-rotation', rotationSnapshot);
      if (rotation) {
        stampThemeRows(rotation);
        bindRotationControls(rotation);
      }
    } else if (rotation) {
      stampThemeRows(rotation);
    }

    let movers = document.getElementById('t-movers');
    if (movers && !movers.querySelector('.mv-wrap')) {
      movers = restore('t-movers', moversSnapshot);
      if (movers) bindTickerButtons(movers);
    }
    document.body.dataset.v38RotationMoversOwner = 'stable';
  }

  function start() {
    let ticks = 0;
    const timer = window.setInterval(function () {
      ticks += 1;
      enforce();
      if (ticks >= 60) window.clearInterval(timer);
    }, 100);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start, {once: true});
  } else {
    start();
  }
})();
