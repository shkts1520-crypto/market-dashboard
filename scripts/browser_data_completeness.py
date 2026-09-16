#!/usr/bin/env python3
from __future__ import annotations

import argparse
from playwright.sync_api import sync_playwright

WIDTHS = (375, 390, 430)
ALL_TABS = (
    '#t-market', '#t-alloc', '#t-port', '#t-today', '#t-rotation', '#t-movers',
    '#t-rs', '#t-weekly', '#t-options', '#t-post1', '#t-rules',
)
FORBIDDEN_PUBLIC_TEXT = (
    'DATA_REQUIRED', 'SOURCE_UNAVAILABLE', 'producer未復元', '正本publish shard',
    'full_v38_ready:', 'blockers:', 'MOCK DATA', '正本producer',
)
ALLOWED_NON_READY_SOURCES = {'account-equity-history', 'economic-calendar'}
REPAIRED_CARD_CONTRACT = {
    '#t-market': ('売買代金 参加度','集積／分散','騰落ライン','攻守ローテーション','レジーム警戒灯','ネット流動性','クレジット推移','VIX期間構造','オプション想定変動幅','ディストリビューション','センチメント','転換初動','フォロースルー'),
    '#t-today': ('Multi VWAP','底打ち','ブレイク一覧','運用ルール','定義・グレード','状態の凡例','コホート分析','入り方','手仕舞い','リーダー監視'),
    '#t-rotation': ('サブテーマ別RS','テーマETFの温度計'),
    '#t-rs': ('Top10 IN / OUT',),
    '#t-port': ('V38 Data','個別株スリーブ'),
    '#t-weekly': ('今週の変化','地合いの帯','週次騰落ボード'),
}


def fetch_json(page, path: str):
    return page.evaluate(
        """async (path) => {
          const r = await fetch(path, {cache: 'no-store'});
          if (!r.ok) throw new Error(path + ' HTTP ' + r.status);
          return r.json();
        }""",
        path,
    )


def visible_cards(section):
    return section.locator('.card:visible')


def card_title(card) -> str:
    return card.evaluate("""(c) => {
      if (c.dataset.v38CardTitle) return c.dataset.v38CardTitle;
      const h=c.querySelector('h2,.hdr h2,.chd h2');
      return h ? h.textContent.replace(/\s+/g,' ').trim() : '';
    }""")


def assert_public_text(page, width: int) -> None:
    text = page.locator('body').inner_text()
    for token in FORBIDDEN_PUBLIC_TEXT:
        assert token not in text, (width, 'forbidden internal text exposed', token)
    exact = page.evaluate("""() => Array.from(document.querySelectorAll('body *')).filter((el) => {
      if (el.children.length) return false;
      const t=String(el.textContent||'').replace(/\s+/g,' ').trim();
      if (t !== '実データ' && t !== '正本の実データ') return false;
      const s=getComputedStyle(el), r=el.getBoundingClientRect();
      return s.display!=='none' && s.visibility!=='hidden' && r.width>0 && r.height>0;
    }).map((el)=>el.textContent.trim())""")
    assert not exact, (width, 'placeholder labels exposed', exact)


def assert_card_contract(section, href: str, width: int) -> None:
    cards = visible_cards(section)
    assert cards.count() > 0 or href == '#t-post1', (width, href, 'no visible cards')
    for index in range(cards.count()):
        item = cards.nth(index)
        source = item.get_attribute('data-v38-truth-source') or ''
        status = item.get_attribute('data-v38-status') or ''
        title = card_title(item)
        assert source, (width, href, title, 'visible card has no truth source')
        assert status != 'ERROR', (width, href, title, source, 'visible card binding error')
        if status != 'READY':
            assert status == 'NOT_CONNECTED' and source in ALLOWED_NON_READY_SOURCES, (
                width, href, title, source, status, 'non-ready card is not an explicit approved external-source gap'
            )


def assert_repaired_cards(page, width: int) -> None:
    seen = 0
    for href, needles in REPAIRED_CARD_CONTRACT.items():
        for needle in needles:
            card = page.locator(f'{href} .card[data-v38-card-title*="{needle}"]')
            assert card.count() == 1, (width, href, needle, 'repaired card missing or duplicated')
            assert card.get_attribute('data-v38-status') == 'READY', (width, href, needle, 'not READY')
            assert card.get_attribute('data-v38-truth-source'), (width, href, needle, 'truth source missing')
            text = ' '.join(card.inner_text().split())
            assert text and text not in {'—', '該当なし'}, (width, href, needle, 'empty repaired card')
            for token in FORBIDDEN_PUBLIC_TEXT + ('表示データを接続できません',):
                assert token not in text, (width, href, needle, token)
            seen += 1
    assert seen == 31, (width, 'repaired-card contract count changed', seen)
    for key in ('volume_participation','up_down_dollar_ratio','mcclellan','risk_rotation','credit_ratio','vix_term','weekly_regime'):
        spark = page.locator(f'svg[data-v38-live-spark="{key}"]')
        assert spark.count() == 1, (width, key, 'required repaired spark missing')
        assert len((spark.locator('polyline').get_attribute('points') or '').split()) >= 2, (width, key, 'spark too short')


