(function () {
  'use strict';

  const canonicalRotation = document.getElementById('t-rotation')
    ? document.getElementById('t-rotation').cloneNode(true)
    : null;

  const SECTORS = [
    ['XLK', '情報技術'], ['XLC', '通信'], ['XLY', '一般消費財'], ['XLP', '生活必需品'],
    ['XLE', 'エネルギー'], ['XLF', '金融'], ['XLV', 'ヘルスケア'], ['XLI', '資本財'],
    ['XLB', '素材'], ['XLRE', '不動産'], ['XLU', '公益']
  ];
  const PERIODS = [
    ['now', '現在', 0], ['w1', '先週', 5], ['w2', '2週前', 10], ['m1', '先月', 21]
  ];

  function finite(value) {
    const number = Number(value);
    return value === null || value === undefined || value === '' || !Number.isFinite(number) ? null : number;
  }

  function pct(value, digits) {
    const number = finite(value);
    if (number === null) return '—';
    return (number > 0 ? '+' : '') + (number * 100).toFixed(digits === undefined ? 1 : digits) + '%';
  }

  function node(tag, className, text) {
    const el = document.createElement(tag);
    if (className) el.className = className;
    if (text !== undefined && text !== null) el.textContent = String(text);
    return el;
  }

  function append(parent, tag, className, text) {
    const el = node(tag, className, text);
    parent.appendChild(el);
    return el;
  }

  function findCard(section, token) {
    return Array.from(section.querySelectorAll(':scope > .card')).find((card) => {
      const h = card.querySelector('h2');
      return h && h.textContent.includes(token);
    }) || null;
  }

  function tickerButton(ticker, extraClass) {
    const button = node('button', 'chip ' + (extraClass || ''), ticker);
    button.type = 'button';
    button.addEventListener('click', function () {
      if (window.V38OpenTickerChart) window.V38OpenTickerChart(ticker);
    });
    return button;
  }

  function restoreRotationShell() {
    const current = document.getElementById('t-rotation');
    if (!current || !canonicalRotation) return current;
    const restored = canonicalRotation.cloneNode(true);
    restored.className = current.className;
    restored.style.cssText = current.style.cssText;
    if (current.hasAttribute('aria-hidden')) restored.setAttribute('aria-hidden', current.getAttribute('aria-hidden'));
    current.replaceWith(restored);
    return restored;
  }

  function byDate(series) {
    const out = new Map();
    (Array.isArray(series) ? series : []).forEach((row) => {
      const value = row && finite(row.close);
      if (row && row.date && value !== null && value > 0) out.set(row.date, value);
    });
    return out;
  }

  function relativeSeries(etfSeries, spySeries) {
    const spy = byDate(spySeries);
    return (Array.isArray(etfSeries) ? etfSeries : []).map((row) => {
      const e = row && finite(row.close);
      const s = row && spy.get(row.date);
      return row && row.date && e !== null && finite(s) !== null && s > 0 ? {date: row.date, value: e / s} : null;
    }).filter(Boolean);
  }

  function rrgPoint(etfSeries, spySeries, offset) {
    const rows = relativeSeries(etfSeries, spySeries);
    const end = rows.length - 1 - offset;
    if (end < 63 || end < 10) return null;
    const current = rows[end].value;
    const baselineRows = rows.slice(Math.max(0, end - 62), end + 1);
    const baseline = baselineRows.reduce((sum, row) => sum + row.value, 0) / baselineRows.length;
    const prior = rows[end - 10].value;
    if (!(current > 0 && baseline > 0 && prior > 0)) return null;
    return {x: 100 * current / baseline, y: 100 * current / prior};
  }

  function svgEl(tag, attrs) {
    const el = document.createElementNS('http://www.w3.org/2000/svg', tag);
    Object.keys(attrs || {}).forEach((key) => el.setAttribute(key, String(attrs[key])));
    return el;
  }

  function renderRrgSnapshot(host, view, offset) {
    const series = ((view.daily || {}).market_series || {});
    const spy = series.SPY || [];
    const points = SECTORS.map(([ticker, name]) => {
      const point = rrgPoint(series[ticker] || [], spy, offset);
      return point ? {ticker, name, ...point} : null;
    }).filter(Boolean);
    host.replaceChildren();
    const chart = append(host, 'div', 'chart', '');
    chart.style.height = 'auto';
    if (!points.length) {
      append(chart, 'div', 'mut', 'DATA_REQUIRED • current ETF/SPY history unavailable');
      return;
    }

    const width = 1040, height = 720, left = 42, right = 998, top = 42, bottom = 678;
    const xs = points.map((p) => p.x).concat([100]);
    const ys = points.map((p) => p.y).concat([100]);
    let minX = Math.min.apply(null, xs), maxX = Math.max.apply(null, xs);
    let minY = Math.min.apply(null, ys), maxY = Math.max.apply(null, ys);
    const padX = Math.max(0.35, (maxX - minX) * 0.15), padY = Math.max(0.35, (maxY - minY) * 0.15);
    minX -= padX; maxX += padX; minY -= padY; maxY += padY;
    const sx = (v) => left + (right - left) * (v - minX) / Math.max(1e-9, maxX - minX);
    const sy = (v) => bottom - (bottom - top) * (v - minY) / Math.max(1e-9, maxY - minY);
    const cx = sx(100), cy = sy(100);
    const svg = svgEl('svg', {viewBox: '0 0 1040 720', preserveAspectRatio: 'xMidYMid meet'});
    [
      [cx, top, right - cx, cy - top, '#25c25f'],
      [left, top, cx - left, cy - top, '#578ada'],
      [cx, cy, right - cx, bottom - cy, '#cba327'],
      [left, cy, cx - left, bottom - cy, '#df5454']
    ].forEach((r) => svg.appendChild(svgEl('rect', {x:r[0],y:r[1],width:Math.max(0,r[2]),height:Math.max(0,r[3]),fill:r[4],opacity:.08})));
    svg.appendChild(svgEl('line', {x1:cx,x2:cx,y1:top,y2:bottom,stroke:'#d4d1c7','stroke-width':1}));
    svg.appendChild(svgEl('line', {x1:left,x2:right,y1:cy,y2:cy,stroke:'#d4d1c7','stroke-width':1}));
    [['主導',right-10,top+48,'#4bdd80','end'],['改善',left+10,top+48,'#204c92','start'],['弱化',right-10,bottom-12,'#806319','end'],['停滞',left+10,bottom-12,'#a21f1f','start']].forEach((t) => {
      const e=svgEl('text',{x:t[1],y:t[2],fill:t[3],'fill-opacity':.72,'font-size':46,'font-weight':800,'text-anchor':t[4]}); e.textContent=t[0]; svg.appendChild(e);
    });
    points.forEach((p, index) => {
      const x=sx(p.x), y=sy(p.y);
      const fill = p.x >= 100 ? (p.y >= 100 ? '#4bdd80' : '#dbb144') : (p.y >= 100 ? '#578ada' : '#df5454');
      svg.appendChild(svgEl('circle',{cx:x,cy:y,r:5,fill}));
      const label=svgEl('text',{x,y:y+(index%2?16:-9),fill:'#242320','font-size':14,'font-weight':700,'text-anchor':'middle'}); label.textContent=p.name; svg.appendChild(label);
    });
    const xlab=svgEl('text',{x:(left+right)/2,y:714,fill:'#9e9780','font-size':12,'text-anchor':'middle'}); xlab.textContent='→ SPY相対力（63営業日基準・100=中立）'; svg.appendChild(xlab);
    const ylab=svgEl('text',{x:12,y:(top+bottom)/2,fill:'#9e9780','font-size':12,'text-anchor':'middle',transform:'rotate(-90 12 '+((top+bottom)/2)+')'}); ylab.textContent='↑ 10営業日の相対モメンタム'; svg.appendChild(ylab);
    chart.appendChild(svg);

    const groups = [
      ['主導','#18813e',(p)=>p.x>=100&&p.y>=100],
      ['改善','#204c92',(p)=>p.x<100&&p.y>=100],
      ['弱化','#806319',(p)=>p.x>=100&&p.y<100],
      ['停滞','#a21f1f',(p)=>p.x<100&&p.y<100]
    ];
    groups.forEach(([label,color,test]) => {
      const row=append(host,'div','rrgq','');
      const lab=append(row,'span','rrgq-l',label); lab.style.color=color;
      const matches=points.filter(test).sort((a,b)=>b.x-a.x);
      if (!matches.length) append(row,'span','empty','なし');
      matches.forEach((p)=>{ const chip=append(row,'span','chip chip-tap',p.name); append(chip,'span','chip-arr','›'); });
    });
  }

  function renderRrgCard(card, view) {
    if (!card) return;
    card.replaceChildren();
    const hdr=append(card,'div','hdr','');
    append(hdr,'h2','', '資金フロー（GICS11）');
    const toggles=append(hdr,'div','rrgtog','');
    append(card,'div','sub','GICS11セクターをSPYとの相対力で配置。表示専用RRG proxy（63営業日基準・10営業日モメンタム）で、売買ゲートには使用しません。');
    const views=[];
    PERIODS.forEach(([key,label,offset],index)=>{
      const b=append(toggles,'button','rtg'+(index===0?' on':''),label); b.type='button';
      const host=append(card,'div','rrgview rrg-per',''); host.dataset.per=key; if(index)host.style.display='none';
      renderRrgSnapshot(host,view,offset); views.push(host);
      b.addEventListener('click',()=>{ Array.from(toggles.children).forEach(x=>x.classList.remove('on')); b.classList.add('on'); views.forEach(v=>v.style.display=v===host?'':'none'); });
    });
    card.dataset.v38Status='READY';
  }

  function sectorRows(view) {
    const summaries=((view.daily||{}).market_summaries||{});
    return SECTORS.map(([ticker,name])=>({ticker,name,summary:summaries[ticker]||{}}));
  }

  function renderHeatmap(card, view) {
    if (!card) return;
    const rows=sectorRows(view);
    card.replaceChildren();
    const hdr=append(card,'div','hdr','');
    const h2=append(hdr,'h2','', 'セクター温度マップ '); append(h2,'span','h2en','Sector Heatmap');
    const tog=append(hdr,'div','rrgtog','');
    append(card,'div','sub','S&P500 GICS11セクターETFの騰落率。緑=上昇、赤=下落。');
    const specs=[['change_1d','日'],['change_1w','週'],['change_1m','月']];
    const grids=[];
    specs.forEach(([key,label],index)=>{
      const b=append(tog,'button','hmp'+(index===0?' on':''),label); b.type='button';
      const grid=append(card,'div','hmgrid',''); if(index)grid.style.display='none'; grids.push(grid);
      rows.slice().sort((a,b)=>(finite(b.summary[key])??-999)-(finite(a.summary[key])??-999)).forEach((row)=>{
        const value=finite(row.summary[key]);
        const cell=append(grid,'div','hm','');
        const magnitude=Math.min(.34, .10 + Math.abs(value||0)*2.4);
        cell.style.background=value===null?'rgba(120,120,120,.08)':value>=0?'rgba(52,160,88,'+magnitude+')':'rgba(198,72,63,'+magnitude+')';
        const name=append(cell,'span','hm-n',row.name); append(name,'span','hm-tk',row.ticker); append(cell,'span','hm-v',pct(value));
      });
      b.addEventListener('click',()=>{ Array.from(tog.children).forEach(x=>x.classList.remove('on')); b.classList.add('on'); grids.forEach(g=>g.style.display=g===grid?'':'none'); });
    });
    card.dataset.v38Status='READY';
  }

  function insertBreadthCard(section, view) {
    const marker=Array.from(section.querySelectorAll(':scope > .msec')).find((el)=>el.textContent.includes('その資金は広いか'));
    if(!marker)return;
    const card=node('div','card');
    const h2=append(card,'h2','', '指数と中身の乖離 '); append(h2,'span','h2en','Index vs Breadth');
    append(card,'div','sub','時価総額加重と等ウェイトの差。表示診断のみで、売買ゲートには使用しません。');
    const summaries=((view.daily||{}).market_summaries||{});
    [['SPY','RSP','S&P500'],['QQQ','QQQE','NASDAQ100']].forEach(([cap,equal,label])=>{
      const row=append(card,'div','rrow','');
      append(row,'div','nm',label);
      const right=append(row,'div','rgt','');
      const w=finite((summaries[cap]||{}).change_1w); const ew=finite((summaries[equal]||{}).change_1w);
      append(right,'span','big',(w===null||ew===null)?'—':pct(ew-w));
      append(row,'div','hint','等ウェイト−指数 1週 • 指数 '+pct(w)+' / 等ウェイト '+pct(ew));
    });
    card.dataset.v38Status='READY';
    marker.insertAdjacentElement('afterend',card);
  }

  function renderLeadingGroups(card, rotation) {
    if(!card)return;
    const rows=(((rotation||{}).diagnostics||{}).sector||[]).slice().sort((a,b)=>(finite(b.rs63_avg)||-999)-(finite(a.rs63_avg)||-999));
    card.replaceChildren();
    const hdr=append(card,'div','hdr',''); const h2=append(hdr,'h2','', '主導セクター・業種 '); append(h2,'span','h2en','Leading Groups');
    append(card,'div','sub','現行Universeの構成銘柄から算出した表示診断。RS63、20日平均騰落率、50MA上比率を表示。');
    const list=append(card,'div','bglist','');
    rows.slice(0,15).forEach((row)=>{
      const item=append(list,'div','bgrow','');
      append(item,'div','bgname',String(row.group||'—'));
      append(item,'div','bgmeta','RS63 '+(finite(row.rs63_avg)===null?'—':finite(row.rs63_avg).toFixed(0))+' ・ 20日 '+pct(row.ret20_avg)+' ・ 50MA上 '+(finite(row.above_sma50_pct)===null?'—':finite(row.above_sma50_pct).toFixed(0)+'%')+' ・ '+String(row.member_count||0)+'銘柄');
    });
    card.dataset.v38Status=rows.length?'READY':'DATA_REQUIRED';
  }

  function renderStrongLeaders(card, rotation) {
    if(!card)return;
    const rows=Array.isArray((rotation||{}).fine_theme_rows)?rotation.fine_theme_rows:[];
    card.replaceChildren();
    const hdr=append(card,'div','hdr',''); const h2=append(hdr,'h2','', '強い業種の主導株 '); append(h2,'span','h2en','Leaders in Strong Groups');
    append(card,'div','sub','Theme RS上位の細目テーマと、その中の主導銘柄。表示用ランキング。');
    rows.slice(0,8).forEach((row)=>{
      const item=append(card,'div','slrow','');
      const name=append(item,'div','slname',String(row.theme_name||row.theme_id||'—'));
      append(name,'span','mut','（'+String(row.major_theme||'')+'・強さ'+(finite(row.theme_rs)===null?'—':finite(row.theme_rs).toFixed(0))+'）');
      const chips=append(item,'div','chips','');
      (Array.isArray(row.leaders)?row.leaders:[]).slice(0,3).forEach((ticker)=>chips.appendChild(tickerButton(String(ticker),'hot')));
    });
    card.dataset.v38Status=rows.length?'READY':'DATA_REQUIRED';
  }

  function renderSectorTable(card, view) {
    if(!card)return;
    const rows=sectorRows(view);
    card.replaceChildren();
    const h2=append(card,'h2','', 'セクターETF強弱 '); append(h2,'span','h2en','Sector ETF Strength');
    append(card,'div','sub','S&P500 GICS11セクターETFの騰落率。');
    const wrap=append(card,'div','sectbl',''); const table=append(wrap,'table','','');
    const tr=append(table,'tr','',''); ['#','セクター','日','週','月'].forEach((x,i)=>append(tr,'th',i<2?'l':'',x));
    rows.slice().sort((a,b)=>(finite(b.summary.change_1w)||-999)-(finite(a.summary.change_1w)||-999)).forEach((row,index)=>{
      const r=append(table,'tr','',''); append(r,'td','l mut',index+1);
      const n=append(r,'td','l tk',row.name+' '); append(n,'span','mut',row.ticker);
      ['change_1d','change_1w','change_1m'].forEach((key)=>{ const v=finite(row.summary[key]); append(r,'td',v===null?'mut':v>=0?'pos':'neg',pct(v)); });
    });
    card.dataset.v38Status='READY';
  }

  function themeState(score) {
    const x=finite(score); if(x===null)return '—'; if(x>=85)return '強い継続'; if(x>=70)return '改善'; if(x>=50)return '監視'; if(x>=30)return '初動'; return '弱い';
  }

  function renderThemeTable(card, rotation) {
    if(!card)return;
    const rows=Array.isArray((rotation||{}).fine_theme_rows)?rotation.fine_theme_rows:[];
    card.replaceChildren();
    const h2=append(card,'h2','', 'サブテーマ別RS（ユニバース内） '); append(h2,'span','h2en','Sub-Theme RS');
    append(card,'div','sub','細目ThemeのRS63×RS189表示ランキング。日/1ヶ月は構成銘柄中央値。');
    const table=append(card,'table','secrs',''); const thead=append(table,'thead','',''); const hr=append(thead,'tr','',''); ['#','サブテーマ','状態','日','1ヶ月','RS63'].forEach((x,i)=>append(hr,'th',i<2?'l':'',x));
    const body=append(table,'tbody','','');
    rows.slice(0,40).forEach((row,index)=>{
      const tr=append(body,'tr','secrow',''); append(tr,'td','l mut secnum',index+1);
      const name=append(tr,'td','l tk',String(row.theme_name||row.theme_id||'—')+' '); append(name,'span','mut',String(row.member_count||0)+'社・RS'+(finite(row.theme_rs)===null?'—':finite(row.theme_rs).toFixed(0)));
      const state=append(tr,'td','',''); append(state,'span','rotb',themeState(row.theme_rs));
      [row.ret1_median,row.ret20_median].forEach((value)=>{ const v=finite(value); append(tr,'td',v===null?'mut':v>=0?'pos':'neg',pct(v)); });
      append(tr,'td','',finite(row.rs63_median)===null?'—':finite(row.rs63_median).toFixed(0));
    });
    card.dataset.v38Status=rows.length?'READY':'DATA_REQUIRED';
  }

  function cleanUnsupportedThemeThermometer(section) {
    const card=findCard(section,'テーマETFの温度計');
    if(!card)return;
    card.replaceChildren();
    const h2=append(card,'h2','', 'テーマETFの温度計 '); append(h2,'span','h2en','Theme ETF RRG');
    append(card,'div','sub','テーマETF56本の同日履歴は現在の公開shardに含まれないため、過去値を流用せず未取得を明示します。');
    const note=append(card,'div','v38-bind-note',''); note.dataset.v38Status='DATA_REQUIRED'; append(note,'strong','','DATA_REQUIRED'); append(note,'div','','THEME_ETF_RRG_CURRENT_HISTORY_NOT_PUBLISHED');
    card.dataset.v38Status='DATA_REQUIRED';
  }

  function renderRotation(view) {
    const section=restoreRotationShell();
    if(!section)return;
    section.dataset.v38Status=((view.rotation||{}).status||'DATA_REQUIRED');
    renderRrgCard(findCard(section,'資金フロー'),view);
    renderHeatmap(findCard(section,'セクター温度マップ'),view);
    insertBreadthCard(section,view);
    renderLeadingGroups(findCard(section,'主導セクター・業種'),view.rotation||{});
    renderStrongLeaders(findCard(section,'強い業種の主導株'),view.rotation||{});
    renderSectorTable(findCard(section,'セクターETF強弱'),view);
    renderThemeTable(findCard(section,'サブテーマ別RS'),view.rotation||{});
    cleanUnsupportedThemeThermometer(section);
  }

  function moverValue(row, key) { return finite(row && row[key]); }

  function renderMoverLine(list, row, key) {
    const line=append(list,'div','mvr','');
    const button=node('button','mvr-t v38-ticker-link',String(row.ticker||'—')); button.type='button'; button.addEventListener('click',()=>{ if(window.V38OpenTickerChart)window.V38OpenTickerChart(row.ticker); }); line.appendChild(button);
    const meta=append(line,'div','mvr-x','');
    append(meta,'span','mvr-e','RS189 '+(finite(row.rs189)===null?'—':finite(row.rs189).toFixed(0)));
    append(meta,'span','mvr-th',String(row.industry||row.sector||''));
    const v=moverValue(row,key); append(line,'div','mvr-v '+(v===null?'mut':v>=0?'pos':'neg'),pct(v));
  }

  function renderMoverColumn(parent, title, rows, key) {
    const col=append(parent,'div','mv-col',''); append(col,'div','mv-col-h',title);
    const list=append(col,'div','mv-list',''); (Array.isArray(rows)?rows:[]).forEach((row)=>renderMoverLine(list,row,key));
    if(!rows || !rows.length)append(list,'div','mut','該当なし');
  }

  function renderMovers(view) {
    const section=document.getElementById('t-movers'); if(!section)return;
    const data=view.movers||{}; section.replaceChildren(); section.dataset.v38Status=data.status||'DATA_REQUIRED';
    const card=append(section,'div','card','');
    const hdr=append(card,'div','hdr',''); const h2=append(hdr,'h2','', '値動き 上位・下位 '); append(h2,'span','h2en','Movers');
    append(card,'div','sub','投資対象ユニバース（'+String(data.universe_count||0)+'銘柄）のパフォーマンス上位・下位を前日・1週・1ヶ月で表示。3窓＝3期間すべてで上位/下位20。');
    if(data.status!=='READY'){
      const note=append(card,'div','v38-bind-note',''); note.dataset.v38Status=data.status||'DATA_REQUIRED'; append(note,'strong','',data.status||'DATA_REQUIRED'); append(note,'div','',data.reason||'CURRENT_RETURN_ROWS_MISSING'); return;
    }
    const wrap=append(card,'div','mv-wrap','');
    append(wrap,'div','mv-sec-h','① 本日の値動きサマリー');
    ['1d','1w','1m'].forEach((key)=>{
      const s=(data.summary||{})[key]||{}; const row=append(wrap,'div','mv-sum','');
      append(row,'b','',String(s.label||key));
      row.appendChild(document.createTextNode('　中央値 '+pct(s.median)+'　上昇 '+(finite(s.advancing_pct)===null?'—':(finite(s.advancing_pct)*100).toFixed(0)+'%')+'　+3%以上 '+String(s.up3_count||0)+'　−3%以下 '+String(s.down3_count||0)));
    });
    append(wrap,'div','mv-sec-h','② 3窓一致（前日・1週・1ヶ月すべてで上位/下位20）');
    const tri=append(wrap,'div','mv-cols','');
    renderMoverColumn(tri,'3窓 上位',(data.three_window||{}).gainers||[],'ret20');
    renderMoverColumn(tri,'3窓 下位',(data.three_window||{}).losers||[],'ret20');
    append(wrap,'div','mv-sec-h','③ 期間別ランキング');
    ['1d','1w','1m'].forEach((key,index)=>{
      const period=(data.periods||{})[key]||{}; const details=append(wrap,'details','mv-per',''); if(index===0)details.open=true;
      append(details,'summary','mv-per-h',String(period.label||key)+' 上位 / 下位20');
      const cols=append(details,'div','mv-cols',''); renderMoverColumn(cols,'上位20',period.gainers||[],period.key||('ret'+key)); renderMoverColumn(cols,'下位20',period.losers||[],period.key||('ret'+key));
    });
  }

  async function apply() {
    if(!window.V38Runtime || typeof window.V38Runtime.loadJson!=='function')return;
    let view; try{ view=await window.V38Runtime.loadJson('data/ui_view_model.json'); }catch(_){ return; }
    renderRotation(view); renderMovers(view);
    document.body.dataset.v38RotationMoversVisual='applied';
  }

  function schedule() {
    let attempts=0;
    const timer=setInterval(()=>{
      attempts+=1;
      if(document.body && document.body.dataset.v38BindingStatus==='ready'){
        clearInterval(timer); window.setTimeout(apply,80);
      } else if(attempts>=80){ clearInterval(timer); }
    },100);
  }

  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',schedule,{once:true}); else schedule();
})();
