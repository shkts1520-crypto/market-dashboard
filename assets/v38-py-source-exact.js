(function(){
'use strict';
const SOURCE='build_dashboard(2).py';
const norm=v=>String(v||'').replace(/\s+/g,' ').trim();
const esc=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
function title(card){if(!card)return'';if(card.dataset.v38CardTitle)return norm(card.dataset.v38CardTitle);const h=card.querySelector('h2');return h?norm(h.textContent):'';}
function cards(id){const s=document.getElementById(id);return s?Array.from(s.querySelectorAll(':scope > .card')):[];}
function findCard(id,needle){return cards(id).find(c=>title(c).includes(needle))||null;}
function hideCard(id,needle){const c=findCard(id,needle);if(c){c.hidden=true;c.classList.add('v38-py-unbound');}}
function h2(card,html){const x=card?.querySelector('h2');if(x)x.innerHTML=html;}
function msec(label,en,q){const d=document.createElement('div');d.className='msec';d.dataset.v38PySource='1';d.innerHTML=`<div class="msec-l">${esc(label)}${en?`<span class="msec-en">${esc(en)}</span>`:''}</div>${q?`<div class="msec-q">${esc(q)}</div>`:''}`;return d;}
function card(html,ttl){const d=document.createElement('div');d.className='card';if(ttl)d.dataset.v38CardTitle=ttl;d.dataset.v38UiSource=SOURCE;d.innerHTML=html;return d;}
function metric(view,key){const r=(view?.daily?.metrics||[]).find(x=>x.key===key);return r||{};}
function pct(v,d=1){return Number.isFinite(Number(v))?`${Number(v).toFixed(d)}%`:'—';}
function num(v,d=1){return Number.isFinite(Number(v))?Number(v).toFixed(d):'—';}
async function getView(){try{const r=await fetch('data/ui_view_model.json',{cache:'no-store'});return r.ok?await r.json():null;}catch(_){return null;}}
function waitBinder(timeout=12000){return new Promise(resolve=>{const st=performance.now();(function tick(){const s=document.documentElement.dataset.v38CanonicalBinder;if(s==='ready'||s==='error'||performance.now()-st>timeout)return resolve(s||'timeout');requestAnimationFrame(tick);})();});}
function exactDaily(){
  hideCard('t-market','ブレッドス推移（50');
  hideCard('t-market','ネット流動性');
  const mc=findCard('t-market','MC57推移');
  if(mc){mc.dataset.v38CardTitle='マーケットステータス推移';h2(mc,'マーケットステータス推移 <span class="h2en">Regime History</span>');}
  document.getElementById('t-market')?.setAttribute('data-v38-exact-source','ready');
}
function exactToday(){hideCard('t-today','ポケットピボット');document.getElementById('t-today')?.setAttribute('data-v38-exact-source','ready');}
function ret(series,n){if(!Array.isArray(series)||series.length<=n)return null;const a=Number(series.at(-1)?.close),b=Number(series.at(-1-n)?.close);return Number.isFinite(a)&&Number.isFinite(b)&&b?100*(a/b-1):null;}
function exactRotation(view){
  hideCard('t-rotation','テーマETFの温度計');
  let c=findCard('t-rotation','指数と中身の乖離');
  if(!c){c=card('', '指数と中身の乖離');}
  const ms=view?.daily?.market_series||{};
  const pairs=[['S&P500','SPY','RSP'],['NASDAQ100','QQQ','QQQE']];
  const rows=pairs.map(([lab,cap,eq])=>{const c21=ret(ms[cap],21),e21=ret(ms[eq],21),c63=ret(ms[cap],63),e63=ret(ms[eq],63);const d21=(c21!=null&&e21!=null)?e21-c21:null;return `<div class="src-index-row"><b>${lab}</b><span>21D 指数 ${pct(c21)}</span><span>等加重 ${pct(e21)}</span><span class="${d21!=null&&d21>=0?'src-pos':'src-neg'}">乖離 ${d21==null?'—':(d21>=0?'+':'')+d21.toFixed(1)+'pt'}</span></div><div class="src-index-row"><span class="mut">${cap} / ${eq}</span><span>63D ${pct(c63)}</span><span>63D ${pct(e63)}</span><span class="mut">幅と持続性を確認</span></div>`;}).join('');
  c.innerHTML=`<div class="hdr"><h2>指数と中身の乖離 <span class="h2en">Index vs Breadth</span></h2></div><div class="sub">指数（時価総額加重）と中身（等加重）の乖離。現在の確定日足から表示。</div>${rows}`;
  c.hidden=false;c.classList.remove('v38-py-unbound');c.dataset.v38UiSource=SOURCE;
  const s=document.getElementById('t-rotation');
  if(s&&!c.isConnected){const hs=Array.from(s.querySelectorAll(':scope > .msec'));const h=hs.find(x=>norm(x.textContent).startsWith('② その資金は広いか'));h?h.after(c):s.appendChild(c);}
  s?.setAttribute('data-v38-exact-source','ready');
}
function candidateRows(view){return (view?.core12?.rows||[]).filter(r=>r&&r.eligibility_status==='ELIGIBLE').slice(0,12);}
function buildPlanner(view){const cands=candidateRows(view);const opts=cands.map(r=>`<option value="${esc(r.ticker)}">${esc(r.ticker)} / $${num(r.price,2)} / RS189 ${num(r.rs189,1)}</option>`).join('');return card(`<div class="hdr"><h2>スイング・プランナー（R建てを分かりやすく） <span class="h2en">Trade Planner</span></h2></div><div class="sub">現行V38の候補と正式Exitを使い、発注前にサイズを確認。表示だけ元pyの入力型へ戻す。</div><div class="src-form-grid"><label>総資産 ¥</label><input id="srcPlanEquity" inputmode="decimal" placeholder="例 7000000"><label>USD/JPY</label><input id="srcPlanFx" inputmode="decimal" placeholder="例 150"><label>候補銘柄</label><select id="srcPlanTicker"><option value="">ティッカー入力可</option>${opts}</select><label>エントリー $</label><input id="srcPlanEntry" inputmode="decimal" placeholder="現在値を入力"><label>初期ストップ</label><input value="終値 Entry×0.92 → 翌寄り全売却" readonly><label>部分利確</label><input value="+24%で翌寄り25%・1回" readonly><label>Winner Trail</label><input value="残75%: max(Entry×0.92, Peak×0.70)" readonly></div><div class="src-callout">現在採用中のV38ルールだけを表示。10SMA / 21EMA / ATR2 / 建値Stop / 隔週強制Exitは使いません。</div><div class="src-equity-actions"><button class="srcctl" type="button">📥 ノート書き出し</button><button class="srcctl" type="button">💾 JSONバックアップ</button></div>`,'スイング・プランナー（R建てを分かりやすく）');}
function buildSizing(view){const mode=metric(view,'market_mode').display||view?.core12?.market_mode||'—',breadth=metric(view,'breadth50').display||'—';const max={ATTACK:12,SELECTIVE:4,STOP:0,DEFENSE:0}[String(mode).toUpperCase()]??Number(view?.core12?.max_new_total_slots||0);const rows=candidateRows(view).map((r,i)=>`<div class="src-minirow"><div><span class="src-ticker">#${i+1} ${esc(r.ticker)}</span><div class="src-meta">RS189 ${num(r.rs189,1)} ・ $${num(r.price,2)} ・ DDV20 $${Number(r.ddv20||0)/1e6>=1000?(Number(r.ddv20)/1e9).toFixed(1)+'B':(Number(r.ddv20||0)/1e6).toFixed(0)+'M'}</div></div><span class="src-badge ${max>0?'green':'amber'}">${max>0?'候補':'新規停止'}</span><span class="src-badge">建値入力</span></div>`).join('');return card(`<h2>資金配分・株数計算 <span class="h2en">Position Sizing</span></h2><div class="sub">現行Market Modeの新規枠上限と、現在のCore12候補を表示。</div><div class="src-kpi"><div><span>Market Mode</span><b>${esc(mode)}</b></div><div><span>Breadth 50</span><b>${esc(breadth)}</b></div><div><span>新規上限</span><b>${max}枠</b></div></div><div class="src-callout ${max? '':'warn'}">通常TQQQ 30% / 通常個別株 最大70%。${max?`現在は最大${max}枠まで新規候補を扱う。`:'現在は新規個別株0枠。既存は正式Exitまで保持（Red時は次回寄り全退避）。'}</div>${rows||'<div class="mut">候補なし</div>'}`,'資金配分・株数計算');}
function buildRebalance(){return card(`<h2>隔週リバランス点検（月曜） <span class="h2en">Rebalance Check</span></h2><div class="sub">元pyのカード位置・外観を復元。中身は現在採用中のV38ルールへ更新。</div><div class="src-callout warn"><b>現行V38では隔週の強制リバランスは不採用。</b><br>空き枠は毎営業日の引け後に判定し、翌寄りで補充。Breadth低下だけで12→4へ強制トリムしません。</div>`,'隔週リバランス点検（月曜）');}
function buildRebalanceNote(){return card(`<div class="sub">順位低下・Theme順位低下・Top12外・隔週日・Breadth閾値割れ・Yellowだけを理由に既存ポジションを売却しません。</div><div class="src-card-note">このカードは元pyのレイアウトを保つための説明枠で、売買ゲートではありません。</div>`,'');}
function buildEquityLog(){return card(`<h2>エクイティ記録 <span class="h2en">Equity Log</span></h2><div class="sub">口座資産の記録欄。現在のportfolio_stateが空の場合は手入力。</div><div class="src-form-grid"><label>今日の総資産</label><input inputmode="decimal" placeholder="例 7642525"><label>米株%</label><input inputmode="decimal" placeholder="任意・空欄OK"><label>メモ</label><input placeholder="入出金・大きな変化など"></div><div class="src-equity-actions"><button class="srcctl" type="button">📋 1行をコピー</button><button class="srcctl" type="button">✏️ 末尾を開いて追記</button></div>`,'エクイティ記録');}
function buildEquityCurve(old){if(old){const c=old.cloneNode(true);c.hidden=false;c.classList.remove('v38-py-unbound');c.dataset.v38CardTitle='エクイティカーブ×21EMA（未設定）';c.dataset.v38UiSource=SOURCE;h2(c,'エクイティカーブ×21EMA（未設定） <span class="h2en">Equity Curve</span>');return c;}return card(`<h2>エクイティカーブ×21EMA（未設定） <span class="h2en">Equity Curve</span></h2><div class="sub">口座資産の時系列データが未接続です。数値は推測しません。</div>`,'エクイティカーブ×21EMA（未設定）');}
function buildBrake(view){const mode=metric(view,'market_mode').display||'—',nq=metric(view,'nqsar').display||'—',b=metric(view,'breadth50').display||'—',mc=metric(view,'mc57').display||'—';const red=String(nq).toLowerCase()==='red';return card(`<div class="src-stop-title"><h2>非常口 <span class="h2en">Emergency Brake</span></h2><strong>${red?'次回寄り全退避':'通常監視'}</strong></div><div class="sub">現行V38のPortfolio Exitを表示。元pyの旧NAV/DDルールは復活させません。</div><div class="src-kpi"><div><span>NQSAR</span><b>${esc(nq)}</b></div><div><span>Breadth50</span><b>${esc(b)}</b></div><div><span>MC57</span><b>${esc(mc)}</b></div></div><div class="src-callout ${red?'warn':''}">${red?'NQSAR Red：通常個別株は次回寄りで全退避。':'Red以外：通常個別株は個別の正式Exitを優先。F1/F2/F3・MC57は通常個別株のHard Gateにしない。'} <b>Mode: ${esc(mode)}</b></div>`,'非常口');}
function exactPositions(view){const s=document.getElementById('t-alloc');if(!s)return;const oldEq=findCard('t-alloc','エクイティカーブ');s.replaceChildren();s.append(msec('トレード計画・保有記録','Plan & Holdings','買う前に株数・撤退・部分利確を決め、そのまま保有に記録'),buildPlanner(view),msec('① 配分計算','Position Sizing','地合い → 今日の株数に落とす'),buildSizing(view),msec('② リバランス点検','Rebalance Check','隔週月曜のチェックリスト'),buildRebalance(),buildRebalanceNote(),msec('資産推移・口座','Equity & Account','資産曲線・要因分解・非常口ブレーキ'),msec('記録','Equity Log','今日の総資産を残す（週1でOK）'),buildEquityLog(),buildEquityCurve(oldEq),buildBrake(view));s.dataset.v38UiSource=SOURCE;s.dataset.v38ExactSource='ready';}
async function apply(){await waitBinder();const view=await getView();await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));exactDaily();exactToday();exactRotation(view);exactPositions(view);document.documentElement.dataset.v38PySourceExact='ready';}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>void apply(),{once:true});else void apply();
})();
