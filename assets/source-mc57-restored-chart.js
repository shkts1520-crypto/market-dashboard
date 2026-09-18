/* Clone-only ticker chart for source-mc57.html. Do not load on index.html. */
(function () {
  'use strict';

  const OPTIONS_URL = 'data/options/index.json';
  const VWAP_URL = 'data/vwap_restore.json';
  const LIGHTWEIGHT_URL = 'https://cdn.jsdelivr.net/npm/lightweight-charts@4.2.3/dist/lightweight-charts.standalone.production.js';
  const MODAL_ID = 'v38-options-chart-modal';
  const STYLE_ID = 'v38-source-mc57-restored-chart-style';
  const BUCKETS = ['0-6', '7-21', '22-45', '0-45'];
  const TICKER_RE = /^[A-Z][A-Z0-9.\-]{0,9}$/;
  let dataPromise = null;
  let libPromise = null;
  let chart = null;
  let observer = null;
  let activeTicker = null;

  function finite(value) {
    if (value === null || value === undefined || value === '') return null;
    const n = Number(value);
    return Number.isFinite(n) ? n : null;
  }

  function cleanTicker(value) {
    const ticker = String(value || '').trim().toUpperCase();
    return TICKER_RE.test(ticker) ? ticker : null;
  }

  function loadData() {
    if (!dataPromise) {
      dataPromise = Promise.all([
        fetch(OPTIONS_URL, {cache: 'no-store'}).then((r) => r.ok ? r.json() : null).catch(() => null),
        fetch(VWAP_URL, {cache: 'no-store'}).then((r) => r.ok ? r.json() : null).catch(() => null)
      ]).then(([options, vwap]) => ({options, vwap}));
    }
    return dataPromise;
  }

  function loadLib() {
    if (window.LightweightCharts) return Promise.resolve(window.LightweightCharts);
    if (!libPromise) {
      libPromise = new Promise((resolve) => {
        const script = document.createElement('script');
        script.src = LIGHTWEIGHT_URL;
        script.async = true;
        script.onload = () => resolve(window.LightweightCharts || null);
        script.onerror = () => resolve(null);
        document.head.appendChild(script);
      });
    }
    return libPromise;
  }

  function rowsForBucket(options, bucket) {
    const buckets = options && options.buckets && typeof options.buckets === 'object' ? options.buckets : {};
    return Array.isArray(buckets[bucket]) ? buckets[bucket] : [];
  }

  function rowForBucket(options, ticker, bucket) {
    return rowsForBucket(options, bucket).find((row) => row && String(row.ticker || '').toUpperCase() === ticker) || null;
  }

  function availableBuckets(options, ticker) {
    return BUCKETS.filter((bucket) => rowForBucket(options, ticker, bucket));
  }

  function resolveRow(options, ticker, bucket) {
    if (bucket) {
      const row = rowForBucket(options, ticker, bucket);
      if (row) return {bucket, row};
    }
    const available = availableBuckets(options, ticker);
    if (available.length) return {bucket: available[0], row: rowForBucket(options, ticker, available[0])};
    const rows = options && Array.isArray(options.rows) ? options.rows : [];
    const row = rows.find((x) => x && String(x.ticker || '').toUpperCase() === ticker);
    return row ? {bucket: String(row.bucket || '0-45'), row} : {bucket: null, row: null};
  }

  function candlesFor(data, ticker) {
    const fromOptions = data.options && data.options.chart_ohlc && data.options.chart_ohlc[ticker];
    const fromVwap = data.vwap && data.vwap.chart_ohlc && data.vwap.chart_ohlc[ticker];
    const rows = Array.isArray(fromOptions) ? fromOptions : Array.isArray(fromVwap) ? fromVwap : [];
    return rows.map((row) => {
      const open = finite(row.open), high = finite(row.high), low = finite(row.low), close = finite(row.close), volume = finite(row.volume);
      if (!row.time || [open, high, low, close].some((v) => v === null)) return null;
      return {time: String(row.time), open, high, low, close, volume: volume === null ? 0 : volume};
    }).filter(Boolean);
  }

  function rollingVwap(candles, length) {
    const result = [];
    const pv = [];
    const vol = [];
    let sumPv = 0, sumVol = 0;
    candles.forEach((c, index) => {
      const source = (c.high + c.low + c.close) / 3;
      const v = Math.max(0, finite(c.volume) || 0);
      const p = source * v;
      pv.push(p); vol.push(v); sumPv += p; sumVol += v;
      if (index >= length) { sumPv -= pv[index - length]; sumVol -= vol[index - length]; }
      if (index >= length - 1 && sumVol > 0) result.push({time: c.time, value: sumPv / sumVol});
    });
    return result;
  }

  function ema(candles, length) {
    if (!Array.isArray(candles) || candles.length < length) return [];
    const alpha = 2 / (length + 1);
    let seed = 0;
    for (let i = 0; i < length; i += 1) seed += candles[i].close;
    let value = seed / length;
    const result = [{time: candles[length - 1].time, value}];
    for (let i = length; i < candles.length; i += 1) {
      value = candles[i].close * alpha + value * (1 - alpha);
      result.push({time: candles[i].time, value});
    }
    return result;
  }

  function levels(row) {
    if (!row) return [];
    const spot = finite(row.spot);
    const em = finite(row.expected_move);
    const emPct = finite(row.expected_move_pct);
    const move = em !== null ? em : (spot !== null && emPct !== null ? spot * emPct : null);
    const upper = finite(row.expected_upper) !== null ? finite(row.expected_upper) : (spot !== null && move !== null ? spot + move : null);
    const lower = finite(row.expected_lower) !== null ? finite(row.expected_lower) : (spot !== null && move !== null ? Math.max(0, spot - move) : null);
    return [
      ['Call Wall', finite(row.call_wall), '#b63d34', 'solid'],
      ['Expected Upper', upper, '#2f64a2', 'dashed'],
      ['Spot', spot, '#4b4b4b', 'dotted'],
      ['Gamma Flip', finite(row.gamma_flip), '#9b6c0d', 'solid'],
      ['Expected Lower', lower, '#2f64a2', 'dashed'],
      ['Put Wall', finite(row.put_wall), '#23724b', 'solid']
    ].filter((x) => x[1] !== null).map((x) => ({label:x[0], value:x[1], color:x[2], style:x[3]}));
  }

  function lifeValue(data, ticker) {
    const item = data.vwap && data.vwap.inception_values && data.vwap.inception_values[ticker];
    return item && finite(item.value) !== null ? finite(item.value) : null;
  }

  function injectStyle() {
    if (document.getElementById(STYLE_ID)) return;
    const style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent = `
      #${MODAL_ID}{position:fixed;inset:0;z-index:2147483600;background:rgba(18,20,18,.64);display:flex;align-items:center;justify-content:center;padding:10px;box-sizing:border-box}#${MODAL_ID}[hidden]{display:none!important}
      .v38-rc-shell,.v38-oc-shell{width:min(1120px,100%);height:min(92vh,850px);background:#f8f7f3;border-radius:17px;border:1px solid rgba(74,63,47,.25);overflow:hidden;display:flex;flex-direction:column;box-shadow:0 24px 80px rgba(0,0,0,.35)}
      .v38-rc-head{display:flex;align-items:center;gap:8px;padding:8px 10px;border-bottom:1px solid rgba(74,63,47,.14)}.v38-rc-title,.v38-oc-title{font-size:18px;font-weight:900;min-width:50px}.v38-rc-buckets{display:flex;gap:4px;overflow-x:auto;scrollbar-width:none}.v38-rc-btn{appearance:none;border:1px solid rgba(74,63,47,.18);border-radius:999px;background:#fff;color:#5d554c;padding:5px 8px;font-size:9px;font-weight:850;white-space:nowrap;cursor:pointer}.v38-rc-btn[aria-pressed="true"]{background:#282722;color:#fff}.v38-rc-btn:disabled{opacity:.35}.v38-rc-spacer{flex:1}.v38-rc-close,.v38-oc-close{appearance:none;border:1px solid rgba(74,63,47,.18);border-radius:8px;background:#fff;padding:6px 10px;font-size:16px;font-weight:900;cursor:pointer}
      .v38-rc-body{position:relative;flex:1;min-height:0;background:#fff}.v38-rc-chart{position:absolute;inset:0}.v38-rc-legend,.v38-oc-levels{position:absolute;z-index:5;left:8px;top:8px;right:52px;display:flex;flex-wrap:wrap;gap:5px 9px;padding:5px 7px;border-radius:8px;background:rgba(250,249,246,.89);font-size:8.5px;font-weight:800;pointer-events:none;box-shadow:0 2px 10px rgba(0,0,0,.07)}.v38-rc-li{display:inline-flex;align-items:center;gap:3px}.v38-rc-swatch{width:12px;height:2px;border-radius:2px;background:currentColor}.v38-rc-status,.v38-oc-status{position:absolute;z-index:5;left:8px;right:8px;bottom:7px;padding:6px 8px;border-radius:8px;background:rgba(250,249,246,.91);font-size:8.5px;line-height:1.4;color:#625b53;pointer-events:none}.v38-rc-empty{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);font-size:11px;font-weight:850;color:#6c655d;background:#fffaf4;border-radius:8px;padding:9px 12px;box-shadow:0 2px 12px rgba(0,0,0,.08)}.v38-rc-svg{width:100%;height:100%;display:block}
      @media(max-width:700px){#${MODAL_ID}{padding:0}.v38-rc-shell,.v38-oc-shell{width:100%;height:100dvh;border-radius:0}.v38-rc-head{padding:7px}.v38-rc-title,.v38-oc-title{font-size:16px}.v38-rc-legend,.v38-oc-levels{left:5px;top:5px;right:44px;font-size:7.5px}.v38-rc-status,.v38-oc-status{left:5px;right:5px;bottom:5px;font-size:7.5px}}
    `;
    document.head.appendChild(style);
  }

  function ensureModal() {
    injectStyle();
    let modal = document.getElementById(MODAL_ID);
    if (modal) return modal;
    modal = document.createElement('div'); modal.id = MODAL_ID; modal.hidden = true;
    modal.innerHTML = '<div class="v38-rc-shell v38-oc-shell" role="dialog" aria-modal="true"><div class="v38-rc-head v38-oc-head"><div class="v38-rc-title v38-oc-title">—</div><div class="v38-rc-buckets v38-oc-buckets"></div><div class="v38-rc-spacer v38-oc-spacer"></div><button class="v38-rc-close v38-oc-close" type="button">×</button></div><div class="v38-rc-body v38-oc-body"><div class="v38-oc-tv"><div class="tradingview-widget-container"><div class="v38-rc-chart v38-oc-chart"></div></div></div><div class="v38-rc-legend v38-oc-levels">V38 Options</div><div class="v38-rc-status v38-oc-status">読み込み中…</div></div></div>';
    document.body.appendChild(modal);
    modal.querySelector('.v38-rc-close').addEventListener('click', close);
    modal.addEventListener('click', (e) => { if (e.target === modal) close(); });
    return modal;
  }

  function dispose() {
    if (observer) { observer.disconnect(); observer = null; }
    if (chart && typeof chart.remove === 'function') { try { chart.remove(); } catch (_) {} }
    chart = null;
  }

  function lineStyle(lib, style) {
    if (!lib || !lib.LineStyle) return 0;
    return style === 'dashed' ? lib.LineStyle.Dashed : style === 'dotted' ? lib.LineStyle.Dotted : lib.LineStyle.Solid;
  }

  function svgFallback(host, candles, optionLevels, ema21, v63, v252, life) {
    host.replaceChildren();
    if (!candles.length) return;
    const width=900,height=560,px=48,py=30;
    const values = candles.flatMap((c) => [c.high,c.low]).concat(optionLevels.map((l)=>l.value), ema21.map((x)=>x.value), v63.map((x)=>x.value), v252.map((x)=>x.value), life === null ? [] : [life]);
    let lo=Math.min(...values), hi=Math.max(...values); const margin=Math.max((hi-lo)*.05,hi*.003); lo-=margin;hi+=margin;
    const x=(i)=>px+(width-2*px)*(i+.5)/candles.length, y=(v)=>py+(hi-v)/Math.max(1e-9,hi-lo)*(height-2*py), step=(width-2*px)/candles.length, bw=Math.max(1.2,Math.min(7,step*.55));
    const ns='http://www.w3.org/2000/svg', svg=document.createElementNS(ns,'svg');svg.setAttribute('class','v38-rc-svg');svg.setAttribute('viewBox',`0 0 ${width} ${height}`);svg.setAttribute('preserveAspectRatio','none');
    candles.forEach((c,i)=>{const xx=x(i),up=c.close>=c.open,col=up?'#2c9a7b':'#d9534f';const w=document.createElementNS(ns,'line');w.setAttribute('x1',xx);w.setAttribute('x2',xx);w.setAttribute('y1',y(c.high));w.setAttribute('y2',y(c.low));w.setAttribute('stroke',col);svg.appendChild(w);const r=document.createElementNS(ns,'rect');r.setAttribute('x',xx-bw/2);r.setAttribute('y',Math.min(y(c.open),y(c.close)));r.setAttribute('width',bw);r.setAttribute('height',Math.max(1,Math.abs(y(c.open)-y(c.close))));r.setAttribute('fill',up?col:'#fff');r.setAttribute('stroke',col);svg.appendChild(r);});
    function poly(rows,color){if(!rows.length)return;const byTime=new Map(rows.map((r)=>[String(r.time),r.value]));const pts=[];candles.forEach((c,i)=>{if(byTime.has(c.time))pts.push(x(i)+','+y(byTime.get(c.time)));});if(pts.length>1){const p=document.createElementNS(ns,'polyline');p.setAttribute('points',pts.join(' '));p.setAttribute('fill','none');p.setAttribute('stroke',color);p.setAttribute('stroke-width','1.6');svg.appendChild(p);}}
    poly(ema21,'#d47a21');poly(v63,'#7a4fb5');poly(v252,'#397c78');
    optionLevels.concat(life===null?[]:[{label:'All-time VWAP',value:life,color:'#6b5b86'}]).forEach((l)=>{const line=document.createElementNS(ns,'line');line.setAttribute('x1',px);line.setAttribute('x2',width-px);line.setAttribute('y1',y(l.value));line.setAttribute('y2',y(l.value));line.setAttribute('stroke',l.color);line.setAttribute('stroke-width','1.2');svg.appendChild(line);});
    host.appendChild(svg);
  }

  function legend(modal, optionLevels, ema21, v63, v252, life) {
    const host = modal.querySelector('.v38-rc-legend'); host.replaceChildren();
    const title = document.createElement('span'); title.textContent = 'V38 Options'; host.appendChild(title);
    const items = optionLevels.map((x)=>({label:x.label,value:x.value,color:x.color}));
    if (ema21.length) items.push({label:'EMA21',value:ema21[ema21.length-1].value,color:'#d47a21'});
    if (v63.length) items.push({label:'VWAP63',value:v63[v63.length-1].value,color:'#7a4fb5'});
    if (v252.length) items.push({label:'VWAP252',value:v252[v252.length-1].value,color:'#397c78'});
    if (life !== null) items.push({label:'All-time VWAP',value:life,color:'#6b5b86'});
    items.forEach((item)=>{const el=document.createElement('span');el.className='v38-rc-li';el.style.color=item.color;const sw=document.createElement('i');sw.className='v38-rc-swatch';const tx=document.createElement('span');tx.textContent=item.label+' '+Number(item.value).toFixed(2);el.append(sw,tx);host.appendChild(el);});
  }

  async function render(modal, data, ticker, found) {
    dispose();
    const host=modal.querySelector('.v38-rc-chart');host.replaceChildren();
    const candles=candlesFor(data,ticker), optionLevels=levels(found && found.row), ema21=ema(candles,21), v63=rollingVwap(candles,63), v252=rollingVwap(candles,252), life=lifeValue(data,ticker);
    legend(modal,optionLevels,ema21,v63,v252,life);
    const status=modal.querySelector('.v38-rc-status');
    const bits=[];if(found&&found.bucket)bits.push(found.bucket+' DTE');if(found&&found.row&&finite(found.row.expected_move_pct)!==null)bits.push('Expected Move '+(found.row.expected_move_pct*100).toFixed(1)+'%');bits.push('EMA21');bits.push('63/252/All-time VWAPは観察線・売買ゲートではありません');status.textContent=bits.join(' • ');
    if(!candles.length){const empty=document.createElement('div');empty.className='v38-rc-empty';empty.textContent='この銘柄のローソク足履歴は未取得';host.appendChild(empty);return;}
    try{
      const lib=await loadLib();if(modal.hidden||activeTicker!==ticker)return;if(!lib||typeof lib.createChart!=='function'){svgFallback(host,candles,optionLevels,ema21,v63,v252,life);return;}
      chart=lib.createChart(host,{width:host.clientWidth||900,height:host.clientHeight||560,layout:{background:{type:'solid',color:'#fff'},textColor:'#494640',fontSize:11},localization:{locale:'en-US'},grid:{vertLines:{color:'#eceae5'},horzLines:{color:'#eceae5'}},rightPriceScale:{borderColor:'#dedbd4',scaleMargins:{top:.08,bottom:.08}},timeScale:{borderColor:'#dedbd4',rightOffset:3,barSpacing:7,minBarSpacing:2,timeVisible:false},handleScroll:{mouseWheel:true,pressedMouseMove:true,horzTouchDrag:true,vertTouchDrag:false},handleScale:{axisPressedMouseMove:true,mouseWheel:true,pinch:true}});
      const cs=chart.addCandlestickSeries({upColor:'#2c9a7b',downColor:'#d9534f',borderUpColor:'#2c9a7b',borderDownColor:'#d9534f',wickUpColor:'#2c9a7b',wickDownColor:'#d9534f',priceLineVisible:false});cs.setData(candles.map(({time,open,high,low,close})=>({time,open,high,low,close})));
      function addLine(rows,color,title){if(!rows.length)return;const ls=chart.addLineSeries({color,lineWidth:2,priceLineVisible:false,lastValueVisible:true,title});ls.setData(rows);}
      addLine(ema21,'#d47a21','EMA21');addLine(v63,'#7a4fb5','VWAP63');addLine(v252,'#397c78','VWAP252');
      optionLevels.forEach((l)=>cs.createPriceLine({price:l.value,color:l.color,lineWidth:l.label==='Spot'?1:2,lineStyle:lineStyle(lib,l.style),axisLabelVisible:true,title:l.label}));
      if(life!==null)cs.createPriceLine({price:life,color:'#6b5b86',lineWidth:2,lineStyle:lib.LineStyle?lib.LineStyle.Dashed:0,axisLabelVisible:true,title:'All-time VWAP'});
      chart.timeScale().fitContent();
      if(window.ResizeObserver){observer=new ResizeObserver(()=>{if(chart){try{chart.applyOptions({width:host.clientWidth,height:host.clientHeight});}catch(_){}}});observer.observe(host);}
    }catch(_){dispose();if(!modal.hidden&&activeTicker===ticker)svgFallback(host,candles,optionLevels,ema21,v63,v252,life);}
  }

  function buttons(modal,data,ticker,selected) {
    const host=modal.querySelector('.v38-rc-buckets');host.replaceChildren();
    const available=new Set(availableBuckets(data.options,ticker));
    BUCKETS.forEach((bucket)=>{const b=document.createElement('button');b.type='button';b.className='v38-rc-btn';b.textContent=bucket;b.disabled=!available.has(bucket);b.setAttribute('aria-pressed',bucket===selected?'true':'false');b.addEventListener('click',()=>{if(b.disabled)return;const found=resolveRow(data.options,ticker,bucket);buttons(modal,data,ticker,bucket);void render(modal,data,ticker,found);});host.appendChild(b);});
  }

  function openTicker(value) {
    const ticker=cleanTicker(value);if(!ticker)return;
    const modal=ensureModal();activeTicker=ticker;modal.hidden=false;modal.querySelector('.v38-rc-title').textContent=ticker;modal.querySelector('.v38-rc-status').textContent='ローソク足・EMA21・VWAP・Options水準を読み込み中…';modal.querySelector('.v38-rc-chart').replaceChildren();modal.querySelector('.v38-rc-legend').replaceChildren();
    loadData().then((data)=>{if(modal.hidden||activeTicker!==ticker)return;const found=resolveRow(data.options,ticker,null);buttons(modal,data,ticker,found&&found.bucket);void render(modal,data,ticker,found);});
  }

  function close(){const modal=document.getElementById(MODAL_ID);if(modal)modal.hidden=true;activeTicker=null;dispose();}

  function tickerFromTarget(target) {
    if(!(target instanceof Element))return null;
    const el=target.closest('[data-tkone],[data-v38-ticker],[data-v38-rs-ticker],[data-ticker],[data-symbol]');
    if(el){return cleanTicker(el.getAttribute('data-tkone')||el.getAttribute('data-v38-ticker')||el.getAttribute('data-v38-rs-ticker')||el.getAttribute('data-ticker')||el.getAttribute('data-symbol'));}
    const link=target.closest('a.v38-ticker-link,a[href*="tradingview.com/chart"]');
    if(link){const text=cleanTicker(link.textContent);if(text)return text;try{return cleanTicker(new URL(link.href,location.href).searchParams.get('symbol'));}catch(_){}}
    const atom=target.closest('.mvr-t,.tk,.chip');return atom?cleanTicker(atom.textContent):null;
  }

  function isTickerTarget(target){return target instanceof Element&&Boolean(target.closest('[data-tkone],[data-v38-ticker],[data-v38-rs-ticker],[data-ticker],[data-symbol],a.v38-ticker-link,a[href*="tradingview.com/chart"],.mvr-t,.tk,.chip'));}

  window.addEventListener('click',(event)=>{if(!isTickerTarget(event.target))return;const ticker=tickerFromTarget(event.target);if(!ticker)return;event.preventDefault();event.stopImmediatePropagation();openTicker(ticker);},true);
  document.addEventListener('keydown',(event)=>{if(event.key==='Escape')close();});
  window.V38OpenTickerChart=openTicker;
})();
