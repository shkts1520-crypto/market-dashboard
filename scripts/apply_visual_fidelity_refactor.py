#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path

BINDER = Path('assets/v38-canonical-binder.js')
TEST = Path('tests/test_visual_fidelity_contract.py')

text = BINDER.read_text(encoding='utf-8')

if 'function html(value)' not in text:
    anchor = """  function el(tag, cls, text) {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined) node.textContent = String(text);
    return node;
  }
"""
    helper = anchor + """  function html(value) {
    return String(value === null || value === undefined ? '' : value)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/\"/g, '&quot;').replace(/'/g, '&#39;');
  }
"""
    if anchor not in text:
        raise SystemExit('el() anchor not found')
    text = text.replace(anchor, helper, 1)

spark = r'''  function spark(cardNode, values, key, current, label, source) {
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
'''
text, count = re.subn(
    r"  function spark\(cardNode, values, key, current, label, source\) \{.*?\n  \}\n(?=  function metricMap)",
    lambda _: spark,
    text,
    count=1,
    flags=re.S,
)
if count != 1:
    raise SystemExit(f'spark replacement count={count}')

# Do not invent ranks. Where the producer has no explicit rank, show RS only.
text = text.replace("value:`Rank ${r.rank ?? '—'} / RS189 ${num(r.rs189,1)}`", "value:`${finite(r.rank)!==null?`Rank ${r.rank} / `:''}RS189 ${num(r.rs189,1)}`")
text = text.replace("value:`Rank ${r.rank ?? '—'} · RS189 ${num(r.rs189,1)}`", "value:`${finite(r.rank)!==null?`Rank ${r.rank} · `:''}RS189 ${num(r.rs189,1)}`")
text = text.replace("value:`Rank ${r.rank??'—'} · RS189 ${num(r.rs189,1)}`", "value:`${finite(r.rank)!==null?`Rank ${r.rank} · `:''}RS189 ${num(r.rs189,1)}`")

