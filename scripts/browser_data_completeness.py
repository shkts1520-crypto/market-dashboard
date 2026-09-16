#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re

from playwright.sync_api import sync_playwright

WIDTHS=(375,390,430)
ALL_TABS=('#t-market','#t-alloc','#t-port','#t-today','#t-rotation','#t-movers','#t-rs','#t-weekly','#t-options','#t-post1','#t-rules')
FORBIDDEN=(
    'DATA_REQUIRED','SOURCE_UNAVAILABLE','正本producer未復元','現行正本データに同一定義',
    '元カードと同一定義の正本がない場合','正本publish shard','full_v38_ready:','blockers:',
    '推移データ不足','MOCK DATA',
)
MOCK_TICKER=re.compile(r'\bM\d{3}\b')


def fetch_json(page,path:str):
    return page.evaluate("""async p=>{const r=await fetch(p,{cache:'no-store'});if(!r.ok)throw new Error(p+' '+r.status);return r.json()}""",path)


def title_card(page,section,needle):
    cards=page.locator(f'{section} .card')
    for i in range(cards.count()):
        c=cards.nth(i)
        original=c.get_attribute('data-v38-card-title') or ''
        heading=''
        h=c.locator('h2,.hdr h2,.chd h2').first
        if h.count(): heading=h.inner_text()
        if needle in original or needle in heading:
            return c
    return page.locator('__v38_missing__')


def assert_ready(page,section,needle,width):
    c=title_card(page,section,needle)
    assert c.count()==1,(width,section,needle,'card missing')
    assert c.is_visible(),(width,section,needle,'card hidden')
    assert c.get_attribute('data-v38-status')=='READY',(width,section,needle,c.get_attribute('data-v38-status'),c.inner_text()[:500])
    src=c.get_attribute('data-v38-truth-source') or ''
    assert src and not src.lower().startswith('canonical'),(width,section,needle,'invalid truth source',src)
    text=c.inner_text()
    for token in FORBIDDEN:
        assert token not in text,(width,section,needle,'forbidden token',token,text[:500])


def assert_no_public_placeholders(page,width):
    body=page.locator('body').inner_text()
    for token in FORBIDDEN:
        assert token not in body,(width,'forbidden public text',token)
    assert not MOCK_TICKER.search(body),(width,'mock ticker exposed')
    generic=page.evaluate("""() => Array.from(document.querySelectorAll('body *')).filter(el=>{
      if(el.children.length)return false;const t=String(el.textContent||'').replace(/\s+/g,' ').trim();
      if(t!=='実データ'&&t!=='正本の実データ')return false;const s=getComputedStyle(el),r=el.getBoundingClientRect();
      return s.display!=='none'&&s.visibility!=='hidden'&&r.width>0&&r.height>0;
    }).map(el=>({tag:el.tagName,text:el.textContent.trim(),cls:String(el.className||'')}))""")
    assert not generic,(width,'generic implementation labels exposed',generic)


def assert_market(page,view,width):
    page.locator('a.tabx[href="#t-market"]').click()
    for key in ('mc57','breadth50','breadth200'):
        c=page.locator(f'#t-market [data-v38-live-series="{key}"]')
        assert c.count()==1 and c.is_visible(),(width,key,'trend card missing')
        s=c.locator(f'svg[data-v38-live-spark="{key}"]')
        assert s.count()==1 and s.is_visible(),(width,key,'sparkline missing')
        pts=s.locator('polyline').get_attribute('points') or ''
        assert len(pts.split())>=20,(width,key,'sparkline too short',len(pts.split()))
        assert c.get_attribute('data-v38-status')=='READY',(width,key,c.get_attribute('data-v38-status'))
    heat=title_card(page,'#t-market','セクター温度マップ')
    assert heat.count()==1 and heat.is_visible(),(width,'sector heatmap missing')
    assert heat.locator('.v38-sector-tile').count()>=11,(width,'sector heatmap lacks 11 sectors',heat.locator('.v38-sector-tile').count())
    assert heat.get_attribute('data-v38-status')=='READY'


