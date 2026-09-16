(function () {
  'use strict';

  const SOURCE = 'build_dashboard(2).py';
  const NON_OPTIONS = ['t-market','t-alloc','t-port','t-today','t-rotation','t-movers','t-rs','t-weekly','t-post1','t-rules'];

  const LAYOUTS = {
    't-market': [
      {label:'① 結論と行動', en:'Verdict & Action', q:'今日・1週間・1カ月・ローテを一画面', cards:['今日のマーケット','前回からの変化'], special:['.sar','.banner']},
      {label:'② 相場の強さ', en:'Market Strength', q:'広がり・参加度・主導株', cards:['マーケットステータス推移','マーケット・パフォーマンス','ブレッドス推移','売買代金 参加度','集積／分散','リーダーの強さ','先導株モメンタム・ラン','騰落ライン','攻守ローテーション']},
      {label:'③ 崩れの兆し', en:'Warning Signs', q:'リーダー脱落・勢い・下落余地', cards:['レジーム警戒灯','信用と金利','クレジット推移','VIX反転シーケンス','VIX期間構造','オプション想定変動幅','ディストリビューション・デイ','センチメント']},
      {label:'④ 反転の確認', en:'Reversal', q:'FTDと復帰候補（調整中のみ）', cards:['転換初動リーダーボード','フォロースルー・デイ']}
    ],
    't-alloc': [
      {label:'トレード計画・保有記録', en:'Plan & Holdings', q:'買う前に株数・撤退・部分利確を決め、そのまま保有に記録', cards:['スイング・プランナー']},
      {label:'① 配分計算', en:'Position Sizing', q:'地合い → 今日の株数に落とす', cards:['資金配分・株数計算']},
      {label:'② リバランス点検', en:'Rebalance Check', q:'隔週月曜のチェックリスト', cards:['隔週リバランス点検'], special:['.liqstick']},
      {label:'資産推移・口座', en:'Equity & Account', q:'資産曲線・要因分解・非常口ブレーキ', cards:[]},
      {label:'記録', en:'Equity Log', q:'今日の総資産を残す（週1でOK）', cards:['エクイティ記録','エクイティカーブ','非常口']}
    ],
    't-port': [
      {label:null, cards:['レジーム警戒灯','防御チェックリスト'], special:['.liqstick']},
      {label:'① 新規参入', en:'New Entrants', q:'36位圏外から30位以内へ飛び込んだ銘柄（今日/今週/今月）', cards:['新規参入']},
      {label:'② 現在の構成', en:'Current Holdings', q:'個別株スリーブ（N=12・等ウェイト）', cards:['個別株スリーブ'], special:['.rspbar','.rsper']},
      {label:'② 控え', en:'Bench', q:'次の入替で上がってくる候補', cards:['RSリーダー控え']}
    ],
    't-today': [
      {label:null, cards:['銘柄検索'], special:['.liqstick']},
      {label:'① 発火前（構造が整い、静かなもの）', en:'Pre-Breakout', q:'出来高が枯れ21EMA/VWAPに張り付いた未発火銘柄。発火を待たずに構造で拾う', cards:['発火前']},
      {label:'② 支えへの接触（オプション）', en:'Put Wall Touch', q:'建玉が積み上がった下値の支えに、強い銘柄が接触しているもの', cards:['支えへの接触']},
      {label:'③ コンフルエンス（事実表示）', en:'Confluence Facts', q:'発火・確認・位置/警戒を分類した一覧', cards:['エントリー候補ボード']},
      {label:'④ 発火トリガー', en:'Entry Triggers', q:'PP・ブレイク・出来高伴う反発', cards:['本日のピックアップ','テクニカル・パターン別']},
      {label:'⑤ セットアップ評価', en:'Setup Quality', q:'VCP・21EMA・63/252/上場来VWAP', cards:['圧縮コイル','21EMAタッチ','Multi VWAPセットアップ']},
      {label:'⑥ 底打ち（構造ピボット）', en:'Structure Pivot', q:'安値切り上げ＋出来高減で下げ止まり。RS63主軸・構造のみ', cards:['底打ち']},
      {label:'⑦ W30ブレイク（30週線）', en:'W30 Breakout', q:'金曜クローズ確定→翌週寄り。◎本格が本線・△ギリ抜けは警戒', cards:['ブレイク一覧','運用ルール','定義・グレード・格付け','状態の凡例','コホート分析','入り方','手仕舞いの目安']},
      {label:'⑧ リーダー母集団', en:'Leaders', q:'RS≥85・200MA上を状態別に', cards:['リーダー監視']}
    ],
    't-rotation': [
      {label:'① どこに資金が向かっているか', en:'Where the Money Is', q:'重複のないGICS11＋スタイルで測る資金フロー', cards:['資金フロー','セクター温度マップ']},
      {label:'② その資金は広いか、数銘柄か', en:'Index vs Breadth', q:'指数（時価総額加重）と中身（等加重）の乖離', cards:['指数と中身の乖離']},
      {label:'③ 自ユニバースで主導しているのは誰か', en:'Leading Groups', q:'セクター→業種→細目テーマ→銘柄。タップで降りる', cards:['主導セクター・業種']},
      {label:'④ その中で買える銘柄はどれか', en:'Leaders in Strong Groups', q:'強いグループ×個別も強い＝順張りの一等地', cards:['強い業種の主導株']},
      {label:'⑤ 一覧で確認する', en:'Full Rankings', q:'見出しタップで並べ替え・行タップで構成銘柄', cards:['セクターETF強弱','サブテーマ別RS']}
    ],
    't-movers': [{label:null, cards:['値動き 上位・下位']}],
    't-rs': [{label:null, cards:['RSマルチタイムフレーム比較','Top10 IN / OUT履歴','RS189 継続性','三窓一致リーダー','RS63 Top10','RS126 Top10','RS189 Top10']}],
    't-weekly': [
      {label:null, cards:['今週の結論']},
      {label:'① 来週の準備', en:'Week Ahead', q:'週末に確認する経済指標と構造マクロ（低頻度で効く）', cards:['来週の経済指標','構造マクロ','金利レジーム','マクロ圧力','今週の変化']},
      {label:'② 今週の地合い', en:'Market Week', q:'地合いの帯で1週間を振り返る（詳細な推移はDaily）', cards:['地合いの帯','週次騰落ボード']},
      {label:'③ 環境の質', en:'Environment Quality', q:'広がり・データ品質・レバ環境', cards:['広域ブレッドス','データ品質','レバレッジ・コンディション']},
      {label:'④ 口座の答え合わせ', en:'Account Review', q:'カーブ×21EMA（残高・非常口・資産曲線はPositions）', cards:['自分 vs QQQ円建て']}
    ],
    't-rules': [{label:null, cards:['Core 12 システムルール']}]
  };

  function norm(value){return String(value||'').replace(/\s+/g,' ').trim();}
  function titleOf(card){
    if(!card)return '';
    if(card.dataset.v38CardTitle)return norm(card.dataset.v38CardTitle);
    const h=card.querySelector('h2,.hdr h2,.chd h2'); return h?norm(h.textContent):'';
  }
  function matches(title,needle){return norm(title).includes(norm(needle));}
  function msec(group){
    if(!group.label)return null;
    const wrap=document.createElement('div'); wrap.className='msec'; wrap.dataset.v38PySource='1';
    const line=document.createElement('div');
    const l=document.createElement('span');l.className='msec-l';l.textContent=group.label;line.appendChild(l);
    if(group.en){const e=document.createElement('span');e.className='msec-en';e.textContent=group.en;line.appendChild(e);}
    wrap.appendChild(line);
    if(group.q){const q=document.createElement('div');q.className='msec-q';q.textContent=group.q;wrap.appendChild(q);}
    return wrap;
  }
  function findSpecial(section,selector,used){
    const nodes=Array.from(section.querySelectorAll(selector));
    return nodes.find((node)=>!used.has(node)&&!node.closest('#t-options'))||null;
  }
  function sourceOrder(sectionId){
    const section=document.getElementById(sectionId), groups=LAYOUTS[sectionId];
    if(!section||!groups)return;
    const cards=Array.from(section.querySelectorAll('.card'));
    const used=new Set(); const frag=document.createDocumentFragment();
    section.querySelectorAll(':scope > .msec[data-v38-py-source="1"]').forEach((node)=>node.remove());
    groups.forEach((group)=>{
      const head=msec(group); if(head)frag.appendChild(head);
      (group.special||[]).forEach((selector)=>{
        const node=findSpecial(section,selector,used); if(node){used.add(node);frag.appendChild(node);}
      });
      (group.cards||[]).forEach((needle)=>{
        const found=cards.find((card)=>!used.has(card)&&matches(titleOf(card),needle));
        if(found){used.add(found);found.hidden=false;found.classList.remove('v38-py-unbound');frag.appendChild(found);}
      });
    });
    cards.forEach((card)=>{if(!used.has(card)){card.hidden=true;card.classList.add('v38-py-unbound');}});
    section.appendChild(frag);
    section.dataset.v38UiSource=SOURCE;
  }

  function sourcePublish(){
    const section=document.getElementById('t-post1'); if(!section)return;
    const wraps=Array.from(section.querySelectorAll(':scope > .postwrap'));
    if(!wraps.length){section.dataset.v38UiSource=SOURCE;return;}
    section.querySelectorAll(':scope > .msec[data-v38-py-source="1"]').forEach((node)=>node.remove());
    const labels=[
      ['マーケット概略','Market Overview','SNS共有用カード'],
      ['セクター・ローテーション','Sector Rotation','SNS共有用カード']
    ];
    wraps.forEach((wrap,index)=>{const group={label:labels[index]?.[0]||'共有カード',en:labels[index]?.[1]||'',q:labels[index]?.[2]||''};section.insertBefore(msec(group),wrap);});
    section.dataset.v38UiSource=SOURCE;
  }

  function sourceRsControl(){
    document.querySelectorAll('#t-port button,#t-port .rspbar,#t-rs button').forEach((node)=>{
      if(norm(node.textContent).startsWith('RS期間:'))node.classList.add('rsper');
    });
  }

  function readKvRows(card){
    return Array.from(card.querySelectorAll('.v38-canonical-row')).map((row)=>{
      const left=row.querySelector('.v38-canonical-left')||row;
      const value=row.querySelector('.v38-canonical-value,b:last-child');
      return {label:norm(left.textContent),value:norm(value&&value.textContent)};
    });
  }
  function regimeClass(value,kind){
    const n=parseFloat(String(value||'').replace('%',''));
    if(!Number.isFinite(n))return 'reg-na';
    const thresholds=kind==='f1'?[20,30]:kind==='f2'?[30,40]:[45,60];
    return n>=thresholds[1]?'reg-bad':n>=thresholds[0]?'reg-warn':'reg-ok';
  }
  function regCell(label,value,role,kind,note){
    const cell=document.createElement('div');cell.className=`reg-cell ${regimeClass(value,kind)}`;
    const k=document.createElement('div');k.className='reg-k';k.textContent=label;
    const r=document.createElement('div');r.className='reg-role';r.textContent=role;cell.append(k,r);
    const v=document.createElement('div');v.className='reg-v';v.textContent=value||'—';cell.appendChild(v);
    if(note){const n=document.createElement('div');n.className='reg-l';n.textContent=note;cell.appendChild(n);}
    return cell;
  }
  function pct(value){const n=Number(value);return Number.isFinite(n)?`${(n*100).toFixed(1)}%`:'—';}

  async function loadOverlay(){
    try{
      const response=await fetch('data/py_source_display.json',{cache:'no-store'});
      if(!response.ok)return null; return await response.json();
    }catch(_){return null;}
  }

  function sourceRegime(overlay){
    ['t-market','t-port'].forEach((sectionId)=>{
      const section=document.getElementById(sectionId);if(!section)return;
      const card=Array.from(section.querySelectorAll('.card')).find((node)=>matches(titleOf(node),'レジーム警戒灯'));
      if(!card)return;
      const existing=readKvRows(card);
      const pick=(needle)=>existing.find((row)=>row.label.includes(needle))?.value||'—';
      const f1=overlay&&overlay.f1_display&&overlay.f1_display.value!==null&&overlay.f1_display.value!==undefined?pct(overlay.f1_display.value):pick('F1');
      const f2=overlay&&overlay.f2&&overlay.f2.value!==null&&overlay.f2.value!==undefined?pct(overlay.f2.value):pick('F2');
      const f3=overlay&&overlay.f3&&overlay.f3.value!==null&&overlay.f3.value!==undefined?pct(overlay.f3.value):pick('F3');
      card.classList.add('reg-card'); card.replaceChildren();
      const hd=document.createElement('div');hd.className='hdr reg-hd';
      const h=document.createElement('h2');h.innerHTML='レジーム警戒灯 <span class="h2en">Regime Early-Warning</span>';hd.appendChild(h);card.appendChild(hd);
      const grid=document.createElement('div');grid.className='reg-grid';
      grid.append(
        regCell('F1 リーダー脱落率',f1,'最速の警報｜20営業日前Top24→現在36位外','f1',overlay?.f1_display?.display_only?'表示専用再構成・売買ゲート非連動':''),
        regCell('F2 勢い細り率',f2,'上位24のうちRS63<85の割合','f2',''),
        regCell('F3 キュー崩れ',f3,'反発待ち・高値からの崩れの深さ','f3',overlay?.f3?.display_only?'表示専用補完・売買ゲート非連動':'')
      );
      card.appendChild(grid);
      const note=document.createElement('div');note.className='note';note.textContent='3灯は足し算しない。F1/F2はタイミング、F3は下落の深さを見る補助計器。NQSARと売買ルール本体は変更しない。';card.appendChild(note);
      card.dataset.v38UiSource=SOURCE;
    });
  }

  function sourceFtd(view){
    const section=document.getElementById('t-market');if(!section)return;
    const card=Array.from(section.querySelectorAll('.card')).find((node)=>matches(titleOf(node),'フォロースルー・デイ'));if(!card)return;
    const proxy=view?.daily?.display_observations?.ftd_proxy||{};
    const indexes=proxy.indexes||proxy.indices||{};
    const safe=(value)=>{
      const text=norm(value);
      if(!text||/^[A-Z0-9_:-]+$/.test(text)||text.includes('SOURCE_DEFINED'))return '観測中';
      return text;
    };
    const items=[];
    Object.entries(indexes).forEach(([name,row])=>items.push([name,safe(row?.state||row?.status||row?.display)]));
    if(!items.length){
      const fallback=safe(proxy.state||proxy.display);
      items.push(['NASDAQ100',fallback],['S&P500',fallback]);
    }
    card.replaceChildren();
    const h=document.createElement('h2');h.innerHTML='フォロースルー・デイ <span class="h2en">FTD (proxy)</span>';card.appendChild(h);
    const sub=document.createElement('div');sub.className='sub';sub.innerHTML='調整局面からの反転確認。<b>Day4以降の上昇＋出来高増</b>を確認する表示専用proxy。';card.appendChild(sub);
    items.forEach(([name,value])=>{const row=document.createElement('div');row.className='ftd-row';const x=document.createElement('span');x.className='ftd-x';x.textContent=name;const s=document.createElement('span');s.className='warnt';s.textContent=value;row.append(x,s);card.appendChild(row);});
    card.dataset.v38UiSource=SOURCE;
  }

  function linePath(values,W,H,P,min,max){
    const span=max-min||1; return values.map((row,index)=>{
      const x=P+index*(W-2*P)/Math.max(1,values.length-1); const y=P+(1-(row.value-min)/span)*(H-2*P); return `${index?'L':'M'}${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(' ');
  }
  function sourceVix(overlay){
    const payload=overlay?.vix_fear_cycle;if(!payload||!Array.isArray(payload.rows)||payload.rows.length<2)return;
    const section=document.getElementById('t-market');if(!section)return;
    const card=Array.from(section.querySelectorAll('.card')).find((node)=>matches(titleOf(node),'VIX反転シーケンス'));if(!card)return;
    card.classList.add('vixcy');card.replaceChildren();
    const current=payload.current||{};
    const hd=document.createElement('div');hd.className='chd';const h=document.createElement('h2');h.innerHTML='VIX反転シーケンス <span class="h2en">VIX FEAR CYCLE</span>';hd.appendChild(h);
    const now=document.createElement('div');now.className='chd-now mut';const b=document.createElement('b');b.textContent=payload.state||'NORMAL';const d=document.createElement('span');d.textContent=payload.session_date||window.V38UiViewModel?.session_date||'';now.append(b,d);hd.appendChild(now);card.appendChild(hd);
    const sub=document.createElement('div');sub.className='sub';sub.textContent='VIX・LWMA5・LWMA10と長期分布の閾値を同じカードで確認。元pyのFear Cycle表示。';card.appendChild(sub);
    const vals=document.createElement('div');vals.className='vixvals';
    [['VIX',current.vix],['High',current.high],['LWMA5',current.lwma5],['LWMA10',current.lwma10],['+1σ',current.plus1_sigma],['+2σ',current.plus2_sigma]].forEach(([lab,val])=>{const box=document.createElement('div');const s=document.createElement('span');s.textContent=lab;const strong=document.createElement('b');strong.textContent=Number.isFinite(Number(val))?Number(val).toFixed(2):'—';box.append(s,strong);vals.appendChild(box);});card.appendChild(vals);
    const leg=document.createElement('div');leg.className='vixleg';[['vix-lg-close','VIX'],['vix-lg-w5','LWMA5'],['vix-lg-w10','LWMA10']].forEach(([cls,lab])=>{const s=document.createElement('span');const i=document.createElement('i');i.className=cls;s.append(i,document.createTextNode(lab));leg.appendChild(s);});card.appendChild(leg);
    const tabs=document.createElement('div');tabs.className='vixwtabs';const chart=document.createElement('div');chart.className='chart vixchart';card.append(tabs,chart);
    const windows=[['3M',63],['1Y',252],['3Y',756],['10Y',2520]];
    function draw(count,button){
      tabs.querySelectorAll('button').forEach((x)=>x.classList.remove('on'));button.classList.add('on');chart.replaceChildren();
      const rows=payload.rows.slice(-Math.min(count,payload.rows.length));const series=[['vix','#1c1b19'],['lwma5','#1f4b8f'],['lwma10','#9f1e62']];
      const all=[];series.forEach(([key])=>rows.forEach((row)=>{const n=Number(row[key]);if(Number.isFinite(n))all.push(n);}));if(!all.length)return;
      const lo0=Math.min(...all),hi0=Math.max(...all),pad=(hi0-lo0||1)*.10,lo=Math.max(0,lo0-pad),hi=hi0+pad,W=680,H=168,P=8;
      const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox',`0 0 ${W} ${H}`);svg.setAttribute('preserveAspectRatio','none');
      for(let i=0;i<4;i++){const value=lo+(hi-lo)*i/3;const y=H-P-(H-2*P)*i/3;const ln=document.createElementNS(svg.namespaceURI,'line');ln.setAttribute('x1',P);ln.setAttribute('x2',W-P);ln.setAttribute('y1',y);ln.setAttribute('y2',y);ln.setAttribute('stroke','#e3e1db');ln.setAttribute('stroke-width','1');svg.appendChild(ln);const tx=document.createElementNS(svg.namespaceURI,'text');tx.setAttribute('x',W-P);tx.setAttribute('y',Math.max(12,y-3));tx.setAttribute('text-anchor','end');tx.setAttribute('fill','#9f9982');tx.setAttribute('font-size','17');tx.textContent=value.toFixed(0);svg.appendChild(tx);}
      series.forEach(([key,color])=>{const pts=rows.map((row)=>({value:Number(row[key])})).filter((row)=>Number.isFinite(row.value));if(pts.length<2)return;const path=document.createElementNS(svg.namespaceURI,'path');path.setAttribute('d',linePath(pts,W,H,P,lo,hi));path.setAttribute('fill','none');path.setAttribute('stroke',color);path.setAttribute('stroke-width',key==='vix'?'2.4':'2.2');path.setAttribute('vector-effect','non-scaling-stroke');svg.appendChild(path);});
      chart.appendChild(svg);
    }
    windows.forEach(([label,count],index)=>{const button=document.createElement('button');button.type='button';button.className='vixwbt';button.textContent=label;button.addEventListener('click',()=>draw(count,button));tabs.appendChild(button);if(index===0)requestAnimationFrame(()=>draw(count,button));});
    card.dataset.v38UiSource=SOURCE;
  }

  function hideMachineText(){
    document.querySelectorAll('section:not(#t-options)').forEach((section)=>{
      const walker=document.createTreeWalker(section,NodeFilter.SHOW_TEXT);let node;
      while((node=walker.nextNode())){const value=node.nodeValue||'';if(/SOURCE_DEFINED_|SOURCE_UNAVAILABLE|DATA_REQUIRED/.test(value))node.nodeValue=value.replace(/SOURCE_DEFINED_[A-Z0-9_]+/g,'観測中').replace(/SOURCE_UNAVAILABLE|DATA_REQUIRED/g,'未取得');}
    });
  }

  function applyStructure(){NON_OPTIONS.filter((id)=>id!=='t-post1').forEach(sourceOrder);sourcePublish();sourceRsControl();document.body.dataset.v38UiAuthority='build_dashboard_2_py';}
  async function afterView(){
    applyStructure(); const view=window.V38UiViewModel||{}; sourceFtd(view); const overlay=await loadOverlay(); sourceRegime(overlay);sourceVix(overlay);hideMachineText();applyStructure();
  }

  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',applyStructure,{once:true});else applyStructure();
  document.addEventListener('v38:view-ready',()=>{void afterView();});
  window.addEventListener('load',()=>{hideMachineText();sourceRsControl();},{once:true});
})();