publish_block = r'''  let publishSparkSeq = 0;
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
    return `*{box-sizing:border-box}html,body{margin:0;width:100%;height:100%;overflow:hidden}body{background:#E9E7DF;color:#1B1D1C;font-family:-apple-system,BlinkMacSystemFont,"Helvetica Neue",Arial,"Hiragino Sans","Noto Sans JP",sans-serif}.stage{position:relative;width:100vw;height:100vh;overflow:hidden}.card{position:absolute;left:50%;top:50%;width:1680px;height:1080px;transform-origin:center center;padding:22px 26px 16px;background:#E9E7DF;display:flex;flex-direction:column;--ink:#1B1D1C;--mut:#727569;--line:#D5D1C6;--panel:#F6F4EE;--accent:#17685C;--pos:#1E7A4D;--neg:#B23A2E;--warn:#B07A16;--blue:#2456A6;--mono:ui-monospace,"SF Mono",Menlo,monospace}.hd{display:flex;align-items:center;gap:12px;margin-bottom:12px}.bar{width:5px;height:26px;background:var(--accent);border-radius:3px}.hd h1{font-size:25px;margin:0;font-weight:850}.state{padding:4px 11px;border:1.5px solid currentColor;border-radius:8px;font-size:13px;font-weight:800}.date{margin-left:auto;color:var(--mut);font:700 14px var(--mono)}.grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));grid-template-rows:220px 220px 1fr;gap:10px;flex:1;min-height:0}.panel{background:var(--panel);border:1px solid var(--line);border-radius:11px;padding:12px 14px;overflow:hidden;min-width:0}.span2{grid-column:span 2}.title{display:flex;align-items:baseline;gap:7px;margin-bottom:8px;font-size:14px;font-weight:850}.title small{font-size:10.5px;color:var(--mut);font-weight:700}.big{font:850 31px var(--mono);letter-spacing:-.03em}.sub{font-size:11.5px;color:var(--mut);line-height:1.45}.kv{display:grid;grid-template-columns:1fr auto;gap:8px;padding:5px 0;border-bottom:1px solid var(--line);font-size:12px}.kv:last-child{border-bottom:0}.kv span{color:var(--mut)}.kv b{font-family:var(--mono)}.pspark{width:100%;height:68px;display:block;margin-top:8px}.p-empty{font-size:11px;color:var(--mut);padding:18px 0}.mini4{display:grid;grid-template-columns:repeat(4,1fr);gap:7px}.mini{border:1px solid var(--line);border-radius:8px;padding:9px;text-align:center}.mini .k{font-size:10px;color:var(--mut);font-weight:750}.mini .v{font:850 20px var(--mono);margin-top:4px}.tbl{width:100%;border-collapse:collapse;font-size:11.5px}.tbl th{font-size:9.5px;color:var(--mut);text-align:right;padding:4px 5px;border-bottom:1.5px solid var(--line)}.tbl th:first-child,.tbl td:first-child{text-align:left}.tbl td{padding:4px 5px;text-align:right;border-bottom:1px solid var(--line)}.tbl tr:last-child td{border-bottom:0}.tk{font:800 12px var(--mono)}.pos{color:var(--pos)}.neg{color:var(--neg)}.mut{color:var(--mut)}.chips{display:flex;gap:5px;flex-wrap:wrap}.chip{padding:3px 7px;border:1px solid var(--line);border-radius:6px;background:#EEEBE3;font:750 10px var(--mono)}.themes{display:grid;grid-template-columns:1fr 1fr;gap:0 16px}.theme{display:grid;grid-template-columns:24px minmax(0,1fr) auto;gap:7px;align-items:center;padding:5px 0;border-bottom:1px solid var(--line);font-size:11px}.theme .rk{color:var(--mut);font:700 10px var(--mono)}.theme .nm{font-weight:800;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.theme .rs{font:800 11px var(--mono);color:var(--accent)}.note{margin-top:auto;padding-top:8px;border-top:1px solid var(--line);font-size:10.5px;color:var(--mut)}`;
  }
  function publishFitScript() {
    return `<script>(function(){function fit(){var c=document.querySelector('.card');if(!c)return;var s=Math.min(innerWidth/1680,innerHeight/1080);c.style.transform='translate(-50%,-50%) scale('+s+')'}fit();addEventListener('resize',fit);setTimeout(fit,60)})()<\/script>`;
  }
  function publishOverviewHtml(view) {
    const daily=view.daily||{}, metrics=metricMap(view), history=Array.isArray(daily.history)?daily.history:[];
    const mcSeries=((((daily.mc57_detail||{}).series||{}).mc57)||daily.mc57_history||[]);
    const mcValues=Array.isArray(mcSeries)?mcSeries.map((r)=>r&&finite(r.value!==undefined?r.value:r.mc57)).filter((v)=>v!==null):[];
    const b50=history.map((r)=>finite(r.breadth50)).filter((v)=>v!==null), b200=history.map((r)=>finite(r.breadth200)).filter((v)=>v!==null);
    const mode=metricDisplay(metrics,'market_mode'), nqsar=metricDisplay(metrics,'nqsar');
    const perf=['QQQ','SPY','RSP','QQQE'].map((ticker)=>{const m=marketSummary(view,ticker);return `<tr><td class="tk">${ticker}</td><td>${pct(m.change_1d)}</td><td>${pct(m.change_1w)}</td><td>${pct(m.change_1m)}</td></tr>`;}).join('');
    const sectorRows=SECTORS.map((ticker)=>({ticker,one:marketSummary(view,ticker).change_1w,month:marketSummary(view,ticker).change_1m})).sort((a,b)=>(finite(b.one)||-99)-(finite(a.one)||-99)).slice(0,8).map((r)=>`<tr><td class="tk">${r.ticker}</td><td class="${(finite(r.one)||0)>=0?'pos':'neg'}">${pct(r.one)}</td><td>${pct(r.month)}</td></tr>`).join('');
    const leaders=((daily.leader_diagnostics||{}).top_ret20||[]).slice(0,8).map((r)=>`<tr><td class="tk">${html(r.ticker)}</td><td>${pct(r.ret20)}</td><td>${num(r.rs189,1)}</td></tr>`).join('');
    const vix=marketSummary(view,'^VIX'), hyg=marketSummary(view,'HYG'), ief=marketSummary(view,'IEF'), tnx=marketSummary(view,'^TNX');
    return `<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>${publishCss()}</style></head><body><div class="stage"><div class="card"><div class="hd"><span class="bar"></span><h1>マーケット <span class="mut" style="font-size:13px">Market Overview</span></h1><span class="state">${html(nqsar)} · ${html(mode)}</span><span class="date">${html(view.session_date||'')}</span></div><div class="grid"><div class="panel"><div class="title">レジーム判定 <small>Regime</small></div><div class="big">${html(nqsar)}</div><div class="sub">Market Mode ${html(mode)}<br>現行V38の市場状態</div><div class="note">売買判定は採用済みルールのみ</div></div><div class="panel"><div class="title">MC57 <small>Market Status</small></div><div class="big">${html(metricDisplay(metrics,'mc57'))}</div>${publishSpark(mcValues,'#2456A6')}</div><div class="panel"><div class="title">50MA Breadth <small>Participation</small></div><div class="big">${html(metricDisplay(metrics,'breadth50'))}</div>${publishSpark(b50,'#17685C')}</div><div class="panel"><div class="title">200MA Breadth <small>Long Trend</small></div><div class="big">${html(metricDisplay(metrics,'breadth200'))}</div>${publishSpark(b200,'#2A9384')}</div><div class="panel span2"><div class="title">マーケット・パフォーマンス <small>Performance</small></div><table class="tbl"><thead><tr><th>Index</th><th>1D</th><th>1W</th><th>1M</th></tr></thead><tbody>${perf}</tbody></table></div><div class="panel"><div class="title">F1 / F2 / F3 <small>Diagnostics</small></div><div class="mini4" style="grid-template-columns:repeat(3,1fr)"><div class="mini"><div class="k">F1</div><div class="v">${html(metricDisplay(metrics,'f1'))}</div></div><div class="mini"><div class="k">F2</div><div class="v">${html(metricDisplay(metrics,'f2'))}</div></div><div class="mini"><div class="k">F3</div><div class="v">${html(metricDisplay(metrics,'f3'))}</div></div></div></div><div class="panel"><div class="title">信用・金利 <small>Credit & Rates</small></div><div class="kv"><span>VIX</span><b>${num(vix.close,2)}</b></div><div class="kv"><span>HYG 1W</span><b>${pct(hyg.change_1w)}</b></div><div class="kv"><span>IEF 1W</span><b>${pct(ief.change_1w)}</b></div><div class="kv"><span>US10Y</span><b>${num(tnx.close,2)}%</b></div></div><div class="panel span2"><div class="title">セクター強弱 <small>Sector Rotation</small></div><table class="tbl"><thead><tr><th>ETF</th><th>1W</th><th>1M</th></tr></thead><tbody>${sectorRows}</tbody></table></div><div class="panel span2"><div class="title">先導株モメンタム <small>Leader Momentum</small></div><table class="tbl"><thead><tr><th>Ticker</th><th>1M</th><th>RS189</th></tr></thead><tbody>${leaders||'<tr><td colspan="3">該当なし</td></tr>'}</tbody></table></div></div></div></div>${publishFitScript()}</body></html>`;
  }
  function publishRotationHtml(view) {
    const rotation=view.rotation||{}, diag=rotation.diagnostics||{}, themes=Array.isArray(diag.industry)?diag.industry:[];
    const sectorRows=SECTORS.map((ticker)=>({ticker,one:marketSummary(view,ticker).change_1w,month:marketSummary(view,ticker).change_1m})).sort((a,b)=>(finite(b.one)||-99)-(finite(a.one)||-99));
    const sectorTable=sectorRows.map((r)=>`<tr><td class="tk">${r.ticker}</td><td class="${(finite(r.one)||0)>=0?'pos':'neg'}">${pct(r.one)}</td><td>${pct(r.month)}</td></tr>`).join('');
    const themeList=themes.slice(0,16).map((r,i)=>`<div class="theme"><span class="rk">${i+1}</span><span class="nm">${html(r.group)}</span><span class="rs">${num(r.theme_rs,1)}</span></div>`).join('');
    const leaders=themes.slice(0,8).map((r)=>`<div class="kv"><span>${html(r.group)}</span><b>${(r.leaders||[]).slice(0,3).map((x)=>html(x)).join(' · ')||'—'}</b></div>`).join('');
    const top=themes[0]||{};
    return `<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>${publishCss()}</style></head><body><div class="stage"><div class="card"><div class="hd"><span class="bar"></span><h1>セクター・ローテーション <span class="mut" style="font-size:13px">Sector Rotation</span></h1><span class="state" style="color:var(--accent)">LIVE</span><span class="date">${html(view.session_date||'')}</span></div><div class="grid"><div class="panel span2"><div class="title">GICS11 ETF 強弱 <small>1W / 1M</small></div><table class="tbl"><thead><tr><th>ETF</th><th>1W</th><th>1M</th></tr></thead><tbody>${sectorTable}</tbody></table></div><div class="panel span2"><div class="title">現在の主導テーマ <small>Fine Theme RS</small></div><div class="big">${html(top.group||'—')}</div><div class="sub">Theme RS ${num(top.theme_rs,1)} · RS63 ${num(top.rs63_avg,1)} · 20D ${pct(top.ret20_avg)}</div><div class="chips" style="margin-top:12px">${(top.leaders||[]).slice(0,6).map((x)=>`<span class="chip">${html(x)}</span>`).join('')}</div><div class="note">細粒度Themeの診断表示。通常個別株RankingではPeer Theme Scoreを別契約で使用。</div></div><div class="panel span2"><div class="title">テーマランキング <small>Top 16</small></div><div class="themes">${themeList}</div></div><div class="panel span2"><div class="title">強い業種の主導株 <small>Leaders</small></div>${leaders||'<div class="p-empty">該当なし</div>'}</div><div class="panel span2"><div class="title">ローテーション概要 <small>Market Breadth</small></div><div class="mini4"><div class="mini"><div class="k">Top Theme</div><div class="v" style="font-size:14px">${html(top.group||'—')}</div></div><div class="mini"><div class="k">Theme RS</div><div class="v">${num(top.theme_rs,1)}</div></div><div class="mini"><div class="k">RS63 Avg</div><div class="v">${num(top.rs63_avg,1)}</div></div><div class="mini"><div class="k">Members</div><div class="v">${finite(top.member_count)??'—'}</div></div></div></div><div class="panel span2"><div class="title">表示契約 <small>Source</small></div><div class="sub">現行Universeの細粒度Theme診断とセクターETF実測値を使用。SectorScoreを通常個別株のハードゲートには使用しません。</div><div class="note">Direction / Confidence 等の未復元値は作りません。</div></div></div></div></div>${publishFitScript()}</body></html>`;
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
'''
text, count = re.subn(
    r"  function renderPublish\(view\) \{.*?\n  \}\n(?=\n  function renderRules)",
    lambda _: publish_block,
    text,
    count=1,
    flags=re.S,
)
if count != 1:
    raise SystemExit(f'publish replacement count={count}')

