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
  @media(max-width:760px){
    #t-options .v38-canonical-options .v38-options-list{grid-template-columns:1fr}
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
function netGexText(v){const n=num(v);if(n===null)return'—';const a=Math.abs(n);if(a>=1e9)return`${n<0?'-':''}${(a/1e9).toFixed(1)}B`;if(a>=1e6)return`${n<0?'-':''}${(a/1e6).toFixed(1)}M`;if(a>=1e3)return`${n<0?'-':''}${(a/1e3).toFixed(1)}K`;return n.toFixed(0);}
function renderOptions(options){
  const section=document.getElementById('t-options');if(!section||!options)return;const root=document.createElement('div');root.className='v38-canonical-options';root.dataset.v38CanonicalVisual='options-v5';const msec=el(root,'div','msec',''),left=el(msec,'div','msec-l','Options Intelligence');el(left,'span','msec-en','DTE Matrix');el(msec,'div','msec-q','期間別に全銘柄を走査。Wall配置とExpected Moveを比較。');const list=el(root,'div','v38-options-list','');
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