(function(){
'use strict';
const SOURCE='build_dashboard(3).py';
const TABS=['t-market','t-alloc','t-port','t-today','t-rotation','t-movers','t-rs','t-weekly','t-post1','t-rules'];
const EXPECTED={
 't-market':['今日のマーケット','前回からの変化','マーケットステータス推移','マーケット・パフォーマンス','ブレッドス推移（50','ブレッドス推移（200','売買代金 参加度','集積／分散','リーダーの強さ','先導株モメンタム・ラン','騰落ライン','攻守ローテーション','レジーム警戒灯','信用と金利','クレジット推移','VIX反転シーケンス','VIX期間構造','オプション想定変動幅','ディストリビューション・デイ','センチメント','転換初動リーダーボード','フォロースルー・デイ'],
 't-alloc':['スイング・プランナー','資金配分・株数計算','隔週リバランス点検','エクイティ記録','エクイティカーブ','非常口'],
 't-port':['レジーム警戒灯','防御チェックリスト','新規参入','個別株スリーブ','RSリーダー控え'],
 't-today':['銘柄検索','発火前','支えへの接触','エントリー候補ボード','本日のピックアップ','テクニカル・パターン別','圧縮コイル','21EMAタッチ','Multi VWAPセットアップ','底打ち','ブレイク一覧','運用ルール','定義・グレード・格付け','状態の凡例','コホート分析','入り方','手仕舞いの目安','リーダー監視'],
 't-rotation':['資金フロー','セクター温度マップ','指数と中身の乖離','主導セクター・業種','強い業種の主導株','セクターETF強弱','サブテーマ別RS'],
 't-movers':['値動き 上位・下位'],
 't-rs':['RSマルチタイムフレーム比較','Top10 IN / OUT履歴','RS189 継続性','三窓一致リーダー','RS63 Top10','RS126 Top10','RS189 Top10'],
 't-weekly':['今週の結論','来週の経済指標','構造マクロ','金利レジーム','マクロ圧力','今週の変化','地合いの帯','週次騰落ボード','広域ブレッドス','データ品質','レバレッジ・コンディション','自分 vs QQQ円建て'],
 't-post1':[], 't-rules':['Core 12 システムルール']
};
const norm=v=>String(v||'').replace(/\s+/g,' ').trim();
const title=c=>{if(!c)return'';if(c.dataset.v38CardTitle)return norm(c.dataset.v38CardTitle);const h=c.querySelector('h2,.hdr h2,.chd h2');return h?norm(h.textContent):'';};
const cards=id=>{const s=document.getElementById(id);return s?Array.from(s.querySelectorAll('.card')):[];};
const all=()=>TABS.flatMap(cards);
const hit=(c,n)=>title(c).includes(norm(n));
const show=c=>{c.hidden=false;c.classList.remove('v38-py-unbound');c.removeAttribute('aria-hidden');c.dataset.v38UiSource=SOURCE;};
const hide=c=>{c.hidden=true;c.classList.add('v38-py-unbound');c.setAttribute('aria-hidden','true');};
function owners(){const m=new Map();Object.entries(EXPECTED).forEach(([id,ns])=>ns.forEach(n=>{if(!m.has(n))m.set(n,[]);m.get(n).push(id);}));return m;}
function score(c,id){return(c.closest('section')?.id===id?100:0)+(c.dataset.v38TruthSource||c.dataset.v38UiSource?20:0)+(c.dataset.v38Status==='READY'?10:0)+(!c.hidden&&!c.classList.contains('v38-py-unbound')?5:0);}
function repairCards(){owners().forEach((ids,n)=>{if(ids.length!==1)return;const id=ids[0],s=document.getElementById(id);if(!s)return;const xs=all().filter(c=>hit(c,n)).sort((a,b)=>score(b,id)-score(a,id));if(!xs.length)return;const keep=xs[0];if(keep.closest('section')?.id!==id)s.appendChild(keep);show(keep);xs.slice(1).forEach(hide);});Object.entries(EXPECTED).forEach(([id,ns])=>ns.forEach(n=>{const xs=cards(id).filter(c=>hit(c,n));if(xs.length>1){show(xs[0]);xs.slice(1).forEach(hide);}}));}
function isRrg(c){const t=title(c);return /RRG/i.test(t)||t.includes('セクター・ローテーション（テーマETF）')||!!c.querySelector('.rrgtog,.rrg-per,.rrgseed,.rrgq');}
function repairRrg(){const s=document.getElementById('t-rotation');if(!s)return;const xs=all().filter(isRrg).sort((a,b)=>score(b,'t-rotation')-score(a,'t-rotation'));if(!xs.length)return;const keep=xs[0];show(keep);const h=s.querySelector(':scope > .msec[data-v38-py-source="1"]');if(h)h.after(keep);else if(keep.closest('section')?.id!=='t-rotation')s.prepend(keep);xs.slice(1).forEach(hide);keep.dataset.v38BuildDashboard3Role='rotation-rrg';}
function metricMap(v){const m={};((((v||{}).daily||{}).metrics)||[]).forEach(r=>{if(r&&r.key)m[r.key]=r;});return m;}
function disp(m,k){const r=m[k];return r&&r.status==='READY'?String(r.display??'—'):'—';}
function nval(m,k){const n=Number(m[k]?.value);return Number.isFinite(n)?n:null;}
function wp(v){if(!Number.isFinite(v))return 0;const p=Math.abs(v)<=1?v*100:v;return Math.max(0,Math.min(100,p));}
function mcDelta(v){const d=(v||{}).daily||{},a=((((d.mc57_detail||{}).series||{}).mc57)||d.mc57_history||[]);if(!Array.isArray(a)||a.length<2)return null;const f=x=>{const n=Number(x&&(x.value!==undefined?x.value:x.mc57));return Number.isFinite(n)?n:null;},x=f(a.at(-1)),y=f(a.at(-2));return x===null||y===null?null:x-y;}
function row(k,v,w,note){const d=document.createElement('div');d.className='mrow';const a=document.createElement('span'),b=document.createElement('span'),bar=document.createElement('span'),i=document.createElement('i'),p=document.createElement('span');a.className='mk2';b.className='mraw';bar.className='mbar';p.className='mpts';a.textContent=k;b.textContent=v||'—';i.style.width=`${w||0}%`;bar.appendChild(i);p.textContent=note||'';d.append(a,b,bar,p);return d;}
function restoreMc57(v){const s=document.getElementById('t-market'),banner=s?.querySelector(':scope > .banner')||s?.querySelector('.banner');if(!banner)return;document.querySelectorAll('#mri-bd').forEach((x,i)=>{if(i)x.remove();});let box=document.getElementById('mri-bd');if(box&&!s.contains(box)){box.remove();box=null;}if(!box){box=document.createElement('div');box.id='mri-bd';box.className='mri-bd';}box.replaceChildren();box.hidden=false;box.classList.remove('v38-py-unbound');box.style.display='block';box.dataset.v38UiSource=SOURCE;const m=metricMap(v),h=document.createElement('div'),g=document.createElement('div');h.className='mbd-h';h.textContent='主要マーケット観測';g.className='mgrp';g.textContent='現在';box.append(h,g);const delta=mcDelta(v),mc=nval(m,'mc57'),b50=nval(m,'breadth50'),b200=nval(m,'breadth200');box.append(row('MC57',disp(m,'mc57'),wp(mc),delta===null?'前日比 —':`${delta>=0?'+':''}${delta.toFixed(1)} / 前日`),row('50MA Breadth',disp(m,'breadth50'),wp(b50),disp(m,'market_mode')),row('200MA Breadth',disp(m,'breadth200'),wp(b200),'長期内部'),row('NQSAR',disp(m,'nqsar'),0,'現行状態'));const fg=document.createElement('div');fg.className='mgrp';fg.textContent='F1 / F2 / F3';box.appendChild(fg);const fs=document.createElement('div');fs.className='bflags';['f1','f2','f3'].forEach(k=>{const z=document.createElement('span');z.className='bfl';z.textContent=`${k.toUpperCase()} ${disp(m,k)}`;fs.appendChild(z);});box.appendChild(fs);banner.appendChild(box);}
function audit(){const r={source:SOURCE,options_touched:false,tabs:{},missing:[],duplicates:[],rrg:[]};Object.entries(EXPECTED).forEach(([id,ns])=>{const cs=cards(id),checks=[];ns.forEach(n=>{const xs=cs.filter(c=>hit(c,n)&&!c.hidden&&!c.classList.contains('v38-py-unbound'));checks.push({needle:n,count:xs.length});if(!xs.length)r.missing.push(`${id}:${n}`);if(xs.length>1)r.duplicates.push(`${id}:${n}:${xs.length}`);});r.tabs[id]={visible:cs.filter(c=>!c.hidden&&!c.classList.contains('v38-py-unbound')).map(title),checks};});const rr=all().filter(c=>isRrg(c)&&!c.hidden&&!c.classList.contains('v38-py-unbound'));r.rrg=rr.map(c=>`${c.closest('section')?.id}:${title(c)}`);if(rr.length!==1||rr[0]?.closest('section')?.id!=='t-rotation')r.duplicates.push(`RRG:${rr.length}`);if(document.querySelectorAll('#t-market #mri-bd').length!==1)r.missing.push('t-market:MC57主要観測表');const p=document.getElementById('t-post1'),pc=p?p.querySelectorAll(':scope > .postwrap').length:0;r.tabs['t-post1'].postwraps=pc;if(pc!==2)r.missing.push(`t-post1:postwrap:${pc}`);r.ok=!r.missing.length&&!r.duplicates.length;window.V38BuildDashboard3Audit=r;document.documentElement.dataset.v38BuildDashboard3Audit=r.ok?'ready':'error';return r;}
async function view(){try{const x=await fetch('data/ui_view_model.json',{cache:'no-store'});return x.ok?await x.json():null;}catch(_){return null;}}
function wait(){return new Promise(res=>{const st=performance.now();function q(){const x=document.documentElement.dataset.v38CanonicalBinder;if(x==='ready'||x==='error'||performance.now()-st>12000)return res();requestAnimationFrame(q);}q();});}
async function run(){await wait();const v=await view();repairCards();repairRrg();if(v)restoreMc57(v);requestAnimationFrame(()=>requestAnimationFrame(audit));}
window.V38BuildDashboard3Fidelity={source:SOURCE,run,audit};if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',run,{once:true});else run();
})();