# Restore compact source-like row density and remove browser default button chrome.
text = text.replace('.v38-canonical-list{display:flex;flex-direction:column;gap:0;margin-top:8px}', '.v38-canonical-list{display:flex;flex-direction:column;gap:0;margin-top:6px}')
text = text.replace('gap:12px;align-items:center;padding:9px 0;', 'gap:10px;align-items:center;padding:6px 0;')
text = text.replace('gap:8px;align-items:baseline;flex-wrap:wrap}.v38-canonical-left small{font-size:11px}', 'gap:7px;align-items:baseline;flex-wrap:wrap}.v38-canonical-left small{font-size:10.5px}')
text = text.replace('text-align:right;font-size:12px}', 'text-align:right;font-size:11.5px}')
text = text.replace('.v38-canonical-spark{width:100%;height:92px;display:block;margin-top:10px}', '.v38-ticker-link{appearance:none;-webkit-appearance:none;border:0;background:transparent;padding:0;margin:0;color:inherit;font:inherit;font-weight:800;line-height:inherit;cursor:pointer;text-align:left}.v38-ticker-link:hover,.v38-ticker-link:focus{text-decoration:underline;outline:none}.v38-canonical-spark{width:100%;height:34px;display:block;margin:5px 0 0}')
old_post = '.postframe{width:100%;min-height:480px;border:0;border-radius:14px;background:#f5f2e8}'
new_post = '.postwrap{position:relative}.postframe{width:100%;aspect-ratio:1680/1080;border:1px solid #D5D1C6;border-radius:12px;display:block;background:#E9E7DF}.pfsbtn,.pfsclose{font:inherit}.postwrap.fs{position:fixed;inset:0;z-index:99999;background:#E9E7DF;display:flex;align-items:center;justify-content:center;margin:0}.postwrap.fs .postframe{width:100vw;height:100vh;max-width:none;aspect-ratio:auto;border-radius:0;border:0}.postwrap.fs .pfsbtn{display:none}.postwrap.fs .pfsclose{display:flex;align-items:center;justify-content:center;position:fixed;top:calc(env(safe-area-inset-top,0px) + 10px);right:10px;z-index:100000;width:34px;height:34px;font-size:16px;font-weight:700;color:#fff;background:rgba(0,0,0,.45);border:1px solid rgba(255,255,255,.3);border-radius:50%;cursor:pointer}.fslock{overflow:hidden!important}'
if old_post not in text:
    raise SystemExit('old postframe style not found')
