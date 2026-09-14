(function () {
  'use strict';

  var busy = false;
  var queued = false;

  var CSS = `
/* Visual-only source fidelity layer. No market calculations live here. */
#v38-universe-search{max-width:none!important;margin:0 0 12px!important;padding:12px 14px!important;position:static!important;z-index:auto!important}
#v38-universe-search .v38-search-head{display:block!important;margin:0!important}
#v38-universe-search .v38-search-head h2{font-size:14.5px!important;font-weight:800!important;margin:0 0 7px!important;color:#1b1a18!important}
#v38-universe-search .v38-search-head .h2en,#v38-universe-search .v38-search-clear{display:none!important}
#v38-universe-search .sub{font-size:11px!important;color:#565243!important;line-height:1.55!important;margin:-3px 0 9px!important}
#v38-universe-search .v38-searchbox{position:static!important}
#v38-universe-search .tksearch{width:100%!important;background:#f2f1ee!important;border:1px solid #d6d4ca!important;border-radius:9px!important;color:#1c1b19!important;font:inherit!important;font-size:15px!important;font-weight:400!important;padding:10px 12px!important;margin-top:4px!important}
#v38-universe-search .tksearch:focus{outline:none!important;border-color:#1c427d!important}
#v38-universe-search .tkresults{position:static!important;inset:auto!important;max-height:none!important;overflow:visible!important;background:transparent!important;border:0!important;border-radius:0!important;box-shadow:none!important;margin-top:8px!important;display:flex!important;flex-direction:column!important;gap:5px!important}
#v38-universe-search .tkresults[hidden]{display:none!important}
#v38-universe-search .v38-search-result{width:100%!important;display:flex!important;align-items:center!important;gap:8px!important;background:#f2f1ee!important;border:1px solid #e3e1db!important;border-radius:8px!important;padding:8px 10px!important;cursor:pointer!important;text-align:left!important;color:#1c1b19!important;font:inherit!important}
#v38-universe-search .v38-search-result b{font-size:14px!important;font-weight:800!important;color:#2c69c9!important;flex:0 0 62px!important}
#v38-universe-search .v38-search-result span{font-size:11px!important;color:#5a5850!important;flex:1!important;overflow:hidden!important;text-overflow:ellipsis!important;white-space:nowrap!important}
#v38-universe-search .v38-search-result em{font-size:11px!important;color:#575242!important;flex:0 0 auto!important;font-style:normal!important}
#v38-universe-search .v38-search-result:active{background:#e4e2dc!important}

#t-options .v38-canonical-options .card.rsx-card{margin-bottom:12px!important}
#t-options .v38-options-list{display:block!important}

#t-rs .v38-vwap-card .vwtbl{table-layout:fixed!important;width:100%!important;font-size:11px!important}
#t-rs .v38-vwap-card .vwtbl th,#t-rs .v38-vwap-card .vwtbl td{white-space:normal!important;overflow-wrap:anywhere!important;vertical-align:top!important;line-height:1.25!important;padding:5px 3px!important}
#t-rs .v38-vwap-card .vwtbl th:nth-child(1){width:20%!important}
#t-rs .v38-vwap-card .vwtbl th:nth-child(n+2){width:20%!important}
#t-rs .v38-vwap-card .v38-vwap-hit{border:0!important;background:transparent!important;padding:0!important;color:inherit!important;font:inherit!important;font-weight:700!important;text-decoration:none!important}

#t-rotation .v38-source-rotation-wrap{position:relative;margin:4px 0}
#t-rotation .v38-source-rotation-wrap>.pfsbtn{display:inline-flex;align-items:center;gap:6px;font-size:13px;font-weight:700;color:#3d4137;background:#DDDAD0;border:1px solid rgba(0,0,0,.14);border-radius:9px;padding:8px 15px;cursor:pointer;margin-bottom:8px}
#t-rotation .v38-source-rotation-frame{width:100%;aspect-ratio:1680/1080;border:1px solid #D5D1C6;border-radius:12px;display:block;background:#E9E7DF;overflow:hidden;position:relative}
#t-rotation .v38-source-stage{width:100%;height:100%;display:flex;align-items:center;justify-content:center;overflow:hidden}
#t-rotation .v38-source-scaler{width:1680px;height:1080px;flex:0 0 1680px;transform-origin:center center}
#t-rotation .v38-source-scaler>.card{width:1680px!important;height:1080px!important;max-width:none!important;margin:0!important;background:#E9E7DF!important;color:#1B1D1C!important;padding:18px 22px 12px!important;display:flex!important;flex-direction:column!important;font-family:-apple-system,'Helvetica Neue',Arial,'Hiragino Sans','Noto Sans JP',sans-serif!important;font-size:13.5px!important;--ink:#1B1D1C;--mut:#727569;--line:#D5D1C6;--card:#F6F4EE;--track:#DAD6CB;--accent:#17685C;--accent2:#2A9384;--pos:#1E7A4D;--posbg:#DBEBDF;--posbg2:#C6E0CC;--neg:#B23A2E;--negbg:#F1DED9;--negbg2:#E7C7C2;--neu:#7C7F78;--neubg:#E6E3DB;--warn:#B07A16;--warnbg:#F0E6CF;--chipbg:#EEEBE3;--fnum:ui-monospace,'SF Mono',Menlo,monospace}
#t-rotation .v38-source-scaler .hd{display:flex!important;align-items:center!important;gap:11px!important;margin-bottom:4px!important}
#t-rotation .v38-source-scaler .hd .bar{width:5px!important;height:21px!important;background:var(--accent)!important;border-radius:3px!important}
#t-rotation .v38-source-scaler .hd h1{font-size:22px!important;font-weight:800!important;letter-spacing:-.02em!important;margin:0!important}
#t-rotation .v38-source-scaler .hd .state,#t-rotation .v38-source-scaler .hd .pg{font-size:11.5px!important;font-weight:800!important;color:var(--accent)!important;border:1.5px solid var(--accent)!important;border-radius:8px!important;padding:2px 10px!important}
#t-rotation .v38-source-scaler .hd .date{margin-left:auto!important;font-size:13.5px!important;color:var(--mut)!important;font-weight:700!important}
#t-rotation .v38-source-scaler .read{font-size:13px!important;font-weight:700!important;color:#33352E!important;margin-bottom:8px!important;line-height:1.35!important;padding-bottom:8px!important;border-bottom:1.5px solid var(--line)!important}
#t-rotation .v38-source-scaler .grid{display:grid!important;grid-template-columns:repeat(4,1fr)!important;grid-template-rows:398px 1fr!important;gap:8px!important;flex:1!important;min-height:0!important}
#t-rotation .v38-source-scaler .sp2{grid-column:span 2!important}#t-rotation .v38-source-scaler .sp3{grid-column:span 3!important}
#t-rotation .v38-source-scaler .t{background:var(--card)!important;border:1px solid var(--line)!important;border-radius:10px!important;padding:9px 11px!important;min-height:0!important;overflow:hidden!important;display:flex!important;flex-direction:column!important}
#t-rotation .v38-source-scaler .th{display:flex!important;align-items:center!important;gap:6px!important;margin-bottom:6px!important}
#t-rotation .v38-source-scaler .th h4{font-size:12.5px!important;font-weight:800!important;letter-spacing:-.01em!important}.v38-source-scaler .th .s{font-size:10px!important;color:var(--mut)!important;font-weight:700!important}.v38-source-scaler .th .g{margin-left:auto!important;color:var(--mut)!important;opacity:.5!important;font-size:12px!important}
#t-rotation .v38-source-scaler .prg{display:grid!important;grid-template-columns:repeat(4,1fr)!important;gap:11px!important;flex:1!important;min-height:0!important}#t-rotation .v38-source-scaler .prg.tight{gap:8px!important}
#t-rotation .v38-source-scaler .prcol{display:flex!important;flex-direction:column!important;min-height:0!important}.v38-source-scaler .prcol .ph{font-size:10.5px!important;font-weight:800!important;color:var(--accent)!important;text-align:center!important;border-bottom:1.5px solid var(--line)!important;padding-bottom:3px!important;margin-bottom:2px!important}.v38-source-scaler .prcol .body{flex:1!important;display:flex!important;flex-direction:column!important;justify-content:space-between!important;min-height:0!important}
#t-rotation .v38-source-scaler .prrow{display:grid!important;grid-template-columns:8px 13px 1fr auto 20px!important;gap:5px!important;align-items:center!important;white-space:nowrap!important}.v38-source-scaler .prrow .rk{color:var(--mut)!important;text-align:center!important}.v38-source-scaler .prrow .nm{font-weight:700!important;overflow:hidden!important;text-overflow:ellipsis!important}.v38-source-scaler .prrow .rv{font-weight:800!important;font-family:var(--fnum)!important;text-align:right!important}.v38-source-scaler .prrow .ar{font-weight:800!important;text-align:right!important}
#t-rotation .v38-source-scaler .maj .prrow{font-size:12px!important}#t-rotation .v38-source-scaler .min .prrow{font-size:10px!important}
#t-rotation .v38-source-rotation-wrap>.pfsclose{display:none}
#t-rotation .v38-source-rotation-wrap.fs{position:fixed;inset:0;z-index:99999;background:#E9E7DF;display:flex;align-items:center;justify-content:center;margin:0}
#t-rotation .v38-source-rotation-wrap.fs>.pfsbtn{display:none}
#t-rotation .v38-source-rotation-wrap.fs>.v38-source-rotation-frame{width:100vw;height:100vh;max-width:none;aspect-ratio:auto;border-radius:0;border:0}
#t-rotation .v38-source-rotation-wrap.fs>.pfsclose{display:flex;align-items:center;justify-content:center;position:fixed;top:calc(env(safe-area-inset-top,0px) + 10px);right:10px;z-index:100000;width:34px;height:34px;font-size:16px;font-weight:700;color:#fff;background:rgba(0,0,0,.45);border:1px solid rgba(255,255,255,.3);border-radius:50%;cursor:pointer;padding:0;line-height:1}
body.fslock{overflow:hidden!important}
@media(max-width:520px){#t-rs .v38-vwap-card .vwtbl{font-size:9.5px!important}#t-rs .v38-vwap-card .vwtbl th,#t-rs .v38-vwap-card .vwtbl td{padding:4px 2px!important}#t-rs .v38-vwap-card .vwtbl .mut{font-size:8px!important}}
`;

  function installStyle() {
    var style = document.getElementById('v38-source-fidelity-style');
    if (!style) {
      style = document.createElement('style');
      style.id = 'v38-source-fidelity-style';
      style.textContent = CSS;
      document.head.appendChild(style);
    }
  }

  function make(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text != null) node.textContent = text;
    return node;
  }

  function normalizeSearch() {
    var card = document.getElementById('v38-universe-search');
    if (!card) return;
    var section = document.getElementById('t-today') || document.getElementById('t-daily');
    if (section && !section.contains(card)) {
      var headers = Array.from(section.querySelectorAll('.msec'));
      var tools = headers.find(function (node) { return /道具|Tools/i.test(node.textContent || ''); });
      if (tools) tools.insertAdjacentElement('afterend', card);
    }
    var input = card.querySelector('.tksearch');
    var results = card.querySelector('.tkresults');
    if (input) input.id = 'tksearch';
    if (results) input && (results.id = 'tkresults');
    card.dataset.v38SourceFidelity = 'ticker-search';
  }

  function normalizeOptions() {
    var root = document.querySelector('#t-options .v38-canonical-options');
    if (!root) return;
    var list = root.querySelector(':scope > .v38-options-list');
    if (list) {
      Array.from(list.children).forEach(function (card) { root.appendChild(card); });
      list.remove();
    }
    root.dataset.v38SourceFidelity = 'native-rsx-stack';
  }

  function cellText(cell) { return cell ? (cell.textContent || '').trim() : '—'; }

  function signalClass(text) {
    if (/回復|上抜|維持|ブレイク|強/.test(text)) return 'pos';
    if (/割れ|下抜|弱/.test(text)) return 'neg';
    return 'mut';
  }

  function addSetupCell(row, signal, value) {
    var td = make('td');
    var b = make('b', signalClass(signal), signal || '—');
    var d = make('div', 'mut', value || '—');
    d.style.fontSize = '9px';
    td.appendChild(b); td.appendChild(d); row.appendChild(td);
  }

  function normalizeVwap() {
    var card = document.querySelector('#t-rs .v38-vwap-card');
    if (!card) return;
    var table = card.querySelector('table');
    if (!table || table.dataset.v38SourceFidelity === 'five-column') return;
    var rows = Array.from(table.querySelectorAll('tr'));
    if (!rows.length) return;
    var headers = Array.from(rows[0].children);
    if (headers.length >= 7) {
      var nextHead = make('tr');
      ['銘柄','63 VWAP','252 VWAP','上場来VWAP','上場来ブレイク'].forEach(function (label, index) {
        var th = make('th', index === 0 ? 'l' : '', label); nextHead.appendChild(th);
      });
      rows[0].replaceWith(nextHead);
      rows.slice(1).forEach(function (row) {
        var cells = Array.from(row.children);
        if (cells.length < 7) return;
        var next = make('tr');
        var ticker = make('td', 'l tk');
        var button = cells[0].querySelector('button');
        if (button) ticker.appendChild(button); else ticker.textContent = cellText(cells[0]);
        next.appendChild(ticker);
        addSetupCell(next, cellText(cells[2]), cellText(cells[1]));
        addSetupCell(next, cellText(cells[4]), cellText(cells[3]));
        next.appendChild(make('td', 'mut', cellText(cells[5])));
        var life = cellText(cells[6]);
        next.appendChild(make('td', /^\+/.test(life) ? 'pos' : (/^-/.test(life) ? 'neg' : 'mut'), life));
        row.replaceWith(next);
      });
    }
    table.classList.add('vwtbl');
    table.dataset.v38SourceFidelity = 'five-column';
    card.dataset.v38SourceFidelity = 'vwap-five-column';
  }

  function fitRotation(wrap) {
    if (!wrap) return;
    var frame = wrap.querySelector('.v38-source-rotation-frame');
    var scaler = wrap.querySelector('.v38-source-scaler');
    if (!frame || !scaler) return;
    var rect = frame.getBoundingClientRect();
    var w = rect.width || frame.clientWidth;
    var h = rect.height || frame.clientHeight;
    if (!w || !h) return;
    var full = wrap.classList.contains('fs');
    var portrait = full && h > w;
    var scale = portrait ? Math.min(w / 1080, h / 1680) : Math.min(w / 1680, h / 1080);
    scaler.style.transform = portrait ? 'rotate(90deg) scale(' + scale + ')' : 'scale(' + scale + ')';
  }

  function normalizeRotation() {
    var root = document.querySelector('#t-rotation .v38-canonical-rotation');
    if (!root) return;
    var existing = root.querySelector(':scope > .v38-source-rotation-wrap');
    if (existing) { fitRotation(existing); return; }
    var card = root.querySelector(':scope > .card');
    if (!card) return;

    var header = make('div', 'msec v38-source-rotation-header');
    var left = make('div', 'msec-l', 'セクター・ローテーション');
    left.appendChild(make('span', 'msec-en', 'Sector Rotation'));
    header.appendChild(left);
    header.appendChild(make('div', 'msec-q', 'SNS共有用カード'));

    var wrap = make('div', 'postwrap v38-source-rotation-wrap');
    var open = make('button', 'pfsbtn', '⛶ 全画面表示'); open.type = 'button';
    var frame = make('div', 'postframe v38-source-rotation-frame');
    var stage = make('div', 'v38-source-stage');
    var scaler = make('div', 'v38-source-scaler');
    var close = make('button', 'pfsclose', '✕'); close.type = 'button';
    scaler.appendChild(card); stage.appendChild(scaler); frame.appendChild(stage);
    wrap.appendChild(open); wrap.appendChild(frame); wrap.appendChild(close);
    root.replaceChildren(header, wrap);

    open.addEventListener('click', function () { wrap.classList.add('fs'); document.body.classList.add('fslock'); fitRotation(wrap); });
    close.addEventListener('click', function () { wrap.classList.remove('fs'); document.body.classList.remove('fslock'); fitRotation(wrap); });
    root.dataset.v38SourceFidelity = 'rotation-1680x1080';
    fitRotation(wrap);
  }

  function apply() {
    if (busy) return;
    busy = true;
    try {
      installStyle(); normalizeSearch(); normalizeOptions(); normalizeVwap(); normalizeRotation();
      document.body.dataset.v38SourceFidelity = 'canonical-v5';
    } finally { busy = false; queued = false; }
  }

  function queue() {
    if (queued) return; queued = true; setTimeout(apply, 0);
  }

  window.addEventListener('resize', queue);
  document.addEventListener('v38:data-ready', queue);
  new MutationObserver(queue).observe(document.documentElement, {childList:true, subtree:true});
  [0,120,500,900,1700,3000,4700].forEach(function (ms) { setTimeout(apply, ms); });
})();
