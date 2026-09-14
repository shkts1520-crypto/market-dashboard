(function(){'use strict';

const PERIODS=[21,63,126,189];
const FLOW_PERIODS=[189,126,63,21];
const SECTOR_ETFS=[
  ['XLB','素材'],['XLC','通信'],['XLE','エネルギー'],['XLF','金融'],
  ['XLI','資本財'],['XLK','情報技術'],['XLP','生活必需品'],['XLRE','不動産'],
  ['XLU','公益'],['XLV','ヘルスケア'],['XLY','一般消費財']
];
const OPTION_BUCKETS=['0-6','7-21','22-45','0-45'];
const SECTOR_COLOR={
  '情報技術':'#C08A3E','テック':'#C08A3E','テクノロジー':'#C08A3E',
  '金融':'#2F6E96','通信':'#7D5EA6','通信サービス':'#7D5EA6',
  '資本財':'#4E8768','資本財/防衛':'#4E8768','ヘルスケア':'#3E9276',
  '一般消費':'#B0794A','一般消費財':'#B0794A','素材':'#8F7B4A',
  'エネルギー':'#A84C40','公益':'#8A8AA0','不動産':'#9A6FA0',
  '生活必需品':'#789A88'
};
const CACHE={};
let SEARCH_ROWS=[];
let BUSY=false;

const num=v=>v===null||v===undefined||v===''?null:(Number.isFinite(Number(v))?Number(v):null);
const price=v=>num(v)===null?'—':num(v).toFixed(2);
const pct=v=>num(v)===null?'—':(num(v)>0?'+':'')+(num(v)*100).toFixed(1)+'%';
function el(parent,tag,cls,text){
  const n=document.createElement(tag);
  if(cls)n.className=cls;
  if(text!==undefined)n.textContent=String(text);
  if(parent)parent.appendChild(n);
  return n;
}
function load(path){
  return CACHE[path]||(CACHE[path]=fetch(path,{cache:'no-store'})
    .then(r=>r.ok?r.json():null).catch(()=>null));
}
function colorFor(name){return SECTOR_COLOR[name]||'#7B7467';}
function installStyle(){
  if(document.getElementById('v38-restored-experience-style'))return;
  const s=document.createElement('style');
  s.id='v38-restored-experience-style';
  s.textContent=`
  /* Canonical v5 paper visual. Scoped so unrelated tabs remain untouched. */
  #t-rotation .v38-canonical-rotation{
    --paper:#E9E7DF;--ink:#1B1D1C;--mut:#727569;--line:#D5D1C6;
    --accent:#17685C;--warn:#B07A16;--neg:#B23A2E;--card:#F3F1EA;
    --track:#DFDCD2;--chipbg:#ECE9E0;--fnum:ui-monospace,SFMono-Regular,Menlo,monospace;
    color:var(--ink);font-family:-apple-system,'Helvetica Neue',Arial,'Hiragino Sans','Noto Sans JP',sans-serif;
  }
  #t-rotation .v38-canonical-rotation>.card{
    background:var(--paper);border:1px solid var(--line);border-radius:13px;
    padding:12px 14px;margin-bottom:12px;box-shadow:none;
  }
  #t-rotation .v38-canonical-rotation .hd{display:flex;align-items:center;gap:11px;margin-bottom:4px}
  #t-rotation .v38-canonical-rotation .hd .bar{width:5px;height:21px;background:var(--accent);border-radius:3px;flex:0 0 auto}
  #t-rotation .v38-canonical-rotation .hd h1{font-size:22px;font-weight:800;letter-spacing:-.02em;margin:0}
  #t-rotation .v38-canonical-rotation .hd h1 .en{font-size:13px;font-weight:600;color:var(--mut);letter-spacing:.02em;margin-left:5px}
  #t-rotation .v38-canonical-rotation .hd .pg{font-size:11.5px;font-weight:800;color:var(--accent);border:1.5px solid var(--accent);border-radius:8px;padding:2px 10px}
  #t-rotation .v38-canonical-rotation .hd .date{margin-left:auto;font-size:13.5px;color:var(--mut);font-weight:700}
  #t-rotation .v38-canonical-rotation .read{font-size:13px;font-weight:700;color:#33352E;margin-bottom:8px;line-height:1.35;padding-bottom:8px;border-bottom:1.5px solid var(--line)}
  #t-rotation .v38-canonical-rotation .read b{color:var(--accent)}
  #t-rotation .v38-canonical-rotation .read .dn{color:var(--neg)}
  #t-rotation .v38-canonical-rotation .grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));grid-template-rows:370px minmax(430px,auto);gap:8px;min-height:0}
  #t-rotation .v38-canonical-rotation .sp2{grid-column:span 2}
  #t-rotation .v38-canonical-rotation .sp3{grid-column:span 3}
  #t-rotation .v38-canonical-rotation .t{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:9px 11px;min-height:0;overflow:hidden;display:flex;flex-direction:column}
  #t-rotation .v38-canonical-rotation .th{display:flex;align-items:center;gap:6px;margin-bottom:6px;min-height:30px}
  #t-rotation .v38-canonical-rotation .th h4{font-size:12.5px;font-weight:800;letter-spacing:-.01em;margin:0}
  #t-rotation .v38-canonical-rotation .th h4 .en{font-size:9.5px;font-weight:600;color:var(--mut);margin-left:6px;letter-spacing:.02em}
  #t-rotation .v38-canonical-rotation .th .s{font-size:10px;color:var(--mut);font-weight:700}
  #t-rotation .v38-canonical-rotation .th .g{margin-left:auto;color:var(--mut);opacity:.5;font-size:12px}
  #t-rotation .v38-canonical-rotation .rank-scroll{flex:1;min-height:0;overflow:auto}
  #t-rotation .v38-canonical-rotation .prg{display:grid;grid-template-columns:repeat(4,minmax(110px,1fr));gap:11px;min-width:540px;height:100%}
  #t-rotation .v38-canonical-rotation .prg.tight{gap:8px}
  #t-rotation .v38-canonical-rotation .prcol{display:flex;flex-direction:column;min-height:0}
  #t-rotation .v38-canonical-rotation .prcol .ph{font-size:10.5px;font-weight:800;color:var(--accent);text-align:center;border-bottom:1.5px solid var(--line);padding-bottom:3px;margin-bottom:2px}
  #t-rotation .v38-canonical-rotation .prcol .ph span{font-size:9px;color:var(--mut);font-weight:700}
  #t-rotation .v38-canonical-rotation .prcol .body{flex:1;display:flex;flex-direction:column;justify-content:space-between;min-height:0}
  #t-rotation .v38-canonical-rotation .prrow{display:grid;grid-template-columns:8px 13px minmax(0,1fr) auto 20px;gap:5px;align-items:center;white-space:nowrap}
  #t-rotation .v38-canonical-rotation .prrow .rk{color:var(--mut);text-align:center}
  #t-rotation .v38-canonical-rotation .prrow .nm{font-weight:700;overflow:hidden;text-overflow:ellipsis}
  #t-rotation .v38-canonical-rotation .prrow .rv{font-weight:800;font-family:var(--fnum);text-align:right}
  #t-rotation .v38-canonical-rotation .prrow .ar{font-weight:800;text-align:right}
  #t-rotation .v38-canonical-rotation .dotc{display:inline-block;width:8px;height:8px;border-radius:50%}
  #t-rotation .v38-canonical-rotation .maj .prrow{font-size:12px}
  #t-rotation .v38-canonical-rotation .maj .prrow .rk{font-size:10px}
  #t-rotation .v38-canonical-rotation .maj .prrow .rv{font-size:12px}
  #t-rotation .v38-canonical-rotation .maj .prrow .ar{font-size:9.5px}
  #t-rotation .v38-canonical-rotation .min .prrow{font-size:10px;grid-template-columns:7px 12px minmax(0,1fr) auto 16px;gap:4px}
  #t-rotation .v38-canonical-rotation .min .prrow .rk{font-size:8.5px}
  #t-rotation .v38-canonical-rotation .min .prrow .rv{font-size:10px}
  #t-rotation .v38-canonical-rotation .min .prrow .ar{font-size:8px}
  #t-rotation .v38-canonical-rotation .min .dotc{width:6px;height:6px}
  #t-rotation .v38-canonical-rotation .up{color:var(--accent)}
  #t-rotation .v38-canonical-rotation .down{color:var(--neg)}
  #t-rotation .v38-canonical-rotation .rrgwrap{flex:1;min-height:0;overflow:hidden}
  #t-rotation .v38-canonical-rotation #bump{width:100%;height:100%}
  #t-rotation .v38-canonical-rotation #bump svg{display:block;width:100%;height:100%}
  #t-rotation .v38-canonical-rotation .flowbody{flex:1;min-height:0;display:flex;flex-direction:column;gap:4px}
  #t-rotation .v38-canonical-rotation .fttl{font-size:10px;font-weight:800;color:var(--accent);margin-bottom:1px}
  #t-rotation .v38-canonical-rotation #majflow{display:flex;flex-direction:column;gap:1px}
  #t-rotation .v38-canonical-rotation .dvrow{display:grid;grid-template-columns:96px 1fr 42px;gap:6px;align-items:center;font-size:11px;padding:1px 0}
  #t-rotation .v38-canonical-rotation .dvrow .dnm{font-weight:700;display:flex;align-items:center;gap:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  #t-rotation .v38-canonical-rotation .dv{position:relative;height:10px;background:var(--track);border-radius:3px}
  #t-rotation .v38-canonical-rotation .dv .zero{position:absolute;left:50%;top:-2px;bottom:-2px;width:1px;background:var(--mut);opacity:.55}
  #t-rotation .v38-canonical-rotation .dv .fill{position:absolute;top:0;bottom:0;border-radius:3px}
  #t-rotation .v38-canonical-rotation .dvrow .dval{text-align:right;font-weight:800;font-family:var(--fnum);font-size:10.5px}
  #t-rotation .v38-canonical-rotation .ldrs{flex:1;display:flex;flex-direction:column;justify-content:space-around;min-height:0;gap:2px}
  #t-rotation .v38-canonical-rotation .ldrow2{border-bottom:1px solid var(--line);padding-bottom:7px}
  #t-rotation .v38-canonical-rotation .ldrow2:last-child{border-bottom:0}
  #t-rotation .v38-canonical-rotation .ldrow2 .lh{font-size:10px;font-weight:800;color:var(--accent);margin-bottom:5px}
  #t-rotation .v38-canonical-rotation .ldrow2 .lh .s{font-size:8.5px;color:var(--mut);margin-left:4px}
  #t-rotation .v38-canonical-rotation .ldrow2 .lc{display:flex;flex-wrap:wrap;gap:5px}
  #t-rotation .v38-canonical-rotation .tchip{font-family:var(--fnum);font-size:11.5px;font-weight:800;background:var(--chipbg);border:1px solid var(--line);border-radius:5px;padding:2.5px 8px;letter-spacing:-.01em;cursor:pointer;color:var(--ink)}
  #t-rotation .v38-canonical-rotation .flownote{margin-top:auto;font-size:10px;font-weight:600;color:#33352E;line-height:1.36;border-top:1.5px solid var(--line);padding-top:5px}
  #t-rotation .v38-canonical-rotation .flownote b{color:var(--accent)}

  /* Search: same neutral card vocabulary as the original dashboard. */
  #v38-universe-search{max-width:1060px;margin:7px auto 10px;padding:10px 14px;position:relative;z-index:80}
  #v38-universe-search .v38-search-head{display:flex;align-items:baseline;gap:7px;margin-bottom:3px}
  #v38-universe-search .v38-search-head h2{margin:0;font-size:14px}
  #v38-universe-search .h2en{font-size:9px;color:#727569;font-weight:600}
  #v38-universe-search .sub{font-size:10px;color:#727569;margin-bottom:6px}
  #v38-universe-search .v38-searchbox{position:relative}
  #v38-universe-search .tksearch{width:100%;box-sizing:border-box;padding:8px 34px 8px 10px;border:1px solid #D5D1C6;border-radius:7px;background:#F7F5EF;color:#1B1D1C;font:700 12px -apple-system,'Helvetica Neue',Arial,sans-serif}
  #v38-universe-search .v38-search-clear{position:absolute;right:7px;top:2px;border:0;background:transparent;font-size:19px;color:#727569;cursor:pointer}
  #v38-universe-search .tkresults{position:absolute;left:0;right:0;top:39px;max-height:320px;overflow:auto;background:#F7F5EF;border:1px solid #D5D1C6;border-radius:8px;box-shadow:0 10px 24px #0002}
  #v38-universe-search .tkresults[hidden]{display:none!important}
  #v38-universe-search .v38-search-result{width:100%;display:grid;grid-template-columns:62px minmax(0,1fr) auto;gap:7px;border:0;border-bottom:1px solid #E1DDD3;background:transparent;padding:7px 9px;text-align:left;cursor:pointer;color:#1B1D1C}
  #v38-universe-search .v38-search-result b{font-size:12px}
  #v38-universe-search .v38-search-result span{font-size:9px;color:#727569;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  #v38-universe-search .v38-search-result em{font-size:9px;color:#17685C;font-style:normal;font-weight:800}

  /* Options keep the original rsx-card/rsx-item visual rather than a new table skin. */
  #t-options .v38-canonical-options>.msec{margin-top:0}
  #t-options .v38-canonical-options .card.rsx-card{margin-bottom:10px}
  #t-options .v38-canonical-options .v38-options-list{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
  #t-options .v38-canonical-options .rsx-item{cursor:pointer}
  #t-options .v38-canonical-options .rsx-name button{border:0;background:transparent;padding:0;color:inherit;font:inherit;font-weight:800;cursor:pointer}
  #t-options .v38-canonical-options .rsx-score b{font-size:13px}
  #t-options .v38-canonical-options .rsx-score small{display:block}
  #t-options .v38-canonical-options .rsx-sub{display:flex;gap:6px 12px;flex-wrap:wrap}
  #t-options .v38-canonical-options .rsx-nums,#t-options .v38-canonical-options .rsx-ret{font-size:10px}
  #t-options .v38-canonical-options .v38-empty{font-size:11px;color:#727569;padding:8px 0}

  /* VWAP uses the dashboard's native card/table vocabulary. */
  #t-today .v38-vwap-card .v38-vwap-ticker{border:0;background:transparent;padding:0;color:inherit;font:inherit;font-weight:800;cursor:pointer}
  #t-today .v38-vwap-card .v38-vwap-hit{color:#17685C;font-weight:800}
  #t-today .v38-vwap-card .v38-vwap-life{color:#675B86;font-weight:800}
  #t-today .v38-vwap-card .v38-vwap-note{font-size:9.5px;color:#727569;margin-top:6px;line-height:1.45}

  @media(max-width:760px){
    #t-rotation .v38-canonical-rotation>.card{padding:10px}
    #t-rotation .v38-canonical-rotation .hd{flex-wrap:wrap;gap:6px}
    #t-rotation .v38-canonical-rotation .hd h1{font-size:18px}
    #t-rotation .v38-canonical-rotation .hd .date{width:100%;margin-left:16px;font-size:10.5px}
    #t-rotation .v38-canonical-rotation .read{font-size:11px}
    #t-rotation .v38-canonical-rotation .grid{grid-template-columns:1fr;grid-template-rows:none}
    #t-rotation .v38-canonical-rotation .sp2,#t-rotation .v38-canonical-rotation .sp3{grid-column:auto}
    #t-rotation .v38-canonical-rotation .t{min-height:330px}
    #t-rotation .v38-canonical-rotation .t.min{min-height:420px}
    #t-rotation .v38-canonical-rotation .th{align-items:flex-start;flex-wrap:wrap}
    #t-rotation .v38-canonical-rotation .th .s{width:100%}
    #t-rotation .v38-canonical-rotation .prg{min-width:520px}
    #t-options .v38-canonical-options .v38-options-list{grid-template-columns:1fr}
    #v38-universe-search{margin:6px 10px 10px}
  }`;
  document.head.appendChild(s);
}

function followTab(){
  const a=document.querySelector('nav a.tabx.on,nav a.tabx[aria-selected="true"]');
  const nav=a&&a.closest('nav');
  if(!a||!nav||nav.scrollWidth<=nav.clientWidth+2)return;
  const x=Math.max(0,a.offsetLeft-(nav.clientWidth-a.offsetWidth)/2);
  try{nav.scrollTo({left:x,behavior:'smooth'});}catch(_){nav.scrollLeft=x;}
}
function bindTabs(){
  document.addEventListener('click',e=>{
    if(e.target instanceof Element&&e.target.closest('nav a.tabx[href^="#"]')){
      setTimeout(followTab,0);setTimeout(followTab,100);
    }
  });
  addEventListener('hashchange',()=>setTimeout(followTab,30));
  addEventListener('popstate',()=>setTimeout(followTab,30));
  setTimeout(followTab,80);
}
function openTicker(ticker){
  const t=String(ticker||'').toUpperCase();
  if(!t)return;
  if(window.V38OpenTickerChart)window.V38OpenTickerChart(t);
  else setTimeout(()=>window.V38OpenTickerChart&&window.V38OpenTickerChart(t),120);
}

function matchSearch(q){
  q=String(q||'').trim().toUpperCase();
  if(!q)return[];
  return SEARCH_ROWS.map(r=>{
    const t=String(r.ticker||'').toUpperCase();
    const n=String(r.name||'').toUpperCase();
    const s=String(r.sector||'').toUpperCase();
    const i=String(r.industry||'').toUpperCase();
    const k=t===q?0:t.startsWith(q)?1:n.startsWith(q)?2:t.includes(q)?3:n.includes(q)?4:(s.includes(q)||i.includes(q))?5:99;
    return{r,k};
  }).filter(x=>x.k<99)
    .sort((a,b)=>a.k-b.k+((num(b.r.rs189)||0)-(num(a.r.rs189)||0)))
    .slice(0,12).map(x=>x.r);
}
function renderSearch(data){
  if(document.getElementById('v38-universe-search'))return;
  SEARCH_ROWS=Array.isArray(data&&data.rows)?data.rows:[];
  const nav=document.querySelector('nav');
  if(!nav)return;
  const card=el(null,'div','card','');
  card.id='v38-universe-search';
  card.dataset.v38CanonicalVisual='ticker-search';
  const head=el(card,'div','v38-search-head','');
  const h=el(head,'h2','','銘柄検索');
  el(h,'span','h2en','Ticker Search');
  el(card,'div','sub','ティッカーで全ユニバースを検索（タップで詳細）');
  const box=el(card,'div','v38-searchbox','');
  const input=el(box,'input','tksearch','');
  input.type='search';input.inputMode='search';input.autocomplete='off';input.placeholder='例: NVDA';
  const clear=el(box,'button','v38-search-clear','×');clear.type='button';clear.setAttribute('aria-label','検索をクリア');
  const results=el(box,'div','tkresults','');results.hidden=true;
  function paint(){
    const rows=matchSearch(input.value);
    results.replaceChildren();
    rows.forEach(r=>{
      const b=el(results,'button','v38-search-result','');b.type='button';
      el(b,'b','',r.ticker||'—');
      el(b,'span','',[r.name,r.sector,r.industry].filter(Boolean).join(' · '));
      el(b,'em','',num(r.rs189)===null?'':`RS189 ${num(r.rs189).toFixed(0)}`);
      b.onclick=()=>{input.value=r.ticker||'';results.hidden=true;openTicker(r.ticker);};
    });
    results.hidden=!rows.length;
  }
  input.oninput=paint;input.onfocus=paint;
  input.onkeydown=e=>{
    if(e.key==='Enter'){const rows=matchSearch(input.value);if(rows.length){e.preventDefault();results.hidden=true;openTicker(rows[0].ticker);}}
    if(e.key==='Escape')results.hidden=true;
  };
  clear.onclick=()=>{input.value='';results.hidden=true;input.focus();};
  document.addEventListener('click',e=>{if(!card.contains(e.target))results.hidden=true;});
  nav.insertAdjacentElement('afterend',card);
}

function periodReturn(series,p){
  const a=(Array.isArray(series)?series:[]).filter(r=>num(r&&r.close)!==null);
  if(a.length<=p)return null;
  return num(a.at(-1).close)/num(a.at(-1-p).close)-1;
}
function rankRows(rows,p,getter){
  const a=rows.filter(r=>num(getter(r))!==null).sort((a,b)=>getter(b)-getter(a));
  a.forEach((r,i)=>{r.rank[p]=i+1;r.score[p]=a.length<2?50:100*(a.length-1-i)/(a.length-1);});
}
function majorRows(view){
  const series=(view.daily&&view.daily.market_series)||{};
  const rows=SECTOR_ETFS.map(([ticker,label])=>({ticker,label,major:label,raw:{},rank:{},score:{}}));
  PERIODS.forEach(p=>{rows.forEach(r=>r.raw[p]=periodReturn(series[r.ticker],p));rankRows(rows,p,r=>r.raw[p]);});
  return rows;
}
function median(values){
  const a=values.map(num).filter(v=>v!==null).sort((a,b)=>a-b);
  if(!a.length)return null;
  const m=Math.floor(a.length/2);return a.length%2?a[m]:(a[m-1]+a[m])/2;
}
function fineRows(data){
  const groups={};
  (data.rows||[]).forEach(r=>{if(r.theme_id)(groups[r.theme_id]||(groups[r.theme_id]=[])).push(r);});
  const out=Object.entries(groups).filter(([,a])=>a.length>=3).map(([label,a])=>({
    label,major:(a.find(x=>x.major_theme)||{}).major_theme||'',
    raw:{21:median(a.map(x=>x.ret20)),63:median(a.map(x=>x.rs63)),126:median(a.map(x=>x.rs126)),189:median(a.map(x=>x.rs189))},rank:{},score:{}
  }));
  PERIODS.forEach(p=>rankRows(out,p,r=>r.raw[p]));return out;
}
function rankDelta(row,p){return num(row.rank[p])===null||num(row.rank[189])===null?null:row.rank[189]-row.rank[p];}
function deltaText(v){return v===null?'':v>0?`▲${v}`:v<0?`▼${Math.abs(v)}`:'•';}
function addPanel(grid,title,en,sub,cls){
  const p=el(grid,'div',`t ${cls||''}`,'');
  const th=el(p,'div','th','');const h=el(th,'h4','',title);el(h,'span','en',en);el(th,'span','s',sub);el(th,'span','g','⚙');return p;
}
function renderPeriodGrid(panel,rows,limit,isFine){
  const scroll=el(panel,'div','rank-scroll','');const g=el(scroll,'div',`prg${isFine?' tight':''}`,'');g.id=isFine?'prgMin':'prgMaj';
  PERIODS.forEach(p=>{
    const col=el(g,'div','prcol','');const ph=el(col,'div','ph',`RS${p}`);el(ph,'span','',p===21?' 短期':p===63?' 中期':p===126?' 中長期':' 長期');const body=el(col,'div','body','');
    rows.slice().sort((a,b)=>(a.rank[p]||999)-(b.rank[p]||999)).slice(0,limit).forEach(r=>{
      const d=rankDelta(r,p),row=el(body,'div','prrow',''),dot=el(row,'span','dotc','');dot.style.background=colorFor(r.major||r.label);
      el(row,'span','rk',r.rank[p]||'—');el(row,'span','nm',r.label);el(row,'span','rv',num(r.score[p])===null?'—':r.score[p].toFixed(0));el(row,'span',`ar ${d>0?'up':d<0?'down':''}`,p===189?'•':deltaText(d));
    });
  });
}
function renderRankFlow(host,rows){
  const W=760,H=320,L=92,R=92,T=28,B=22,N=Math.max(rows.length,2),xs=FLOW_PERIODS.map((_,i)=>L+(W-L-R)*i/3),y=rank=>T+(H-T-B)*(Math.max(1,Math.min(N,rank))-1)/Math.max(1,N-1),ns='http://www.w3.org/2000/svg',svg=document.createElementNS(ns,'svg');
  svg.setAttribute('viewBox',`0 0 ${W} ${H}`);
  FLOW_PERIODS.forEach((p,i)=>{const line=document.createElementNS(ns,'line');line.setAttribute('x1',xs[i]);line.setAttribute('x2',xs[i]);line.setAttribute('y1',T);line.setAttribute('y2',H-B);line.setAttribute('stroke','#D5D1C6');line.setAttribute('stroke-width','1');svg.appendChild(line);const text=document.createElementNS(ns,'text');text.setAttribute('x',xs[i]);text.setAttribute('y','15');text.setAttribute('text-anchor','middle');text.setAttribute('font-size','11');text.setAttribute('font-weight','700');text.setAttribute('fill','#727569');text.textContent=`RS${p}`;svg.appendChild(text);});
  rows.forEach((r,k)=>{const points=FLOW_PERIODS.map((p,i)=>[xs[i],y(r.rank[p]||N)]),line=document.createElementNS(ns,'polyline');line.setAttribute('points',points.map(q=>q.join(',')).join(' '));line.setAttribute('fill','none');line.setAttribute('stroke',colorFor(r.label));line.setAttribute('stroke-width',k<5?'2':'1.3');line.setAttribute('opacity',k<8?'1':'.7');svg.appendChild(line);[points[0],points.at(-1)].forEach((q,j)=>{const text=document.createElementNS(ns,'text');text.setAttribute('x',j?W-R+5:L-5);text.setAttribute('y',q[1]+3);text.setAttribute('text-anchor',j?'start':'end');text.setAttribute('font-size','9');text.setAttribute('font-weight','700');text.setAttribute('fill',colorFor(r.label));text.textContent=r.label;svg.appendChild(text);});});host.replaceChildren(svg);
}
function leaderRows(data,p){const key=p===21?'ret20':`rs${p}`;return(data.rows||[]).filter(r=>num(r[key])!==null).sort((a,b)=>num(b[key])-num(a[key])).slice(0,5);}
function renderMoneyFlow(panel,majors,data){
  const body=el(panel,'div','flowbody','');el(body,'div','fttl','大分類フロー（左=流出 ／ 右=流入）');const flow=el(body,'div','','');flow.id='majflow';
  const rows=majors.map(r=>({r,v:(num(r.score[21])||0)-(num(r.score[189])||0)})).sort((a,b)=>b.v-a.v),max=Math.max(1,...rows.map(x=>Math.abs(x.v)));
  rows.forEach(({r,v})=>{const row=el(flow,'div','dvrow',''),name=el(row,'div','dnm',''),dot=el(name,'i','dotc','');dot.style.background=colorFor(r.label);el(name,'span','',r.label);const track=el(row,'div','dv','');el(track,'i','zero','');const fill=el(track,'i','fill',''),w=50*Math.abs(v)/max;fill.style.width=`${w}%`;fill.style.left=`${v<0?50-w:50}%`;fill.style.background=v<0?'#B23A2E':'#17685C';el(row,'div',`dval ${v>0?'up':v<0?'down':''}`,(v>0?'+':'')+v.toFixed(0));});
  const ft=el(body,'div','fttl','期間ごとの先導株（RS上位5）');ft.style.marginTop='5px';const leaders=el(body,'div','ldrs','');leaders.id='leaders';
  PERIODS.forEach(p=>{const row=el(leaders,'div','ldrow2',''),lh=el(row,'div','lh',`RS${p}`);el(lh,'span','s',p===21?'短期':p===63?'中期':p===126?'中長期':'長期');const chips=el(row,'div','lc','');leaderRows(data,p).forEach(x=>{const b=el(chips,'button','tchip',x.ticker||'—');b.type='button';b.dataset.v38Ticker=x.ticker||'';b.onclick=()=>openTicker(x.ticker);});});
  const note=el(body,'div','flownote','');note.id='fnote';note.innerHTML='短期RS − 長期RSを表示。<b>Rotationは売買ゲートではなく、WHERE（資金の向き）の確認用。</b>';
}
function renderRotation(view,data){
  /* 09/05 Rotation is the authority; bind its existing hosts elsewhere. */
  return;
  const section=document.getElementById('t-rotation');if(!section)return;const majors=majorRows(view),fine=fineRows(data);if(!majors.some(r=>num(r.score[21])!==null))return;
  const root=document.createElement('div');root.className='v38-canonical-rotation';root.dataset.v38CanonicalVisual='rotation-v5';const card=el(root,'div','card',''),head=el(card,'div','hd','');el(head,'span','bar','');const h=el(head,'h1','','セクター・ローテーション');el(h,'span','en','Sector Rotation');el(head,'span','pg','2 / 詳細');el(head,'span','date num',view.session_date||'—');
  const top=majors.slice().sort((a,b)=>(a.rank[21]||99)-(b.rank[21]||99)).slice(0,3).map(r=>r.label),lag=majors.slice().sort((a,b)=>((a.score[21]||0)-(a.score[189]||0))-((b.score[21]||0)-(b.score[189]||0))).slice(0,2).map(r=>r.label),read=el(card,'div','read','');read.append('短期RSで ');el(read,'b','',top.join('・'));read.append(' が上位。');el(read,'span','dn',lag.join('・'));read.append(' は長期RSに対し短期が沈み後退。');
  const grid=el(card,'div','grid',''),major=addPanel(grid,'大分類 — 期間ごとランキング','Major Sectors · Rank by Period','RS21/63/126/189・▲▼＝長期(RS189)順位からの変化','sp2 maj');renderPeriodGrid(major,majors,11,false);
  const rankFlow=addPanel(grid,'順位フロー（大分類）','Rank Flow','長期→短期のRS順位推移・右肩上がり＝資金流入 / 右肩下がり＝流出','sp2'),wrap=el(rankFlow,'div','rrgwrap',''),bump=el(wrap,'div','','');bump.id='bump';renderRankFlow(bump,majors);
  const themes=addPanel(grid,'小分類（サブテーマ）— 期間ごとランキング','Sub-themes · Rank by Period','RS21/63/126/189・色＝大分類・▲▼＝長期順位からの変化','sp3 min');renderPeriodGrid(themes,fine,14,true);const money=addPanel(grid,'資金の流れ','Money Flow','短期RS − 長期RS','');renderMoneyFlow(money,majors,data);
  const compat=el(root,'div','card','サブテーマ別RS');compat.hidden=true;compat.dataset.v38Status='READY';compat.dataset.v38ThemeRows=String(fine.length);section.replaceChildren(root);section.dataset.v38Status=(view.rotation&&view.rotation.status)||'READY';section.dataset.v38RotationRestoreStatus='canonical-v5-layout-ready';
}

function optionRows(options,bucket){return((((options||{}).buckets||{})[bucket])||[]).slice(0,24);}
function netGexText(v){const n=num(v);if(n===null)return'—';const a=Math.abs(n);if(a>=1e9)return`${n<0?'-':''}${(a/1e9).toFixed(1)}B`;if(a>=1e6)return`${n<0?'-':''}${(a/1e6).toFixed(1)}M`;if(a>=1e3)return`${n<0?'-':''}${(a/1e3).toFixed(1)}K`;return n.toFixed(0);}
function renderOptions(options){
  const section=document.getElementById('t-options');if(!section||!options)return;const root=document.createElement('div');root.className='v38-canonical-options';root.dataset.v38CanonicalVisual='options-v5';const msec=el(root,'div','msec',''),left=el(msec,'div','msec-l','Options Intelligence');el(left,'span','msec-en','DTE Matrix');el(msec,'div','msec-q','期間別に全銘柄を走査。Wall配置とExpected Moveを比較。');const list=el(root,'div','v38-options-list','');
  OPTION_BUCKETS.forEach(bucket=>{const rows=optionRows(options,bucket),card=el(list,'div','card rsx-card',''),title=bucket.replace('-','–')+' DTE';card.dataset.v38Status='READY';card.dataset.v38OptionBucket=bucket;card.dataset.v38OptionRows=String(rows.length);card.dataset.v38CanonicalTitle=title;card.dataset.v38CardTitle=title;const hdr=el(card,'div','hdr',''),h=el(hdr,'h2','',title);el(h,'span','h2en',bucket==='0-6'?'Short Term':bucket==='7-21'?'Swing':bucket==='22-45'?'Medium Term':'All 0–45');el(card,'div','sub','ランキングは期間ごとに独立。Spot・Wall・Flip・Expected Move・Qualityを同じ行で確認。');if(!rows.length){el(card,'div','v38-empty','該当データなし');return;}
    rows.forEach((x,i)=>{const item=el(card,'div','rsx-item','');item.dataset.v38Ticker=x.ticker||'';const row=el(item,'div','rsx-row','');el(row,'span','rsx-rk',i+1);const name=el(row,'div','rsx-name',''),nameLine=el(name,'div','',''),b=el(nameLine,'button','',x.ticker||'—');b.type='button';b.dataset.v38Ticker=x.ticker||'';b.onclick=()=>openTicker(x.ticker);el(name,'small','',x.theme||x.sector||x.expiry||'Options');const score=el(row,'div','rsx-score','');el(score,'b','',netGexText(x.net_gex));el(score,'small','Net GEX');const sub=el(item,'div','rsx-sub',''),nums=el(sub,'span','rsx-nums','Spot ');el(nums,'b','',price(x.spot));nums.append(' ・ Call / Flip / Put ');el(nums,'b','',`${price(x.call_wall)} / ${price(x.gamma_flip)} / ${price(x.put_wall)}`);const ret=el(sub,'span','rsx-ret','Expected Move ');el(ret,'b','',num(x.expected_move_pct)===null?'—':`±${(100*num(x.expected_move_pct)).toFixed(1)}%`);ret.append(' ・ Quality ');el(ret,'b','',String(x.quality||'READY'));item.onclick=e=>{if(!e.target.closest('button'))openTicker(x.ticker);};});
  });section.replaceChildren(root);section.dataset.v38Status=options.status||'READY';section.dataset.v38OptionsRestoreStatus='canonical-v5-layout-ready';
}

function vwapSignalText(x){if(!x)return'—';const flags=[];if(x.break)flags.push('上抜け');if(x.touch)flags.push('タッチ維持');if(x.near)flags.push('近接');return flags.length?flags.join(' / '):'—';}
function renderVwap(vwap){
  const section=document.getElementById('t-rs');if(!section||!vwap||!Array.isArray(vwap.rows))return;let card=section.querySelector('.v38-vwap-card');if(!card){card=document.createElement('div');card.className='card v38-vwap-card';section.appendChild(card);}card.replaceChildren();const hdr=el(card,'div','hdr',''),h=el(hdr,'h2','','Multi VWAPセットアップ');el(h,'span','h2en','63 / 252 / All-time VWAP');el(card,'div','sub','63/252は押し・再加速と深い押しの位置確認。All-timeは取得済み上場来履歴。売買ゲートやRS加点には使わない。');const wrap=el(card,'div','','');wrap.style.overflow='auto';const table=el(wrap,'table','tbl',''),thead=el(table,'thead','',''),trh=el(thead,'tr','','');['銘柄','63 VWAP','判定','252 VWAP','判定','All-time VWAP','All-time差'].forEach(x=>el(trh,'th','',x));const tbody=el(table,'tbody','',''),rows=vwap.rows.filter(x=>(x.vwap63&&(x.vwap63.break||x.vwap63.touch||x.vwap63.near))||(x.vwap252&&(x.vwap252.break||x.vwap252.touch||x.vwap252.near))).slice(0,30);
  rows.forEach(x=>{const tr=el(tbody,'tr','',''),td=el(tr,'td','', ''),b=el(td,'button','v38-vwap-ticker',x.ticker||'—');b.type='button';b.onclick=()=>openTicker(x.ticker);el(tr,'td','',price(x.vwap63&&x.vwap63.value));el(tr,'td','v38-vwap-hit',vwapSignalText(x.vwap63));el(tr,'td','',price(x.vwap252&&x.vwap252.value));el(tr,'td','v38-vwap-hit',vwapSignalText(x.vwap252));el(tr,'td','v38-vwap-life',x.vwap_life&&x.vwap_life.valid?price(x.vwap_life.value):'対象外');el(tr,'td','v38-vwap-life',x.vwap_life&&x.vwap_life.valid&&num(x.vwap_life.dist)!==null?pct(x.vwap_life.dist):'対象外');});el(card,'div','v38-vwap-note','63日＝通常の押し/再加速、252日＝深い押し・反転候補。上場来履歴未完成は対象外表示。');card.dataset.v38VwapRestore='63-252-all-time';card.dataset.v38CanonicalVisual='vwap-card';
}

async function apply(){
  if(BUSY)return;BUSY=true;
  try{installStyle();const[view,searchData,vwap,options]=await Promise.all([load('data/ui_view_model.json'),load('data/search_index.json'),load('data/vwap_restore.json'),load('data/options/index.json')]);if(searchData)renderSearch(searchData);if(view&&searchData)renderRotation(view,searchData);if(options)renderOptions(options);if(vwap)renderVwap(vwap);followTab();document.body.dataset.v38RestoredExperience='canonical-v5-ready';}finally{BUSY=false;}
}
function start(){installStyle();bindTabs();apply();[700,1500,2600,4300].forEach(t=>setTimeout(apply,t));document.addEventListener('v38:data-ready',apply);}
document.readyState==='loading'?document.addEventListener('DOMContentLoaded',start,{once:true}):start();
})();
