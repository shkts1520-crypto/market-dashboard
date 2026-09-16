from pathlib import Path
import re

p = Path('assets/v38-canonical-binder.js')
s = p.read_text(encoding='utf-8')

old_rank = "const ranked=rows.map((r,i)=>({...r,_rank:finite(r.rank)!==null?r.rank:i+1}));"
new_rank = "const ranked=rows.map((r)=>({...r,_rank:finite(r.rank)!==null?r.rank:'—'}));"
assert old_rank in s
s = s.replace(old_rank, new_rank, 1)

marker = "  function renderWeekly(view) {"
assert marker in s
ribbon = r'''  function regimeRibbon(cardNode, records, source) {
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

'''
s = s.replace(marker, ribbon + marker, 1)

old_weekly = "    const regime=((daily.display_observations||{}).regime_history)||{};\n    const regimeRows=regime.rows||regime.series||[];\n    if(Array.isArray(regimeRows)&&regimeRows.length>1) spark(card('t-weekly','地合いの帯'),regimeRows.map((r)=>r.value??r.mc57),'weekly_regime',metricDisplay(metrics,'mc57'),'地合いの帯 Regime History','data/ui_view_model.json.daily.display_observations.regime_history');"
new_weekly = "    const regime=((daily.display_observations||{}).regime_history)||{};\n    const regimeRows=regime.records||regime.rows||regime.series||[];\n    regimeRibbon(card('t-weekly','地合いの帯'),regimeRows,'data/ui_view_model.json.daily.display_observations.regime_history.records');"
assert old_weekly in s
s = s.replace(old_weekly, new_weekly, 1)

pat = re.compile(r"  function renderOptions\(options\) \{.*?\n  \}\n\n  let publishSparkSeq", re.S)
assert pat.search(s)
new_options = r'''  function optionRows(options,bucket) {
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

  let publishSparkSeq'''
s = pat.sub(new_options, s, count=1)

old_css = ".v38-theme-bar{grid-template-columns:20px minmax(90px,1fr) minmax(70px,1.3fr) 36px}.v38-theme-bar small{display:none}"
new_css = ".v38-theme-bar{grid-template-columns:20px minmax(78px,.95fr) minmax(62px,1.15fr) 34px minmax(72px,.9fr);gap:5px}.v38-theme-bar small{min-width:0;font-size:8px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}"
assert old_css in s
s = s.replace(old_css, new_css, 1)

assert "bucket.replace('-','–')+' DTE'" in s
assert 'display:none' not in s.replace(' ', '')
assert 'style.display' not in s
p.write_text(s, encoding='utf-8')
print('source-fidelity binder patch applied')
