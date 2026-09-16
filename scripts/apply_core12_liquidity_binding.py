#!/usr/bin/env python3
from pathlib import Path

path = Path('assets/v38-canonical-binder.js')
text = path.read_text(encoding='utf-8')

anchor = "  function setupRows(cardNode,title,rows,source,subtitle) {\n"
helper = """  function bindLiquidityUtility(sectionId, source) {
    const utility=document.querySelector(`#${sectionId} .card.liqstick`);
    if(!utility)return;
    mark(utility,source,'READY');
    const apply=(button)=>{
      utility.querySelectorAll('button').forEach((x)=>x.classList.toggle('active',x===button));
      const label=String(button.textContent||'');
      const m=label.match(/\\$(\\d+)M/);
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

"""
if helper.strip() not in text:
    if anchor not in text:
        raise SystemExit('setupRows anchor not found')
    text = text.replace(anchor, helper + anchor, 1)

old = """    const utility=document.querySelector('#t-today .card.liqstick');
    if(utility){mark(utility,'data/ui_view_model.json.setups','READY');utility.querySelectorAll('button').forEach((button)=>{button.removeAttribute('onclick');button.addEventListener('click',()=>{utility.querySelectorAll('button').forEach((x)=>x.classList.remove('active'));button.classList.add('active');const label=String(button.textContent||'');const m=label.match(/\\$(\\d+)M/);const threshold=m?Number(m[1]):-1;document.querySelectorAll('#t-today .v38-canonical-row[data-liq]').forEach((row)=>{const value=Number(row.dataset.liq||0);row.hidden=threshold>=0&&value<threshold;});});});}
"""
new = "    bindLiquidityUtility('t-today','data/ui_view_model.json.setups');\n"
if old not in text:
    raise SystemExit('existing Setups liquidity block not found')
text = text.replace(old, new, 1)

old = "  function renderCore(view) {\n    const core = view.core12 || {}, metrics = metricMap(view);\n"
new = "  function renderCore(view) {\n    const core = view.core12 || {}, metrics = metricMap(view);\n    bindLiquidityUtility('t-port','data/ui_view_model.json.core12.rows');\n"
if old not in text:
    raise SystemExit('renderCore anchor not found')
text = text.replace(old, new, 1)

text = text.replace("{ticker:r.ticker,meta:r.theme_name||r.industry||'',value:`${finite(r.rank)!==null?`Rank ${r.rank} · `:''}RS189 ${num(r.rs189,1)}`}", "{ticker:r.ticker,ddv20:r.ddv20,meta:r.theme_name||r.industry||'',value:`${finite(r.rank)!==null?`Rank ${r.rank} · `:''}RS189 ${num(r.rs189,1)}`}" )
text = text.replace("{ticker:r.ticker,value:`${finite(r.rank)!==null?`Rank ${r.rank} · `:''}RS189 ${num(r.rs189,1)}`}", "{ticker:r.ticker,ddv20:r.ddv20,value:`${finite(r.rank)!==null?`Rank ${r.rank} · `:''}RS189 ${num(r.rs189,1)}`}" )

path.write_text(text, encoding='utf-8')

test = Path('tests/test_visual_fidelity_contract.py')
t = test.read_text(encoding='utf-8')
block = """

def test_core12_liquidity_utility_is_bound_not_left_as_blank_card():
    assert "function bindLiquidityUtility(sectionId, source)" in BINDER
    assert "bindLiquidityUtility('t-port','data/ui_view_model.json.core12.rows')" in BINDER
    assert "bindLiquidityUtility('t-today','data/ui_view_model.json.setups')" in BINDER
    assert "ddv20:r.ddv20" in BINDER
"""
if 'test_core12_liquidity_utility_is_bound_not_left_as_blank_card' not in t:
    test.write_text(t + block, encoding='utf-8')
