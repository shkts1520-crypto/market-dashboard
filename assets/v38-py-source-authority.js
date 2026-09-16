(function(){
'use strict';
const SOURCE='build_dashboard(2).py';
const NON_OPTIONS=['t-market','t-alloc','t-port','t-today','t-rotation','t-movers','t-rs','t-weekly','t-post1','t-rules'];
const LAYOUTS={
 't-market':[
  {label:'① 結論と行動',en:'Verdict & Action',q:'今日・1週間・1カ月・ローテを一画面',cards:['今日のマーケット','前回からの変化'],special:['.sar','.banner']},
  {label:'② 相場の強さ',en:'Market Strength',q:'広がり・参加度・主導株',cards:['マーケットステータス推移','マーケット・パフォーマンス','ブレッドス推移（50','ブレッドス推移（200','売買代金 参加度','集積／分散','リーダーの強さ','先導株モメンタム・ラン','騰落ライン','攻守ローテーション']},
  {label:'③ 崩れの兆し',en:'Warning Signs',q:'リーダー脱落・勢い・下落余地',cards:['レジーム警戒灯','信用と金利','クレジット推移','VIX反転シーケンス','VIX期間構造','オプション想定変動幅','ディストリビューション・デイ','センチメント']},
  {label:'④ 反転の確認',en:'Reversal',q:'FTDと復帰候補（調整中のみ）',cards:['転換初動リーダーボード','フォロースルー・デイ']}
 ],
 't-alloc':[
  {label:'トレード計画・保有記録',en:'Plan & Holdings',q:'買う前に株数・撤退・部分利確を決め、そのまま保有に記録',cards:['スイング・プランナー']},
  {label:'① 配分計算',en:'Position Sizing',q:'地合い → 今日の株数に落とす',cards:['資金配分・株数計算']},
  {label:'② リバランス点検',en:'Rebalance Check',q:'隔週月曜のチェックリスト',cards:['隔週リバランス点検'],special:['.liqstick']},
  {label:'資産推移・口座',en:'Equity & Account',q:'資産曲線・要因分解・非常口ブレーキ',cards:[]},
  {label:'記録',en:'Equity Log',q:'今日の総資産を残す（週1でOK）',cards:['エクイティ記録','エクイティカーブ','非常口']}
 ],
 't-port':[
  {label:null,cards:['レジーム警戒灯','防御チェックリスト'],special:['.liqstick']},
  {label:'① 新規参入',en:'New Entrants',q:'36位圏外から30位以内へ飛び込んだ銘柄（今日/今週/今月）',cards:['新規参入']},
  {label:'② 現在の構成',en:'Current Holdings',q:'個別株スリーブ（N=12・等ウェイト）',cards:['個別株スリーブ'],special:['.rspbar','.rsper']},
  {label:'② 控え',en:'Bench',q:'次の入替で上がってくる候補',cards:['RSリーダー控え']}
 ],
 't-today':[
  {label:null,cards:['銘柄検索'],special:['.liqstick']},
  {label:'① 発火前（構造が整い、静かなもの）',en:'Pre-Breakout',q:'出来高が枯れ21EMA/VWAPに張り付いた未発火銘柄。発火を待たずに構造で拾う',cards:['発火前']},
  {label:'② 支えへの接触（オプション）',en:'Put Wall Touch',q:'建玉が積み上がった下値の支えに、強い銘柄が接触しているもの',cards:['支えへの接触']},
  {label:'③ コンフルエンス（事実表示）',en:'Confluence Facts',q:'発火・確認・位置/警戒を分類した一覧',cards:['エントリー候補ボード']},
  {label:'④ 発火トリガー',en:'Entry Triggers',q:'PP・ブレイク・出来高伴う反発',cards:['本日のピックアップ','テクニカル・パターン別']},
  {label:'⑤ セットアップ評価',en:'Setup Quality',q:'VCP・21EMA・63/252/上場来VWAP',cards:['圧縮コイル','21EMAタッチ','Multi VWAPセットアップ']},
  {label:'⑥ 底打ち（構造ピボット）',en:'Structure Pivot',q:'安値切り上げ＋出来高減で下げ止まり。RS63主軸・構造のみ',cards:['底打ち']},
  {label:'⑦ W30ブレイク（30週線）',en:'W30 Breakout',q:'金曜クローズ確定→翌週寄り。◎本格が本線・△ギリ抜けは警戒',cards:['ブレイク一覧','運用ルール','定義・グレード・格付け','状態の凡例','コホート分析','入り方','手仕舞いの目安']},
  {label:'⑧ リーダー母集団',en:'Leaders',q:'RS≥85・200MA上を状態別に',cards:['リーダー監視']}
 ],
 't-rotation':[
  {label:'① どこに資金が向かっているか',en:'Where the Money Is',q:'重複のないGICS11＋スタイルで測る資金フロー',cards:['資金フロー','セクター温度マップ']},
  {label:'② その資金は広いか、数銘柄か',en:'Index vs Breadth',q:'指数（時価総額加重）と中身（等加重）の乖離',cards:['指数と中身の乖離']},
  {label:'③ 自ユニバースで主導しているのは誰か',en:'Leading Groups',q:'セクター→業種→細目テーマ→銘柄。タップで降りる',cards:['主導セクター・業種']},
  {label:'④ その中で買える銘柄はどれか',en:'Leaders in Strong Groups',q:'強いグループ×個別も強い＝順張りの一等地',cards:['強い業種の主導株']},
  {label:'⑤ 一覧で確認する',en:'Full Rankings',q:'見出しタップで並べ替え・行タップで構成銘柄',cards:['セクターETF強弱','サブテーマ別RS']}
 ],
 't-movers':[{label:null,cards:['値動き 上位・下位']}],
 't-rs':[{label:null,cards:['RSマルチタイムフレーム比較','Top10 IN / OUT履歴','RS189 継続性','三窓一致リーダー','RS63 Top10','RS126 Top10','RS189 Top10']}],
 't-weekly':[
  {label:null,cards:['今週の結論']},
  {label:'① 来週の準備',en:'Week Ahead',q:'週末に確認する経済指標と構造マクロ（低頻度で効く）',cards:['来週の経済指標','構造マクロ','金利レジーム','マクロ圧力','今週の変化']},
  {label:'② 今週の地合い',en:'Market Week',q:'地合いの帯で1週間を振り返る（詳細な推移はDaily）',cards:['地合いの帯','週次騰落ボード']},
  {label:'③ 環境の質',en:'Environment Quality',q:'広がり・データ品質・レバ環境',cards:['広域ブレッドス','データ品質','レバレッジ・コンディション']},
  {label:'④ 口座の答え合わせ',en:'Account Review',q:'カーブ×21EMA（残高・非常口・資産曲線はPositions）',cards:['自分 vs QQQ円建て']}
 ],
 't-rules':[{label:null,cards:['Core 12 システムルール']}]
};
const norm=v=>String(v||'').replace(/\s+/g,' ').trim();
function titleOf(card){if(!card)return'';if(card.dataset.v38CardTitle)return norm(card.dataset.v38CardTitle);const h=card.querySelector('h2,.hdr h2,.chd h2');return h?norm(h.textContent):'';}
const matches=(title,needle)=>norm(title).includes(norm(needle));
function msec(g){if(!g.label)return null;const w=document.createElement('div');w.className='msec';w.dataset.v38PySource='1';const line=document.createElement('div'),l=document.createElement('span');l.className='msec-l';l.textContent=g.label;line.appendChild(l);if(g.en){const e=document.createElement('span');e.className='msec-en';e.textContent=g.en;line.appendChild(e);}w.appendChild(line);if(g.q){const q=document.createElement('div');q.className='msec-q';q.textContent=g.q;w.appendChild(q);}return w;}
function findSpecial(section,selector,used){return Array.from(section.querySelectorAll(selector)).find(n=>!used.has(n)&&!n.closest('#t-options'))||null;}
function sourceOrder(id){const section=document.getElementById(id),groups=LAYOUTS[id];if(!section||!groups)return;const cards=Array.from(section.querySelectorAll('.card')),used=new Set(),frag=document.createDocumentFragment();section.querySelectorAll(':scope > .msec[data-v38-py-source="1"]').forEach(n=>n.remove());groups.forEach(g=>{const h=msec(g);if(h)frag.appendChild(h);(g.special||[]).forEach(sel=>{const n=findSpecial(section,sel,used);if(n){used.add(n);frag.appendChild(n);}});(g.cards||[]).forEach(needle=>{const found=cards.find(c=>!used.has(c)&&matches(titleOf(c),needle));if(found){used.add(found);found.hidden=false;found.classList.remove('v38-py-unbound');frag.appendChild(found);}});});cards.forEach(c=>{if(!used.has(c)){c.hidden=true;c.classList.add('v38-py-unbound');}});section.appendChild(frag);section.dataset.v38UiSource=SOURCE;}
function sourcePublish(){const s=document.getElementById('t-post1');if(!s)return;const wraps=Array.from(s.querySelectorAll(':scope > .postwrap'));if(!wraps.length){s.dataset.v38UiSource=SOURCE;return;}s.querySelectorAll(':scope > .msec[data-v38-py-source="1"]').forEach(n=>n.remove());const labs=[['マーケット概略','Market Overview','SNS共有用カード'],['セクター・ローテーション','Sector Rotation','SNS共有用カード']];wraps.forEach((w,i)=>s.insertBefore(msec({label:labs[i]?.[0]||'共有カード',en:labs[i]?.[1]||'',q:labs[i]?.[2]||''}),w));s.dataset.v38UiSource=SOURCE;}
function sourceRsControl(){document.querySelectorAll('#t-port button,#t-port .rspbar,#t-rs button').forEach(n=>{if(norm(n.textContent).startsWith('RS期間:'))n.classList.add('rsper');});}
function readKvRows(card){return Array.from(card.querySelectorAll('.v38-canonical-row')).map(r=>({label:norm((r.querySelector('.v38-canonical-left')||r).textContent),value:norm(r.querySelector('.v38-canonical-value,b:last-child')?.textContent)}));}
function regimeClass(value,kind){const n=parseFloat(String(value||'').replace('%',''));if(!Number.isFinite(n))return'reg-na';const t=kind==='f1'?[20,30]:kind==='f2'?[30,40]:[45,60];return n>=t[1]?'reg-bad':n>=t[0]?'reg-warn':'reg-ok';}
function regCell(label,value,role,kind,note){const c=document.createElement('div');c.className=`reg-cell ${regimeClass(value,kind)}`;const k=document.createElement('div'),r=document.createElement('div'),v=document.createElement('div');k.className='reg-k';k.textContent=label;r.className='reg-role';r.textContent=role;v.className='reg-v';v.textContent=value||'—';c.append(k,r,v);if(note){const n=document.createElement('div');n.className='reg-l';n.textContent=note;c.appendChild(n);}return c;}
const pct=v=>Number.isFinite(Number(v))?`${(Number(v)*100).toFixed(1)}%`:'—';
async function loadOverlay(){try{const r=await fetch('data/py_source_display.json',{cache:'no-store'});return r.ok?await r.json():null;}catch(_){return null;}}
function sourceRegime(o){['t-market','t-port'].forEach(id=>{const s=document.getElementById(id);if(!s)return;const card=Array.from(s.querySelectorAll('.card')).find(n=>matches(titleOf(n),'レジーム警戒灯'));if(!card)return;const rows=readKvRows(card),pick=n=>rows.find(r=>r.label.includes(n))?.value||'—',f1=o?.f1_display?.value!=null?pct(o.f1_display.value):pick('F1'),f2=o?.f2?.value!=null?pct(o.f2.value):pick('F2'),f3=o?.f3?.value!=null?pct(o.f3.value):pick('F3');card.classList.add('reg-card');card.replaceChildren();const hd=document.createElement('div'),h=document.createElement('h2');hd.className='hdr reg-hd';h.innerHTML='レジーム警戒灯 <span class="h2en">Regime Early-Warning</span>';hd.appendChild(h);card.appendChild(hd);const grid=document.createElement('div');grid.className='reg-grid';grid.append(regCell('F1 リーダー脱落率',f1,'最速の警報｜20営業日前Top24→現在36位外','f1',o?.f1_display?.display_only?'表示専用再構成・売買ゲート非連動':''),regCell('F2 勢い細り率',f2,'上位24のうちRS63<85の割合','f2',''),regCell('F3 キュー崩れ',f3,'反発待ち・高値からの崩れの深さ','f3',o?.f3?.display_only?'表示専用補完・売買ゲート非連動':''));card.appendChild(grid);const note=document.createElement('div');note.className='note';note.textContent='3灯は足し算しない。F1/F2はタイミング、F3は下落の深さを見る補助計器。NQSARと売買ルール本体は変更しない。';card.appendChild(note);card.dataset.v38UiSource=SOURCE;});}
function sourceFtd(view){const s=document.getElementById('t-market');if(!s)return;const card=Array.from(s.querySelectorAll('.card')).find(n=>matches(titleOf(n),'フォロースルー・デイ'));if(!card)return;const p=view?.daily?.display_observations?.ftd_proxy||{},idx=p.indexes||p.indices||{},safe=v=>{const t=norm(v);return !t||/^[A-Z0-9_:-]+$/.test(t)||t.includes('SOURCE_DEFINED')?'観測中':t;},items=[];Object.entries(idx).forEach(([n,r])=>items.push([n,safe(r?.state||r?.status||r?.display)]));if(!items.length){const f=safe(p.state||p.display);items.push(['NASDAQ100',f],['S&P500',f]);}card.replaceChildren();const h=document.createElement('h2'),sub=document.createElement('div');h.innerHTML='フォロースルー・デイ <span class="h2en">FTD (proxy)</span>';sub.className='sub';sub.innerHTML='調整局面からの反転確認。<b>Day4以降の上昇＋出来高増</b>を確認する表示専用proxy。';card.append(h,sub);items.forEach(([n,v])=>{const row=document.createElement('div'),x=document.createElement('span'),w=document.createElement('span');row.className='ftd-row';x.className='ftd-x';x.textContent=n;w.className='warnt';w.textContent=v;row.append(x,w);card.appendChild(row);});card.dataset.v38UiSource=SOURCE;}
function linePath(values,W,H,P,min,max){const span=max-min||1;return values.map((r,i)=>{const x=P+i*(W-2*P)/Math.max(1,values.length-1),y=P+(1-(r.value-min)/span)*(H-2*P);return`${i?'L':'M'}${x.toFixed(1)},${y.toFixed(1)}`;}).join(' ');}
function sourceVix(o){const p=o?.vix_fear_cycle;if(!p||!Array.isArray(p.rows)||p.rows.length<2)return;const s=document.getElementById('t-market');if(!s)return;const card=Array.from(s.querySelectorAll('.card')).find(n=>matches(titleOf(n),'VIX反転シーケンス'));if(!card)return;card.classList.add('vixcy');card.replaceChildren();const c=p.current||{},hd=document.createElement('div'),h=document.createElement('h2'),now=document.createElement('div'),b=document.createElement('b'),d=document.createElement('span');hd.className='chd';h.innerHTML='VIX反転シーケンス <span class="h2en">VIX FEAR CYCLE</span>';now.className='chd-now mut';b.textContent=p.state||'NORMAL';d.textContent=p.session_date||window.V38UiViewModel?.session_date||'';now.append(b,d);hd.append(h,now);card.appendChild(hd);const sub=document.createElement('div');sub.className='sub';sub.textContent='VIX・LWMA5・LWMA10と長期分布の閾値を同じカードで確認。元pyのFear Cycle表示。';card.appendChild(sub);const vals=document.createElement('div');vals.className='vixvals';[['VIX',c.vix],['High',c.high],['LWMA5',c.lwma5],['LWMA10',c.lwma10],['+1σ',c.plus1_sigma],['+2σ',c.plus2_sigma]].forEach(([lab,val])=>{const box=document.createElement('div'),sp=document.createElement('span'),st=document.createElement('b');sp.textContent=lab;st.textContent=Number.isFinite(Number(val))?Number(val).toFixed(2):'—';box.append(sp,st);vals.appendChild(box);});card.appendChild(vals);const leg=document.createElement('div');leg.className='vixleg';[['vix-lg-close','VIX'],['vix-lg-w5','LWMA5'],['vix-lg-w10','LWMA10']].forEach(([cls,lab])=>{const sp=document.createElement('span'),i=document.createElement('i');i.className=cls;sp.append(i,document.createTextNode(lab));leg.appendChild(sp);});card.appendChild(leg);const tabs=document.createElement('div'),chart=document.createElement('div');tabs.className='vixwtabs';chart.className='chart vixchart';card.append(tabs,chart);function draw(count,btn){tabs.querySelectorAll('button').forEach(x=>x.classList.remove('on'));btn.classList.add('on');chart.replaceChildren();const rows=p.rows.slice(-Math.min(count,p.rows.length)),series=[['vix','#1c1b19'],['lwma5','#1f4b8f'],['lwma10','#9f1e62']],all=[];series.forEach(([k])=>rows.forEach(r=>{const n=Number(r[k]);if(Number.isFinite(n))all.push(n);}));if(!all.length)return;const lo0=Math.min(...all),hi0=Math.max(...all),pad=(hi0-lo0||1)*.1,lo=Math.max(0,lo0-pad),hi=hi0+pad,W=680,H=168,P=8,svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox',`0 0 ${W} ${H}`);svg.setAttribute('preserveAspectRatio','none');for(let i=0;i<4;i++){const val=lo+(hi-lo)*i/3,y=H-P-(H-2*P)*i/3,ln=document.createElementNS(svg.namespaceURI,'line'),tx=document.createElementNS(svg.namespaceURI,'text');ln.setAttribute('x1',P);ln.setAttribute('x2',W-P);ln.setAttribute('y1',y);ln.setAttribute('y2',y);ln.setAttribute('stroke','#e3e1db');tx.setAttribute('x',W-P);tx.setAttribute('y',Math.max(12,y-3));tx.setAttribute('text-anchor','end');tx.setAttribute('fill','#9f9982');tx.setAttribute('font-size','17');tx.textContent=val.toFixed(0);svg.append(ln,tx);}series.forEach(([k,col])=>{const pts=rows.map(r=>({value:Number(r[k])})).filter(r=>Number.isFinite(r.value));if(pts.length<2)return;const path=document.createElementNS(svg.namespaceURI,'path');path.setAttribute('d',linePath(pts,W,H,P,lo,hi));path.setAttribute('fill','none');path.setAttribute('stroke',col);path.setAttribute('stroke-width',k==='vix'?'2.4':'2.2');path.setAttribute('vector-effect','non-scaling-stroke');svg.appendChild(path);});chart.appendChild(svg);} [['3M',63],['1Y',252],['3Y',756],['10Y',2520]].forEach(([lab,n],i)=>{const btn=document.createElement('button');btn.type='button';btn.className='vixwbt';btn.textContent=lab;btn.addEventListener('click',()=>draw(n,btn));tabs.appendChild(btn);if(i===0)requestAnimationFrame(()=>draw(n,btn));});card.dataset.v38UiSource=SOURCE;}
function hideMachineText(){document.querySelectorAll('section:not(#t-options)').forEach(s=>{const w=document.createTreeWalker(s,NodeFilter.SHOW_TEXT);let n;while((n=w.nextNode())){const v=n.nodeValue||'';if(/SOURCE_DEFINED_|SOURCE_UNAVAILABLE|DATA_REQUIRED/.test(v))n.nodeValue=v.replace(/SOURCE_DEFINED_[A-Z0-9_]+/g,'観測中').replace(/SOURCE_UNAVAILABLE|DATA_REQUIRED/g,'未取得');}});}
function applyStructure(){NON_OPTIONS.filter(id=>id!=='t-post1').forEach(sourceOrder);sourcePublish();sourceRsControl();document.body.dataset.v38UiAuthority='build_dashboard_2_py';}
async function afterView(){applyStructure();const view=window.V38UiViewModel||{};sourceFtd(view);const o=await loadOverlay();sourceRegime(o);sourceVix(o);hideMachineText();applyStructure();}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',applyStructure,{once:true});else applyStructure();
document.addEventListener('v38:view-ready',()=>{void afterView();});
window.addEventListener('load',()=>{hideMachineText();sourceRsControl();},{once:true});
})();