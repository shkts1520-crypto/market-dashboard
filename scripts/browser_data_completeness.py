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
    '#t-port': ('新規参入','個別株スリーブ'),
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
    for key in ('volume_participation','up_down_dollar_ratio','mcclellan','risk_rotation','credit_ratio','vix_term'):
        spark = page.locator(f'svg[data-v38-live-spark="{key}"]')
        assert spark.count() == 1, (width, key, 'required repaired trend missing')
        assert len((spark.locator('polyline').get_attribute('points') or '').split()) >= 2, (width, key, 'trend too short')
    ribbon = page.locator('#t-weekly .card[data-v38-card-title*="地合いの帯"] .ribbon .rb')
    assert ribbon.count() >= 1, (width, 'weekly source-format regime ribbon missing')


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
        assert svg.count() == 1 and svg.is_visible(), (width, key, 'required trend chart missing')
        assert svg.get_attribute('data-v38-full-trend') == '1', (width, key, 'compact spark regressed over full source chart')
        points = svg.locator('polyline').get_attribute('points') or ''
        assert len(points.split()) >= 20, (width, key, 'trend has too few points')
        assert svg.locator('text.v38-y-label').count() >= 4, (width, key, 'vertical-axis labels missing')
        assert svg.locator('line.v38-grid-line').count() >= 4, (width, key, 'vertical-axis grid/ticks missing')
    mc57 = page.locator('#t-market svg[data-v38-live-spark="mc57"]')
    assert mc57.count() == 1 and mc57.locator('text.v38-y-label').count() >= 4, (width, 'MC57 source chart axis missing')
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
    flow_card = page.locator('#t-rotation .card[data-v38-card-title*="資金フロー"]')
    assert flow_card.count() == 1, (width, 'money-flow card missing')
    assert flow_card.get_attribute('data-v38-status') == 'READY', (width, 'money-flow card not READY')
    assert flow_card.get_attribute('data-v38-truth-source'), (width, 'money-flow truth source missing')
    assert flow_card.locator('svg.v38-rrg-svg').count() == 1, (width, 'source-format RRG missing')
    assert flow_card.locator('.v38-rrg-quadrant').count() == 4, (width, 'RRG quadrants missing')
    qnodes = flow_card.locator('.v38-rrg-quadrant')
    quadrants = {str(qnodes.nth(i).text_content() or '').strip() for i in range(qnodes.count())}
    assert quadrants == {'主導', '改善', '弱化', '停滞'}, (width, 'RRG must be Japanese-first', quadrants)
    assert flow_card.locator('.v38-rrg-qrow').count() == 4, (width, 'Japanese quadrant chip rows missing')
    heat = page.locator('#t-rotation .v38-sector-cell')
    assert heat.count() == 11, (width, 'rotation heatmap must contain 11 GICS sectors', heat.count())
    assert heat.nth(0).locator('b').inner_text() == '素材', (width, 'heatmap sector name must be Japanese-first')
    controls = page.locator('#t-rotation .v38-heat-controls button')
    assert controls.count() == 3, (width, 'rotation 日/週/月 heatmap controls missing')
    assert controls.all_inner_texts() == ['日', '週', '月'], (width, 'rotation heatmap controls must be Japanese', controls.all_inner_texts())
    breadth = page.locator('#t-rotation .card[data-v38-generated="breadth-quality"]')
    assert breadth.count() == 1 and breadth.get_attribute('data-v38-status') == 'READY', (width, 'breadth-quality diagnosis missing')
    breadth_text = breadth.inner_text()
    for required in ('テクノロジー', '通信', '一般消費財', '生活必需品', 'エネルギー', '金融', 'ヘルスケア', '資本財', '素材', '公益'):
        assert required in breadth_text, (width, 'Japanese GICS breadth row missing', required)
    rotation_text = page.locator('#t-rotation').inner_text()
    for banned in ('Energy Minerals', 'Health Services', 'Technology Services', 'Commercial Services', 'Consumer Services', 'Distribution Services'):
        assert banned not in rotation_text, (width, 'English sector label leaked into Rotation UI', banned)
    leading = page.locator('#t-rotation .card[data-v38-card-title*="主導セクター・業種"]')
    assert leading.count() == 1 and leading.locator('.v38-leading-groups-source .bgrow').count() >= 10, (width, 'source-style leading groups missing')
    leading_text = leading.inner_text()
    for required in ('RS63', '1カ月', '50日線上', '銘柄'):
        assert required in leading_text, (width, 'leading-group current metric missing', required)
    strong = page.locator('#t-rotation .card[data-v38-card-title*="強い業種の主導株"]')
    assert strong.count() == 1 and strong.locator('.v38-strong-theme-group').count() >= 1, (width, 'source-style grouped strong-theme leaders missing')
    assert strong.locator('.v38-strong-theme-chips .v38-ticker-link').count() >= 1, (width, 'qualified leader chips missing')
    assert 'RS—' not in strong.inner_text(), (width, 'missing RS must not render as a fake score placeholder')
    headers = page.locator('#t-rotation .v38-source-table th').all_inner_texts()
    for banned in ('Group', 'Breadth50', 'Members', 'Ticker', 'Theme', '1D', '1W', '1M'):
        assert banned not in headers, (width, 'Rotation table header regressed to English-first', banned, headers)
    for required in ('セクター', 'ETF', '日', '週', '月', '順位', 'サブテーマ', 'テーマRS', 'RS63', 'RS189', '1カ月', '主導株'):
        assert required in headers, (width, 'Japanese Rotation table header missing', required, headers)


def assert_rs(page, width: int) -> None:
    page.locator('a.tabx[href="#t-rs"]').click()
    overlap = page.locator('#t-rs .card[data-v38-card-title*="RSマルチタイムフレーム比較"]')
    assert overlap.count() == 1 and overlap.get_attribute('data-v38-status') == 'READY', (width, 'RS overlap card not connected')
    assert overlap.locator('.v38-rs-box').count() == 4, (width, 'RS overlap structure missing')
    for period in (63, 126, 189):
        top = page.locator(f'#t-rs .card[data-v38-card-title*="RS{period} Top10"]')
        assert top.count() == 1 and top.get_attribute('data-v38-status') == 'READY', (width, period, 'RS Top10 card missing')
        assert top.locator('tbody tr').count() >= 1, (width, period, 'RS Top10 data missing')
    persist = page.locator('#t-rs .card[data-v38-card-title*="RS189 継続性"]')
    assert persist.count() == 1 and persist.get_attribute('data-v38-status') == 'READY', (width, 'RS persistence missing')


def assert_options(page, width: int) -> None:
    page.locator('a.tabx[href="#t-options"]').click()
    buckets = page.locator('#t-options [data-v38-option-bucket]')
    assert buckets.count() == 4, (width, 'four DTE buckets missing', buckets.count())
    text = page.locator('#t-options').inner_text()
    assert 'Confidence' not in text and 'Direction' not in text, (width, 'removed inferred option labels resurfaced')
    nonempty = page.locator('#t-options .card[data-v38-option-bucket] .rsx-item')
    assert nonempty.count() >= 1, (width, 'source-format option rows missing')


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
                assert_rs(page, width)
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
