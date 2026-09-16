from pathlib import Path
import re

binder = Path('assets/v38-canonical-binder.js')
s = binder.read_text(encoding='utf-8')

anchor = "  const SECTOR_LABELS = {XLB:'素材',XLC:'通信',XLE:'エネルギー',XLF:'金融',XLI:'資本財',XLK:'テクノロジー',XLP:'生活必需品',XLRE:'不動産',XLU:'公益',XLV:'ヘルスケア',XLY:'一般消費財'};"
if 'const TV_SECTOR_LABELS' not in s:
    addition = anchor + "\n  const TV_SECTOR_LABELS = {'Electronic Technology':'電子テクノロジー','Technology Services':'テクノロジーサービス','Retail Trade':'小売業','Communications':'通信','Consumer Durables':'耐久消費財','Health Technology':'ヘルスケアテクノロジー','Finance':'金融','Producer Manufacturing':'生産財製造','Energy Minerals':'エネルギー鉱物','Non-Energy Minerals':'非エネルギー鉱物','Process Industries':'加工産業','Commercial Services':'商業サービス','Consumer Non-Durables':'非耐久消費財','Consumer Services':'消費者サービス','Distribution Services':'流通サービス','Health Services':'ヘルスサービス','Industrial Services':'産業サービス','Transportation':'交通・輸送','Utilities':'公益事業','Miscellaneous':'その他'};\n  const GICS_DIAG_GROUPS = [['テクノロジー','XLK',['Electronic Technology','Technology Services']],['通信','XLC',['Communications']],['一般消費財','XLY',['Consumer Durables','Retail Trade','Consumer Services']],['生活必需品','XLP',['Consumer Non-Durables','Distribution Services']],['エネルギー','XLE',['Energy Minerals','Industrial Services']],['金融','XLF',['Finance']],['ヘルスケア','XLV',['Health Technology','Health Services']],['資本財','XLI',['Producer Manufacturing','Transportation']],['素材','XLB',['Non-Energy Minerals','Process Industries']],['不動産','XLRE',['Finance']],['公益','XLU',['Utilities']]];"
    assert anchor in s
    s = s.replace(anchor, addition, 1)

new_breadth = '''  function ensureBreadthQualityCard(view){
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
'''
pattern = r"  function ensureBreadthQualityCard\(view\)\{.*?\n  function renderRotation\(view\) \{"
m = re.search(pattern, s, re.S)
assert m, 'breadth block not found'
s = s[:m.start()] + new_breadth + "  function renderRotation(view) {" + s[m.end():]

pattern = r"    richTable\(card\('t-rotation','主導セクター・業種'\).*?\n    const leaderRows=\[\];"
m = re.search(pattern, s, re.S)
assert m, 'leading groups table call not found'
s = s[:m.start()] + "    renderLeadingGroups(card('t-rotation','主導セクター・業種'),sectors);\n    const leaderRows=[];" + s[m.end():]

s = s.replace("{label:'Ticker',key:'ticker',ticker:true,align:'left'}", "{label:'銘柄',key:'ticker',ticker:true,align:'left'}")
s = s.replace("{label:'1M',format:(r)=>pct(r.ret20_avg)}", "{label:'1カ月',format:(r)=>pct(r.ret20_avg)}")

binder.write_text(s, encoding='utf-8')

p = Path('scripts/browser_data_completeness.py')
t = p.read_text(encoding='utf-8')
t = t.replace("    quadrants = set(flow_card.locator('.v38-rrg-quadrant').all_inner_texts())", "    qnodes = flow_card.locator('.v38-rrg-quadrant')\n    quadrants = {str(qnodes.nth(i).text_content() or '').strip() for i in range(qnodes.count())}")
anchor = "    assert breadth.count() == 1 and breadth.get_attribute('data-v38-status') == 'READY', (width, 'breadth-quality diagnosis missing')"
if "Japanese GICS breadth row missing" not in t:
    extra = anchor + "\n    breadth_text = breadth.inner_text()\n    for required in ('テクノロジー', '通信', '一般消費財', '生活必需品', 'エネルギー', '金融', 'ヘルスケア', '資本財', '素材', '公益'):\n        assert required in breadth_text, (width, 'Japanese GICS breadth row missing', required)\n    rotation_text = page.locator('#t-rotation').inner_text()\n    for banned in ('Energy Minerals', 'Health Services', 'Technology Services', 'Commercial Services', 'Consumer Services', 'Distribution Services'):\n        assert banned not in rotation_text, (width, 'English sector label leaked into Rotation UI', banned)"
    assert anchor in t
    t = t.replace(anchor, extra, 1)
p.write_text(t, encoding='utf-8')
