(function (global) {
  'use strict';

  const REQUIRED_META = [
    'session_date',
    'generated_at',
    'coverage',
    'source',
    'schema_version',
    'calculation_version'
  ];

  function missing(value) {
    return value === null ||
      value === undefined ||
      value === '' ||
      (
        typeof value === 'number' &&
        !Number.isFinite(value)
      );
  }

  function display(
    value,
    decimals
  ) {
    if (missing(value)) {
      return '—';
    }

    if (
      typeof value === 'number' &&
      Number.isInteger(decimals)
    ) {
      return value.toFixed(
        decimals
      );
    }

    return String(value);
  }

  function assessShard(
    obj,
    targetSession
  ) {
    if (
      !obj ||
      typeof obj !== 'object' ||
      Array.isArray(obj)
    ) {
      return {
        status: 'DATA_REQUIRED',
        reason: 'EXPECTED_JSON_OBJECT'
      };
    }

    const absent =
      REQUIRED_META.filter(
        (key) => !(key in obj)
      );

    if (absent.length) {
      return {
        status: 'DATA_REQUIRED',
        reason: 'MISSING_METADATA',
        missing: absent
      };
    }

    if (
      obj.session_date !==
      targetSession
    ) {
      return {
        status: 'STALE',
        reason: 'SESSION_MISMATCH',
        session_date:
          obj.session_date
      };
    }

    return {
      status: 'READY',
      reason: 'CURRENT_SESSION'
    };
  }

  async function loadJson(path) {
    const response =
      await fetch(
        path,
        {
          cache: 'no-store'
        }
      );

    if (!response.ok) {
      throw new Error(
        'HTTP ' +
        response.status +
        ' for ' +
        path
      );
    }

    return response.json();
  }

  function finite(value) {
    const number = Number(value);
    return Number.isFinite(number) ? number : null;
  }

  function node(tag, className, text) {
    const out = document.createElement(tag);
    if (className) out.className = className;
    if (text !== undefined && text !== null) out.textContent = String(text);
    return out;
  }

  function findCard(section, titlePart) {
    return Array.from(section.querySelectorAll('.card')).find((card) => {
      const title = String(card.dataset.v38CardTitle || '');
      return title.includes(titlePart);
    }) || null;
  }

  function insertBeforeStatus(card, child) {
    const note = card.querySelector('.v38-bind-note');
    if (note) card.insertBefore(child, note);
    else card.appendChild(child);
  }

  function sparkline(parent, points, colour, height) {
    const values = (Array.isArray(points) ? points : []).map((point) => {
      if (!point || typeof point !== 'object') return null;
      const value = finite(point.value !== undefined ? point.value : point.close);
      return value === null ? null : value;
    }).filter((value) => value !== null);
    if (!values.length) return null;

    const width = 680;
    const chartHeight = height || 58;
    const padX = 6;
    const padY = 6;
    let low = Math.min.apply(null, values);
    let high = Math.max.apply(null, values);
    if (high === low) {
      high += 1;
      low -= 1;
    }
    const x = (index) => padX + (width - padX * 2) * index / Math.max(1, values.length - 1);
    const y = (value) => padY + (chartHeight - padY * 2) * (high - value) / (high - low);
    const coords = values.map((value, index) => [x(index), y(value)]);
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('class', 'spark v38-live-spark v38-mc57-spark');
    svg.setAttribute('viewBox', '0 0 ' + width + ' ' + chartHeight);
    svg.setAttribute('preserveAspectRatio', 'none');
    svg.setAttribute('role', 'img');
    svg.setAttribute('aria-label', 'MC57 historical trend');

    const area = document.createElementNS(svg.namespaceURI, 'path');
    const path = coords.map((point, index) => (index ? 'L' : 'M') + point[0].toFixed(1) + ',' + point[1].toFixed(1)).join(' ');
    area.setAttribute('d', path + ' L' + coords[coords.length - 1][0].toFixed(1) + ',' + (chartHeight - padY) + ' L' + coords[0][0].toFixed(1) + ',' + (chartHeight - padY) + ' Z');
    area.setAttribute('fill', colour || '#1E7A4D');
    area.setAttribute('opacity', '0.08');
    svg.appendChild(area);

    const line = document.createElementNS(svg.namespaceURI, 'polyline');
    line.setAttribute('points', coords.map((point) => point[0].toFixed(1) + ',' + point[1].toFixed(1)).join(' '));
    line.setAttribute('fill', 'none');
    line.setAttribute('stroke', colour || '#1E7A4D');
    line.setAttribute('stroke-width', '2');
    svg.appendChild(line);

    const dot = document.createElementNS(svg.namespaceURI, 'circle');
    dot.setAttribute('cx', coords[coords.length - 1][0].toFixed(1));
    dot.setAttribute('cy', coords[coords.length - 1][1].toFixed(1));
    dot.setAttribute('r', '3.0');
    dot.setAttribute('fill', colour || '#1E7A4D');
    svg.appendChild(dot);
    parent.appendChild(svg);
    return svg;
  }

  function trendBlock(card, label, current, points, colour, suffix, decimals) {
    if (!card || !Array.isArray(points) || !points.length) return;
    const block = node('div', 'v38-mc57-trend', '');
    const row = node('div', 'v38-live-kv', '');
    row.appendChild(node('span', '', label));
    const value = finite(current);
    const text = value === null ? '—' : value.toFixed(decimals === undefined ? 1 : decimals) + (suffix || '');
    row.appendChild(node('b', '', text));
    block.appendChild(row);
    sparkline(block, points, colour, 58);
    insertBeforeStatus(card, block);
  }

  function noteBlock(card, text) {
    if (!card) return;
    const line = node('div', 'v38-bind-note', text);
    insertBeforeStatus(card, line);
  }

  function decorateMc57(view) {
    const daily = view && view.daily && typeof view.daily === 'object' ? view.daily : null;
    const detail = daily && daily.mc57_detail && typeof daily.mc57_detail === 'object' ? daily.mc57_detail : null;
    const section = document.getElementById('t-market');
    if (!daily || !section) return;

    const pitSessions = Number(daily.pit_breadth_history_sessions || 0);
    ['ブレッドス推移（50', 'ブレッドス推移（200'].forEach((title) => {
      const card = findCard(section, title);
      if (card && !card.dataset.v38PitBreadthNote) {
        noteBlock(card, '通常株PIT履歴 ' + pitSessions + '営業日 • 遡及推計なし');
        card.dataset.v38PitBreadthNote = 'true';
      }
    });

    if (!detail || detail.status !== 'READY') return;
    const series = detail.series && typeof detail.series === 'object' ? detail.series : {};
    const current = detail.current && typeof detail.current === 'object' ? detail.current : {};

    const today = findCard(section, '今日のマーケット');
    if (today && !today.dataset.v38Mc57Decorated) {
      trendBlock(today, 'MC57 ' + detail.history_sessions + '日', current.mc57, series.mc57, '#1E7A4D', '', 1);
      trendBlock(today, 'MC57 Raw', current.raw, series.raw, '#2c69c9', '', 1);
      trendBlock(today, 'MC57 EMA2 Raw', current.ema2_raw, series.ema2_raw, '#7b5c36', '', 1);
      trendBlock(today, 'MC57 Z', current.z, series.z, '#B84A42', '', 2);
      today.dataset.v38Mc57Decorated = 'true';
    }

    const fixed = detail.fixed57_breadth && typeof detail.fixed57_breadth === 'object' ? detail.fixed57_breadth : {};
    const breadth50 = findCard(section, 'ブレッドス推移（50');
    if (breadth50 && !breadth50.dataset.v38Mc57BreadthDecorated) {
      trendBlock(breadth50, '57ETF 20MA上', fixed.sma20, series.fixed57_breadth_sma20, '#1E7A4D', '%', 1);
      trendBlock(breadth50, '57ETF 50MA上', fixed.sma50, series.fixed57_breadth_sma50, '#2c69c9', '%', 1);
      breadth50.dataset.v38Mc57BreadthDecorated = 'true';
    }

    const breadth200 = findCard(section, 'ブレッドス推移（200');
    if (breadth200 && !breadth200.dataset.v38Mc57BreadthDecorated) {
      trendBlock(breadth200, '57ETF 200MA上', fixed.sma200, series.fixed57_breadth_sma200, '#7b5c36', '%', 1);
      breadth200.dataset.v38Mc57BreadthDecorated = 'true';
    }

    const regime = findCard(section, 'レジーム警戒灯');
    if (regime && !regime.dataset.v38Mc57MetricDecorated) {
      const metricSeries = detail.metrics && typeof detail.metrics === 'object' ? detail.metrics : {};
      const scores = detail.metric_scores && typeof detail.metric_scores === 'object' ? detail.metric_scores : {};
      const available = Object.keys(metricSeries).filter((key) => Array.isArray(metricSeries[key]) && metricSeries[key].length).length;
      noteBlock(regime, 'MC57内部 12指標履歴 ' + available + '/12 • 固定57ETF');
      [
        ['21日プラス率', 'ret21_gt_0', '#1E7A4D'],
        ['63日プラス率', 'ret63_gt_0', '#2c69c9'],
        ['SMA20>SMA50', 'sma20_gt_sma50', '#7b5c36'],
        ['SMA50>SMA200', 'sma50_gt_sma200', '#B84A42'],
        ['52週高値DD score', 'dd52_continuous_score', '#1E7A4D']
      ].forEach((spec) => {
        trendBlock(regime, spec[0], scores[spec[1]], metricSeries[spec[1]], spec[2], '%', 1);
      });
      regime.dataset.v38Mc57MetricDecorated = 'true';
    }
  }

  function scheduleMc57Decoration() {
    let attempts = 0;
    const tick = async function () {
      attempts += 1;
      if (document.body && document.body.dataset.v38BindingStatus === 'ready') {
        try {
          const view = await loadJson('data/ui_view_model.json');
          decorateMc57(view);
        } catch (_) {
          return;
        }
        return;
      }
      if (attempts < 200) global.setTimeout(tick, 50);
    };
    global.setTimeout(tick, 0);
  }

  global.V38Runtime =
    Object.freeze(
      {
        missing,
        display,
        assessShard,
        loadJson,
        decorateMc57
      }
    );

  document.addEventListener('DOMContentLoaded', scheduleMc57Decoration);
})(window);
