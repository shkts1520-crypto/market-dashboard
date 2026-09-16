#!/usr/bin/env python3
from pathlib import Path


def replace_once(path, old, new):
    p=Path(path); text=p.read_text(encoding='utf-8')
    if old not in text:
        raise SystemExit(f'pattern missing: {path}: {old[:120]!r}')
    p.write_text(text.replace(old,new,1),encoding='utf-8')

p=Path('assets/v38-canonical-binder.js')
s=p.read_text(encoding='utf-8')
s=s.replace('実測Wall / Gamma Flip / Expected Moveのみ。Direction / Confidenceは表示しません。','実測Wall / Gamma Flip / Expected Moveのみを表示。')
s=s.replace('経済指標カレンダーの正本データソースが未接続です。日付は推測しません。','経済指標カレンダーの取得元が未接続です。日付は推測しません。')
s=s.replace("simpleList(intro,'RSマルチタイムフレーム比較',[], 'data/ui_view_model.json.rs',{subtitle:''});","simpleList(intro,'RSマルチタイムフレーム比較',[], 'data/ui_view_model.json.rs','63・126・189営業日の強弱を同じ画面で比較。');")

# Add live banner/ribbon binding before the first Daily card.
anchor="""    const today = card('t-market', '今日のマーケット');
"""
insert="""    const banner=document.querySelector('#t-market > .banner');
    if(banner){banner.replaceChildren();banner.append(el('div','lab','マーケットステータス（MC57）'),el('div','val',metricDisplay(metrics,'mc57')),el('div','st','最新セッション'));const aux=el('div','aux');kv(aux,'50MA Breadth',metricDisplay(metrics,'breadth50'));kv(aux,'NQSAR',metricDisplay(metrics,'nqsar'));banner.appendChild(aux);mark(banner,'data/ui_view_model.json.daily.metrics','READY');}
    document.querySelectorAll('#t-market > .ribwrap').forEach((rib)=>{rib.replaceChildren();const line=el('div','riblab',`現在 ${metricDisplay(metrics,'nqsar')} · 50MA Breadth ${metricDisplay(metrics,'breadth50')}`);rib.appendChild(line);mark(rib,'data/ui_view_model.json.daily.metrics','READY');});
    const pill=document.getElementById('sarPill');
    if(pill){const state=metricDisplay(metrics,'nqsar');pill.classList.remove('sar-blue','sar-green','sar-yellow','sar-red');if(state&&state!=='—')pill.classList.add('sar-'+state.toLowerCase());const badge=pill.querySelector('#sarBadge');const col=pill.querySelector('#sarCol');const jud=pill.querySelector('#sarJud');const lot=pill.querySelector('#sarLot');if(badge)badge.textContent='LIVE';if(col)col.textContent=state;if(jud)jud.textContent=metricDisplay(metrics,'market_mode');if(lot)lot.textContent='最新セッション';mark(pill,'data/ui_view_model.json.daily.metrics','READY');}

    const today = card('t-market', '今日のマーケット');
"""
if anchor not in s: raise SystemExit('daily anchor missing')
s=s.replace(anchor,insert,1)

# Treat the restored liquidity filter as a bound utility instead of an error, and wire it to rendered setup rows.
anchor2="""  function renderSetups(view) {
    const data = view.setups || {};
"""
insert2="""  function renderSetups(view) {
    const data = view.setups || {};
    const utility=document.querySelector('#t-today .card.liqstick');
    if(utility){mark(utility,'data/ui_view_model.json.setups','READY');utility.querySelectorAll('button').forEach((button)=>{button.removeAttribute('onclick');button.addEventListener('click',()=>{utility.querySelectorAll('button').forEach((x)=>x.classList.remove('active'));button.classList.add('active');const label=String(button.textContent||'');const m=label.match(/\$(\d+)M/);const threshold=m?Number(m[1]):-1;document.querySelectorAll('#t-today .v38-canonical-row[data-liq]').forEach((row)=>{const value=Number(row.dataset.liq||0);row.hidden=threshold>=0&&value<threshold;});});});}
"""
if anchor2 not in s: raise SystemExit('setup anchor missing')
s=s.replace(anchor2,insert2,1)

# Preserve liquidity data on rendered rows for the restored filter.
old="""      line.append(left, el('b', 'v38-canonical-value', row.value === undefined ? '—' : row.value));
      list.appendChild(line);
"""
new="""      line.append(left, el('b', 'v38-canonical-value', row.value === undefined ? '—' : row.value));
      if (finite(row.ddv20) !== null) line.dataset.liq = String(Number(row.ddv20) / 1e6);
      list.appendChild(line);
"""
if old not in s: raise SystemExit('list row anchor missing')
s=s.replace(old,new,1)
# Pass ddv20 through setup rows.
s=s.replace("{ticker:r.ticker,meta:[r.industry,r.stage2?'Stage2':'',r.confluence&&r.confluence.length?r.confluence.join(' / '):''].filter(Boolean).join(' · '),value:`RS189 ${num(r.rs189,1)} · piv ${pct(r.pivot_dist)} · DDV ${finite(r.ddv20)===null?'—':`$${(r.ddv20/1e6).toFixed(1)}M`}`}","{ticker:r.ticker,ddv20:r.ddv20,meta:[r.industry,r.stage2?'Stage2':'',r.confluence&&r.confluence.length?r.confluence.join(' / '):''].filter(Boolean).join(' · '),value:`RS189 ${num(r.rs189,1)} · piv ${pct(r.pivot_dist)} · DDV ${finite(r.ddv20)===null?'—':`$${(r.ddv20/1e6).toFixed(1)}M`}`}" )

p.write_text(s,encoding='utf-8')

# Mobile containment: tabs scroll inside nav; page itself never clips horizontally.
css=Path('assets/v38-source-mobile.css')
text=css.read_text(encoding='utf-8')
addition='''\n@media (max-width: 600px) {\n  html, body { max-width: 100%; overflow-x: hidden; }\n  nav { max-width: 100%; overflow-x: auto; -webkit-overflow-scrolling: touch; scrollbar-width: none; overscroll-behavior-inline: contain; }\n  nav::-webkit-scrollbar { display: none; }\n  nav .tabx { flex: 0 0 auto; }\n}\n'''
if 'nav .tabx { flex: 0 0 auto; }' not in text:
    css.write_text(text+addition,encoding='utf-8')

print('single binder followup applied')
