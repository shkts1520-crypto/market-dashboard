(function () {
  'use strict';

  const SECTORS = ['XLB','XLC','XLE','XLF','XLI','XLK','XLP','XLRE','XLU','XLV','XLY'];
  const SECTOR_LABELS = {XLB:'素材',XLC:'通信',XLE:'エネルギー',XLF:'金融',XLI:'資本財',XLK:'テクノロジー',XLP:'生活必需品',XLRE:'不動産',XLU:'公益',XLV:'ヘルスケア',XLY:'一般消費財'};
  const TV_SECTOR_LABELS = {'Electronic Technology':'電子テクノロジー','Technology Services':'テクノロジーサービス','Retail Trade':'小売業','Communications':'通信','Consumer Durables':'耐久消費財','Health Technology':'ヘルスケアテクノロジー','Finance':'金融','Producer Manufacturing':'生産財製造','Energy Minerals':'エネルギー鉱物','Non-Energy Minerals':'非エネルギー鉱物','Process Industries':'加工産業','Commercial Services':'商業サービス','Consumer Non-Durables':'非耐久消費財','Consumer Services':'消費者サービス','Distribution Services':'流通サービス','Health Services':'ヘルスサービス','Industrial Services':'産業サービス','Transportation':'交通・輸送','Utilities':'公益事業','Miscellaneous':'その他'};
  const GICS_DIAG_GROUPS = [['テクノロジー','XLK',['Electronic Technology','Technology Services']],['通信','XLC',['Communications']],['一般消費財','XLY',['Consumer Durables','Retail Trade','Consumer Services']],['生活必需品','XLP',['Consumer Non-Durables','Distribution Services']],['エネルギー','XLE',['Energy Minerals','Industrial Services']],['金融','XLF',['Finance']],['ヘルスケア','XLV',['Health Technology','Health Services']],['資本財','XLI',['Producer Manufacturing','Transportation']],['素材','XLB',['Non-Energy Minerals','Process Industries']],['不動産','XLRE',['Finance']],['公益','XLU',['Utilities']]];
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
  function html(value) {
    return String(value === null || value === undefined ? '' : value)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
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
    const W = 680, H = 68, P = 6;
    const lo = Math.min(...points), hi = Math.max(...points), span = hi - lo || 1;
    const X = (index) => P + index * (W - 2 * P) / Math.max(1, points.length - 1);
    const Y = (value) => H - P - (value - lo) / span * (H - 2 * P);
    const coords = points.map((value, index) => `${X(index).toFixed(1)},${Y(value).toFixed(1)}`);
    const area = `M${coords[0]} ${coords.slice(1).map((point) => `L${point}`).join(' ')} L${X(points.length - 1).toFixed(1)},${H-P} L${X(0).toFixed(1)},${H-P} Z`;
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.classList.add('spark', 'v38-canonical-spark');
    svg.dataset.v38LiveSpark = key;
    svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
    svg.setAttribute('preserveAspectRatio', 'none');
    svg.setAttribute('role', 'img');
    svg.setAttribute('aria-label', label);
    const defs = document.createElementNS(svg.namespaceURI, 'defs');
    const gradient = document.createElementNS(svg.namespaceURI, 'linearGradient');
    const gid = `v38-sp-${String(key || 'series').replace(/[^a-z0-9_-]/gi, '')}-${Math.random().toString(36).slice(2,8)}`;
    gradient.id = gid;
    gradient.setAttribute('x1','0'); gradient.setAttribute('y1','0'); gradient.setAttribute('x2','0'); gradient.setAttribute('y2','1');
    const stop0 = document.createElementNS(svg.namespaceURI, 'stop');
    stop0.setAttribute('offset','0'); stop0.setAttribute('stop-color','#6f93c9'); stop0.setAttribute('stop-opacity','0.28');
    const stop1 = document.createElementNS(svg.namespaceURI, 'stop');
    stop1.setAttribute('offset','1'); stop1.setAttribute('stop-color','#6f93c9'); stop1.setAttribute('stop-opacity','0');
    gradient.append(stop0, stop1); defs.appendChild(gradient); svg.appendChild(defs);
    const fill = document.createElementNS(svg.namespaceURI, 'path');
    fill.setAttribute('d', area); fill.setAttribute('fill', `url(#${gid})`); svg.appendChild(fill);
    const line = document.createElementNS(svg.namespaceURI, 'polyline');
    line.setAttribute('points', coords.join(' ')); line.setAttribute('fill','none'); line.setAttribute('stroke','#6f93c9'); line.setAttribute('stroke-width','2'); line.setAttribute('vector-effect','non-scaling-stroke'); svg.appendChild(line);
    const dot = document.createElementNS(svg.namespaceURI, 'circle');
    dot.setAttribute('cx', X(points.length - 1).toFixed(1)); dot.setAttribute('cy', Y(points.at(-1)).toFixed(1)); dot.setAttribute('r','3.2'); dot.setAttribute('fill','#6f93c9'); svg.appendChild(dot);
    cardNode.appendChild(svg);
    cardNode.dataset.v38LiveSeries = key;
    mark(cardNode, source, 'READY');
  }

  function chartSeries(rows, valueAccessor, multiplier) {
    const mult = multiplier === undefined ? 1 : multiplier;
    return (rows || []).map((row, index) => {
      const raw = typeof valueAccessor === 'function' ? valueAccessor(row, index) : row;
      const value = finite(raw);
      const date = row && typeof row === 'object' ? (row.date || row.session_date || row.observed_date || '') : '';
      return value === null ? null : {value:value * mult, date:String(date || '')};
    }).filter(Boolean);
  }
  function niceTicks(lo, hi, count) {
    if (!Number.isFinite(lo) || !Number.isFinite(hi)) return [];
    if (lo === hi) { lo -= 1; hi += 1; }
    const n = Math.max(3, count || 4), raw = (hi - lo) / (n - 1);
    const power = Math.pow(10, Math.floor(Math.log10(Math.abs(raw) || 1)));
    const norm = raw / power;
    const step = (norm <= 1 ? 1 : norm <= 2 ? 2 : norm <= 2.5 ? 2.5 : norm <= 5 ? 5 : 10) * power;
    const start = Math.floor(lo / step) * step, end = Math.ceil(hi / step) * step;
    const out=[]; for(let v=start; v<=end+step*.25 && out.length<8; v+=step) out.push(Number(v.toFixed(8)));
    return out;
  }
  function dateLabel(value) {
    if (!value) return '';
    const m = String(value).match(/(\d{4})-(\d{2})-(\d{2})/);
    return m ? `${m[1].slice(2)}/${Number(m[2])}/${Number(m[3])}` : String(value);
  }
  function trendChart(cardNode, rows, valueAccessor, key, current, label, source, options) {
    if (!cardNode) return;
    const opt=options||{}, series=chartSeries(rows,valueAccessor,opt.multiplier), values=series.map((r)=>r.value);
    cardNode.replaceChildren();
    const header=el('div','chd v38-source-chd'); header.appendChild(el('h2','',label));
    const now=el('div','chd-now v38-source-now'); now.append(el('b','',current||'—'),el('span','',opt.currentLabel||'現在')); header.appendChild(now); cardNode.appendChild(header);
    if(opt.subtitle) cardNode.appendChild(el('div','sub',opt.subtitle));
    if(values.length<2){cardNode.appendChild(el('div','empty','履歴の蓄積が不足しています。'));mark(cardNode,source,'ERROR','SERIES_TOO_SHORT');return;}
    const W=680,H=180,P=6,R=52;
    let lo=opt.yMin!==undefined?Number(opt.yMin):Math.min(...values), hi=opt.yMax!==undefined?Number(opt.yMax):Math.max(...values);
    if(opt.includeBaseline!==undefined){lo=Math.min(lo,Number(opt.includeBaseline));hi=Math.max(hi,Number(opt.includeBaseline));}
    if(opt.yMin===undefined||opt.yMax===undefined){const span=(hi-lo)||1; if(opt.yMin===undefined)lo-=span*.10;if(opt.yMax===undefined)hi+=span*.10;}
    if(lo===hi){lo-=1;hi+=1;} const rng=hi-lo;
    const X=(i)=>P+i*(W-R-P)/Math.max(1,values.length-1),Y=(v)=>P+(1-(v-lo)/rng)*(H-2*P);
    const svg=document.createElementNS('http://www.w3.org/2000/svg','svg'); svg.classList.add('v38-trend-svg');svg.dataset.v38LiveSpark=key;svg.dataset.v38FullTrend='1';svg.setAttribute('viewBox',`0 0 ${W} ${H}`);svg.setAttribute('preserveAspectRatio','none');svg.setAttribute('role','img');svg.setAttribute('aria-label',label);
    const ticks=(opt.ticks&&opt.ticks.length?opt.ticks:niceTicks(lo,hi,5)).filter((g)=>g>=lo-1e-9&&g<=hi+1e-9);
    (opt.bands||[]).forEach((band)=>{const a=Math.max(lo,band[0]),b=Math.min(hi,band[1]);if(b<=a)return;const rect=document.createElementNS(svg.namespaceURI,'rect');rect.setAttribute('x',P);rect.setAttribute('y',Y(b));rect.setAttribute('width',W-R-P);rect.setAttribute('height',Math.max(0,Y(a)-Y(b)));rect.setAttribute('fill',band[2]);rect.setAttribute('opacity',band[3]===undefined?'0.07':String(band[3]));svg.appendChild(rect);});
    ticks.forEach((g)=>{const line=document.createElementNS(svg.namespaceURI,'line');line.setAttribute('x1',P);line.setAttribute('x2',W-R);line.setAttribute('y1',Y(g));line.setAttribute('y2',Y(g));line.setAttribute('class','v38-grid-line');svg.appendChild(line);const t=document.createElementNS(svg.namespaceURI,'text');t.setAttribute('x',W-4);t.setAttribute('y',Y(g)-2);t.setAttribute('text-anchor','end');t.setAttribute('class','v38-y-label');const d=opt.tickDigits===undefined?(Math.abs(g)>=10?0:2):opt.tickDigits;t.textContent=`${Number(g).toFixed(d).replace(/\.00$/,'')}${opt.suffix||''}`;svg.appendChild(t);});
    if(opt.baseline!==undefined&&Number(opt.baseline)>=lo&&Number(opt.baseline)<=hi){const base=document.createElementNS(svg.namespaceURI,'line');base.setAttribute('x1',P);base.setAttribute('x2',W-R);base.setAttribute('y1',Y(Number(opt.baseline)));base.setAttribute('y2',Y(Number(opt.baseline)));base.setAttribute('class','v38-baseline');svg.appendChild(base);}
    const coords=values.map((v,i)=>`${X(i).toFixed(1)},${Y(v).toFixed(1)}`),gid=`v38full-${String(key).replace(/[^a-z0-9_-]/gi,'')}-${Math.random().toString(36).slice(2,8)}`;
    const defs=document.createElementNS(svg.namespaceURI,'defs'),grad=document.createElementNS(svg.namespaceURI,'linearGradient');grad.id=gid;grad.setAttribute('x1','0');grad.setAttribute('y1','0');grad.setAttribute('x2','0');grad.setAttribute('y2','1');const a=document.createElementNS(svg.namespaceURI,'stop'),b=document.createElementNS(svg.namespaceURI,'stop');a.setAttribute('offset','0');a.setAttribute('stop-color',opt.color||'#58a6ff');a.setAttribute('stop-opacity','.35');b.setAttribute('offset','1');b.setAttribute('stop-color',opt.color||'#58a6ff');b.setAttribute('stop-opacity','0');grad.append(a,b);defs.appendChild(grad);svg.appendChild(defs);
    const area=document.createElementNS(svg.namespaceURI,'path');area.setAttribute('d',`M${coords[0]} ${coords.slice(1).map((p)=>`L${p}`).join(' ')} L${X(values.length-1).toFixed(1)},${H-P} L${X(0).toFixed(1)},${H-P} Z`);area.setAttribute('fill',`url(#${gid})`);svg.appendChild(area);
    const poly=document.createElementNS(svg.namespaceURI,'polyline');poly.setAttribute('points',coords.join(' '));poly.setAttribute('fill','none');poly.setAttribute('stroke',opt.color||'#58a6ff');poly.setAttribute('stroke-width','2');poly.setAttribute('vector-effect','non-scaling-stroke');svg.appendChild(poly);
    const dot=document.createElementNS(svg.namespaceURI,'circle');dot.setAttribute('cx',X(values.length-1));dot.setAttribute('cy',Y(values.at(-1)));dot.setAttribute('r','3.5');dot.setAttribute('fill',opt.color||'#58a6ff');svg.appendChild(dot);
    const chart=el('div','chart v38-source-chart');chart.appendChild(svg);
    const dated=series.filter((r)=>r.date);if(dated.length){const dax=el('div','dax v38-date-axis');[0,Math.floor((dated.length-1)/2),dated.length-1].forEach((i)=>dax.appendChild(el('span','v38-date-label',dateLabel(dated[i].date))));chart.appendChild(dax);} cardNode.appendChild(chart);
    cardNode.dataset.v38LiveSeries=key;mark(cardNode,source,'READY');
  }
  function richTable(cardNode,title,columns,rows,source,subtitle) {
    if(!cardNode)return;heading(cardNode,title,subtitle);const wrap=el('div','v38-table-wrap'),table=el('table','v38-source-table'),thead=el('thead'),trh=el('tr');columns.forEach((c)=>trh.appendChild(el('th',c.align==='left'?'l':'',c.label)));thead.appendChild(trh);table.appendChild(thead);const body=el('tbody');(rows||[]).forEach((row)=>{const tr=el('tr');columns.forEach((c)=>{const td=el('td',c.align==='left'?'l':'');if(c.ticker){td.appendChild(tickerButton(row[c.key]));}else td.textContent=c.format?c.format(row):String(row[c.key]??'—');tr.appendChild(td);});body.appendChild(tr);});table.appendChild(body);wrap.appendChild(table);cardNode.appendChild(wrap);if(!rows||!rows.length)cardNode.appendChild(el('div','empty','該当なし'));mark(cardNode,source,'READY');
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

    trendChart(card('t-market','ブレッドス推移（50'),history,(row)=>row.breadth50,'breadth50',metricDisplay(metrics,'breadth50'),'ブレッドス推移（50日線上の割合）','data/ui_view_model.json.daily.history.breadth50',{multiplier:100,yMin:0,yMax:100,ticks:[20,40,50,60,80],suffix:'%',tickDigits:0,color:'#58a6ff',currentLabel:'50日線上',subtitle:'通常個別株Universeの50日線上比率'});
    trendChart(card('t-market','ブレッドス推移（200'),history,(row)=>row.breadth200,'breadth200',metricDisplay(metrics,'breadth200'),'ブレッドス推移（200日線上の割合）','data/ui_view_model.json.daily.history.breadth200',{multiplier:100,yMin:0,yMax:100,ticks:[20,40,50,60,80],suffix:'%',tickDigits:0,color:'#58a6ff',currentLabel:'200日線上'});
    const mcSeries = ((((daily.mc57_detail || {}).series || {}).mc57) || daily.mc57_history || []);
    const mcValues = Array.isArray(mcSeries) ? mcSeries.map((row)=>row && (row.value !== undefined ? row.value : row.mc57)) : [];
    if (mcValues.length >= 2) trendChart(card('t-market','MC57推移'),Array.isArray(mcSeries)?mcSeries:[],(row)=>row&&(row.value!==undefined?row.value:row.mc57),'mc57',metricDisplay(metrics,'mc57'),'マーケットステータス推移 MC57','data/ui_view_model.json.daily.mc57_detail',{yMin:0,yMax:100,ticks:[25,40,55,70],tickDigits:0,color:'#34d399',currentLabel:'Market Status',bands:[[0,25,'#ef4444'],[25,40,'#f97316'],[40,55,'#64748b'],[55,70,'#22c55e'],[70,100,'#16a34a']]});

    const change = card('t-market','前回からの変化');
    if (change) {
      const current = history.at(-1) || {}, previous = history.at(-2) || {};
      simpleList(change,'前回からの変化 Change Log',['breadth50','breadth200','f2','f3'].map((key)=>({label:key.toUpperCase(),value:finite(current[key])===null?'—':`${num(current[key],2)}${finite(previous[key])===null?'':` / Δ ${num(current[key]-previous[key],2)}`}`})),'data/ui_view_model.json.daily.history');
    }
    const vix = marketSeries(view,'^VIX');
    if (vix.length > 1) trendChart(card('t-market','VIX反転シーケンス'),vix,(r)=>r.close,'vix',num(marketSummary(view,'^VIX').close,2),'VIX反転シーケンス VIX Fear Cycle','data/ui_view_model.json.daily.market_series.^VIX',{color:'#a78bfa',tickDigits:1,currentLabel:'VIX'});
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
      if (values.filter((value)=>finite(value)!==null).length >= 2) trendChart(card('t-market',needle),diagnostics,(row)=>row&&row[key],key,num(values.at(-1),key==='mcclellan'?1:2),label,`data/ui_view_model.json.daily.market_diagnostics.series.${key}`,key==='volume_participation'?{ticks:[0.8,1.0,1.2,1.4],baseline:1,includeBaseline:1,tickDigits:1,color:'#38bdf8',currentLabel:'200日平均比'}:key==='up_down_dollar_ratio'?{baseline:1,includeBaseline:1,tickDigits:2,color:'#34d399',currentLabel:'比率'}:{baseline:0,includeBaseline:0,tickDigits:1,color:'#f59e0b',currentLabel:'Oscillator'});
    });
    const cardObservations=daily.card_observations||{};
    [['攻守ローテーション','risk_rotation','攻守ローテーション（XLY / XLP）'],
     ['クレジット推移','credit_ratio','クレジット推移（HYG / IEF）'],
     ['VIX期間構造','vix_term','VIX期間構造（1M / 3M）']].forEach(([needle,key,label])=>{
      const observation=cardObservations[key]||{}, values=(observation.rows||[]).map((row)=>row.value);
      if(values.length>=2)trendChart(card('t-market',needle),observation.rows||[],(row)=>row&&row.value,key,num(observation.current,3),label,`data/ui_view_model.json.daily.card_observations.${key}`,key==='vix_term'?{ticks:[0.90,0.95,1.00,1.05],baseline:1,includeBaseline:1,tickDigits:2,color:'#c4b5fd',currentLabel:'1M / 3M'}:key==='risk_rotation'?{baseline:1,includeBaseline:1,tickDigits:2,color:'#60a5fa',currentLabel:'XLY / XLP'}:{tickDigits:2,color:'#fb7185',currentLabel:'HYG / IEF'});
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
      cell.style.setProperty('--heat', String(Math.min(1,Math.abs(w||0)/0.06)));
      cell.append(el('b','',ticker),el('span','',`1W ${pct(w)} · 1M ${pct(m)}`));
      grid.appendChild(cell);
    });
    cardNode.appendChild(grid); mark(cardNode,source,'READY');
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
        simpleList(expected,'現在の想定ポジション Current Expected 12',(core.rows||[]).slice(0,limit).map((r)=>({ticker:r.ticker,meta:r.theme_name||r.industry||'',value:`${finite(r.rank)!==null?`Rank ${r.rank} / `:''}RS189 ${num(r.rs189,1)}`})),'data/ui_view_model.json.core12.rows','空枠を無理に埋めず、現行適格候補だけを表示。');
      }
    }
    simpleList(card('t-alloc','マーケット回復後'), 'マーケット回復後のポジション入り銘柄 Recovery Candidates',(core.rows||[]).slice(0,12).map((r)=>({ticker:r.ticker,meta:r.theme_name||r.industry||'',value:`${finite(r.rank)!==null?`Rank ${r.rank} / `:''}RS189 ${num(r.rs189,1)}`})),'data/ui_view_model.json.core12.rows','回復時にはその時点の順位で再計算。これは現在値による待機候補。');
    notConnected(card('t-alloc','エクイティカーブ×21日EMA'),'エクイティカーブ×21日EMA Equity Curve','口座資産の時系列データが未接続です。数値は推測しません。','account-equity-history');
  }

  function renderCore(view) {
    const core=view.core12||{}, metrics=metricMap(view), rows=Array.isArray(core.rows)?core.rows:[];
    bindLiquidityUtility('t-port','data/ui_view_model.json.core12.rows');
    simpleList(card('t-port','レジーム警戒灯'),'レジーム警戒灯 Regime Early-Warning',[{label:'Market Mode',value:core.market_mode||metricDisplay(metrics,'market_mode')},{label:'NQSAR',value:metricDisplay(metrics,'nqsar')},{label:'50MA Breadth',value:metricDisplay(metrics,'breadth50')},{label:'新規上限',value:core.max_new_total_slots??'—'}],'data/ui_view_model.json.core12+daily.metrics');
    const entrants=core.new_entrants||{};simpleList(card('t-port','新規参入'),'新規参入（ポート候補36位圏） New Entrants',(entrants.rows||[]).map((r)=>({ticker:r.ticker,value:`現在 ${r.rank??'—'}位 / 20日前 ${r.prior_rank??'圏外'}`})),'data/ui_view_model.json.core12.new_entrants');
    const cols=[{label:'#',key:'_rank'},{label:'Ticker',key:'ticker',ticker:true,align:'left'},{label:'Final',format:(r)=>num(r.final_score,1)},{label:'RS63',format:(r)=>num(r.rs63,1)},{label:'RS126',format:(r)=>num(r.rs126,1)},{label:'RS189',format:(r)=>num(r.rs189,1)},{label:'Price',format:(r)=>finite(r.price)===null?'—':`$${num(r.price,2)}`},{label:'DDV20',format:(r)=>finite(r.ddv20)===null?'—':`$${(r.ddv20/1e6).toFixed(0)}M`},{label:'Trend',format:(r)=>finite(r.sma50)!==null&&finite(r.sma200)!==null?(r.sma50>r.sma200?'50>200':'50≤200'):'—'}];
    const ranked=rows.map((r)=>({...r,_rank:finite(r.rank)!==null?r.rank:'—'}));
    richTable(card('t-port','個別株スリーブ Core 12'),'個別株スリーブ Core 12',cols,ranked.slice(0,12),'data/ui_view_model.json.core12.rows','順位だけでなくFinal Score・3期間RS・流動性・トレンドを同時確認。');
    richTable(card('t-port','RSリーダー控え'),'RSリーダー控え Bench',cols,ranked.slice(12,24),'data/ui_view_model.json.core12.rows');
    cards('t-port').filter((node)=>!node.dataset.v38TruthSource).forEach((node)=>{const title=originalTitle(node);if(title.includes('V38 Data'))simpleList(node,'Core 12 データ品質',[{label:'Eligible',value:rows.length},{label:'Market Mode',value:core.market_mode||'—'},{label:'新規上限',value:core.max_new_total_slots??'—'}],'data/ui_view_model.json.core12');else if(title.includes('個別株スリーブ'))richTable(node,'個別株スリーブ Core 12',cols,ranked.slice(0,12),'data/ui_view_model.json.core12.rows');});
  }

  function bindLiquidityUtility(sectionId, source) {
    const utility=document.querySelector(`#${sectionId} .card.liqstick`);
    if(!utility)return;
    mark(utility,source,'READY');
    const apply=(button)=>{
      utility.querySelectorAll('button').forEach((x)=>x.classList.toggle('active',x===button));
      const label=String(button.textContent||'');
      const m=label.match(/\$(\d+)M/);
      const threshold=m?Number(m[1]):-1;
      document.querySelectorAll(`#${sectionId} .v38-canonical-row[data-liq]`).forEach((row)=>{
        const value=Number(row.dataset.liq||0);
        row.hidden=threshold>=0&&value<threshold;
      });
    };
    utility.querySelectorAll('button').forEach((button)=>{
      button.removeAttribute('onclick');
      button.addEventListener('click',()=>apply(button));
    });
    const active=utility.querySelector('button.active')||utility.querySelector('button');
    if(active)apply(active);
  }

  function setupRows(cardNode,title,rows,source,subtitle) {
    simpleList(cardNode,title,(rows||[]).map((r)=>({ticker:r.ticker,ddv20:r.ddv20,meta:[r.industry,r.stage2?'Stage2':'',r.confluence&&r.confluence.length?r.confluence.join(' / '):''].filter(Boolean).join(' · '),value:`RS189 ${num(r.rs189,1)} · piv ${pct(r.pivot_dist)} · DDV ${finite(r.ddv20)===null?'—':`$${(r.ddv20/1e6).toFixed(1)}M`}`})),source,subtitle);
  }
  function renderSetups(view) {
    const data = view.setups || {};
    bindLiquidityUtility('t-today','data/ui_view_model.json.setups');
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
    if(!cardNode)return;const rows=Array.isArray(((view.rotation||{}).money_flow||{}).rows)?view.rotation.money_flow.rows:[];
    heading(cardNode,'資金フロー（GICS11＋スタイル）','GICS11セクター＋スタイル5本をSPYとの相対力で配置。横=相対力（100が市場並み）、縦=その10日モメンタム。重複のない集合で「資金がどこへ移ったか」を見る。');
    if(rows.length<11){cardNode.appendChild(el('div','empty','GICS11系列が揃っていません。'));mark(cardNode,'data/ui_view_model.json.rotation.money_flow','ERROR','RRG_GICS_SERIES_INCOMPLETE');return;}
    const W=1040,H=720,CX=W/2,CY=H/2,svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.classList.add('v38-rrg-svg');svg.dataset.v38Rrg='source';svg.setAttribute('viewBox',`0 0 ${W} ${H}`);svg.setAttribute('role','img');svg.setAttribute('aria-label','Relative Rotation Graph');
    [['#dff2e5',CX,0,CX,CY],['#e6eef9',0,0,CX,CY],['#f7eadb',0,CY,CX,CY],['#f3dede',CX,CY,CX,CY]].forEach(([fill,x,y,w,h])=>{const r=document.createElementNS(svg.namespaceURI,'rect');r.setAttribute('x',x);r.setAttribute('y',y);r.setAttribute('width',w);r.setAttribute('height',h);r.setAttribute('fill',fill);r.setAttribute('opacity','.72');svg.appendChild(r);});
    [['主導',W-24,28,'end'],['改善',24,28,'start'],['停滞',24,H-18,'start'],['弱化',W-24,H-18,'end']].forEach(([txt,x,y,anc])=>{const t=document.createElementNS(svg.namespaceURI,'text');t.textContent=txt;t.setAttribute('x',x);t.setAttribute('y',y);t.setAttribute('text-anchor',anc);t.setAttribute('class','v38-rrg-quadrant');svg.appendChild(t);});
    const axisX=document.createElementNS(svg.namespaceURI,'line'),axisY=document.createElementNS(svg.namespaceURI,'line');axisX.setAttribute('x1',24);axisX.setAttribute('x2',W-24);axisX.setAttribute('y1',CY);axisX.setAttribute('y2',CY);axisY.setAttribute('x1',CX);axisY.setAttribute('x2',CX);axisY.setAttribute('y1',24);axisY.setAttribute('y2',H-24);[axisX,axisY].forEach((a)=>{a.setAttribute('class','v38-rrg-cross');svg.appendChild(a);});
    const vals=rows.map((r)=>[finite(r.x),finite(r.y)]).filter((r)=>r[0]!==null&&r[1]!==null),span=Math.max(3,...vals.flatMap(([x,y])=>[Math.abs(x-100),Math.abs(y-100)]));const SX=(x)=>CX+(x-100)/span*(CX-90),SY=(y)=>CY-(y-100)/span*(CY-75);
    rows.forEach((r)=>{const x=finite(r.x),y=finite(r.y);if(x===null||y===null)return;const g=document.createElementNS(svg.namespaceURI,'g');g.dataset.v38Ticker=r.ticker||'';const c=document.createElementNS(svg.namespaceURI,'circle');c.setAttribute('cx',SX(x));c.setAttribute('cy',SY(y));c.setAttribute('r',SECTORS.includes(r.ticker)?10:7);c.setAttribute('class',y>=100?'v38-rrg-point up':'v38-rrg-point down');const t=document.createElementNS(svg.namespaceURI,'text');t.textContent=r.label||SECTOR_LABELS[r.ticker]||STYLE_LABELS[r.ticker]||r.ticker;t.setAttribute('x',SX(x)+12);t.setAttribute('y',SY(y)+4);t.setAttribute('class','v38-rrg-label');g.append(c,t);svg.appendChild(g);});
    const xlab=document.createElementNS(svg.namespaceURI,'text');xlab.textContent='相対強度 →';xlab.setAttribute('x',W-26);xlab.setAttribute('y',CY-10);xlab.setAttribute('text-anchor','end');xlab.setAttribute('class','v38-rrg-axislabel');svg.appendChild(xlab);const ylab=document.createElementNS(svg.namespaceURI,'text');ylab.textContent='相対モメンタム →';ylab.setAttribute('x',CX+12);ylab.setAttribute('y',28);ylab.setAttribute('class','v38-rrg-axislabel');svg.appendChild(ylab);
    const plot=el('div','v38-rrg-source');plot.appendChild(svg);cardNode.appendChild(plot);const legend=el('div','v38-rrg-legend');legend.innerHTML='<span><i class="gics"></i>GICS11セクター</span><span><i class="style"></i>スタイル</span><span>中心=100</span>';cardNode.appendChild(legend);const qrows=el('div','v38-rrg-qrows');[['主導',(r)=>finite(r.x)>=100&&finite(r.y)>=100],['改善',(r)=>finite(r.x)<100&&finite(r.y)>=100],['弱化',(r)=>finite(r.x)>=100&&finite(r.y)<100],['停滞',(r)=>finite(r.x)<100&&finite(r.y)<100]].forEach(([q,pred])=>{const qr=el('div','v38-rrg-qrow');qr.appendChild(el('span','v38-rrg-qname',q));const chips=el('div','v38-rrg-chips');rows.filter(pred).sort((a,b)=>(finite(b.x)||0)-(finite(a.x)||0)).forEach((r)=>{const name=r.label||SECTOR_LABELS[r.ticker]||STYLE_LABELS[r.ticker]||r.ticker;const ch=el('span','v38-rrg-chip',`${name} ${r.ticker}`);chips.appendChild(ch);});if(!chips.childElementCount)chips.appendChild(el('span','mut','なし'));qr.appendChild(chips);qrows.appendChild(qr);});cardNode.appendChild(qrows);mark(cardNode,'data/ui_view_model.json.rotation.money_flow','READY');
  }
  function renderRotationHeatmap(cardNode,view){if(!cardNode)return;heading(cardNode,'セクター温度マップ','セクターETFの騰落率を強い順に確認。緑=上昇、赤=下落、濃さ=値幅。');const controls=el('div','v38-heat-controls'),grid=el('div','v38-sector-heatmap v38-rotation-heat');const periods=[['日','change_1d'],['週','change_1w'],['月','change_1m']];function draw(key){grid.replaceChildren();SECTORS.forEach((ticker)=>{const s=marketSummary(view,ticker),v=finite(s[key]),cell=el('div','v38-sector-cell');cell.dataset.direction=v===null?'flat':v>=0?'up':'down';cell.style.setProperty('--heat',String(Math.min(1,Math.abs(v||0)/.06)));cell.append(el('b','',SECTOR_LABELS[ticker]||ticker),el('small','mut',ticker),el('span','',pct(v)));grid.appendChild(cell);});}periods.forEach(([lab,key],i)=>{const b=el('button',i===1?'active':'',lab);b.type='button';b.dataset.v38HeatPeriod=key;b.addEventListener('click',()=>{controls.querySelectorAll('button').forEach((x)=>x.classList.toggle('active',x===b));draw(key);});controls.appendChild(b);});cardNode.append(controls,grid);draw('change_1w');mark(cardNode,'data/ui_view_model.json.daily.market_summaries','READY');}
  function ensureBreadthQualityCard(view){
    const section=document.getElementById('t-rotation');if(!section)return;
    let node=section.querySelector('.card[data-v38-generated="breadth-quality"]');
    if(!node){const heads=Array.from(section.querySelectorAll('.msec'));const h=heads.find((x)=>String(x.textContent||'').includes('②'));node=el('div','card v38-breadth-quality');node.dataset.v38Generated='breadth-quality';if(h&&h.nextSibling)h.parentNode.insertBefore(node,h.nextSibling);else section.appendChild(node);}
    heading(node,'指数と中身の乖離','左=セクターETFの相対力（100が市場並み）。右=同領域の自ユニバースのRS63・50日線上比率・銘柄数。指数だけ強く中身が薄い状態を見分ける。');
    const diag=Array.isArray(((view.rotation||{}).diagnostics||{}).sector)?view.rotation.diagnostics.sector:[];
    const flow=Array.isArray(((view.rotation||{}).money_flow||{}).rows)?view.rotation.money_flow.rows:[];
    const byGroup=new Map(diag.map((r)=>[String(r.group||''),r])),byTicker=new Map(flow.map((r)=>[String(r.ticker||''),r]));
    const rows=[];
    GICS_DIAG_GROUPS.forEach(([ja,ticker,groups])=>{const parts=groups.map((g)=>byGroup.get(g)).filter(Boolean);const idx=byTicker.get(ticker);if(!parts.length||!idx)return;const denom=parts.reduce((a,r)=>a+(finite(r.member_count)||1),0)||1;const wavg=(key)=>parts.reduce((a,r)=>a+(finite(r[key])||0)*(finite(r.member_count)||1),0)/denom;const n=parts.reduce((a,r)=>a+(finite(r.member_count)||0),0);const x=finite(idx.x),br=wavg('above_sma50_pct'),rs=wavg('rs63_avg');const q=x===null?'—':(x>=100?(br>=50?'主導':'指数先行'):(br>=50?'中身改善':'停滞'));rows.push({ja,ticker,x,br,rs,n,q});});
    rows.sort((a,b)=>(finite(b.x)||0)-(finite(a.x)||0)||b.br-a.br);
    const list=el('div','v38-ivb-source');
    rows.forEach((r)=>{const warn=r.x>=100&&r.br<50?'⚠':r.br>=60?'◎':'・';const row=el('div','ivbrow v38-ivb-row');row.innerHTML=`<div class="ivbn">${warn} ${html(r.ja)} <span class="mut">${html(r.ticker)}</span></div><div class="ivbm ${warn==='⚠'?'neg':warn==='◎'?'pos':'mut'}">指数 ${num(r.x,1)}（${html(r.q)}） ／ 中身 RS63 ${num(r.rs,1)} ・ 50日線上 ${num(r.br,0)}% ・ ${Math.round(r.n)}銘柄</div>`;list.appendChild(row);});
    if(!rows.length)list.appendChild(el('div','empty','セクター別の指数と中身を接続できません。'));
    node.appendChild(list);mark(node,'data/ui_view_model.json.rotation.money_flow+diagnostics.sector','READY');
  }
  function renderLeadingGroups(cardNode,rows){
    if(!cardNode)return;heading(cardNode,'主導セクター・業種','ETFではなく構成銘柄の実データから算出。現行RS63・1カ月騰落・50日線上比率・銘柄数を、元ネタの主導グループ書式で表示。');
    const list=el('div','bglist v38-leading-groups-source');
    (rows||[]).slice(0,18).forEach((r)=>{const line=el('div','bgrow');const name=TV_SECTOR_LABELS[r.group]||r.group||'—';line.innerHTML=`<div class="bgname">${html(name)}</div><div class="bgmeta">RS63 ${num(r.rs63_avg,1)} ・ 1カ月 ${pct(r.ret20_avg)} ・ 50日線上 ${finite(r.above_sma50_pct)===null?'—':num(r.above_sma50_pct,0)+'%'} ・ ${finite(r.member_count)===null?'—':Math.round(Number(r.member_count))+'銘柄'}</div>`;list.appendChild(line);});
    if(!list.childElementCount)list.appendChild(el('div','empty','該当なし'));cardNode.appendChild(list);mark(cardNode,'data/ui_view_model.json.rotation.diagnostics.sector','READY');
  }
  function renderRotation(view) {
    renderMoneyFlow(card('t-rotation','資金フロー'),view);renderRotationHeatmap(card('t-rotation','セクター温度マップ'),view);ensureBreadthQualityCard(view);
    const rot=view.rotation||{},diag=rot.diagnostics||{},industries=Array.isArray(diag.industry)?diag.industry:[],sectors=Array.isArray(diag.sector)?diag.sector:[],fine=Array.isArray(rot.fine_theme_rows)?rot.fine_theme_rows:[],major=Array.isArray(rot.major_theme_groups)?rot.major_theme_groups:[];
    renderLeadingGroups(card('t-rotation','主導セクター・業種'),sectors);
    const strong=card('t-rotation','強い業種の主導株');if(strong){heading(strong,'強い業種の主導株','強いサブテーマごとに、復元済み定義（RS189≥85かつ200日線上）を満たす主導株をまとめて表示。表示専用で売買ゲートではありません。');const list=el('div','bglist v38-strong-theme-list'),rsMap=new Map((view.rs&&Array.isArray(view.rs.rows)?view.rs.rows:[]).map((r)=>[String(r.ticker||''),r]));industries.filter((r)=>Array.isArray(r.leaders)&&r.leaders.length).slice(0,12).forEach((r)=>{const line=el('div','bgrow v38-strong-theme-group');const name=el('div','bgname',r.group||'—'),meta=el('div','bgmeta',`${r.major_theme||''}${r.major_theme?' ・ ':''}テーマRS ${num(r.theme_rs,1)} ・ RS63 ${num(r.rs63_avg,1)} ・ 1カ月 ${pct(r.ret20_avg)}`),chips=el('div','chips v38-strong-theme-chips');(r.leaders||[]).slice(0,5).forEach((ticker)=>{const raw=rsMap.get(String(ticker))||{};const chip=el('button','chip v38-ticker-link',`${ticker}  RS${num(raw.rs189,0)}`);chip.type='button';chip.dataset.v38Ticker=ticker;chips.appendChild(chip);});line.append(name,meta,chips);list.appendChild(line);});if(!list.childElementCount)list.appendChild(el('div','empty','該当なし'));strong.appendChild(list);mark(strong,'data/ui_view_model.json.rotation.diagnostics.industry.leaders+rs.rows','READY');}
    richTable(card('t-rotation','セクターETF強弱'),'セクターETF強弱',[{label:'順位',key:'rank'},{label:'セクター',format:(r)=>SECTOR_LABELS[r.ticker]||r.ticker,align:'left'},{label:'ETF',key:'ticker',ticker:true,align:'left'},{label:'日',format:(r)=>pct(r.d1)},{label:'週',format:(r)=>pct(r.w1)},{label:'月',format:(r)=>pct(r.m1)}],SECTORS.map((ticker)=>({ticker,d1:marketSummary(view,ticker).change_1d,w1:marketSummary(view,ticker).change_1w,m1:marketSummary(view,ticker).change_1m})).sort((a,b)=>(finite(b.m1)||-99)-(finite(a.m1)||-99)).map((r,i)=>({...r,rank:i+1})),'data/ui_view_model.json.daily.market_summaries');
    richTable(card('t-rotation','サブテーマ別RS'),'サブテーマ別RS（ユニバース内）',[{label:'順位',key:'rank'},{label:'サブテーマ',key:'theme_name',align:'left'},{label:'テーマRS',format:(r)=>num(r.theme_rs,1)},{label:'RS63',format:(r)=>num(r.rs63_median,1)},{label:'RS189',format:(r)=>num(r.rs189_median,1)},{label:'1カ月',format:(r)=>pct(r.ret20_median)},{label:'主導株',format:(r)=>(r.leaders||[]).slice(0,3).join(' · ')}],fine.slice(0,24).map((r,i)=>({...r,rank:i+1})),'data/ui_view_model.json.rotation.fine_theme_rows');
    const thermometer=card('t-rotation','テーマETFの温度計');if(thermometer){heading(thermometer,'テーマ温度計','現行テーマ診断を日本語主体で表示。元ネタのテーマETF RRGとは別物なので混同しない。');const bars=el('div','v38-theme-bars');major.slice(0,16).forEach((r,i)=>{const score=finite(r.theme_rs);const row=el('div','v38-theme-bar');row.innerHTML=`<span class="rk">${i+1}</span><span class="name">${html(r.group)}</span><div class="track"><i style="width:${Math.max(0,Math.min(100,score||0))}%"></i></div><b>${num(score,1)}</b><small>${(r.leaders||[]).slice(0,3).map(html).join(' · ')}</small>`;bars.appendChild(row);});thermometer.appendChild(bars);mark(thermometer,'data/ui_view_model.json.rotation.major_theme_groups','READY');}
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
    const rs=view.rs||{},windows=rs.windows||{};let history={};try{const response=await fetch('data/rs_history.json',{cache:'no-store'});if(response.ok)history=await response.json();}catch(_){}
    const sets={};[63,126,189].forEach((p)=>sets[p]=new Set((windows[String(p)]||[]).map((r)=>r.ticker)));const inter=(a,b,c)=>Array.from(sets[a]).filter((x)=>sets[b].has(x)&&(!c||sets[c].has(x)));
    const intro=card('t-rs','RSマルチタイムフレーム比較');if(intro){heading(intro,'RSマルチタイムフレーム比較','63・126・189営業日のTop10重複を元ネタ同様に俯瞰。');const grid=el('div','rsx-overlap v38-rs-overlap');[['3期間すべて',inter(63,126,189)],['63 × 126',inter(63,126)],['126 × 189',inter(126,189)],['63 × 189',inter(63,189)]].forEach(([label,tickers])=>{const box=el('div','v38-rs-box');box.innerHTML=`<div class="rh"><span class="rl">${label}</span><span class="rn num">${tickers.length}</span></div><div class="chips">${tickers.map((t)=>`<button class="chip v38-ticker-link" data-v38-ticker="${html(t)}" type="button">${html(t)}</button>`).join('')||'<span class="mut">該当なし</span>'}</div>`;grid.appendChild(box);});intro.appendChild(grid);mark(intro,'data/ui_view_model.json.rs.windows','READY');}
    [63,126,189].forEach((period)=>{const rows=windows[String(period)]||[];richTable(card('t-rs',`RS${period} Top10`),`RS${period} Top10`,[{label:'#',key:'rank'},{label:'銘柄',key:'ticker',ticker:true,align:'left'},{label:'Industry',key:'industry',align:'left'},{label:'RS63',format:(r)=>num(r.rs63,1)},{label:'RS126',format:(r)=>num(r.rs126,1)},{label:'RS189',format:(r)=>num(r.rs189,1)},{label:'1M',format:(r)=>pct(r.ret20)},{label:'DDV',format:(r)=>r.ddv20_display||'—'}],rows,`data/ui_view_model.json.rs.windows.${period}`);});
    const pRows=((history.persistence||{}).rows)||[];const persist=card('t-rs','RS189 継続性');if(persist){heading(persist,'RS189 Leadership Persistence','Top10/Top24滞在と21営業日変化。現在のRS189だけでは見えない定着度を確認。');const groups=el('div','v38-persist-groups');const classes=['定着','新規急浮上','再浮上','失速中','一日急騰型','継続'];classes.forEach((cl)=>{const n=pRows.filter((r)=>r.classification===cl).length;if(n){const chip=el('span','v38-persist-chip',`${cl} ${n}`);chip.dataset.kind=cl;groups.appendChild(chip);}});persist.appendChild(groups);const wrap=el('div','v38-table-wrap'),table=el('table','v38-source-table v38-persist-table');table.innerHTML='<thead><tr><th class="l">Ticker</th><th>状態</th><th>連続Top10</th><th>1M Top10</th><th>1M Top24</th><th>RS189</th><th>21D順位Δ</th><th>ΔRS63/126/189</th></tr></thead>';const tb=el('tbody');pRows.slice(0,24).forEach((r)=>{const tr=el('tr');tr.innerHTML=`<td class="l"><button type="button" class="v38-ticker-link" data-v38-ticker="${html(r.ticker)}">${html(r.ticker)}</button></td><td><span class="v38-class-pill">${html(r.classification||'—')}</span></td><td>${r.consecutive_top10_observed??'—'}</td><td>${r.top10_days??'—'}</td><td>${finite(r.top24_pct)===null?'—':num(r.top24_pct,0)+'%'}</td><td>${num(r.rs189,1)}</td><td>${finite(r.rank_change)===null?'—':(r.rank_change>0?'+':'')+r.rank_change}</td><td>${num(r.delta_rs63,1)} / ${num(r.delta_rs126,1)} / ${num(r.delta_rs189,1)}</td>`;tb.appendChild(tr);});table.appendChild(tb);wrap.appendChild(table);persist.appendChild(wrap);mark(persist,'data/rs_history.json.persistence','READY');}
    const cross=(rs.rows||[]).filter((r)=>finite(r.rs63)>=85&&finite(r.rs126)>=85&&finite(r.rs189)>=85);richTable(card('t-rs','三窓一致リーダー'),'三窓一致リーダー Cross-Window Leaders',[{label:'銘柄',key:'ticker',ticker:true,align:'left'},{label:'Industry',key:'industry',align:'left'},{label:'RS63',format:(r)=>num(r.rs63,1)},{label:'RS126',format:(r)=>num(r.rs126,1)},{label:'RS189',format:(r)=>num(r.rs189,1)},{label:'52W距離',format:(r)=>pct(r.dist52)}],cross,'data/ui_view_model.json.rs.rows');
    const historyCard=card('t-rs','Top10 IN / OUT');if(historyCard){heading(historyCard,'Top10 IN / OUT履歴','1日・1週・1カ月の入替を3期間RSごとに表示。');const grid=el('div','v38-rs-history');[63,126,189].forEach((period)=>{const block=el('div','v38-rs-history-block');block.appendChild(el('h3','',`RS${period}`));((((history.windows||{})[String(period)]||{}).comparisons)||[]).filter((r)=>r.status==='READY').forEach((r)=>{const row=el('div','v38-rs-history-row');row.innerHTML=`<b>${html(r.label)}</b><div><span class="in">IN</span> ${(r.in||[]).map((t)=>`<button type="button" class="v38-ticker-link" data-v38-ticker="${html(t)}">${html(t)}</button>`).join(' · ')||'なし'}</div><div><span class="out">OUT</span> ${(r.out||[]).map((t)=>html(t)).join(' · ')||'なし'}</div>`;block.appendChild(row);});grid.appendChild(block);});historyCard.appendChild(grid);mark(historyCard,'data/rs_history.json.windows','READY');}
  }

  function regimeRibbon(cardNode, records, source) {
    if (!cardNode) return;
    cardNode.replaceChildren();
    const h2=el('h2'); h2.append('地合いの帯 ',el('span','h2en','Regime History')); cardNode.appendChild(h2);
    const rows=(records||[]).filter((r)=>r&&r.state);
    if(!rows.length){cardNode.appendChild(el('div','empty','観測済みのレジーム履歴がありません。'));mark(cardNode,source,'READY','EMPTY_IS_VALID');return;}
    const wrap=el('div','ribwrap');
    const first=rows[0],last=rows.at(-1);
    const label=el('div','riblab',`レジーム履歴 ${first.date||'—'} → ${last.date||'—'}（観測${rows.length}日）`);
    const ribbon=el('div','ribbon');
    const cls={Blue:'c-bl',Green:'c-gr',Yellow:'c-yl',Red:'c-rd'};
    rows.forEach((r)=>{const cell=el('span',`rb ${cls[r.state]||''}`);cell.title=`${r.date||''} ${r.state||''}`.trim();cell.setAttribute('aria-label',cell.title);ribbon.appendChild(cell);});
    wrap.append(label,ribbon);
    if(rows.length<5)wrap.appendChild(el('div','sub','観測済み履歴のみ表示。過去分は推測しません。'));
    cardNode.appendChild(wrap);mark(cardNode,source,'READY');
  }

  function renderWeekly(view) {
    const weekly=view.weekly||{}, metrics=metricMap(view), daily=view.daily||{};
    simpleList(card('t-weekly','今週の結論'),'今週の結論 This Week',[
      {label:'Market Mode',value:metricDisplay(metrics,'market_mode')},{label:'NQSAR',value:metricDisplay(metrics,'nqsar')},{label:'MC57',value:metricDisplay(metrics,'mc57')},{label:'50MA Breadth',value:metricDisplay(metrics,'breadth50')}
    ],'data/ui_view_model.json.daily.metrics');
    notConnected(card('t-weekly','来週の経済指標'),'来週の経済指標 Next Week','経済指標カレンダーの取得元が未接続です。日付は推測しません。','economic-calendar');
    simpleList(card('t-weekly','構造マクロ'),'構造マクロ Structural Macro',['DX-Y.NYB','CL=F','GC=F'].map((ticker)=>({ticker,value:`1W ${pct(marketSummary(view,ticker).change_1w)} · 1M ${pct(marketSummary(view,ticker).change_1m)}`})),'data/ui_view_model.json.daily.market_summaries');
    simpleList(card('t-weekly','金利レジーム'),'金利レジーム Rates',[{label:'米10年',value:`${num(marketSummary(view,'^TNX').close,2)}%`},{label:'米5年',value:`${num(marketSummary(view,'^FVX').close,2)}%`},{label:'IEF',value:`1W ${pct(marketSummary(view,'IEF').change_1w)}`}],'data/ui_view_model.json.daily.market_summaries');
    simpleList(card('t-weekly','マクロ圧力'),'マクロ圧力 Macro Pressure',[{label:'VIX',value:num(marketSummary(view,'^VIX').close,2)},{label:'HYG',value:`1W ${pct(marketSummary(view,'HYG').change_1w)}`},{label:'DXY',value:`1W ${pct(marketSummary(view,'DX-Y.NYB').change_1w)}`}],'data/ui_view_model.json.daily.market_summaries');
    const changes=weekly.changes||weekly.diff||[];
    if(Array.isArray(changes)&&changes.length)simpleList(card('t-weekly','今週の変化'),'今週の変化 Weekly Diff',changes.map((r)=>({label:r.label||r.key||r.name,value:r.display||r.value||'—'})),'data/ui_view_model.json.weekly.changes');
    else simpleList(card('t-weekly','今週の変化'),'今週の変化 Weekly Diff',[{label:'Breadth50',value:metricDisplay(metrics,'breadth50')},{label:'Breadth200',value:metricDisplay(metrics,'breadth200')},{label:'MC57',value:metricDisplay(metrics,'mc57')}],'data/ui_view_model.json.daily.metrics');
    const regime=((daily.display_observations||{}).regime_history)||{};
    const regimeRows=regime.records||regime.rows||regime.series||[];
    regimeRibbon(card('t-weekly','地合いの帯'),regimeRows,'data/ui_view_model.json.daily.display_observations.regime_history.records');
    simpleList(card('t-weekly','週次騰落ボード'),'週次騰落ボード Weekly Movers',['QQQ','SPY','RSP','IWM'].map((ticker)=>({ticker,value:`1W ${pct(marketSummary(view,ticker).change_1w)} · 1M ${pct(marketSummary(view,ticker).change_1m)}`})),'data/ui_view_model.json.daily.market_summaries');
    simpleList(card('t-weekly','Breadth'),'Breadth',[{label:'50MA',value:metricDisplay(metrics,'breadth50')},{label:'200MA',value:metricDisplay(metrics,'breadth200')}],'data/ui_view_model.json.daily.metrics');
    simpleList(card('t-weekly','Data Quality'),'Data Quality',[{label:'Stock coverage',value:finite(daily.stock_data_coverage)===null?'—':pval(100*daily.stock_data_coverage,2)},{label:'Breadth coverage',value:finite(daily.breadth_coverage)===null?'—':pval(100*daily.breadth_coverage,2)}],'data/ui_view_model.json.daily');
    simpleList(card('t-weekly','レバレッジ'),'レバレッジ条件 Leverage Conditions',[{label:'通常TQQQ',value:'30%'},{label:'Panic上限',value:'80%'},{label:'総エクスポージャー',value:'原則100%以内'}],'data/ui_view_model.json.rules');
    notConnected(card('t-weekly','自分 vs QQQ円建て'),'自分 vs QQQ円建て My Week','口座損益の時系列データが未接続です。値は推測しません。','account-equity-history');
  }

  function optionRows(options,bucket) {
    const raw=(((options||{}).buckets)||{})[bucket];
    if(Array.isArray(raw)) return raw;
    if(raw&&Array.isArray(raw.rows)) return raw.rows;
    return [];
  }
  function renderOptionCard(cardNode,bucket,rows,source) {
    if(!cardNode)return;
    cardNode.replaceChildren();
    const hdr=el('div','hdr');
    const h2=el('h2');h2.append(bucket.replace('-','–')+' DTE');
    const en={ '0-6':'Short Term','7-21':'Swing','22-45':'Medium Term','0-45':'Multi-expiry' }[bucket]||'';
    if(en)h2.append(' ',el('span','h2en',en));hdr.appendChild(h2);cardNode.appendChild(hdr);
    cardNode.appendChild(el('div','sub','現行producerの実測Wall / Gamma Flip / Expected Move / Qualityを元ネタ行書式へ接続。未復元の推測値は表示しません。'));
    if(!rows.length){cardNode.appendChild(el('div','empty','このDTE bucketの該当データはありません。'));mark(cardNode,source,'READY','EMPTY_IS_VALID');cardNode.dataset.v38OptionBucket=bucket;return;}
    rows.slice(0,20).forEach((r,index)=>{
      const item=el('div','rsx-item');
      const row=el('div','rsx-row'),rank=el('span','rsx-rk',finite(r.data_rank)!==null?r.data_rank:index+1),name=el('div','rsx-name'),nameTop=el('div'),ticker=tickerButton(r.ticker),quality=String(r.quality||'').trim();
      nameTop.appendChild(ticker);if(quality)nameTop.appendChild(el('span','rsx-badge',quality));name.append(nameTop,el('small','',r.expiry||'—'));
      const score=el('div','rsx-score');score.append(el('b','',finite(r.data_rank)!==null?r.data_rank:'—'),el('small','','Data Rank'));row.append(rank,name,score);
      const sub=el('div','rsx-sub'),walls=el('span','rsx-nums');walls.append('Call / Flip / Put ',el('b','',`${num(r.call_wall,2)} / ${num(r.gamma_flip,2)} / ${num(r.put_wall,2)}`));
      const move=el('span','rsx-ret');move.append('Expected Move ',el('b','',finite(r.expected_move_pct)===null?'—':`±${(100*r.expected_move_pct).toFixed(1)}%`));if(quality)move.append(' ・ Quality ',el('b','',quality));sub.append(walls,move);item.append(row,sub);cardNode.appendChild(item);
    });
    cardNode.dataset.v38OptionBucket=bucket;mark(cardNode,source,'READY');
  }
  function renderOptions(options) {
    const section=document.getElementById('t-options'); if(!section)return;
    OPTION_BUCKETS.forEach((bucket)=>{
      const sourceTitle=bucket.replace('-','–')+' DTE';
      const c=Array.from(section.querySelectorAll('.card')).find((node)=>originalTitle(node).includes(sourceTitle));
      renderOptionCard(c,bucket,optionRows(options,bucket),`data/options/index.json.buckets.${bucket}`);
    });
  }

  let publishSparkSeq = 0;
  function publishSpark(values, color) {
    const points=(values||[]).map((v)=>finite(v)).filter((v)=>v!==null);
    if(points.length<2)return '<div class="p-empty">履歴不足</div>';
    const W=680,H=68,P=6,lo=Math.min(...points),hi=Math.max(...points),span=hi-lo||1;
    const X=(i)=>P+i*(W-2*P)/Math.max(1,points.length-1),Y=(v)=>H-P-(v-lo)/span*(H-2*P);
    const coords=points.map((v,i)=>`${X(i).toFixed(1)},${Y(v).toFixed(1)}`);
    const area=`M${coords[0]} ${coords.slice(1).map((p)=>`L${p}`).join(' ')} L${X(points.length-1).toFixed(1)},${H-P} L${X(0).toFixed(1)},${H-P} Z`;
    const gid=`pubsp${++publishSparkSeq}`, c=color||'#17685C';
    return `<svg class="pspark" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none"><defs><linearGradient id="${gid}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${c}" stop-opacity=".28"/><stop offset="1" stop-color="${c}" stop-opacity="0"/></linearGradient></defs><path d="${area}" fill="url(#${gid})"/><polyline points="${coords.join(' ')}" fill="none" stroke="${c}" stroke-width="2"/><circle cx="${X(points.length-1).toFixed(1)}" cy="${Y(points.at(-1)).toFixed(1)}" r="3.2" fill="${c}"/></svg>`;
  }
  function publishCss() {
    return `*{box-sizing:border-box}html,body{margin:0;width:100%;height:100%;overflow:hidden}body{background:#E9E7DF;color:#1B1D1C;font-family:-apple-system,BlinkMacSystemFont,"Helvetica Neue",Arial,"Hiragino Sans","Noto Sans JP",sans-serif}.stage{position:relative;width:100vw;height:100vh;overflow:hidden}.card{position:absolute;left:50%;top:50%;width:1680px;height:1080px;transform-origin:center center;padding:22px 26px 16px;background:#E9E7DF;display:flex;flex-direction:column;--ink:#1B1D1C;--mut:#727569;--line:#D5D1C6;--panel:#F6F4EE;--track:#DAD6CB;--accent:#17685C;--accent2:#2A9384;--pos:#1E7A4D;--neg:#B23A2E;--warn:#B07A16;--blue:#2456A6;--mono:ui-monospace,"SF Mono",Menlo,monospace}.hd{display:flex;align-items:center;gap:12px;margin-bottom:9px}.bar{width:5px;height:24px;background:var(--accent);border-radius:3px}.hd h1{font-size:24px;margin:0;font-weight:850}.state{padding:3px 11px;border:1.5px solid currentColor;border-radius:8px;font-size:13px;font-weight:800}.date{margin-left:auto;color:var(--mut);font:700 14px var(--mono)}.grid{display:grid;grid-template-columns:repeat(4,1fr);grid-template-rows:200px 150px 1fr 200px;gap:10px;flex:1;min-height:0}.panel{background:var(--panel);border:1px solid var(--line);border-radius:11px;padding:10px 12px;overflow:hidden;min-width:0}.sp2{grid-column:span 2}.title{display:flex;align-items:baseline;gap:7px;margin-bottom:6px;font-size:13.5px;font-weight:850}.title small{font-size:10.5px;color:var(--mut);font-weight:700}.big{font:850 28px var(--mono)}.sub{font-size:11px;color:var(--mut);line-height:1.4}.kv{display:grid;grid-template-columns:1fr auto;gap:7px;padding:4px 0;border-bottom:1px solid var(--line);font-size:11px}.kv:last-child{border-bottom:0}.kv span{color:var(--mut)}.kv b{font-family:var(--mono)}.pspark{width:100%;height:70px;display:block;margin-top:5px}.tbl{width:100%;border-collapse:collapse;font-size:10.5px}.tbl th{font-size:9px;color:var(--mut);padding:3px 4px;border-bottom:1.5px solid var(--line);text-align:right}.tbl th:first-child,.tbl td:first-child{text-align:left}.tbl td{padding:3px 4px;border-bottom:1px solid var(--line);text-align:right}.tk{font:800 11px var(--mono)}.pos{color:var(--pos)}.neg{color:var(--neg)}.mut{color:var(--mut)}.chips{display:flex;gap:4px;flex-wrap:wrap}.chip{padding:3px 6px;border:1px solid var(--line);border-radius:6px;background:#EEEBE3;font:750 10px var(--mono)}.rsgrid{display:grid;grid-template-columns:1fr 1fr;gap:6px}.rsbox{border:1px solid var(--line);border-radius:8px;padding:7px}.rsbox .rh{display:flex;justify-content:space-between;font-size:10px;font-weight:800}.rsbox .rn{font:850 16px var(--mono);color:var(--accent)}.themes{display:grid;grid-template-columns:1fr 1fr;gap:0 12px}.theme{display:grid;grid-template-columns:24px minmax(0,1fr) 44px;gap:6px;align-items:center;padding:4px 0;border-bottom:1px solid var(--line);font-size:10.5px}.theme .nm{font-weight:800;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.theme .rs{font:800 10.5px var(--mono);color:var(--accent);text-align:right}.rrg{position:relative;height:145px;border:1px solid var(--line);border-radius:8px;background:linear-gradient(90deg,rgba(178,58,46,.05) 50%,rgba(30,122,77,.05) 50%),linear-gradient(0deg,rgba(178,58,46,.04) 50%,rgba(30,122,77,.04) 50%)}.rrg:before,.rrg:after{content:"";position:absolute;background:rgba(80,75,65,.28)}.rrg:before{left:50%;top:0;bottom:0;width:1px}.rrg:after{top:50%;left:0;right:0;height:1px}.dot{position:absolute;transform:translate(-50%,-50%);font:800 8px var(--mono)}.flow{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}.flowcol{border-left:1px solid var(--line);padding-left:8px}.flowcol:first-child{border-left:0;padding-left:0}.flowrow{display:flex;justify-content:space-between;gap:6px;padding:3px 0;font-size:10px}.note{margin-top:auto;padding-top:6px;border-top:1px solid var(--line);font-size:9.5px;color:var(--mut)}`;
  }
  function publishFitScript(){return `<script>(function(){function fit(){var c=document.querySelector('.card');if(!c)return;var s=Math.min(innerWidth/1680,innerHeight/1080);c.style.transform='translate(-50%,-50%) scale('+s+')'}fit();addEventListener('resize',fit);setTimeout(fit,60)})()<\/script>`;}
  function publishOverviewHtml(view){
    const d=view.daily||{},m=metricMap(view),hist=Array.isArray(d.history)?d.history:[],mc=((((d.mc57_detail||{}).series||{}).mc57)||[]),mcVals=mc.map((r)=>r.value),b50=hist.map((r)=>finite(r.breadth50)*100).filter(Number.isFinite),diag=(d.market_diagnostics||{}).series||[],vp=diag.map((r)=>r.volume_participation),sent=((d.display_observations||{}).sentiment||{}),fine=((view.rotation||{}).fine_theme_rows||[]).slice(0,8),sectors=SECTORS.map((t)=>({t,d:marketSummary(view,t).change_1d,w:marketSummary(view,t).change_1w,m:marketSummary(view,t).change_1m})).sort((a,b)=>(finite(b.m)||-99)-(finite(a.m)||-99));
    const rs=view.rs||{},wins=rs.windows||{},sets={};[63,126,189].forEach((p)=>sets[p]=new Set((wins[String(p)]||[]).map((r)=>r.ticker)));const all=Array.from(sets[63]).filter((x)=>sets[126].has(x)&&sets[189].has(x));const leadGroups=[63,126,189].map((p)=>({lab:`RS${p}`,rows:(wins[String(p)]||[]).slice(0,5)}));
    const secRows=sectors.slice(0,8).map((r)=>`<tr><td class="tk">${r.t}</td><td class="${(finite(r.d)||0)>=0?'pos':'neg'}">${pct(r.d)}</td><td>${pct(r.w)}</td><td>${pct(r.m)}</td></tr>`).join('');const subRows=fine.map((r)=>`<tr><td>${html(r.theme_name)}</td><td>${num(r.theme_rs,1)}</td><td>${num(r.rs63_median,1)}</td><td>${num(r.rs189_median,1)}</td><td>${pct(r.ret20_median)}</td></tr>`).join('');const topRows=leadGroups.map((g)=>`<tr><th colspan="6" style="text-align:left">${g.lab}</th></tr>`+g.rows.map((r)=>`<tr><td>${r.rank}</td><td class="tk">${html(r.ticker)}</td><td>${num(r.rs63,1)}</td><td>${num(r.rs126,1)}</td><td>${num(r.rs189,1)}</td><td>${pct(r.ret20)}</td></tr>`).join('')).join('');
    const rateRows=['^TNX','^FVX','HYG','IEF'].map((t)=>`<div class="kv"><span>${t}</span><b>${num(marketSummary(view,t).close,2)}</b></div>`).join('');
    return `<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>${publishCss()}</style></head><body><div class="stage"><div class="card"><div class="hd"><span class="bar"></span><h1>マーケット <span class="mut" style="font-size:13px">Market</span></h1><span class="state">${html(metricDisplay(m,'nqsar'))} · ${html(metricDisplay(m,'market_mode'))}</span><span class="date">${html(view.session_date||'')}</span></div><div class="grid"><div class="panel"><div class="title">レジーム判定 <small>Regime</small></div><div class="big">${html(metricDisplay(m,'nqsar'))}</div><div class="sub">Market Mode ${html(metricDisplay(m,'market_mode'))}<br>50MA Breadth ${html(metricDisplay(m,'breadth50'))}</div><div class="note">現行V38市場モード</div></div><div class="panel"><div class="title">マーケットステータス <small>Market Status</small></div><div class="big">${html(metricDisplay(m,'mc57'))}</div>${publishSpark(mcVals,'#34a36f')}</div><div class="panel sp2"><div class="title">マーケットコメント <small>Commentary</small></div><div class="sub">${html(metricDisplay(m,'market_mode'))} / ${html(metricDisplay(m,'nqsar'))}。Breadth 50日 ${html(metricDisplay(m,'breadth50'))}、200日 ${html(metricDisplay(m,'breadth200'))}。F1 ${html(metricDisplay(m,'f1'))} / F2 ${html(metricDisplay(m,'f2'))} / F3 ${html(metricDisplay(m,'f3'))}。</div><div class="note">売買ルールではなく、当日状態を1枚で共有するための要約。</div></div><div class="panel"><div class="title">ブレッドスプレッド <small>Breadth</small></div><div class="big">${html(metricDisplay(m,'breadth50'))}</div>${publishSpark(b50,'#17685C')}</div><div class="panel"><div class="title">売買代金 <small>Dollar Volume</small></div><div class="big">${num(vp.at(-1),2)}×</div>${publishSpark(vp,'#2A9384')}</div><div class="panel"><div class="title">センチメント <small>Sentiment</small></div><div class="big">${finite(sent.composite)===null?'—':num(sent.composite,0)}</div><div class="sub">VIX ${num(marketSummary(view,'^VIX').close,2)}</div></div><div class="panel"><div class="title">先導の崩れ <small>Leader Breakdown</small></div><div class="kv"><span>F1</span><b>${html(metricDisplay(m,'f1'))}</b></div><div class="kv"><span>F2</span><b>${html(metricDisplay(m,'f2'))}</b></div><div class="kv"><span>F3</span><b>${html(metricDisplay(m,'f3'))}</b></div></div><div class="panel sp2"><div class="title">サブテーマRS <small>Sub-theme RS</small></div><table class="tbl"><thead><tr><th>Theme</th><th>Score</th><th>RS63</th><th>RS189</th><th>1M</th></tr></thead><tbody>${subRows}</tbody></table></div><div class="panel sp2"><div class="title">セクター騰落 <small>Sector Moves</small></div><table class="tbl"><thead><tr><th>ETF</th><th>1D</th><th>1W</th><th>1M</th></tr></thead><tbody>${secRows}</tbody></table></div><div class="panel sp2"><div class="title">期間別リーダー（各RS期間 上位5） <small>Period Leaders</small></div><table class="tbl"><thead><tr><th>#</th><th>Ticker</th><th>RS63</th><th>RS126</th><th>RS189</th><th>1M</th></tr></thead><tbody>${topRows}</tbody></table></div><div class="panel"><div class="title">RSマルチTF 継続性 <small>Persistence</small></div><div class="rsgrid"><div class="rsbox"><div class="rh"><span>3期間Top10</span><span class="rn">${all.length}</span></div><div class="chips">${all.map((t)=>`<span class="chip">${html(t)}</span>`).join('')||'—'}</div></div><div class="rsbox"><div class="rh"><span>RS63 Top10</span><span class="rn">${sets[63].size}</span></div></div><div class="rsbox"><div class="rh"><span>RS126 Top10</span><span class="rn">${sets[126].size}</span></div></div><div class="rsbox"><div class="rh"><span>RS189 Top10</span><span class="rn">${sets[189].size}</span></div></div></div></div><div class="panel"><div class="title">金利・マクロ圧力 <small>Rates & Macro</small></div>${rateRows}</div></div></div></div>${publishFitScript()}</body></html>`;
  }
  function publishRotationHtml(view){
    const rot=view.rotation||{},flow=((rot.money_flow||{}).rows)||[],fine=(rot.fine_theme_rows||[]).slice(0,18),major=(rot.major_theme_groups||[]).slice(0,11),sector=SECTORS.map((t)=>({t,d:marketSummary(view,t).change_1d,w:marketSummary(view,t).change_1w,m:marketSummary(view,t).change_1m}));
    const ranks=(key)=>sector.slice().sort((a,b)=>(finite(b[key])||-99)-(finite(a[key])||-99));const cols=[['前日','d'],['1週','w'],['1ヶ月','m']];const majorRank=cols.map(([lab,key])=>`<div class="flowcol"><b>${lab}</b>${ranks(key).map((r,i)=>`<div class="flowrow"><span>${i+1} ${r.t}</span><b class="${(finite(r[key])||0)>=0?'pos':'neg'}">${pct(r[key])}</b></div>`).join('')}</div>`).join('');
    const themeRows=fine.map((r,i)=>`<div class="theme"><span>${i+1}</span><span class="nm">${html(r.theme_name)}</span><span class="rs">${num(r.theme_rs,1)}</span></div>`).join('');const leaderRows=major.slice(0,8).map((r)=>`<div class="kv"><span>${html(r.group)}</span><b>${(r.leaders||[]).slice(0,4).map(html).join(' · ')||'—'}</b></div>`).join('');
    const xs=flow.map((r)=>finite(r.x)).filter((v)=>v!==null),ys=flow.map((r)=>finite(r.y)).filter((v)=>v!==null),span=Math.max(3,...flow.flatMap((r)=>[Math.abs((finite(r.x)||100)-100),Math.abs((finite(r.y)||100)-100)]));const dots=flow.map((r)=>{const x=50+((finite(r.x)||100)-100)/span*43,y=50-((finite(r.y)||100)-100)/span*43;return `<span class="dot" style="left:${x}%;top:${y}%">${html(r.ticker)}</span>`}).join('');
    return `<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>${publishCss()}</style></head><body><div class="stage"><div class="card"><div class="hd"><span class="bar"></span><h1>セクター・ローテーション <span class="mut" style="font-size:13px">Sector Rotation</span></h1><span class="state">LIVE</span><span class="date">${html(view.session_date||'')}</span></div><div class="grid" style="grid-template-rows:1fr 1fr"><div class="panel sp2"><div class="title">大分類 — 期間ごとランキング <small>Major Sectors · Rank by Period</small></div><div class="flow">${majorRank}</div></div><div class="panel sp2"><div class="title">順位フロー（大分類） <small>Rank Flow</small></div><div class="flow">${majorRank}</div></div><div class="panel sp2"><div class="title">小分類（サブテーマ）— 期間ごとランキング <small>Sub-themes · Rank by Period</small></div><div class="themes">${themeRows}</div></div><div class="panel"><div class="title">資金の流れ <small>Money Flow</small></div><div class="rrg">${dots}</div><div class="sub">横=相対強度 / 縦=相対モメンタム / 中央100</div></div><div class="panel"><div class="title">主導Themeの銘柄 <small>Leaders</small></div>${leaderRows}</div></div></div></div>${publishFitScript()}</body></html>`;
  }

  function ensurePublishControls(wrap, title) {
    if (!wrap) return null;
    let open=wrap.querySelector('.pfsbtn');
    if(!open){open=el('button','pfsbtn','⛶ 全画面表示');open.type='button';wrap.prepend(open);} else open.removeAttribute('onclick');
    let frame=wrap.querySelector('iframe.postframe');
    if(!frame){frame=el('iframe','postframe');wrap.appendChild(frame);} frame.title=title;
    let close=wrap.querySelector('.pfsclose');
    if(!close){close=el('button','pfsclose','✕');close.type='button';wrap.appendChild(close);} else close.removeAttribute('onclick');
    if(!wrap.dataset.v38PublishControlBound){
      open.addEventListener('click',()=>{wrap.classList.add('fs');document.body.classList.add('fslock');});
      close.addEventListener('click',()=>{wrap.classList.remove('fs');document.body.classList.remove('fslock');});
      wrap.dataset.v38PublishControlBound='true';
    }
    return frame;
  }
  function renderPublish(view) {
    const section=document.getElementById('t-post1'); if(!section)return;
    const wraps=Array.from(section.querySelectorAll('.postwrap'));
    const docs=[publishOverviewHtml(view),publishRotationHtml(view)];
    docs.forEach((srcdoc,index)=>{
      const frame=ensurePublishControls(wraps[index],index===0?'Market Overview share card':'Sector Rotation share card');
      if(!frame)return;
      frame.srcdoc=srcdoc;
      mark(wraps[index],index===0?'data/ui_view_model.json.daily':'data/ui_view_model.json.rotation','READY');
    });
    if(!document.documentElement.dataset.v38PublishEscape){
      document.addEventListener('keydown',(event)=>{if(event.key!=='Escape')return;document.querySelectorAll('#t-post1 .postwrap.fs').forEach((wrap)=>wrap.classList.remove('fs'));document.body.classList.remove('fslock');});
      document.documentElement.dataset.v38PublishEscape='1';
    }
    mark(section,'data/ui_view_model.json.publish','READY'); section.dataset.v38PublishCards='ready';
  }

  function renderRules(view) {
    const rules=view.rules||{},cs=cards('t-rules'),rows=rules.rows||[],normal=rows.filter((r)=>!String(r.key||'').startsWith('tqqq_panic.')),tqqq=rows.filter((r)=>String(r.key||'').startsWith('tqqq_panic.'));
    function ruleCard(node,title,data){if(!node)return;heading(node,title);const list=el('div','v38-rule-list');data.forEach((r)=>{const row=el('div','v38-rule-row');row.append(el('code','v38-rule-key',r.key),el('div','v38-rule-value',r.value));list.appendChild(row);});node.appendChild(list);mark(node,'data/ui_view_model.json.rules.rows','READY');}
    ruleCard(cs[0],'通常個別株 Normal Stock',normal);ruleCard(cs[1],'TQQQ Normal + Panic',tqqq);
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
    .v38-canonical-list{display:flex;flex-direction:column;gap:0;margin-top:6px}.v38-canonical-row{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:10px;align-items:center;padding:6px 0;border-bottom:1px solid rgba(120,110,90,.16)}.v38-canonical-row:last-child{border-bottom:0}.v38-canonical-left{min-width:0;display:flex;gap:7px;align-items:baseline;flex-wrap:wrap}.v38-canonical-left small{font-size:10.5px}.v38-canonical-value{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;text-align:right;font-size:11.5px}.v38-ticker-link{appearance:none;-webkit-appearance:none;border:0;background:transparent;padding:0;margin:0;color:inherit;font:inherit;font-weight:800;line-height:inherit;cursor:pointer;text-align:left}.v38-ticker-link:hover,.v38-ticker-link:focus{text-decoration:underline;outline:none}.v38-canonical-spark{width:100%;height:34px;display:block;margin:5px 0 0}.v38-sector-heatmap{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:7px;margin-top:10px}.v38-sector-cell{min-width:0;border:1px solid rgba(100,90,70,.16);border-radius:10px;padding:10px;background:rgba(255,255,255,.35)}.v38-sector-cell[data-direction="up"]{box-shadow:inset 0 0 0 999px rgba(38,122,77,calc(var(--heat)*.12))}.v38-sector-cell[data-direction="down"]{box-shadow:inset 0 0 0 999px rgba(184,74,66,calc(var(--heat)*.12))}.v38-sector-cell b,.v38-sector-cell small,.v38-sector-cell span{display:block}.v38-sector-cell small{font-size:8.5px;margin-top:1px}.v38-sector-cell span{font-size:10px;margin-top:4px}.v38-rrg{height:280px;position:relative;margin-top:12px;border:1px solid rgba(100,90,70,.18);border-radius:12px;background:linear-gradient(90deg,rgba(184,74,66,.05) 50%,rgba(38,122,77,.05) 50%),linear-gradient(0deg,rgba(184,74,66,.04) 50%,rgba(38,122,77,.04) 50%)}.v38-rrg:before,.v38-rrg:after{content:"";position:absolute;background:rgba(90,80,65,.25)}.v38-rrg:before{left:50%;top:0;bottom:0;width:1px}.v38-rrg:after{top:50%;left:0;right:0;height:1px}.v38-rrg-dot{position:absolute;transform:translate(-50%,-50%);border:0;border-radius:999px;padding:4px 6px;font-size:9px;font-weight:700;background:#fff;box-shadow:0 1px 5px rgba(0,0,0,.15);z-index:2}.v38-rrg-axis{position:absolute;font-size:9px;color:#777}.v38-rrg-axis.x{left:51%;bottom:2px}.v38-rrg-axis.y{left:2px;top:48%}.tkresult{width:100%;display:flex;justify-content:space-between;gap:12px;padding:9px;border:0;border-bottom:1px solid rgba(100,90,70,.15);background:transparent;text-align:left}.postwrap{position:relative}.postframe{width:100%;aspect-ratio:1680/1080;border:1px solid #D5D1C6;border-radius:12px;display:block;background:#E9E7DF}.pfsbtn,.pfsclose{font:inherit}.postwrap.fs{position:fixed;inset:0;z-index:99999;background:#E9E7DF;display:flex;align-items:center;justify-content:center;margin:0}.postwrap.fs .postframe{width:100vw;height:100vh;max-width:none;aspect-ratio:auto;border-radius:0;border:0}.postwrap.fs .pfsbtn{visibility:hidden;opacity:0;pointer-events:none}.postwrap.fs .pfsclose{display:flex;align-items:center;justify-content:center;position:fixed;top:calc(env(safe-area-inset-top,0px) + 10px);right:10px;z-index:100000;width:34px;height:34px;font-size:16px;font-weight:700;color:#fff;background:rgba(0,0,0,.45);border:1px solid rgba(255,255,255,.3);border-radius:50%;cursor:pointer}.fslock{overflow:hidden!important}.v38-source-chd{display:flex;align-items:flex-end;justify-content:space-between;gap:12px}.v38-source-chd h2{margin:0}.v38-source-now{display:flex;flex-direction:column;align-items:flex-end;line-height:1.05}.v38-source-now b{font:800 20px ui-monospace,SFMono-Regular,Menlo,monospace}.v38-source-now span{font-size:9px;color:#727569;margin-top:3px}.v38-source-chart{margin-top:8px}.v38-trend-svg{width:100%;height:180px;display:block}.v38-grid-line{stroke:rgba(80,75,65,.16);stroke-width:1}.v38-y-label{fill:#777;font-size:18px;font-weight:650}.v38-baseline{stroke:rgba(70,65,55,.45);stroke-width:1;stroke-dasharray:4 3}.v38-date-axis{display:flex;justify-content:space-between;color:#8a877d;font:600 9px ui-monospace,SFMono-Regular,Menlo,monospace;padding:2px 48px 0 6px}.v38-table-wrap{display:block;width:100%;max-width:100%;min-width:0;overflow-x:auto;overflow-y:hidden;-webkit-overflow-scrolling:touch}.v38-source-table{width:100%;border-collapse:collapse;font-size:10.5px;margin-top:6px;min-width:560px}#t-rs .card{min-width:0;max-width:100%;overflow:hidden}#t-rs .v38-table-wrap{overflow-x:auto;overscroll-behavior-x:contain}.v38-source-table th{color:#777;font-size:9px;font-weight:750;text-align:right;padding:5px 6px;border-bottom:1px solid rgba(100,90,70,.25);white-space:nowrap}.v38-source-table td{text-align:right;padding:6px;border-bottom:1px solid rgba(100,90,70,.14);font-variant-numeric:tabular-nums}.v38-source-table th.l,.v38-source-table td.l{text-align:left}.v38-rrg-source{margin-top:10px;border:1px solid rgba(100,90,70,.18);border-radius:12px;overflow:hidden}.v38-rrg-svg{display:block;width:100%;height:auto;aspect-ratio:1040/720}.v38-rrg-cross{stroke:rgba(70,65,55,.38);stroke-width:1.5;stroke-dasharray:5 4}.v38-rrg-quadrant{font-size:22px;font-weight:800;fill:#706d65}.v38-rrg-axislabel{font-size:18px;font-weight:750;fill:#777}.v38-rrg-point{stroke:#fff;stroke-width:2}.v38-rrg-point.up{fill:#2f8d61}.v38-rrg-point.down{fill:#b45d52}.v38-rrg-label{font-size:17px;font-weight:800;fill:#2a2926}.v38-rrg-legend{display:flex;gap:14px;flex-wrap:wrap;font-size:10px;color:#777;margin-top:7px}.v38-rrg-qrows{display:grid;gap:5px;margin-top:9px}.v38-rrg-qrow{display:grid;grid-template-columns:38px minmax(0,1fr);gap:7px;align-items:start}.v38-rrg-qname{font-size:10px;font-weight:900;color:#5f5b52}.v38-rrg-chips{display:flex;gap:5px;flex-wrap:wrap}.v38-rrg-chip{border:1px solid #d5d1c6;border-radius:999px;padding:3px 7px;background:#f6f4ee;font-size:9px;font-weight:750}.v38-heat-controls{display:flex;gap:6px;margin:7px 0}.v38-heat-controls button{border:1px solid #d5d1c6;background:#f6f4ee;border-radius:999px;padding:4px 9px;font:700 10px inherit}.v38-heat-controls button.active{background:#1b1d1c;color:#fff}.v38-pair-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:8px}.v38-pair{border:1px solid rgba(100,90,70,.18);border-radius:10px;padding:9px;background:rgba(255,255,255,.3)}.v38-pair-title{font-weight:800;font-size:11px}.v38-pair-title small{color:#777}.v38-pair-values{display:flex;justify-content:space-between;gap:8px;font-size:10px;margin-top:5px}.v38-breadth-grid{margin-top:10px;display:grid;gap:5px}.v38-breadth-row{display:grid;grid-template-columns:minmax(100px,1.4fr) minmax(80px,3fr) 40px;gap:8px;align-items:center;font-size:10px}.v38-breadth-bar{height:7px;background:#e0ddd4;border-radius:99px;overflow:hidden}.v38-breadth-bar i{display:block;height:100%;background:#2a9384;border-radius:99px}.v38-theme-bars{display:grid;gap:6px;margin-top:8px}.v38-theme-bar{display:grid;grid-template-columns:22px minmax(100px,1.2fr) minmax(80px,2fr) 42px minmax(100px,1fr);gap:7px;align-items:center;font-size:9.5px}.v38-theme-bar .track{height:7px;background:#e0ddd4;border-radius:99px;overflow:hidden}.v38-theme-bar .track i{display:block;height:100%;background:#17685c}.v38-theme-bar small{color:#777;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.v38-rs-overlap{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:10px}.v38-rs-box{border:1px solid rgba(100,90,70,.18);border-radius:10px;padding:10px;background:rgba(255,255,255,.28)}.v38-rs-box .rh{display:flex;justify-content:space-between;align-items:center}.v38-rs-box .rn{font:850 20px ui-monospace,SFMono-Regular,Menlo,monospace}.v38-rs-box .chips{display:flex;gap:4px;flex-wrap:wrap;margin-top:7px}.v38-rs-box .chip{border:1px solid #d5d1c6;border-radius:6px;padding:3px 6px;background:#eeebe3;font-size:9.5px}.v38-persist-groups{display:flex;gap:5px;flex-wrap:wrap;margin-top:8px}.v38-persist-chip,.v38-class-pill{border:1px solid #d5d1c6;border-radius:999px;padding:3px 7px;font-size:9px;font-weight:800;background:#f6f4ee}.v38-rs-history{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin-top:8px}.v38-rs-history-block{border:1px solid rgba(100,90,70,.18);border-radius:10px;padding:9px}.v38-rs-history-block h3{margin:0 0 5px;font-size:11px}.v38-rs-history-row{display:grid;gap:3px;padding:5px 0;border-top:1px solid rgba(100,90,70,.13);font-size:9.5px}.v38-rs-history-row .in{color:#1e7a4d;font-weight:850}.v38-rs-history-row .out{color:#b23a2e;font-weight:850}.v38-rule-list{display:grid;gap:0;margin-top:8px}.v38-rule-row{display:grid;grid-template-columns:minmax(0,1.3fr) minmax(0,2fr);gap:10px;align-items:start;padding:7px 0;border-bottom:1px solid rgba(100,90,70,.15)}.v38-rule-key{white-space:normal;overflow-wrap:anywhere;word-break:break-word;font-size:9.5px;color:#6e6b63}.v38-rule-value{min-width:0;overflow-wrap:anywhere;word-break:break-word;font-size:10.5px;font-weight:700;line-height:1.35}@media(max-width:600px){.v38-sector-heatmap{grid-template-columns:repeat(2,minmax(0,1fr))}.v38-rrg{height:240px}.v38-canonical-row{grid-template-columns:minmax(0,1fr) auto;gap:8px;padding:5px 0}.v38-canonical-value{text-align:right;font-size:10.5px}.v38-canonical-left small{font-size:9.5px}.postframe{aspect-ratio:1680/1080}.v38-trend-svg{height:170px}.v38-source-table{font-size:9.5px}.v38-pair-grid{grid-template-columns:1fr}.v38-rs-overlap{grid-template-columns:1fr}.v38-rs-history{grid-template-columns:1fr}.v38-rule-row{grid-template-columns:minmax(0,1fr);gap:3px}.v38-theme-bar{grid-template-columns:20px minmax(78px,.95fr) minmax(62px,1.15fr) 34px minmax(72px,.9fr);gap:5px}.v38-theme-bar small{min-width:0;font-size:8px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
  `;document.head.appendChild(style);
})();
