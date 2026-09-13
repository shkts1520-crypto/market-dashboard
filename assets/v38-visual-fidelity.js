(function () {
  'use strict';

  const STYLE_ID = 'v38-visual-fidelity-style';
  let running = false;

  function finite(value) {
    if (value === null || value === undefined || value === '') return null;
    const n = Number(value);
    return Number.isFinite(n) ? n : null;
  }

  function injectStyle() {
    if (document.getElementById(STYLE_ID)) return;
    const style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent = `
      .v38-mc57-head,.v38-vix-head{display:flex;align-items:flex-start;gap:10px;justify-content:space-between}
      .v38-mc57-now,.v38-vix-now{text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}
      .v38-mc57-now b,.v38-vix-now b{display:block;font-size:28px;line-height:1;font-weight:900}.v38-mc57-now span,.v38-vix-now span{display:block;margin-top:4px;font-size:11px;font-weight:800;letter-spacing:.04em}
      .v38-mc57-read{margin:7px 0 5px;font-size:11px;color:#6a655d;line-height:1.45}.v38-mc57-read b{color:#282522}
      .v38-robust-note{font-size:9px;color:#898279;margin-top:4px;text-align:right}
      .v38-vix-sub{margin:6px 0 8px;color:#6a655d;font-size:11px;line-height:1.45}.v38-vix-sub details{display:inline}.v38-vix-sub summary{display:inline;cursor:pointer;font-weight:800}
      .v38-vix-values{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:6px;margin:7px 0 6px}.v38-vix-values div{min-width:0}.v38-vix-values span{display:block;font-size:9px;color:#79736b}.v38-vix-values b{font-size:15px;font-variant-numeric:tabular-nums}
      .v38-vix-legend{display:flex;gap:12px;flex-wrap:wrap;font-size:9px;font-weight:800;color:#625d56;margin:5px 0}.v38-vix-legend i{display:inline-block;width:15px;height:2px;vertical-align:middle;margin-right:4px}
      .v38-vix-tabs{display:flex;gap:5px;margin:6px 0}.v38-vix-tabs button{appearance:none;border:1px solid rgba(78,70,61,.18);background:#fff;border-radius:999px;padding:4px 8px;font-size:9px;font-weight:800;color:#69625b}.v38-vix-tabs button.on{background:#282722;color:#fff;border-color:#282722}
      .v38-vix-outside{font-size:9px;color:#817a72;margin:3px 0 6px}.v38-vix-events{margin-top:7px;overflow-x:auto}.v38-vix-events table{width:100%;font-size:9px;border-collapse:collapse}.v38-vix-events th,.v38-vix-events td{padding:4px 5px;text-align:right;white-space:nowrap;border-bottom:1px solid rgba(78,70,61,.08)}.v38-vix-events th:first-child,.v38-vix-events td:first-child{text-align:left}
      @media(max-width:620px){.v38-vix-values{grid-template-columns:repeat(3,minmax(0,1fr))}.v38-mc57-now b,.v38-vix-now b{font-size:24px}}
    `;
    document.head.appendChild(style);
  }

  function cardByTitle(titlePart) {
    const section = document.getElementById('t-market');
    if (!section) return null;
    return Array.from(section.querySelectorAll('.card')).find((card) => {
      const canonical = String(card.dataset.v38CanonicalTitle || card.dataset.v38CardTitle || '');
      const heading = card.querySelector('h2');
      return canonical.includes(titlePart) || Boolean(heading && heading.textContent.includes(titlePart));
    }) || null;
  }

  function cloneHeading(card) {
    const heading = card && card.querySelector('h2');
    return heading ? heading.cloneNode(true) : null;
  }

  function chartAxis(parent, points) {
    if (!parent || !points.length) return;
    const picks = [0, Math.floor((points.length - 1) / 3), Math.floor(2 * (points.length - 1) / 3), points.length - 1];
    const axis = document.createElement('div');
    axis.className = 'dax v38-quarter-axis';
    Array.from(new Set(picks)).forEach((index) => {
      const span = document.createElement('span');
      const date = String(points[index].date || '');
      const m = /^(\d{4})-(\d{2})/.exec(date);
      span.textContent = m ? m[1].slice(2) + '/' + Number(m[2]) : date;
      axis.appendChild(span);
    });
    parent.appendChild(axis);
  }

  function mcBand(value) {
    if (value >= 70) return ['強気', '#16a34a'];
    if (value >= 55) return ['やや強気', '#22c55e'];
    if (value >= 40) return ['中立', '#64748b'];
    if (value >= 25) return ['弱含み', '#f97316'];
    return ['弱気', '#ef4444'];
  }

  function drawMc57(parent, points) {
    const values = (Array.isArray(points) ? points : []).map((point) => {
      const value = finite(point && (point.value !== undefined ? point.value : point.mc57));
      return point && point.date && value !== null ? {date: String(point.date), value} : null;
    }).filter(Boolean);
    if (values.length < 2) return false;
    const width = 680, height = 180, pad = 7;
    let low = Math.max(0, Math.min.apply(null, values.map((p) => p.value)) - 4);
    let high = Math.min(100, Math.max.apply(null, values.map((p) => p.value)) + 4);
    if (high - low < 18) { low = Math.max(0, low - 9); high = Math.min(100, high + 9); }
    const x = (i) => pad + (width - 2 * pad) * i / Math.max(1, values.length - 1);
    const y = (v) => pad + (1 - (v - low) / Math.max(1e-9, high - low)) * (height - 2 * pad);
    const zones = [[0,25,'#ef4444'],[25,40,'#f97316'],[40,55,'#64748b'],[55,70,'#22c55e'],[70,100,'#16a34a']];
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('class', 'spark v38-live-spark v38-mc57-banded');
    svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
    svg.setAttribute('preserveAspectRatio', 'none');
    zones.forEach(([a0,b0,color]) => {
      const a = Math.max(Number(a0), low), b = Math.min(Number(b0), high);
      if (b <= a) return;
      const rect = document.createElementNS(svg.namespaceURI, 'rect');
      rect.setAttribute('x', String(pad)); rect.setAttribute('y', y(b).toFixed(1));
      rect.setAttribute('width', String(width - 2 * pad)); rect.setAttribute('height', Math.max(0, y(a) - y(b)).toFixed(1));
      rect.setAttribute('fill', String(color)); rect.setAttribute('opacity', '0.075'); svg.appendChild(rect);
    });
    [25,40,55,70].forEach((level) => {
      if (level < low || level > high) return;
      const line = document.createElementNS(svg.namespaceURI, 'line');
      line.setAttribute('x1', String(pad)); line.setAttribute('x2', String(width - pad));
      line.setAttribute('y1', y(level).toFixed(1)); line.setAttribute('y2', y(level).toFixed(1));
      line.setAttribute('stroke', '#756f66'); line.setAttribute('stroke-width', '1'); line.setAttribute('stroke-opacity', '.35'); svg.appendChild(line);
      const text = document.createElementNS(svg.namespaceURI, 'text');
      text.setAttribute('x', String(width - pad)); text.setAttribute('y', (y(level) - 3).toFixed(1));
      text.setAttribute('fill', '#817a72'); text.setAttribute('font-size', '14'); text.setAttribute('font-weight', '700'); text.setAttribute('text-anchor', 'end');
      text.textContent = String(level); svg.appendChild(text);
    });
    const poly = document.createElementNS(svg.namespaceURI, 'polyline');
    poly.setAttribute('points', values.map((p,i) => `${x(i).toFixed(1)},${y(p.value).toFixed(1)}`).join(' '));
    poly.setAttribute('fill', 'none'); poly.setAttribute('stroke', '#1f6f49'); poly.setAttribute('stroke-width', '2'); svg.appendChild(poly);
    const last = values.length - 1;
    const dot = document.createElementNS(svg.namespaceURI, 'circle');
    dot.setAttribute('cx', x(last).toFixed(1)); dot.setAttribute('cy', y(values[last].value).toFixed(1)); dot.setAttribute('r', '3.7'); dot.setAttribute('fill', mcBand(values[last].value)[1]); svg.appendChild(dot);
    parent.replaceChildren(svg); chartAxis(parent, values); return true;
  }

  function renderMc57(daily) {
    const detail = daily && daily.mc57_detail;
    const series = detail && detail.series && detail.series.mc57;
    const current = detail && detail.current;
    const value = finite(current && current.mc57);
    const card = cardByTitle('MC57推移');
    if (!card || !detail || detail.status !== 'READY' || value === null || !Array.isArray(series) || series.length < 2) return;
    const heading = cloneHeading(card);
    const band = mcBand(value);
    card.replaceChildren();
    card.dataset.v38Status = 'READY';
    card.dataset.v38BindingKey = 'daily-mc57-history';
    card.dataset.v38HistoryPoints = String(series.length);
    card.dataset.v38Temperature = band[0];
    const head = document.createElement('div'); head.className = 'v38-mc57-head';
    if (heading) head.appendChild(heading);
    const now = document.createElement('div'); now.className = 'v38-mc57-now'; now.style.color = band[1];
    now.innerHTML = `<b>${value.toFixed(1)}</b><span>${band[0]}</span>`; head.appendChild(now); card.appendChild(head);
    const sub = document.createElement('div'); sub.className = 'sub'; sub.textContent = '取得済み固定57ETF履歴。'; card.appendChild(sub);
    const read = document.createElement('div'); read.className = 'v38-mc57-read';
    read.innerHTML = '<b>温度帯</b>　70以上 強気 / 55–69 やや強気 / 40–54 中立 / 25–39 弱含み / 24以下 弱気'; card.appendChild(read);
    const chart = document.createElement('div'); chart.className = 'chart'; card.appendChild(chart); drawMc57(chart, series);
  }

  function quantile(sorted, q) {
    if (!sorted.length) return null;
    const pos = (sorted.length - 1) * q, base = Math.floor(pos), rest = pos - base;
    return sorted[base + 1] !== undefined ? sorted[base] + rest * (sorted[base + 1] - sorted[base]) : sorted[base];
  }

  function drawRobust(parent, points, colour, reference) {
    const values = (Array.isArray(points) ? points : []).map((p) => {
      const value = finite(p && p.value); return p && p.date && value !== null ? {date:String(p.date), value} : null;
    }).filter(Boolean);
    if (values.length < 2) return false;
    const sorted = values.map((p) => p.value).slice().sort((a,b) => a-b);
    let low = quantile(sorted, .02), high = quantile(sorted, .98);
    if (low === null || high === null) return false;
    if (finite(reference) !== null) { low = Math.min(low, Number(reference)); high = Math.max(high, Number(reference)); }
    if (high === low) { low -= .5; high += .5; }
    const margin = (high - low) * .05; low -= margin; high += margin;
    const width=680,height=180,pad=7;
    const x=(i)=>pad+(width-2*pad)*i/Math.max(1,values.length-1);
    const clamp=(v)=>Math.max(low,Math.min(high,v));
    const y=(v)=>pad+(1-(clamp(v)-low)/(high-low))*(height-2*pad);
    const svg=document.createElementNS('http://www.w3.org/2000/svg','svg'); svg.setAttribute('class','spark v38-live-spark v38-two-year-trend v38-robust-trend'); svg.setAttribute('viewBox',`0 0 ${width} ${height}`); svg.setAttribute('preserveAspectRatio','none');
    if (finite(reference)!==null && reference>=low && reference<=high) { const line=document.createElementNS(svg.namespaceURI,'line'); line.setAttribute('x1',String(pad));line.setAttribute('x2',String(width-pad));line.setAttribute('y1',y(reference).toFixed(1));line.setAttribute('y2',y(reference).toFixed(1));line.setAttribute('stroke','#8c867d');line.setAttribute('stroke-width','1');line.setAttribute('stroke-dasharray','4 4');line.setAttribute('stroke-opacity','.55');svg.appendChild(line); }
    const path=values.map((p,i)=>(i?'L':'M')+x(i).toFixed(1)+','+y(p.value).toFixed(1)).join(' ');
    const area=document.createElementNS(svg.namespaceURI,'path'); area.setAttribute('d',path+` L${x(values.length-1).toFixed(1)},${height-pad} L${x(0).toFixed(1)},${height-pad} Z`); area.setAttribute('fill',colour); area.setAttribute('opacity','.07'); svg.appendChild(area);
    const line=document.createElementNS(svg.namespaceURI,'path'); line.setAttribute('d',path); line.setAttribute('fill','none'); line.setAttribute('stroke',colour); line.setAttribute('stroke-width','2'); svg.appendChild(line);
    const last=values.length-1,dot=document.createElementNS(svg.namespaceURI,'circle');dot.setAttribute('cx',x(last).toFixed(1));dot.setAttribute('cy',y(values[last].value).toFixed(1));dot.setAttribute('r','3.2');dot.setAttribute('fill',colour);svg.appendChild(dot);
    parent.replaceChildren(svg); parent.dataset.v38Scale='robust-p02-p98'; chartAxis(parent,values);
    const note=document.createElement('div'); note.className='v38-robust-note'; note.textContent='表示レンジのみ2–98%ileで外れ値耐性化（現在値・元データは実値）'; parent.appendChild(note); return true;
  }

  function renderRobustDiagnostics(daily) {
    const rows = daily && daily.market_diagnostics && Array.isArray(daily.market_diagnostics.series) ? daily.market_diagnostics.series : [];
    if (!rows.length) return;
    [['売買代金 参加度','volume_participation','#2c69c9'],['集積／分散','up_down_dollar_ratio','#7b5c36']].forEach((spec) => {
      const card=cardByTitle(spec[0]); if(!card)return; const chart=card.querySelector('.chart'); if(!chart)return;
      drawRobust(chart, rows.map((row)=>({date:row.date,value:row[spec[1]]})), spec[2], 1.0);
    });
  }

  function vixWindow(series, days) { return Array.isArray(series) ? series.slice(-days) : []; }
  function vixNum(value) { const n=finite(value); return n===null?'—':n.toFixed(2); }

  function drawVixChart(host, payload, days) {
    const series=vixWindow(payload.series,days); if(series.length<2)return;
    const visible=[]; series.forEach((r)=>['close','lwma5','lwma10'].forEach((k)=>{const n=finite(r[k]);if(n!==null)visible.push(n);})); if(!visible.length)return;
    let low=Math.min.apply(null,visible), high=Math.max.apply(null,visible); const span=Math.max(1,high-low); low=Math.max(0,low-span*.10); high+=span*.10;
    const width=680,height=168,padX=7,padTop=8,padBottom=24;
    const x=(i)=>padX+(width-2*padX)*i/Math.max(1,series.length-1), y=(v)=>padTop+(high-v)/(high-low)*(height-padTop-padBottom);
    host.replaceChildren(); const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('class','vixspark v38-vix-fear-svg');svg.setAttribute('viewBox',`0 0 ${width} ${height}`);svg.setAttribute('preserveAspectRatio','none');
    for(let i=0;i<4;i++){const value=low+(high-low)*i/3,yy=y(value);const gl=document.createElementNS(svg.namespaceURI,'line');gl.setAttribute('x1',String(padX));gl.setAttribute('x2',String(width-padX));gl.setAttribute('y1',yy.toFixed(1));gl.setAttribute('y2',yy.toFixed(1));gl.setAttribute('stroke','#dedbd4');gl.setAttribute('stroke-width','1');svg.appendChild(gl);}
    const colour={close:'#b84a42',lwma5:'#c69222',lwma10:'#2f7560'};
    ['close','lwma5','lwma10'].forEach((key)=>{const coords=[];series.forEach((r,i)=>{const n=finite(r[key]);if(n!==null)coords.push([x(i),y(n)]);});if(coords.length<2)return;const line=document.createElementNS(svg.namespaceURI,'polyline');line.setAttribute('points',coords.map((p)=>p[0].toFixed(1)+','+p[1].toFixed(1)).join(' '));line.setAttribute('fill','none');line.setAttribute('stroke',colour[key]);line.setAttribute('stroke-width',key==='close'?'2':'1.6');svg.appendChild(line);});
    const current=payload.current||{}; [['plus1_sigma','+1σ'],['plus2_sigma','+2σ']].forEach((spec)=>{const level=finite(current[spec[0]]);if(level===null||level<low||level>high)return;const yy=y(level);const line=document.createElementNS(svg.namespaceURI,'line');line.setAttribute('x1',String(padX));line.setAttribute('x2',String(width-padX));line.setAttribute('y1',yy.toFixed(1));line.setAttribute('y2',yy.toFixed(1));line.setAttribute('stroke','#a21f1f');line.setAttribute('stroke-width','1');line.setAttribute('stroke-dasharray','4 4');line.setAttribute('stroke-opacity','.55');svg.appendChild(line);const text=document.createElementNS(svg.namespaceURI,'text');text.setAttribute('x',String(width-padX));text.setAttribute('y',(yy-3).toFixed(1));text.setAttribute('fill','#a21f1f');text.setAttribute('font-size','11');text.setAttribute('font-weight','800');text.setAttribute('text-anchor','end');text.textContent=spec[1];svg.appendChild(text);});
    const indexByDate={};series.forEach((r,i)=>{indexByDate[r.date]=i;}); const markerStyle={EVENT:['E','#a21f1f'],ROLLOVER:['R','#c69222'],BOTTOM:['B','#2a8b5b'],'RE-EXTREME':['+2','#a21f1f']};
    (payload.markers||[]).forEach((m)=>{const idx=indexByDate[m.date],style=markerStyle[m.kind];if(idx===undefined||!style)return;const row=series[idx],val=finite(row.close)||finite(row.high);if(val===null)return;const xx=x(idx),yy=y(Math.max(low,Math.min(high,val)));const vl=document.createElementNS(svg.namespaceURI,'line');vl.setAttribute('x1',xx.toFixed(1));vl.setAttribute('x2',xx.toFixed(1));vl.setAttribute('y1',String(padTop));vl.setAttribute('y2',String(height-padBottom));vl.setAttribute('stroke',style[1]);vl.setAttribute('stroke-opacity','.25');svg.appendChild(vl);const text=document.createElementNS(svg.namespaceURI,'text');text.setAttribute('x',xx.toFixed(1));text.setAttribute('y',Math.max(14,yy-6).toFixed(1));text.setAttribute('fill',style[1]);text.setAttribute('font-size','12');text.setAttribute('font-weight','900');text.setAttribute('text-anchor','middle');text.textContent=style[0];svg.appendChild(text);});
    host.appendChild(svg); chartAxis(host,series);
  }

  function renderVix(daily) {
    const payload=daily&&daily.vix_fear_cycle, card=cardByTitle('VIX反転シーケンス'); if(!payload||payload.status!=='READY'||!card)return;
    const heading=cloneHeading(card), current=payload.current||{}; card.replaceChildren();card.dataset.v38Status='READY';card.dataset.v38BindingKey='daily-vix-fear-cycle';card.dataset.v38VixState=String(payload.state||'NORMAL');
    const head=document.createElement('div');head.className='v38-vix-head';if(heading)head.appendChild(heading);const now=document.createElement('div');now.className='v38-vix-now';now.innerHTML=`<b>${String(payload.state||'NORMAL')}</b><span>${payload.session_date||''}</span>`;head.appendChild(now);card.appendChild(head);
    const sub=document.createElement('div');sub.className='v38-vix-sub';sub.innerHTML='Yahoo ^VIX日足Highを1990年から月次集計。 <details><summary>詳しく</summary><span> log10・完了月のみ。+2σ超=EVENT、LWMA5低下=ROLLOVER、LWMA5がLWMA10を下抜け=BOTTOM。</span></details>';card.appendChild(sub);
    const vals=document.createElement('div');vals.className='v38-vix-values';[['VIX','vix'],['High','high'],['LWMA5','lwma5'],['LWMA10','lwma10'],['+1σ','plus1_sigma'],['+2σ','plus2_sigma']].forEach((spec)=>{const div=document.createElement('div');div.innerHTML=`<span>${spec[0]}</span><b>${vixNum(current[spec[1]])}</b>`;vals.appendChild(div);});card.appendChild(vals);
    const legend=document.createElement('div');legend.className='v38-vix-legend';legend.innerHTML='<span><i style="background:#b84a42"></i>VIX</span><span><i style="background:#c69222"></i>LWMA5</span><span><i style="background:#2f7560"></i>LWMA10</span>';card.appendChild(legend);
    const tabs=document.createElement('div');tabs.className='v38-vix-tabs';const chart=document.createElement('div');chart.className='chart vixchart';const windows=[['3M',66],['1Y',252],['3Y',756],['10Y',2520]];windows.forEach((spec,index)=>{const btn=document.createElement('button');btn.type='button';btn.textContent=spec[0];if(index===0)btn.classList.add('on');btn.addEventListener('click',()=>{tabs.querySelectorAll('button').forEach((x)=>x.classList.remove('on'));btn.classList.add('on');drawVixChart(chart,payload,spec[1]);});tabs.appendChild(btn);});card.appendChild(tabs);card.appendChild(chart);drawVixChart(chart,payload,66);
    const p1=finite(current.plus1_sigma),p2=finite(current.plus2_sigma), recent=vixWindow(payload.series,66);const valsVisible=recent.flatMap((r)=>[finite(r.close),finite(r.lwma5),finite(r.lwma10)]).filter((x)=>x!==null);if(valsVisible.length){const mx=Math.max.apply(null,valsVisible);const outside=[];if(p1!==null&&p1>mx)outside.push('+1σ '+p1.toFixed(2));if(p2!==null&&p2>mx)outside.push('+2σ '+p2.toFixed(2));if(outside.length){const note=document.createElement('div');note.className='v38-vix-outside';note.textContent='レンジ外のため非表示：'+outside.join('・');card.appendChild(note);}}
    const events=Array.isArray(payload.events)?payload.events.slice().reverse():[];if(events.length){const box=document.createElement('div');box.className='v38-vix-events';const table=document.createElement('table');table.innerHTML='<thead><tr><th>EVENT</th><th>ROLL</th><th>BOTTOM</th><th>日</th><th>PEAK</th></tr></thead>';const body=document.createElement('tbody');events.slice(0,10).forEach((e)=>{const tr=document.createElement('tr');tr.innerHTML=`<td>${e.event||'—'}</td><td>${e.roll?String(e.roll).slice(5):'—'}</td><td>${e.bottom?String(e.bottom).slice(5):'—'}</td><td>${e.days??'—'}</td><td>${finite(e.peak)===null?'—':Number(e.peak).toFixed(2)}</td>`;body.appendChild(tr);});table.appendChild(body);box.appendChild(table);card.appendChild(box);}
  }

  async function apply() {
    if(running)return;running=true;
    try { injectStyle(); const runtime=window.V38Runtime; const view=runtime&&typeof runtime.loadJson==='function'?await runtime.loadJson('data/ui_view_model.json'):await fetch('data/ui_view_model.json',{cache:'no-store'}).then((r)=>r.json()); const daily=view&&view.daily; if(!daily)return; renderMc57(daily);renderRobustDiagnostics(daily);renderVix(daily);document.body.dataset.v38VisualFidelityStatus='ready'; }
    catch(_){document.body.dataset.v38VisualFidelityStatus='failed';}
    finally{running=false;}
  }

  function waitForRepair(){if(document.body&&document.body.dataset.v38DataRepairStatus==='ready'){apply();window.setTimeout(apply,1250);window.setTimeout(apply,1950);window.setTimeout(apply,2550);window.setTimeout(apply,3300);return;}window.setTimeout(waitForRepair,60);}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',waitForRepair,{once:true});else waitForRepair();
})();