def assert_positions(page,width):
    page.locator('a.tabx[href="#t-alloc"]').click()
    assert_ready(page,'#t-alloc','保有ポジション',width)
    assert_ready(page,'#t-alloc','現在の想定ポジション',width)
    assert_ready(page,'#t-alloc','マーケット回復後のポジション入り銘柄',width)


def assert_setups(page,setup,width):
    assert setup.get('status')=='READY',(width,'setup producer not READY',setup.get('status'))
    assert float(setup.get('coverage') or 0)>=0.90,(width,'setup coverage too low',setup.get('coverage'),setup.get('requested'),setup.get('received'))
    page.locator('a.tabx[href="#t-today"]').click()
    for needle in ('発火前','エントリー候補ボード','ポケットピボット','本日のピックアップ','テクニカル・パターン別','圧縮コイル','21EMAタッチ'):
        assert_ready(page,'#t-today',needle,width)
    vwap=title_card(page,'#t-today','Multi VWAP')
    if vwap.count() and vwap.is_visible():
        assert vwap.get_attribute('data-v38-status')=='READY',(width,'Multi VWAP not READY',vwap.get_attribute('data-v38-status'))


def assert_publish(page,view,width):
    page.locator('a.tabx[href="#t-post1"]').click()
    s=page.locator('#t-post1')
    assert s.get_attribute('data-v38-publish-cards')=='ready',(width,'publish contract missing')
    frames=s.locator('iframe.postframe')
    assert frames.count()>=2,(width,'publish cards missing',frames.count())
    for i in range(2):
        srcdoc=frames.nth(i).get_attribute('srcdoc') or ''
        assert len(srcdoc)>100,(width,'empty publish srcdoc',i)
        for token in FORBIDDEN:
            assert token not in srcdoc,(width,'publish forbidden',i,token)
    assert str(view.get('session_date') or '') in (frames.nth(0).get_attribute('srcdoc') or ''),(width,'publish session stale')


def assert_tab_contract(page,href,width):
    page.locator(f'a.tabx[href="{href}"]').click()
    sec=page.locator(href)
    assert sec.is_visible(),(width,href,'tab not visible')
    bad=sec.evaluate("""root=>Array.from(root.querySelectorAll('.card')).filter(c=>{
      const s=getComputedStyle(c),r=c.getBoundingClientRect();if(c.hidden||s.display==='none'||s.visibility==='hidden'||r.width<=0||r.height<=0)return false;
      if(c.classList.contains('liqstick'))return false;
      return !c.dataset.v38TruthSource;
    }).map(c=>({title:(c.dataset.v38CardTitle||((c.querySelector('h2')||{}).textContent)||'').trim(),text:String(c.textContent||'').trim().slice(0,180)}))""")
    assert not bad,(width,href,'visible cards without truth source',bad[:20])
    overflow=page.evaluate("""()=>document.documentElement.scrollWidth-window.innerWidth""")
    assert overflow<=3,(width,href,'page horizontal overflow',overflow)


def main()->int:
    ap=argparse.ArgumentParser();ap.add_argument('--url',default='http://127.0.0.1:8000/');args=ap.parse_args()
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        try:
            for width in WIDTHS:
                page=browser.new_page(viewport={'width':width,'height':900})
                page.goto(args.url,wait_until='networkidle')
                page.wait_for_function("document.body.dataset.v38BindingStatus === 'ready'")
                page.wait_for_function("document.body.dataset.v38TruthBinding === 'ready'")
                page.wait_for_function("document.body.dataset.v38AuthoritativeFinal === 'ready'")
                page.wait_for_function("document.documentElement.dataset.v38PublicFinal === 'ready'")
                page.wait_for_timeout(300)
                view=fetch_json(page,'data/ui_view_model.json')
                setup=fetch_json(page,'data/setup_restore.json')
                assert_no_public_placeholders(page,width)
                assert_market(page,view,width)
                assert_positions(page,width)
                assert_setups(page,setup,width)
                assert_publish(page,view,width)
                for href in ALL_TABS:
                    assert_tab_contract(page,href,width)
                page.close()
        finally:
            browser.close()
    print('production truth browser acceptance: OK')
    return 0

if __name__=='__main__':
    raise SystemExit(main())