text = text.replace(old_post, new_post, 1)
text = text.replace('.v38-canonical-row{grid-template-columns:minmax(0,1fr);gap:4px}.v38-canonical-value{text-align:left}.postframe{min-height:430px}', '.v38-canonical-row{grid-template-columns:minmax(0,1fr) auto;gap:8px;padding:5px 0}.v38-canonical-value{text-align:right;font-size:10.5px}.v38-canonical-left small{font-size:9.5px}.postframe{aspect-ratio:1680/1080}')

BINDER.write_text(text, encoding='utf-8')

TEST.write_text(r'''from pathlib import Path

BINDER = Path("assets/v38-canonical-binder.js").read_text(encoding="utf-8")


def test_sparklines_keep_source_format_contract():
    assert "const W = 680, H = 68, P = 6" in BINDER
    assert "classList.add('spark', 'v38-canonical-spark')" in BINDER
    assert "stop-opacity','0.28'" in BINDER
    assert "stroke-width','2'" in BINDER
    assert "dot.setAttribute('r','3.2')" in BINDER
    assert ".v38-canonical-spark{width:100%;height:34px" in BINDER


def test_publish_cards_are_fixed_1680_by_1080_live_cards():
    assert "width:1680px;height:1080px" in BINDER
    assert "aspect-ratio:1680/1080" in BINDER
    assert "publishOverviewHtml(view)" in BINDER
    assert "publishRotationHtml(view)" in BINDER
    assert "ensurePublishControls" in BINDER
    assert "frame.srcdoc=srcdoc" in BINDER
    assert "wraps[index].replaceChildren()" not in BINDER
    assert "V38 MARKET OVERVIEW" not in BINDER


def test_ticker_links_do_not_use_browser_button_chrome():
    assert ".v38-ticker-link{appearance:none;-webkit-appearance:none;border:0;background:transparent" in BINDER


def test_missing_core_rank_is_not_fabricated_or_printed_as_rank_dash():
    assert "Rank ${r.rank ?? '—'}" not in BINDER
    assert "Rank ${r.rank??'—'}" not in BINDER
''', encoding='utf-8')

print('visual fidelity refactor applied')