def assert_mobile_geometry(page, href: str, width: int) -> None:
    overflow = page.evaluate("""() => {
      const root=document.documentElement;
      return Math.max(root.scrollWidth, document.body.scrollWidth) - root.clientWidth;
    }""")
    assert overflow <= 3, (width, href, 'unexpected page horizontal overflow', overflow)
    nav = page.locator('nav').first
    if nav.count():
        assert nav.evaluate('(n)=>n.scrollWidth >= n.clientWidth'), (width, 'tab nav geometry invalid')


def assert_daily_visuals(page, width: int) -> None:
    page.locator('a.tabx[href="#t-market"]').click()
    for key in ('breadth50', 'breadth200'):
        svg = page.locator(f'#t-market svg[data-v38-live-spark="{key}"]')
        assert svg.count() == 1 and svg.is_visible(), (width, key, 'required trend spark missing')
        points = svg.locator('polyline').get_attribute('points') or ''
        assert len(points.split()) >= 20, (width, key, 'trend has too few points')
    heat = page.locator('#t-market .v38-sector-cell')
    if heat.count():
        assert heat.count() == 11, (width, 'daily sector heatmap must have 11 sectors', heat.count())


def assert_positions(page, view: dict, width: int) -> None:
    page.locator('a.tabx[href="#t-alloc"]').click()
    mode = str((view.get('core12') or {}).get('market_mode') or '')
    expected = page.locator('#t-alloc .card[data-v38-card-title*="現在の想定ポジション"]')
    assert expected.count() == 1, (width, 'expected-position card missing')
    if mode.upper() in {'STOP', 'DEFENSE'}:
        assert '新規ポジションは0' in expected.inner_text(), (width, mode, expected.inner_text()[:500])


def assert_setups(page, width: int) -> None:
    page.locator('a.tabx[href="#t-today"]').click()
    for needle in ('発火前', 'エントリー候補ボード', 'ポケットピボット', '本日のピックアップ', 'テクニカル・パターン別'):
        card = page.locator(f'#t-today .card[data-v38-card-title*="{needle}"]')
        assert card.count() == 1, (width, needle, 'setup card missing')
        assert card.get_attribute('data-v38-status') == 'READY', (width, needle, card.get_attribute('data-v38-status'))


def assert_rotation(page, width: int) -> None:
    page.locator('a.tabx[href="#t-rotation"]').click()
    flow = page.locator('#t-rotation .v38-rrg')
    assert flow.count() == 1 and flow.is_visible(), (width, 'money-flow RRG missing')
    dots = flow.locator('.v38-rrg-dot')
    assert dots.count() == 16, (width, 'money-flow must contain GICS11 + five styles', dots.count())
    heat = page.locator('#t-rotation .v38-sector-cell')
    assert heat.count() == 11, (width, 'rotation heatmap must contain 11 GICS sectors', heat.count())


def assert_options(page, width: int) -> None:
    page.locator('a.tabx[href="#t-options"]').click()
    buckets = page.locator('#t-options [data-v38-option-bucket]')
    assert buckets.count() == 4, (width, 'four DTE buckets missing', buckets.count())
    text = page.locator('#t-options').inner_text()
    assert 'Confidence' not in text and 'Direction' not in text, (width, 'removed inferred option labels resurfaced')


def assert_publish(page, view: dict, width: int) -> None:
    page.locator('a.tabx[href="#t-post1"]').click()
    section = page.locator('#t-post1')
    assert section.get_attribute('data-v38-publish-cards') == 'ready', (width, 'publish cards not ready')
    frames = section.locator('iframe.postframe')
    assert frames.count() >= 2, (width, 'two live publish cards required', frames.count())
    for index in range(2):
        srcdoc = frames.nth(index).get_attribute('srcdoc') or ''
        assert str(view.get('session_date') or '') in srcdoc, (width, index, 'publish card session missing')
        for token in FORBIDDEN_PUBLIC_TEXT:
            assert token not in srcdoc, (width, index, token, 'internal token in publish card')


def main() -> int:
    parser = argparse.ArgumentParser(description='Validate the actually rendered V38 product')
    parser.add_argument('--url', default='http://127.0.0.1:8000/')
    args = parser.parse_args()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            for width in WIDTHS:
                page = browser.new_page(viewport={'width': width, 'height': 900})
                page.goto(args.url, wait_until='networkidle')
                page.wait_for_function("document.body.dataset.v38BindingStatus === 'ready'")
                page.wait_for_function("['ready','error'].includes(document.documentElement.dataset.v38CanonicalBinder)")
                state = page.evaluate("document.documentElement.dataset.v38CanonicalBinder")
                assert state == 'ready', (width, 'canonical binder reported errors', page.evaluate("document.body.dataset.v38CanonicalBinderErrors"))
                view = fetch_json(page, 'data/ui_view_model.json')
                assert_public_text(page, width)
                assert_daily_visuals(page, width)
                assert_positions(page, view, width)
                assert_setups(page, width)
                assert_rotation(page, width)
                assert_options(page, width)
                assert_publish(page, view, width)
                assert_repaired_cards(page, width)

                for href in ALL_TABS:
                    page.locator(f'a.tabx[href="{href}"]').click()
                    section = page.locator(href)
                    assert section.is_visible(), (width, href, 'tab did not become visible')
                    assert_card_contract(section, href, width)
                    assert_mobile_geometry(page, href, width)
                    assert_public_text(page, width)
                page.close()
        finally:
            browser.close()
    print('rendered product browser acceptance: OK')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
