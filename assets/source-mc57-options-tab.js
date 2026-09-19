(function(){
'use strict';

const OPTION_BUCKETS=['0-6','7-21','22-45','0-45'];
const CACHE={};

const num=v=>v===null||v===undefined||v===''?null:(Number.isFinite(Number(v))?Number(v):null);
const price=v=>num(v)===null?'—':num(v).toFixed(2);
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
function installStyle(){
  if(document.getElementById('source-mc57-options-exact-style'))return;
  const s=document.createElement('style');
  s.id='source-mc57-options-exact-style';
  s.textContent=`
  /* Exact copy of the production #t-options scoped rules. */
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
  #t-options .v38-canonical-options .v38-upward-card{grid-column:1/-1;box-shadow:inset 3px 0 0 #17685c}
  #t-options .v38-canonical-options .v38-upward-groups{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-top:8px}
  #t-options .v38-canonical-options .v38-upward-group{border:1px solid rgba(100,90,70,.16);border-radius:10px;padding:8px;min-width:0}
  #t-options .v38-canonical-options .v38-upward-head{display:flex;justify-content:space-between;gap:8px;align-items:baseline;margin-bottom:4px}
  #t-options .v38-canonical-options .v38-upward-head b{font-size:11px}
  #t-options .v38-canonical-options .v38-upward-count{font:800 11px ui-monospace,SFMono-Regular,Menlo,monospace}
  #t-options .v38-canonical-options .v38-upward-row{display:grid;grid-template-columns:24px minmax(54px,.8fr) 48px minmax(0,1.7fr);gap:6px;align-items:center;padding:4px 0;border-top:1px solid rgba(100,90,70,.12);font-size:10px}
  #t-options .v38-canonical-options .v38-upward-row:first-of-type{border-top:0}
  #t-options .v38-canonical-options .v38-upward-row button{border:0;background:transparent;padding:0;text-align:left;color:inherit;font:inherit;font-weight:850;cursor:pointer}
  #t-options .v38-canonical-options .v38-upward-score{font-weight:850;white-space:nowrap}
  #t-options .v38-canonical-options .v38-upward-geom{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#727569}
  @media(max-width:760px){
    #t-options .v38-canonical-options .v38-options-list{grid-template-columns:1fr}
    #t-options .v38-canonical-options .v38-upward-groups{grid-template-columns:1fr}
    #t-options .v38-canonical-options .v38-upward-row{grid-template-columns:22px minmax(48px,.7fr) 44px minmax(0,1.6fr);gap:5px}
    #t-port,#t-port .card,#t-port .v38-table-wrap{box-sizing:border-box;min-width:0;max-width:100%}
    #t-port .v38-table-wrap{overflow-x:auto;-webkit-overflow-scrolling:touch;overscroll-behavior-inline:contain}
    #t-port table{display:block;max-width:100%;overflow-x:auto;-webkit-overflow-scrolling:touch;overscroll-behavior-inline:contain}
  }`;
  document.head.appendChild(s);
}
function openTicker(ticker){
  const t=String(ticker||'').toUpperCase();
  if(!t)return;
  if(window.V38OpenTickerChart)window.V38OpenTickerChart(t);
  else setTimeout(()=>window.V38OpenTickerChart&&window.V38OpenTickerChart(t),120);
}
function optionRows(options,bucket){return((((options||{}).buckets||{})[bucket])||[]).slice(0,24);}
function upwardRows(options,bucket){const rows=((((options||{}).upward_rankings||{})[bucket])||[]);return Array.isArray(rows)?rows:[];}
function ratioText(v){const n=num(v);return n===null?'—':n.toFixed(2)+'×';}
function renderUpward(root,options){
  const card=el(root,'div','card rsx-card v38-upward-card','');
  card.dataset.v38Status='READY';
  card.dataset.v38CardTitle='上方向配置';
  const hdr=el(card,'div','hdr',''),h=el(hdr,'h2','','上方向配置');
  el(h,'span','h2en','Upward Positioning');
  el(card,'div','sub','実オプション配置の既存4条件で抽出。上昇予測ではなく表示専用。0–45DTEを総合として先頭表示。');
  const groups=el(card,'div','v38-upward-groups','');
  ['0-45','0-6','7-21','22-45'].forEach(bucket=>{
    const rows=upwardRows(options,bucket),group=el(groups,'div','v38-upward-group',''),head=el(group,'div','v38-upward-head','');
    el(head,'b','',bucket.replace('-','–')+' DTE');
    el(head,'span','v38-upward-count',rows.length+'銘柄');
    if(!rows.length){el(group,'div','v38-empty','該当なし');return;}
    rows.slice(0,12).forEach((x,i)=>{
      const row=el(group,'div','v38-upward-row','');
      el(row,'span','rsx-rk',x.upward_rank||i+1);
      const b=el(row,'button','',x.ticker||'—');b.type='button';b.dataset.v38Ticker=x.ticker||'';b.onclick=()=>openTicker(x.ticker);
      el(row,'span','v38-upward-score',String(x.upward_structure_score||0)+'/'+String(x.upward_structure_observed||0));
      el(row,'span','v38-upward-geom',`C/P ${ratioText(x.call_put_gex_ratio)} ・ Spot ${price(x.spot)} / Flip ${price(x.gamma_flip)} / Call ${price(x.call_wall)}`);
    });
    if(rows.length>12)el(group,'div','v38-empty',`上位12件を表示（全${rows.length}件）`);
  });
}
function netGexText(v){const n=num(v);if(n===null)return'—';const a=Math.abs(n);if(a>=1e9)return`${n<0?'-':''}${(a/1e9).toFixed(1)}B`;if(a>=1e6)return`${n<0?'-':''}${(a/1e6).toFixed(1)}M`;if(a>=1e3)return`${n<0?'-':''}${(a/1e3).toFixed(1)}K`;return n.toFixed(0);}
function renderOptions(options){
  const section=document.getElementById('t-options');if(!section||!options)return;const root=document.createElement('div');root.className='v38-canonical-options';root.dataset.v38CanonicalVisual='options-v5';const msec=el(root,'div','msec',''),left=el(msec,'div','msec-l','Options Intelligence');el(left,'span','msec-en','DTE Matrix');el(msec,'div','msec-q','期間別に全銘柄を走査。Wall配置とExpected Moveを比較。');renderUpward(root,options);const list=el(root,'div','v38-options-list','');
  OPTION_BUCKETS.forEach(bucket=>{const rows=optionRows(options,bucket),card=el(list,'div','card rsx-card',''),title=bucket.replace('-','–')+' DTE';card.dataset.v38Status='READY';card.dataset.v38OptionBucket=bucket;card.dataset.v38OptionRows=String(rows.length);card.dataset.v38CanonicalTitle=title;card.dataset.v38CardTitle=title;const hdr=el(card,'div','hdr',''),h=el(hdr,'h2','',title);el(h,'span','h2en',bucket==='0-6'?'Short Term':bucket==='7-21'?'Swing':bucket==='22-45'?'Medium Term':'All 0–45');el(card,'div','sub','ランキングは期間ごとに独立。Spot・Wall・Flip・Expected Move・Qualityを同じ行で確認。');if(!rows.length){el(card,'div','v38-empty','該当データなし');return;}
    rows.forEach((x,i)=>{const item=el(card,'div','rsx-item','');item.dataset.v38Ticker=x.ticker||'';const row=el(item,'div','rsx-row','');el(row,'span','rsx-rk',i+1);const name=el(row,'div','rsx-name',''),nameLine=el(name,'div','',''),b=el(nameLine,'button','',x.ticker||'—');b.type='button';b.dataset.v38Ticker=x.ticker||'';b.onclick=()=>openTicker(x.ticker);el(name,'small','',x.theme||x.sector||x.expiry||'Options');const score=el(row,'div','rsx-score','');el(score,'b','',netGexText(x.net_gex));el(score,'small','Net GEX');const sub=el(item,'div','rsx-sub',''),nums=el(sub,'span','rsx-nums','Spot ');el(nums,'b','',price(x.spot));nums.append(' ・ Call / Flip / Put ');el(nums,'b','',`${price(x.call_wall)} / ${price(x.gamma_flip)} / ${price(x.put_wall)}`);const ret=el(sub,'span','rsx-ret','Expected Move ');el(ret,'b','',num(x.expected_move_pct)===null?'—':`±${(100*num(x.expected_move_pct)).toFixed(1)}%`);ret.append(' ・ Quality ');el(ret,'b','',String(x.quality||'READY'));item.onclick=e=>{if(!e.target.closest('button'))openTicker(x.ticker);};});
  });section.replaceChildren(root);section.dataset.v38Status=options.status||'READY';section.dataset.v38OptionsRestoreStatus='canonical-v5-layout-ready';
}

function ensureExactTab(){
  const nav=document.querySelector('nav');
  if(!nav)return null;
  let a=nav.querySelector('a.tabx[href="#t-options"]');
  if(!a){
    a=document.createElement('a');
    a.className='tabx';
    a.href='#t-options';
    a.textContent='Options';
    a.setAttribute('onclick',"tab('t-options',this);return false;");
    const publish=nav.querySelector('a.tabx[href="#t-post1"]');
    nav.insertBefore(a,publish||null);
  }
  let section=document.getElementById('t-options');
  if(!section){
    section=document.createElement('section');
    section.id='t-options';
    const publishSection=document.getElementById('t-post1');
    if(publishSection&&publishSection.parentNode)publishSection.parentNode.insertBefore(section,publishSection);
    else (nav.parentElement||document.body).appendChild(section);
  }
  return {a,section};
}
function activateHash(){
  if(location.hash!=='#t-options')return;
  const x=ensureExactTab();
  if(!x)return;
  if(typeof window.tab==='function')window.tab('t-options',x.a);
}
async function start(){
  installStyle();
  const x=ensureExactTab();
  if(!x)return;
  const options=await load('data/options/index.json');
  if(options)renderOptions(options);
  activateHash();
}
addEventListener('hashchange',activateHash);
document.readyState==='loading'?document.addEventListener('DOMContentLoaded',start,{once:true}):start();
})();