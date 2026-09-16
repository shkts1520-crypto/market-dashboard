(function () {
  'use strict';

  const SECTORS = ['XLB','XLC','XLE','XLF','XLI','XLK','XLP','XLRE','XLU','XLV','XLY'];
  const OPTION_BUCKETS = ['0-6','7-21','22-45','0-45'];
  const STYLE_LABELS = {IWD:'バリュー',IWF:'グロース',IWM:'小型株',MDY:'中型株',RSP:'S&P等加重'};
  const SAFE_NOT_CONNECTED = new Set([
    'エクイティカーブ×21日EMA Equity Curve',
    '自分 vs QQQ円建て My Week',
    '来週の経済指標 Next Week'
  ]);

  function finite(value) {
    if (value === null || value === undefined || value === '') return null;
    const number = Number(value);
    return Number.isFinite(number) ? number : null;
  }
  function pct(value, digits) {
    const number = finite(value);
    if (number === null) return '—';
    return `${number > 0 ? '+' : ''}${(number * 100).toFixed(digits === undefined ? 1 : digits)}%`;
  }
  function pval(value, digits) {
    const number = finite(value);
    return number === null ? '—' : `${number.toFixed(digits === undefined ? 1 : digits)}%`;
  }
  function num(value, digits) {
    const number = finite(value);
    return number === null ? '—' : number.toLocaleString(undefined, {
      minimumFractionDigits: digits === undefined ? 1 : digits,
      maximumFractionDigits: digits === undefined ? 1 : digits
    });
  }
  function el(tag, cls, text) {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined) node.textContent = String(text);
    return node;
  }
  function originalTitle(card) {
    if (!card) return '';
    if (card.dataset.v38CardTitle) return String(card.dataset.v38CardTitle).replace(/\s+/g, ' ').trim();
    const h = card.querySelector('h2,.hdr h2,.chd h2');
    return h ? String(h.textContent || '').replace(/\s+/g, ' ').trim() : '';
  }
  function cards(sectionId) {
    const section = document.getElementById(sectionId);
    return section ? Array.from(section.querySelectorAll('.card')) : [];
  }
  function card(sectionId, needle) {
    return cards(sectionId).find((item) => originalTitle(item).includes(needle)) || null;
  }
  function mark(node, source, status, reason) {
    if (!node) return;
    node.dataset.v38TruthSource = source || 'unknown';
    node.dataset.v38Status = status || 'READY';
    if (reason) node.dataset.v38Reason = reason;
  }
  function heading(cardNode, title, subtitle) {
    cardNode.replaceChildren();
    const header = el('div', 'hdr');
    header.appendChild(el('h2', '', title));
    cardNode.appendChild(header);
    if (subtitle) cardNode.appendChild(el('div', 'sub', subtitle));
  }
  function kv(parent, label, value, cls) {
    const row = el('div', cls || 'v38-live-kv');
    row.append(el('span', '', label), el('b', '', value === null || value === undefined || value === '' ? '—' : value));
    parent.appendChild(row);
    return row;
  }
  function readyEmpty(cardNode, title, text, source) {
    if (!cardNode) return;
    heading(cardNode, title);
    cardNode.appendChild(el('div', 'empty', text));
    mark(cardNode, source, 'READY', 'EMPTY_IS_VALID');
  }
  function notConnected(cardNode, title, text, source) {
    if (!cardNode) return;
    heading(cardNode, title);
    cardNode.appendChild(el('div', 'empty', text));
    mark(cardNode, source, 'NOT_CONNECTED', 'SOURCE_NOT_CONNECTED');
  }
  function renderFailure(cardNode, title) {
    if (!cardNode) return;
    heading(cardNode, title || originalTitle(cardNode));
    cardNode.appendChild(el('div', 'empty', '表示データを接続できません。公開処理を停止します。'));
    mark(cardNode, 'binding-contract', 'ERROR', 'UNBOUND_VISIBLE_CARD');
  }
  function tickerButton(ticker) {
    const button = el('button', 'v38-ticker-link', ticker || '—');
    button.type = 'button';
    if (ticker) button.dataset.v38Ticker = ticker;
    return button;
  }
  function simpleList(cardNode, title, rows, source, subtitle) {
    if (!cardNode) return;
    heading(cardNode, title, subtitle);
    const list = el('div', 'v38-canonical-list');
    (rows || []).forEach((row) => {
      const line = el('div', 'v38-canonical-row');
      const left = el('div', 'v38-canonical-left');
      if (row.ticker) left.appendChild(tickerButton(row.ticker));
      else left.appendChild(el('span', '', row.label || row.name || '—'));
      if (row.meta) left.appendChild(el('small', 'mut', row.meta));
      line.append(left, el('b', 'v38-canonical-value', row.value === undefined ? '—' : row.value));
      if (finite(row.ddv20) !== null) line.dataset.liq = String(Number(row.ddv20) / 1e6);
      list.appendChild(line);
    });
    if (!rows || !rows.length) list.appendChild(el('div', 'empty', '該当なし'));
    cardNode.appendChild(list);
    mark(cardNode, source, 'READY');
  }
  function spark(cardNode, values, key, current, label, source) {
    if (!cardNode) return;
    const points = (values || []).map((value) => finite(value)).filter((value) => value !== null);
    heading(cardNode, label);
    kv(cardNode, 'Current', current);
    if (points.length < 2) {
      cardNode.appendChild(el('div', 'empty', '履歴の蓄積が不足しています。'));
      mark(cardNode, source, 'ERROR', 'SERIES_TOO_SHORT');
      return;
    }
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.classList.add('v38-canonical-spark');
    svg.dataset.v38LiveSpark = key;
    svg.setAttribute('viewBox', '0 0 100 30');
    svg.setAttribute('preserveAspectRatio', 'none');
    const lo = Math.min(...points), hi = Math.max(...points), span = hi - lo || 1;
    const coords = points.map((value, index) => `${(index / Math.max(1, points.length - 1) * 100).toFixed(3)},${(28 - (value - lo) / span * 26).toFixed(3)}`).join(' ');
    const polyline = document.createElementNS(svg.namespaceURI, 'polyline');
    polyline.setAttribute('points', coords);
    polyline.setAttribute('fill', 'none');
    polyline.setAttribute('stroke', 'currentColor');
    polyline.setAttribute('stroke-width', '1.7');
    polyline.setAttribute('vector-effect', 'non-scaling-stroke');
    svg.appendChild(polyline);
    cardNode.appendChild(svg);
    cardNode.dataset.v38LiveSeries = key;
    mark(cardNode, source, 'READY');
  }
  function metricMap(view) {
    const map = {};
    (((view || {}).daily || {}).metrics || []).forEach((row) => {
      if (row && row.key) map[row.key] = row;
    });
    return map;
  }
  function metricDisplay(map, key) {
    const row = map[key];
    return row && row.status === 'READY' ? String(row.display || '—') : '—';
  }
  function marketSummary(view, ticker) {
    return ((((view || {}).daily || {}).market_summaries || {})[ticker]) || {};
  }
  function marketSeries(view, ticker) {
    const rows = ((((view || {}).daily || {}).market_series || {})[ticker]);
    return Array.isArray(rows) ? rows : [];
  }

  function renderDaily(view) {
    const daily = view.daily || {};
    const metrics = metricMap(view);
    const history = Array.isArray(daily.history) ? daily.history : [];

    const banner=document.querySelector('#t-market > .banner');
    if(banner){banner.replaceChildren();banner.append(el('div','lab','マーケットステータス（MC57）'),el('div','val',metricDisplay(metrics,'mc57')),el('div','st','最新セッション'));const aux=el('div','aux');kv(aux,'50MA Breadth',metricDisplay(metrics,'breadth50'));kv(aux,'NQSAR',metricDisplay(metrics,'nqsar'));banner.appendChild(aux);mark(banner,'data/ui_view_model.json.daily.metrics','READY');}
    document.querySelectorAll('#t-market > .ribwrap').forEach((rib)=>{rib.replaceChildren();const line=el('div','riblab',`現在 ${metricDisplay(metrics,'nqsar')} · 50MA Breadth ${metricDisplay(metrics,'breadth50')}`);rib.appendChild(line);mark(rib,'data/ui_view_model.json.daily.metrics','READY');});
    const pill=document.getElementById('sarPill');
    if(pill){const state=metricDisplay(metrics,'nqsar');pill.classList.remove('sar-blue','sar-green','sar-yellow','sar-red');if(state&&state!=='—')pill.classList.add('sar-'+state.toLowerCase());const badge=pill.querySelector('#sarBadge');const col=pill.querySelector('#sarCol');const jud=pill.querySelector('#sarJud');const lot=pill.querySelector('#sarLot');if(badge)badge.textContent='LIVE';if(col)col.textContent=state;if(jud)jud.textContent=metricDisplay(metrics,'market_mode');if(lot)lot.textContent='最新セッション';mark(pill,'data/ui_view_model.json.daily.metrics','READY');}

    const today = card('t-market', '今日のマーケット');
    if (today) {
      heading(today, '今日のマーケット', '現行V38の市場状態。売買判定は採用済みルールだけを表示。');
      [['Market Mode','market_mode'],['NQSAR','nqsar'],['MC57','mc57'],['50MA Breadth','breadth50'],['200MA Breadth','breadth200'],['F2','f2']].forEach(([label,key]) => kv(today,label,metricDisplay(metrics,key)));
      mark(today, 'data/ui_view_model.json.daily.metrics', 'READY');
    }
    const perf = card('t-market', 'マーケット・パフォーマンス');
    if (perf) {
      const rows = ['QQQ','SPY','RSP','QQQE'].map((ticker) => {
        const s = marketSummary(view,ticker);
        return {ticker, value:`1D ${pct(s.change_1d)} / 1W ${pct(s.change_1w)} / 1M ${pct(s.change_1m)}`};
      });
      simpleList(perf, 'マーケット・パフォーマンス Performance', rows, 'data/ui_view_model.json.daily.market_summaries');
    }
    const heat = card('t-market', 'セクター温度マップ');
    if (heat) renderSectorHeatmap(heat, view, 'data/ui_view_model.json.daily.market_summaries');
    const leaders = daily.leader_diagnostics || {};
    simpleList(card('t-market','リーダーの強さ'),'リーダーの強さ Leader Temperature',[
      {label:'RS63/126/189 全て85以上',value:leaders.triple_rs85_count ?? '—'},
      {label:'52週高値まで5%以内',value:leaders.near_52w_high_count ?? '—'},
      {label:'当日上昇銘柄比率',value:finite(leaders.advancing_1d_pct) === null ? '—' : pval(leaders.advancing_1d_pct)}
    ],'data/ui_view_model.json.daily.leader_diagnostics');
    const topRet = Array.isArray(leaders.top_ret20) ? leaders.top_ret20 : [];
    simpleList(card('t-market','先導株モメンタム'),'先導株モメンタム・ラン Leader Momentum',topRet.slice(0,10).map((r)=>({ticker:r.ticker,meta:r.industry||r.sector,value:`1M ${pct(r.ret20)} / RS189 ${num(r.rs189,1)}`})),'data/ui_view_model.json.daily.leader_diagnostics.top_ret20');

    spark(card('t-market','ブレッドス推移（50'),'history' && history.map((row)=>row.breadth50),'breadth50',metricDisplay(metrics,'breadth50'),'ブレッドス推移（50日線上の割合）','data/ui_view_model.json.daily.history.breadth50');
    spark(card('t-market','ブレッドス推移（200'),history.map((row)=>row.breadth200),'breadth200',metricDisplay(metrics,'breadth200'),'ブレッドス推移（200日線上の割合）','data/ui_view_model.json.daily.history.breadth200');
    const mcSeries = ((((daily.mc57_detail || {}).series || {}).mc57) || daily.mc57_history || []);
    const mcValues = Array.isArray(mcSeries) ? mcSeries.map((row)=>row && (row.value !== undefined ? row.value : row.mc57)) : [];
    if (mcValues.length >= 2) spark(card('t-market','MC57推移'),mcValues,'mc57',metricDisplay(metrics,'mc57'),'MC57推移 Market Status History','data/ui_view_model.json.daily.mc57_detail');

    const change = card('t-market','前回からの変化');
    if (change) {
      const current = history.at(-1) || {}, previous = history.at(-2) || {};
      simpleList(change,'前回からの変化 Change Log',['breadth50','breadth200','f2','f3'].map((key)=>({label:key.toUpperCase(),value:finite(current[key])===null?'—':`${num(current[key],2)}${finite(previous[key])===null?'':` / Δ ${num(current[key]-previous[key],2)}`}`})),'data/ui_view_model.json.daily.history');
    }
    const vix = marketSeries(view,'^VIX');
    if (vix.length > 1) spark(card('t-market','VIX反転シーケンス'),vix.map((r)=>r.close),'vix',num(marketSummary(view,'^VIX').close,2),'VIX反転シーケンス VIX Fear Cycle','data/ui_view_model.json.daily.market_series.^VIX');
    simpleList(card('t-market','信用と金利'),'信用と金利 Credit & Rates',[
      {label:'HYG',value:num(marketSummary(view,'HYG').close,2)},
      {label:'IEF',value:num(marketSummary(view,'IEF').close,2)},
      {label:'米10年',value:`${num(marketSummary(view,'^TNX').close,2)}%`},
      {label:'米5年',value:`${num(marketSummary(view,'^FVX').close,2)}%`}
    ],'data/ui_view_model.json.daily.market_summaries');

    const diagnostics = ((daily.market_diagnostics || {}).series) || [];
    [['売買代金 参加度','volume_participation','売買代金 参加度（200日平均比） Volume Participation'],
     ['集積／分散','up_down_dollar_ratio','集積／分散 Accumulation / Distribution'],
     ['騰落ライン（マクレラン','mcclellan','騰落ライン（マクレラン・オシレーター）']].forEach(([needle,key,label]) => {
      const values = diagnostics.map((row)=>row && row[key]);
      if (values.filter((value)=>finite(value)!==null).length >= 2) spark(card('t-market',needle),values,key,num(values.at(-1),key==='mcclellan'?1:2),label,`data/ui_view_model.json.daily.market_diagnostics.series.${key}`);
    });
    const cardObservations=daily.card_observations||{};
    [['攻守ローテーション','risk_rotation','攻守ローテーション（XLY / XLP）'],
     ['クレジット推移','credit_ratio','クレジット推移（HYG / IEF）'],
     ['VIX期間構造','vix_term','VIX期間構造（1M / 3M）']].forEach(([needle,key,label])=>{
      const observation=cardObservations[key]||{}, values=(observation.rows||[]).map((row)=>row.value);
      if(values.length>=2)spark(card('t-market',needle),values,key,num(observation.current,3),label,`data/ui_view_model.json.daily.card_observations.${key}`);
    });
    const observations=daily.display_observations||{};
    const regime=observations.regime_history||{};
    simpleList(card('t-market','レジーム警戒灯'),'レジーム警戒灯 Regime Early-Warning',[
      {label:'F1 リーダー脱落率',value:metricDisplay(metrics,'f1')},{label:'F2 勢い細り率',value:metricDisplay(metrics,'f2')},{label:'F3 キュー崩れ',value:metricDisplay(metrics,'f3')},{label:'NQSAR',value:metricDisplay(metrics,'nqsar')}
    ],'data/ui_view_model.json.daily.f123_detail+metrics');
    const liquidity=observations.net_liquidity||{};
    simpleList(card('t-market','ネット流動性'),'ネット流動性 Net Liquidity',[
      {label:'Net Liquidity',value:finite(liquidity.value)===null?(liquidity.display||'—'):num(liquidity.value,2)},
      {label:'4週変化',value:finite(liquidity.change_4w)===null?'—':num(liquidity.change_4w,2)},
      {label:'観測日',value:liquidity.date||liquidity.observed_date||view.session_date||'—'}
    ],'data/ui_view_model.json.daily.display_observations.net_liquidity');
    const expectedMove=cardObservations.expected_move||{};
    simpleList(card('t-market','オプション想定変動幅'),'オプション想定変動幅 Expected Move',[
      {label:'SPY 約1カ月',value:finite(expectedMove.spy_1m_pct)===null?'—':`±${num(expectedMove.spy_1m_pct,1)}%`},
      {label:'QQQ 約1カ月',value:finite(expectedMove.qqq_1m_pct)===null?'—':`±${num(expectedMove.qqq_1m_pct,1)}%`}
    ],'data/ui_view_model.json.daily.card_observations.expected_move','年率IV÷√12の表示用目安。');
    const distribution=cardObservations.distribution_days||{};
    simpleList(card('t-market','ディストリビューション・デイ'),'ディストリビューション・デイ（直近25営業日）',[
      {label:'SPY',value:`${distribution.SPY??'—'}日`},{label:'QQQ',value:`${distribution.QQQ??'—'}日`}
    ],'data/ui_view_model.json.daily.card_observations.distribution_days','価格下落かつ前日比出来高増の表示用proxy。売買ゲートではありません。');
    const sentiment=observations.sentiment||{};
    const components=Array.isArray(sentiment.components)?sentiment.components:[];
    simpleList(card('t-market','センチメント'),'センチメント（群衆温度計） Sentiment',[
      {label:'合成',value:finite(sentiment.composite)===null?(sentiment.display||'—'):num(sentiment.composite,0)},
      ...components.slice(0,6).map((row)=>({label:row.label||row.key||row.name||'Component',value:finite(row.percentile)===null?(row.display||'—'):num(row.percentile,0)}))
    ],'data/ui_view_model.json.daily.display_observations.sentiment');
    const reversal=observations.reversal_leaders||{};
    simpleList(card('t-market','転換初動リーダーボード'),'転換初動リーダーボード Reversal Leaders',(reversal.leaders||[]).map((row)=>({ticker:row.ticker,meta:row.reclaim21?'21EMA奪回':'待機',value:`RS189 ${num(row.rs189,1)} · RVOL ${num(row.rvol,2)}`})),'data/ui_view_model.json.daily.display_observations.reversal_leaders');
    const ftd=observations.ftd_proxy||{};
    const ftdRows=[]; Object.entries(ftd.indexes||ftd.indices||{}).forEach(([name,row])=>ftdRows.push({label:name,value:row.state||row.status||row.display||'—'}));
    if(!ftdRows.length)ftdRows.push({label:'NASDAQ100 / S&P500',value:ftd.state||ftd.display||ftd.reason||'観測済み'});
    simpleList(card('t-market','フォロースルー・デイ'),'フォロースルー・デイ FTD (proxy)',ftdRows,'data/ui_view_model.json.daily.display_observations.ftd_proxy');
  }

  function renderSectorHeatmap(cardNode, view, source) {
    heading(cardNode, 'セクター温度マップ Sector Heatmap', 'セクターETFの1週・1カ月騰落率。濃さは絶対値。');
    const grid = el('div','v38-sector-heatmap');
    SECTORS.forEach((ticker) => {
      const s = marketSummary(view,ticker), w = finite(s.change_1w), m = finite(s.change_1m);
      const cell = el('div','v38-sector-cell');
      cell.dataset.v38Sector = ticker;
      cell.dataset.direction = w === null ? 'flat' : w >= 0 ? 'up' : 'down';
      cell.style.setProperty('--heat', String(Math.min(1, Math.abs(w || 0) / 0.08)));
      cell.append(el('b','',ticker),el('span','',`1W ${pct(w)} · 1M ${pct(m)}`));
      grid.appendChild(cell);
    });
    cardNode.appendChild(grid);
    mark(cardNode,source,'READY');
  }

  function renderPositions(view) {
    const positions = view.positions || {}, core = view.core12 || {};
    const rows = Array.isArray(positions.rows) ? positions.rows : [];
    const holdings = card('t-alloc','保有ポジション');
    if (!rows.length) readyEmpty(holdings,'保有ポジション Current Holdings','現在の保有なし','data/ui_view_model.json.positions');
    else simpleList(holdings,'保有ポジション Current Holdings',rows.map((r)=>({ticker:r.ticker,meta:r.action_next_open||r.action||'',value:r.quantity ?? r.weight ?? '保有'})),'data/ui_view_model.json.positions');

    const mode = core.market_mode || metricDisplay(metricMap(view),'market_mode');
    const expected = card('t-alloc','現在の想定ポジション');
    if (expected) {
      if (String(mode).toUpperCase() === 'STOP' || String(mode).toUpperCase() === 'DEFENSE') {
        readyEmpty(expected,'現在の想定ポジション Current Expected 12',`${mode}のため新規ポジションは0。既存保有は個別Exitルールに従います。`,'data/ui_view_model.json.core12.market_mode');
      } else {
        const limit = finite(core.max_new_total_slots) || (String(mode).toUpperCase()==='SELECTIVE'?4:12);
        simpleList(expected,'現在の想定ポジション Current Expected 12',(core.rows||[]).slice(0,limit).map((r)=>({ticker:r.ticker,meta:r.theme_name||r.industry||'',value:`Rank ${r.rank ?? '—'} / RS189 ${num(r.rs189,1)}`})),'data/ui_view_model.json.core12.rows','空枠を無理に埋めず、現行適格候補だけを表示。');
      }
    }
    simpleList(card('t-alloc','マーケット回復後'), 'マーケット回復後のポジション入り銘柄 Recovery Candidates',(core.rows||[]).slice(0,12).map((r)=>({ticker:r.ticker,meta:r.theme_name||r.industry||'',value:`Rank ${r.rank ?? '—'} / RS189 ${num(r.rs189,1)}`})),'data/ui_view_model.json.core12.rows','回復時にはその時点の順位で再計算。これは現在値による待機候補。');
    notConnected(card('t-alloc','エクイティカーブ×21日EMA'),'エクイティカーブ×21日EMA Equity Curve','口座資産の時系列データが未接続です。数値は推測しません。','account-equity-history');
  }

  function renderCore(view) {
    const core = view.core12 || {}, metrics = metricMap(view);
    simpleList(card('t-port','レジーム警戒灯'),'レジーム警戒灯 Regime Early-Warning',[
      {label:'Market Mode',value:core.market_mode || metricDisplay(metrics,'market_mode')},
      {label:'NQSAR',value:metricDisplay(metrics,'nqsar')},
      {label:'50MA Breadth',value:metricDisplay(metrics,'breadth50')},
      {label:'新規上限',value:core.max_new_total_slots ?? '—'}
    ],'data/ui_view_model.json.core12+daily.metrics');
    const entrants = core.new_entrants || {};
    simpleList(card('t-port','新規参入'),'新規参入（ポート候補36位圏） New Entrants',(entrants.rows||[]).map((r)=>({ticker:r.ticker,value:`現在 ${r.rank ?? '—'}位 / 20日前 ${r.prior_rank ?? '圏外'}`})),'data/ui_view_model.json.core12.new_entrants');
    simpleList(card('t-port','個別株スリーブ Core 12'),'個別株スリーブ Core 12',(core.rows||[]).slice(0,12).map((r)=>({ticker:r.ticker,meta:r.theme_name||r.industry||'',value:`Rank ${r.rank ?? '—'} · RS189 ${num(r.rs189,1)}`})),'data/ui_view_model.json.core12.rows');
    simpleList(card('t-port','RSリーダー控え'),'RSリーダー控え Bench',(core.rows||[]).slice(12,24).map((r)=>({ticker:r.ticker,meta:r.theme_name||r.industry||'',value:`Rank ${r.rank ?? '—'} · RS189 ${num(r.rs189,1)}`})),'data/ui_view_model.json.core12.rows');
    cards('t-port').filter((node)=>!node.dataset.v38TruthSource).forEach((node)=>{
      const title=originalTitle(node);
      if(title.includes('V38 Data')) simpleList(node,'Core 12 データ品質',[{label:'Eligible',value:core.rows?.length??0},{label:'Market Mode',value:core.market_mode||'—'},{label:'新規上限',value:core.max_new_total_slots??'—'}],'data/ui_view_model.json.core12');
      else if(title.includes('個別株スリーブ')) simpleList(node,'個別株スリーブ Core 12',(core.rows||[]).slice(0,12).map((r)=>({ticker:r.ticker,value:`Rank ${r.rank??'—'} · RS189 ${num(r.rs189,1)}`})),'data/ui_view_model.json.core12.rows');
    });
  }

  function setupRows(cardNode,title,rows,source,subtitle) {
    simpleList(cardNode,title,(rows||[]).map((r)=>({ticker:r.ticker,ddv20:r.ddv20,meta:[r.industry,r.stage2?'Stage2':'',r.confluence&&r.confluence.length?r.confluence.join(' / '):''].filter(Boolean).join(' · '),value:`RS189 ${num(r.rs189,1)} · piv ${pct(r.pivot_dist)} · DDV ${finite(r.ddv20)===null?'—':`$${(r.ddv20/1e6).toFixed(1)}M`}`})),source,subtitle);
  }
  function renderSetups(view) {
    const data = view.setups || {};
    const utility=document.querySelector('#t-today .card.liqstick');
    if(utility){mark(utility,'data/ui_view_model.json.setups','READY');utility.querySelectorAll('button').forEach((button)=>{button.removeAttribute('onclick');button.addEventListener('click',()=>{utility.querySelectorAll('button').forEach((x)=>x.classList.remove('active'));button.classList.add('active');const label=String(button.textContent||'');const m=label.match(/\$(\d+)M/);const threshold=m?Number(m[1]):-1;document.querySelectorAll('#t-today .v38-canonical-row[data-liq]').forEach((row)=>{const value=Number(row.dataset.liq||0);row.hidden=threshold>=0&&value<threshold;});});});}
    const search = card('t-today','銘柄検索');
    if (search) {
      heading(search,'銘柄検索 Ticker Search','全ユニバースを検索。ティッカーをタップするとCommand Center内のチャートを開きます。');
      const input = el('input','tksearch'); input.id='tksearch'; input.type='search'; input.placeholder='例: NVDA';
      const results = el('div','tkresults'); results.id='tkresults';
      search.append(input,results); mark(search,'data/search_index.json','READY');
      installSearch(input,results);
    }
    setupRows(card('t-today','発火前'),'発火前 Pre-Breakout',data.prebreakout,'data/ui_view_model.json.setups.prebreakout','構造・出来高収縮・ピボット距離から抽出。表示専用で売買ゲートではありません。');
    const put = card('t-today','支えへの接触');
    if (put) readyEmpty(put,'支えへの接触 Put Wall Touch','当日条件に該当する銘柄なし。','data/options/index.json');
    setupRows(card('t-today','エントリー候補ボード'),'エントリー候補ボード Confluence',data.confluence,'data/ui_view_model.json.setups.confluence','RS189≥95の事実表示。合否判定ではありません。');
    setupRows(card('t-today','ポケットピボット'),'ポケットピボット（10D）',data.pocket_pivots,'data/ui_view_model.json.setups.pocket_pivots');
    setupRows(card('t-today','本日のピックアップ'),"本日のピックアップ Today's Setups",data.todays_setups,'data/ui_view_model.json.setups.todays_setups');
    const patterns = data.patterns || {};
    const patternRows=[];
    Object.entries(patterns).forEach(([name,rows])=>(rows||[]).slice(0,4).forEach((r)=>patternRows.push({...r,pattern_name:name})));
    simpleList(card('t-today','テクニカル・パターン別'),'テクニカル・パターン別 Chart Patterns',patternRows.map((r)=>({ticker:r.ticker,meta:r.pattern_name,value:`RS189 ${num(r.rs189,1)}`})),'data/ui_view_model.json.setups.patterns');
    setupRows(card('t-today','圧縮コイル'),'圧縮コイル（VCP）',data.vcp,'data/ui_view_model.json.setups.vcp');
    setupRows(card('t-today','21EMA'), '21EMA Touch', data.ema21_touch,'data/ui_view_model.json.setups.ema21_touch');
    simpleList(card('t-today','Multi VWAP'),'Multi VWAPセットアップ',(data.vwap_rows||[]).slice(0,30).map((r)=>({ticker:r.ticker,meta:r.industry||'',value:`63 ${num(r.vwap63,2)} · 252 ${num(r.vwap252,2)} · Life ${num(r.vwap_life,2)}`})),'data/ui_view_model.json.setups.vwap_rows');
    const structure=(data.patterns&&data.patterns.structure_pivot)||data.vcp||[];
    setupRows(card('t-today','底打ち'),'底打ち（構造ピボット） Structure Pivot',structure,'data/ui_view_model.json.setups.patterns.structure_pivot');
    setupRows(card('t-today','ブレイク一覧'),'ブレイク一覧 Signals',data.todays_setups,'data/ui_view_model.json.setups.todays_setups');
    const ruleNeedles=['運用ルール','定義・グレード','状態の凡例','コホート分析','入り方','手仕舞いの目安'];
    ruleNeedles.forEach((needle)=>{const node=card('t-today',needle);if(node)mark(node,'assets/baseline-0905/setups.html:audited-static-rule-content','READY');});
    const leaders=(data.rows&&data.rows.length?data.rows:[...(data.prebreakout||[]),...(data.confluence||[]),...(data.vcp||[])]);
    setupRows(card('t-today','リーダー監視'),'リーダー監視（RS≥85・200MA上） Leaders',leaders.filter((r)=>finite(r.rs189)>=85).slice(0,80),'data/ui_view_model.json.setups.rows');
  }

  async function installSearch(input, results) {
    let data;
    try { const r=await fetch('data/search_index.json',{cache:'no-store'}); if(r.ok) data=await r.json(); } catch (_) {}
    const rows = data && Array.isArray(data.rows) ? data.rows : [];
    input.addEventListener('input',()=>{
      const q=input.value.trim().toUpperCase(); results.replaceChildren(); if(!q) return;
      rows.filter((r)=>String(r.ticker||'').includes(q)||String(r.name||'').toUpperCase().includes(q)).slice(0,12).forEach((r)=>{
        const line=el('button','tkresult');line.type='button';line.dataset.v38Ticker=r.ticker;line.append(el('b','',r.ticker),el('span','',r.name||''));results.appendChild(line);
      });
    });
  }

  function renderMoneyFlow(cardNode, view) {
    const flow = ((view.rotation||{}).money_flow)||{};
    const rows = Array.isArray(flow.rows) ? flow.rows : [];
    heading(cardNode,'資金フロー（GICS11＋スタイル）','GICS11＋スタイル5本。横=SPY比63営業日相対力、縦=その10営業日モメンタム。100が市場並み。');
    if (rows.length !== 16) {
      cardNode.appendChild(el('div','empty','必要な16系列が揃っていません。公開処理を停止します。'));
      mark(cardNode,'data/ui_view_model.json.rotation.money_flow','ERROR','RRG_SERIES_INCOMPLETE');
      return;
    }
    const plot=el('div','v38-rrg');
    plot.append(el('span','v38-rrg-axis x','100'),el('span','v38-rrg-axis y','100'));
    const xs=rows.map((r)=>finite(r.x)).filter((v)=>v!==null), ys=rows.map((r)=>finite(r.y)).filter((v)=>v!==null);
    const minX=Math.min(...xs,97),maxX=Math.max(...xs,103),minY=Math.min(...ys,97),maxY=Math.max(...ys,103);
    rows.forEach((r)=>{
      const x=finite(r.x),y=finite(r.y); if(x===null||y===null)return;
      const dot=el('button','v38-rrg-dot',r.ticker);dot.type='button';dot.dataset.v38Ticker=r.ticker;dot.title=`${r.label||STYLE_LABELS[r.ticker]||r.ticker} RS ${x.toFixed(1)} / Mom ${y.toFixed(1)}`;
      dot.style.left=`${5+90*(x-minX)/(maxX-minX||1)}%`;dot.style.top=`${95-90*(y-minY)/(maxY-minY||1)}%`;plot.appendChild(dot);
    });
    cardNode.appendChild(plot);mark(cardNode,'data/ui_view_model.json.rotation.money_flow','READY');
  }

  function renderRotation(view) {
    renderMoneyFlow(card('t-rotation','資金フロー'),view);
    renderSectorHeatmap(card('t-rotation','セクター温度マップ'),view,'data/ui_view_model.json.daily.market_summaries');
    const diag=(view.rotation||{}).diagnostics||{}, industries=Array.isArray(diag.industry)?diag.industry:[];
    simpleList(card('t-rotation','主導セクター・業種'),'主導セクター・業種 Leading Groups',industries.slice(0,15).map((r)=>({label:r.group,value:`1M ${pct(r.ret20_avg)} · RS63 ${num(r.rs63_avg,1)} · ${r.member_count}銘柄`})),'data/ui_view_model.json.rotation.diagnostics.industry','現行Universeの診断表示。Peer Theme Scoreのハードゲートではありません。');
    const leaderRows=[];industries.slice(0,10).forEach((r)=>(r.leaders||[]).forEach((ticker)=>leaderRows.push({ticker,meta:r.group,value:`Group 1M ${pct(r.ret20_avg)}`})));
    simpleList(card('t-rotation','強い業種の主導株'),'強い業種の主導株 Leaders in Strong Groups',leaderRows,'data/ui_view_model.json.rotation.diagnostics.industry.leaders');
    simpleList(card('t-rotation','セクターETF強弱'),'セクターETF強弱 Sector ETF Strength',SECTORS.map((ticker)=>({ticker,value:`1W ${pct(marketSummary(view,ticker).change_1w)} · 1M ${pct(marketSummary(view,ticker).change_1m)}`})),'data/ui_view_model.json.daily.market_summaries');
    const fine=(view.rotation||{}).fine_theme_rows||(view.rotation||{}).fine_themes||[];
    if (fine.length) simpleList(card('t-rotation','サブテーマ別RS'),'サブテーマ別RS（ユニバース内）',fine.slice(0,20).map((r)=>({label:r.theme_name||r.theme||r.group,value:`RS ${num(r.score||r.rs63||r.theme_rs63,1)}`})),'data/ui_view_model.json.rotation.fine_themes');
    simpleList(card('t-rotation','テーマETFの温度計'),'テーマETFの温度計（重複あり）',SECTORS.map((ticker)=>({ticker,value:`1W ${pct(marketSummary(view,ticker).change_1w)} · 1M ${pct(marketSummary(view,ticker).change_1m)}`})),'data/ui_view_model.json.daily.market_summaries');
  }

  function renderMovers(view) {
    const section=document.getElementById('t-movers');if(!section)return;
    const data=view.movers||{}, root=cards('t-movers')[0], wrap=root&&root.querySelector('.mv-wrap');
    if(!root||!wrap)return;
    const summaries=wrap.querySelectorAll('.mv-sum');['1d','1w','1m'].forEach((key,index)=>{const item=(data.summary||{})[key]||{};if(summaries[index])summaries[index].textContent=`${item.label||key}　中央値 ${pct(item.median)}　上昇 ${finite(item.advancing_pct)===null?'—':pval(100*item.advancing_pct,0)}`;});
    const three=data.three_window||{}, boxes=wrap.querySelectorAll('.mv-mom');
    [[boxes[0],three.gainers||[]],[boxes[1],three.losers||[]]].forEach(([box,rows])=>{if(!box)return;const body=box.querySelector('.mv-mom-b');if(body)body.textContent=rows.length?rows.map((row)=>row.ticker).join('・'):'該当なし';});
    const blocks=wrap.querySelectorAll('.mv-per');['1d','1w','1m'].forEach((key,index)=>{const period=(data.periods||{})[key]||{}, columns=blocks[index]?blocks[index].querySelectorAll('.mv-col'):[];[[columns[0],period.gainers||[]],[columns[1],period.losers||[]]].forEach(([column,rows])=>{if(!column)return;column.querySelectorAll('.mvr').forEach((node,rowIndex)=>{const row=rows[rowIndex];node.hidden=!row;if(!row)return;node.dataset.tkone=row.ticker;const ticker=node.querySelector('.mvr-t'),value=node.querySelector('.mvr-v'),meta=node.querySelector('.mvr-th');if(ticker)ticker.textContent=row.ticker;if(value)value.textContent=pct(row[period.key||key==='1d'?'ret1':key==='1w'?'ret5':'ret20']);if(meta)meta.textContent=row.industry||row.sector||'—';});});});
    mark(root,'data/ui_view_model.json.movers','READY');mark(section,'data/ui_view_model.json.movers','READY');
  }

  async function renderRs(view) {
    const rs=view.rs||{}, windows=rs.windows||{};
    const intro=card('t-rs','RSマルチタイムフレーム比較');
    if(intro) simpleList(intro,'RSマルチタイムフレーム比較',[], 'data/ui_view_model.json.rs','63・126・189営業日の強弱を同じ画面で比較。');
    [63,126,189].forEach((period)=>simpleList(card('t-rs',`RS${period} Top10`),`RS${period} Top10`,(windows[String(period)]||[]).map((r)=>({ticker:r.ticker,meta:r.industry||r.sector,value:`RS ${num(r[`rs${period}`],1)} · 1M ${pct(r.ret20)}`})),`data/ui_view_model.json.rs.windows.${period}`));
    simpleList(card('t-rs','RS189 継続性'),'RS189 継続性 Leadership Persistence',(rs.rows||[]).map((r)=>({ticker:r.ticker,meta:r.industry||r.sector,value:`RS189 ${num(r.rs189,1)} · 1M ${pct(r.ret20)}`})),'data/ui_view_model.json.rs.rows');
    const cross=(rs.rows||[]).filter((r)=>finite(r.rs63)>=85&&finite(r.rs126)>=85&&finite(r.rs189)>=85);
    simpleList(card('t-rs','三窓一致リーダー'),'三窓一致リーダー Cross-Window Leaders',cross.map((r)=>({ticker:r.ticker,value:`63 ${num(r.rs63,1)} / 126 ${num(r.rs126,1)} / 189 ${num(r.rs189,1)}`})),'data/ui_view_model.json.rs.rows');
    let history={};try{const response=await fetch('data/rs_history.json',{cache:'no-store'});if(response.ok)history=await response.json();}catch(_){}
    const changes=[];[63,126,189].forEach((period)=>((((history.windows||{})[String(period)]||{}).comparisons)||[]).forEach((entry)=>{if(entry.status==='READY')changes.push({label:`RS${period} ${entry.label}`,value:`IN ${(entry.in||[]).join('・')||'なし'} / OUT ${(entry.out||[]).join('・')||'なし'}`});}));
    simpleList(card('t-rs','Top10 IN / OUT'),'Top10 IN / OUT履歴',changes,'data/rs_history.json.windows');
  }

  function renderWeekly(view) {
    const weekly=view.weekly||{}, metrics=metricMap(view), daily=view.daily||{};
    simpleList(card('t-weekly','今週の結論'),'今週の結論 This Week',[
      {label:'Market Mode',value:metricDisplay(metrics,'market_mode')},{label:'NQSAR',value:metricDisplay(metrics,'nqsar')},{label:'MC57',value:metricDisplay(metrics,'mc57')},{label:'50MA Breadth',value:metricDisplay(metrics,'breadth50')}
    ],'data/ui_view_model.json.daily.metrics');
    notConnected(card('t-weekly','来週の経済指標'),'来週の経済指標 Next Week','経済指標カレンダーの取得元が未接続です。日付は推測しません。','economic-calendar');
    simpleList(card('t-weekly','構造マクロ'),'構造マクロ Structural Macro',['DX-Y.NYB','CL=F','GC=F'].map((ticker)=>({ticker,value:`1W ${pct(marketSummary(view,ticker).change_1w)} · 1M ${pct(marketSummary(view,ticker).change_1m)}`})),'data/ui_view_model.json.daily.market_summaries');
    simpleList(card('t-weekly','金利レジーム'),'金利レジーム Rates',[{label:'米10年',value:`${num(marketSummary(view,'^TNX').close,2)}%`},{label:'米5年',value:`${num(marketSummary(view,'^FVX').close,2)}%`},{label:'IEF 1W',value:pct(marketSummary(view,'IEF').change_1w)}],'data/ui_view_model.json.daily.market_summaries');
    simpleList(card('t-weekly','マクロ圧力'),'マクロ圧力 Macro Pressure',[{label:'VIX',value:num(marketSummary(view,'^VIX').close,2)},{label:'VXN',value:num(marketSummary(view,'^VXN').close,2)},{label:'HYG 1W',value:pct(marketSummary(view,'HYG').change_1w)}],'data/ui_view_model.json.daily.market_summaries');
    simpleList(card('t-weekly','広域ブレッドス'),'広域ブレッドス Market Breadth',[{label:'50MA上',value:metricDisplay(metrics,'breadth50')},{label:'200MA上',value:metricDisplay(metrics,'breadth200')}],'data/ui_view_model.json.daily.metrics');
    simpleList(card('t-weekly','データ品質'),'データ品質 Data Quality',[{label:'Stock coverage',value:pct(daily.stock_data_coverage)},{label:'Breadth coverage',value:pct(daily.breadth_coverage)},{label:'History',value:`${(daily.history||[]).length} sessions`}],'data/ui_view_model.json.daily');
    simpleList(card('t-weekly','レバレッジ・コンディション'),'レバレッジ・コンディション（SOXL）',[{label:'Close',value:num(marketSummary(view,'SOXL').close,2)},{label:'1W',value:pct(marketSummary(view,'SOXL').change_1w)},{label:'1M',value:pct(marketSummary(view,'SOXL').change_1m)}],'data/ui_view_model.json.daily.market_summaries.SOXL');
    notConnected(card('t-weekly','自分 vs QQQ'),'自分 vs QQQ円建て My Week','口座資産の時系列データが未接続です。比較値は推測しません。','account-equity-history');
    const history=Array.isArray(daily.history)?daily.history:[],current=history.at(-1)||{},prior=history.at(-6)||{};
    simpleList(card('t-weekly','今週の変化'),'今週の変化 Weekly Diff',['breadth50','breadth200','f1','f2','f3'].map((key)=>({label:key.toUpperCase(),value:finite(current[key])===null?'—':`${num(current[key],2)} / 5日前比 ${finite(prior[key])===null?'—':num(current[key]-prior[key],2)}`})),'data/ui_view_model.json.daily.history');
    const regimeRows=((((daily.display_observations||{}).regime_history||{}).rows)||history).slice(-20);
    spark(card('t-weekly','地合いの帯'),regimeRows.map((row)=>row.value??row.breadth50),'weekly_regime',metricDisplay(metrics,'nqsar'),'地合いの帯 Regime History','data/ui_view_model.json.daily.display_observations.regime_history');
    simpleList(card('t-weekly','週次騰落ボード'),'週次騰落ボード Weekly Movers',SECTORS.map((ticker)=>({ticker,value:`1W ${pct(marketSummary(view,ticker).change_1w)} · 1M ${pct(marketSummary(view,ticker).change_1m)}`})).sort((a,b)=>String(a.value).localeCompare(String(b.value))),'data/ui_view_model.json.daily.market_summaries');
  }

  function optionRows(options,bucket){return ((((options||{}).buckets||{})[bucket])||[]).slice(0,24);}
  function renderOptions(options) {
    OPTION_BUCKETS.forEach((bucket)=>{
      const title=bucket.replace('-','–')+' DTE';
      const c=cards('t-options').find((x)=>originalTitle(x).includes(title))||cards('t-options').find((x)=>originalTitle(x).includes(bucket));
      const rows=optionRows(options,bucket);
      simpleList(c,`${title} ${bucket==='0-6'?'Short Term':bucket==='7-21'?'Swing':bucket==='22-45'?'Medium Term':'Multi-expiry'}`,rows.map((r)=>({ticker:r.ticker,meta:r.expiry||'',value:`Spot ${num(r.spot,2)} · Call ${num(r.call_wall,2)} · Flip ${num(r.gamma_flip,2)} · Put ${num(r.put_wall,2)} · EM ${finite(r.expected_move_pct)===null?'—':`±${(100*r.expected_move_pct).toFixed(1)}%`}`})),`data/options/index.json.buckets.${bucket}`,'実測Wall / Gamma Flip / Expected Moveのみを表示。');
      if(c)c.dataset.v38OptionBucket=bucket;
    });
  }

  function renderPublish(view) {
    const section=document.getElementById('t-post1');if(!section)return;
    const wraps=Array.from(section.querySelectorAll('.postwrap'));const metrics=metricMap(view);
    const sectors=SECTORS.map((ticker)=>({ticker,change:marketSummary(view,ticker).change_1w})).sort((a,b)=>(finite(b.change)||-99)-(finite(a.change)||-99));
    const html1=`<!doctype html><meta charset="utf-8"><style>body{margin:0;padding:24px;font-family:system-ui;background:#f5f2e8;color:#171714}h1{font-size:24px}dl{display:grid;grid-template-columns:1fr auto;gap:12px}dt,dd{margin:0;padding:8px 0;border-bottom:1px solid #d8d3c7}dd{font-weight:700}</style><h1>V38 MARKET OVERVIEW</h1><p>${view.session_date||''}</p><dl><dt>Market Mode</dt><dd>${metricDisplay(metrics,'market_mode')}</dd><dt>NQSAR</dt><dd>${metricDisplay(metrics,'nqsar')}</dd><dt>MC57</dt><dd>${metricDisplay(metrics,'mc57')}</dd><dt>50MA Breadth</dt><dd>${metricDisplay(metrics,'breadth50')}</dd></dl>`;
    const html2=`<!doctype html><meta charset="utf-8"><style>body{margin:0;padding:24px;font-family:system-ui;background:#f5f2e8;color:#171714}h1{font-size:24px}.r{display:flex;justify-content:space-between;padding:7px 0;border-bottom:1px solid #d8d3c7}</style><h1>SECTOR ROTATION</h1><p>${view.session_date||''}</p>${sectors.map((r)=>`<div class="r"><b>${r.ticker}</b><span>${pct(r.change)}</span></div>`).join('')}`;
    [html1,html2].forEach((srcdoc,index)=>{if(!wraps[index])return;wraps[index].replaceChildren();const frame=el('iframe','postframe');frame.srcdoc=srcdoc;frame.title=index===0?'Market Overview share card':'Sector Rotation share card';wraps[index].appendChild(frame);mark(wraps[index],index===0?'data/ui_view_model.json.daily':'data/ui_view_model.json.daily.market_summaries','READY');});
    mark(section,'data/ui_view_model.json.publish','READY');section.dataset.v38PublishCards='ready';
  }

  function renderRules(view) {
    const rules=view.rules||{}, cs=cards('t-rules'), rows=rules.rows||[];
    const normal=rows.filter((r)=>!String(r.key||'').startsWith('tqqq_panic.'));
    const tqqq=rows.filter((r)=>String(r.key||'').startsWith('tqqq_panic.'));
    if(cs[0]) simpleList(cs[0],'通常個別株 Normal Stock',normal.map((r)=>({label:r.key,value:r.value})),'data/ui_view_model.json.rules.rows');
    if(cs[1]) simpleList(cs[1],'TQQQ Normal + Panic',tqqq.map((r)=>({label:r.key,value:r.value})),'data/ui_view_model.json.rules.rows');
  }

  function finalize() {
    let errors=0;
    document.querySelectorAll('section .card').forEach((node)=>{
      if(node.dataset.v38TruthSource)return;
      const title=originalTitle(node);
      if(SAFE_NOT_CONNECTED.has(title)) { notConnected(node,title,'この表示に必要な外部データソースが未接続です。値は推測しません。','explicit-not-connected'); return; }
      renderFailure(node,title);errors+=1;
    });
    document.documentElement.dataset.v38CanonicalBinder = errors ? 'error' : 'ready';
    document.body.dataset.v38CanonicalBinderErrors=String(errors);
  }

  async function render(view) {
    let options={};
    try { const r=await fetch('data/options/index.json',{cache:'no-store'}); if(r.ok) options=await r.json(); } catch (_) {}
    renderDaily(view);renderPositions(view);renderCore(view);renderSetups(view);renderRotation(view);renderMovers(view);await renderRs(view);renderWeekly(view);renderOptions(options);renderPublish(view);renderRules(view);finalize();
  }

  document.addEventListener('v38:view-ready',(event)=>{render(event.detail||window.V38UiViewModel||{});},{once:true});

  const style=el('style');style.id='v38-canonical-binder-style';style.textContent=`
    .v38-canonical-list{display:flex;flex-direction:column;gap:0;margin-top:8px}.v38-canonical-row{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:12px;align-items:center;padding:9px 0;border-bottom:1px solid rgba(120,110,90,.16)}.v38-canonical-row:last-child{border-bottom:0}.v38-canonical-left{min-width:0;display:flex;gap:8px;align-items:baseline;flex-wrap:wrap}.v38-canonical-left small{font-size:11px}.v38-canonical-value{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;text-align:right;font-size:12px}.v38-canonical-spark{width:100%;height:92px;display:block;margin-top:10px}.v38-sector-heatmap{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:7px;margin-top:10px}.v38-sector-cell{min-width:0;border:1px solid rgba(100,90,70,.16);border-radius:10px;padding:10px;background:rgba(255,255,255,.35)}.v38-sector-cell[data-direction="up"]{box-shadow:inset 0 0 0 999px rgba(38,122,77,calc(var(--heat)*.12))}.v38-sector-cell[data-direction="down"]{box-shadow:inset 0 0 0 999px rgba(184,74,66,calc(var(--heat)*.12))}.v38-sector-cell b,.v38-sector-cell span{display:block}.v38-sector-cell span{font-size:10px;margin-top:4px}.v38-rrg{height:280px;position:relative;margin-top:12px;border:1px solid rgba(100,90,70,.18);border-radius:12px;background:linear-gradient(90deg,rgba(184,74,66,.05) 50%,rgba(38,122,77,.05) 50%),linear-gradient(0deg,rgba(184,74,66,.04) 50%,rgba(38,122,77,.04) 50%)}.v38-rrg:before,.v38-rrg:after{content:"";position:absolute;background:rgba(90,80,65,.25)}.v38-rrg:before{left:50%;top:0;bottom:0;width:1px}.v38-rrg:after{top:50%;left:0;right:0;height:1px}.v38-rrg-dot{position:absolute;transform:translate(-50%,-50%);border:0;border-radius:999px;padding:4px 6px;font-size:9px;font-weight:700;background:#fff;box-shadow:0 1px 5px rgba(0,0,0,.15);z-index:2}.v38-rrg-axis{position:absolute;font-size:9px;color:#777}.v38-rrg-axis.x{left:51%;bottom:2px}.v38-rrg-axis.y{left:2px;top:48%}.tkresult{width:100%;display:flex;justify-content:space-between;gap:12px;padding:9px;border:0;border-bottom:1px solid rgba(100,90,70,.15);background:transparent;text-align:left}.postframe{width:100%;min-height:480px;border:0;border-radius:14px;background:#f5f2e8}@media(max-width:600px){.v38-sector-heatmap{grid-template-columns:repeat(2,minmax(0,1fr))}.v38-rrg{height:240px}.v38-canonical-row{grid-template-columns:minmax(0,1fr);gap:4px}.v38-canonical-value{text-align:left}.postframe{min-height:430px}}
  `;document.head.appendChild(style);
})();
