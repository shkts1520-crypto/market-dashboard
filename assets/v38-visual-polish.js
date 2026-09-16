(function () {
  'use strict';

  function finite(value) {
    if (value === null || value === undefined || value === '') return null;
    var n = Number(value);
    return Number.isFinite(n) ? n : null;
  }

  function findCard(sectionId, needle) {
    var section = document.getElementById(sectionId);
    if (!section) return null;
    return Array.from(section.querySelectorAll('.card')).find(function (node) {
      return String(node.textContent || '').indexOf(needle) >= 0;
    }) || null;
  }

  function repairSentiment(view) {
    var daily = (view && view.daily) || {};
    var sentiment = ((daily.display_observations || {}).sentiment) || {};
    var current = finite(sentiment.current);
    if (current === null) return;
    var node = findCard('t-market', 'センチメント');
    if (!node) return;
    var rows = Array.from(node.querySelectorAll('.v38-canonical-row'));
    var row = rows.find(function (item) {
      var left = item.querySelector('.v38-canonical-left');
      return left && String(left.textContent || '').trim() === '合成';
    });
    if (!row) return;
    var value = row.querySelector('.v38-canonical-value');
    if (!value) return;
    var band = String(sentiment.band || '').trim();
    value.textContent = band ? current.toFixed(0) + ' · ' + band : current.toFixed(0);
    row.dataset.v38DisplaySource = 'daily.display_observations.sentiment.current';
  }

  function repairBreadthChart(view, key) {
    var history = (((view || {}).daily || {}).history) || [];
    if (!Array.isArray(history)) return;
    var values = history.map(function (row) { return finite(row && row[key]); }).filter(function (v) { return v !== null; });
    if (values.length < 2) return;
    var maxAbs = Math.max.apply(null, values.map(Math.abs));
    if (maxAbs <= 1.5) values = values.map(function (v) { return v * 100; });

    var svg = document.querySelector('#t-market svg[data-v38-live-spark="' + key + '"]');
    if (!svg) return;
    var W = 680, H = 180, P = 6, R = 52;
    var x = function (i) { return P + i * (W - R - P) / Math.max(1, values.length - 1); };
    var y = function (v) { return P + (1 - Math.max(0, Math.min(100, v)) / 100) * (H - 2 * P); };
    var coords = values.map(function (v, i) { return x(i).toFixed(1) + ',' + y(v).toFixed(1); });
    var poly = svg.querySelector('polyline');
    var dot = svg.querySelector('circle');
    var area = Array.from(svg.querySelectorAll('path')).find(function (path) {
      return String(path.getAttribute('fill') || '').indexOf('url(') === 0;
    });
    if (poly) poly.setAttribute('points', coords.join(' '));
    if (dot) {
      dot.setAttribute('cx', x(values.length - 1).toFixed(1));
      dot.setAttribute('cy', y(values[values.length - 1]).toFixed(1));
    }
    if (area) {
      area.setAttribute('d', 'M' + coords[0] + ' ' + coords.slice(1).map(function (p) { return 'L' + p; }).join(' ') +
        ' L' + x(values.length - 1).toFixed(1) + ',' + (H - P) + ' L' + x(0).toFixed(1) + ',' + (H - P) + ' Z');
    }
    svg.dataset.v38BreadthScale = maxAbs <= 1.5 ? 'fraction-to-percent' : 'percent-points';
  }

  function repairBreadth(view) {
    repairBreadthChart(view, 'breadth50');
    repairBreadthChart(view, 'breadth200');
  }

  function polishPublishFrame(frame) {
    if (!frame || !frame.srcdoc) return;
    frame.style.setProperty('width', '100%', 'important');
    frame.style.setProperty('max-width', '100%', 'important');
    if (frame.dataset.v38VisualPolish === '1') return;
    var css = '<style id="v38-publish-visual-polish">' +
      '.card{padding:26px 30px 20px!important}' +
      '.hd{margin-bottom:12px!important;padding-bottom:10px;border-bottom:1px solid rgba(90,82,68,.14)}' +
      '.bar{height:28px!important}.hd h1{font-size:28px!important;letter-spacing:-.02em}' +
      '.state{font-size:14px!important;padding:4px 12px!important}.date{font-size:14px!important}' +
      '.grid{gap:12px!important}.panel{border-radius:13px!important;padding:12px 14px!important;background:#f7f5ef!important;box-shadow:0 1px 0 rgba(60,55,45,.05)}' +
      '.title{font-size:15px!important;margin-bottom:7px!important;letter-spacing:-.01em}.title small{font-size:10px!important;letter-spacing:.05em}' +
      '.big{font-size:32px!important;letter-spacing:-.035em}.sub{font-size:11.5px!important}.kv{font-size:11.5px!important;padding:4px 0!important}' +
      '.tbl{font-size:10.7px!important}.tbl th{font-size:9.2px!important}.pspark{height:72px!important}.theme{font-size:10.7px!important}' +
      '.rrg{height:150px!important}.note{font-size:9.8px!important}' +
      '</style>';
    if (frame.srcdoc.indexOf('</head>') >= 0) frame.srcdoc = frame.srcdoc.replace('</head>', css + '</head>');
    else frame.srcdoc = css + frame.srcdoc;
    frame.dataset.v38VisualPolish = '1';
  }

  function polishPublish() {
    document.querySelectorAll('#t-post1 .postframe').forEach(polishPublishFrame);
  }

  function apply(view) {
    var model = view || window.V38UiViewModel || {};
    repairSentiment(model);
    repairBreadth(model);
    polishPublish();
    document.documentElement.dataset.v38VisualPolish = 'ready';
  }

  function schedule(view) {
    [0, 100, 300, 900].forEach(function (delay) {
      setTimeout(function () { apply(view); }, delay);
    });
  }

  document.addEventListener('v38:view-ready', function (event) { schedule(event.detail || {}); });
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { schedule(window.V38UiViewModel || {}); }, {once:true});
  } else {
    schedule(window.V38UiViewModel || {});
  }
})();
