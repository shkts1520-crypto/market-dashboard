#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re

from playwright.sync_api import sync_playwright


WIDTHS = (375, 390, 430)
DYNAMIC_TABS = (
    '#t-market', '#t-alloc', '#t-port', '#t-today', '#t-rotation', '#t-movers',
    '#t-rs', '#t-weekly', '#t-options', '#t-post1',
)
ALL_TABS = DYNAMIC_TABS + ('#t-rules',)
MOCK_TICKER = re.compile(r'\bM\d{3}\b')
FORBIDDEN_PUBLIC_TEXT = (
    'SOURCE_UNAVAILABLE',
    '正本publish shard',
    'full_v38_ready:',
    'blockers:',
)


CANONICAL_SNAPSHOT_SCRIPT = r"""
document.addEventListener('DOMContentLoaded', () => {
  const cards = Array.from(document.querySelectorAll('section .card'));
  window.__v38CanonicalCardSnapshot = cards.map((card, index) => {
    const section = card.closest('section');
    const heading = card.querySelector('h2,.hdr h2,.chd h2');
    return {
      index,
      sectionId: section ? String(section.id || '') : '',
      heading: heading ? String(heading.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 240) : '',
      text: String(card.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 1200),
      html: String(card.outerHTML || '').slice(0, 6000)
    };
  });
}, {once: true});
"""


def fetch_json(page, path: str):
    return page.evaluate(
        """async (path) => {
          const r = await fetch(path, {cache: 'no-store'});
          if (!r.ok) throw new Error(path + ' HTTP ' + r.status);
          return r.json();
        }""",
        path,
    )


def metric_display(view: dict, key: str) -> str:
    for row in (view.get('daily') or {}).get('metrics') or []:
        if row.get('key') == key:
            return str(row.get('display') or '—')
    return '—'


def market_summary(view: dict, symbol: str) -> dict:
    return ((view.get('daily') or {}).get('market_summaries') or {}).get(symbol) or {}


def has_close(view: dict, symbols: tuple[str, ...]) -> bool:
    for symbol in symbols:
        value = market_summary(view, symbol).get('close')
        if not isinstance(value, (int, float)):
            return False
    return True


def card_by_original_title(page, section: str, needle: str):
    return page.locator(f'{section} .card[data-v38-card-title*="{needle}"]').first


def assert_ready_card(page, section: str, needle: str, width: int, source_reason: str) -> None:
    card = card_by_original_title(page, section, needle)
    assert card.count() == 1, (width, section, needle, 'expected authoritative card missing', source_reason)
    assert card.get_attribute('data-v38-status') == 'READY', (
        width, section, needle, 'source is available but card is not READY', source_reason,
        card.get_attribute('data-v38-status'), card.inner_text()[:500],
    )
    text = card.inner_text()
    assert 'DATA_REQUIRED' not in text and 'STALE' not in text, (
        width, section, needle, 'false missing visible', source_reason, text[:500],
    )


def missing_details(section):
    return section.evaluate(
        """(root) => Array.from(root.querySelectorAll('*')).filter((el) => {
          const text = String(el.textContent || '').trim();
          const explicitMissingState = el.matches('.mut, .v38-bind-note, [data-v38-status="DATA_REQUIRED"], [data-v38-status="STALE"]') ||
            Boolean(el.closest('.v38-bind-note, [data-v38-status="DATA_REQUIRED"], [data-v38-status="STALE"]'));
          return explicitMissingState &&
            (text.includes('データ未取得') || text.includes('DATA_REQUIRED') || text.includes('STALE')) &&
            !Array.from(el.children || []).some((child) => {
              const childText = String(child.textContent || '').trim();
              return childText.includes('データ未取得') || childText.includes('DATA_REQUIRED') || childText.includes('STALE');
            });
        }).slice(0, 30).map((el) => ({
          tag: el.tagName,
          className: String(el.className || ''),
          text: String(el.textContent || '').trim().slice(0, 300),
          status: String(el.dataset && el.dataset.v38Status || '')
        }))"""
    )


def assert_truth_bound(section, href: str, width: int) -> None:
    if href == '#t-post1':
        return
    unbound = section.evaluate(
        """(root) => Array.from(root.querySelectorAll(':scope > .card')).filter((card) => {
          return !card.dataset.v38TruthSource;
        }).map((card) => {
          const h = card.querySelector('h2,.hdr h2,.chd h2');
          return h ? h.textContent.trim() : card.className;
        })"""
    )
    assert not unbound, (width, href, 'cards without truth provenance', unbound)


def assert_options_upward_rankings(page, options: dict, width: int) -> None:
    rankings = options.get('upward_rankings')
    if not isinstance(rankings, dict):
        return
    expected_buckets = ('0-6', '7-21', '22-45', '0-45')
    assert set(expected_buckets).issubset(rankings), (width, 'missing option DTE rankings', rankings.keys())
    page.locator('a.tabx[href="#t-options"]').click()
    card = page.locator('#t-options .v38-options-upward-card')
    assert card.count() == 1 and card.is_visible(), (width, 'upward options card missing')
    assert card.get_attribute('data-v38-truth-source') == 'data/options/index.json.upward_rankings'

    scan = options.get('universe_scan') or {}
    target_count = scan.get('target_count')
    if target_count is not None:
        assert f'Universe {target_count}' in card.inner_text(), (width, target_count, card.inner_text()[:800])

    card_text = card.inner_text()
    for bucket in expected_buckets:
        rows = rankings.get(bucket) or []
        assert f'{bucket} DTE' in card_text, (width, bucket, 'bucket heading missing')
        if rows:
            ticker = str(rows[0].get('ticker') or '').upper()
            assert ticker, (width, bucket, 'empty ranked ticker')
            locator = card.locator(f'[data-v38-ticker="{ticker}"]')
            assert locator.count() >= 1, (width, bucket, ticker, 'ranked ticker not rendered')


def assert_no_canonical_truth_sources(page, width: int) -> None:
    bad = page.evaluate(
        """() => Array.from(document.querySelectorAll('[data-v38-truth-source]'))
          .filter((el) => String(el.dataset.v38TruthSource || '').toLowerCase().startsWith('canonical'))
          .map((el) => ({tag: el.tagName, source: el.dataset.v38TruthSource, text: String(el.textContent || '').trim().slice(0, 180)}))"""
    )
    assert not bad, (width, 'canonical/fixed content used as production truth', bad)


def assert_false_missing_contract(page, view: dict, width: int) -> None:
    daily = view.get('daily') or {}
    history = daily.get('history') or []
    if len(history) >= 2:
        assert_ready_card(page, '#t-market', '前回からの変化', width, 'daily.history has previous/current sessions')

    core = view.get('core12') or {}
    entrants = core.get('new_entrants') or {}
    if entrants.get('status') == 'READY':
        assert_ready_card(page, '#t-port', '新規参入', width, 'core12.new_entrants READY')

    rs = view.get('rs') or {}
    if rs.get('status') == 'READY':
        for period in (63, 126, 189):
            if (rs.get('windows') or {}).get(str(period)):
                assert_ready_card(page, '#t-rs', f'RS{period} Top10', width, f'rs.windows.{period} populated')
        if rs.get('rows'):
            assert_ready_card(page, '#t-rs', 'RS189 継続性', width, 'rs.rows populated')

    rs_history = fetch_json(page, 'data/rs_history.json')
    comparisons_ready = any(
        cmp.get('status') == 'READY'
        for window in (rs_history.get('windows') or {}).values()
        for cmp in (window.get('comparisons') or [])
        if isinstance(cmp, dict)
    )
    if rs_history.get('status') == 'READY' and comparisons_ready:
        assert_ready_card(page, '#t-rs', 'Top10 IN / OUT', width, 'rs_history comparison READY')

    weekly_specs = (
        ('構造マクロ', ('DX-Y.NYB', 'CL=F', 'GC=F')),
        ('金利レジーム', ('^TNX', '^FVX', 'IEF')),
        ('マクロ圧力', ('^VIX', '^VXN', 'HYG', 'DX-Y.NYB')),
        ('レバレッジ・コンディション', ('SOXL',)),
    )
    for needle, symbols in weekly_specs:
        if has_close(view, symbols):
            assert_ready_card(page, '#t-weekly', needle, width, f'market_summaries available for {symbols}')
    metrics = {row.get('key'): row for row in daily.get('metrics') or [] if isinstance(row, dict)}
    if (metrics.get('breadth50') or {}).get('status') == 'READY' and (metrics.get('breadth200') or {}).get('status') == 'READY':
        assert_ready_card(page, '#t-weekly', '広域ブレッドス', width, 'breadth50/breadth200 READY')
    if len(history) >= 6:
        assert_ready_card(page, '#t-weekly', '今週の変化', width, 'daily.history has six sessions')


def assert_public_render_contract(page, view: dict, width: int) -> None:
    body_text = page.locator('body').inner_text()
    for token in FORBIDDEN_PUBLIC_TEXT:
        assert token not in body_text, (width, 'forbidden public/internal text', token)

    exact_placeholders = page.evaluate(
        """() => Array.from(document.querySelectorAll('body *')).filter((el) => {
          if (el.children.length) return false;
          const text = String(el.textContent || '').replace(/\s+/g, ' ').trim();
          if (text !== '実データ' && text !== '正本の実データ') return false;
          const style = getComputedStyle(el);
          const rect = el.getBoundingClientRect();
          return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0;
        }).map((el) => ({tag: el.tagName, className: String(el.className || ''), text: el.textContent.trim()}))"""
    )
    assert not exact_placeholders, (width, 'public placeholder labels exposed', exact_placeholders)
    assert_no_canonical_truth_sources(page, width)

    page.locator('a.tabx[href="#t-market"]').click()
    for key in ('mc57', 'breadth50', 'breadth200'):
        card = page.locator(f'#t-market [data-v38-live-series="{key}"]')
        assert card.count() == 1 and card.is_visible(), (width, key, 'required live trend card missing')
        spark = card.locator(f'svg[data-v38-live-spark="{key}"]')
        assert spark.count() == 1 and spark.is_visible(), (width, key, 'required live trend spark missing')
        points = spark.locator('polyline').get_attribute('points') or ''
        assert len(points.split()) >= 2, (width, key, 'live trend has fewer than two points')
        assert card.get_attribute('data-v38-status') == 'READY', (width, key, card.get_attribute('data-v38-status'))

    banner = page.locator('#t-market > .banner')
    if banner.count():
        assert metric_display(view, 'mc57') in banner.inner_text(), (width, 'MC57 banner is not current authoritative value', banner.inner_text())
    ribbons = page.locator('#t-market > .ribwrap')
    if ribbons.count():
        for i in range(ribbons.count()):
            text = ribbons.nth(i).inner_text()
            assert 'DATA_REQUIRED' in text, (width, 'unverified fixed regime history survived', text)

    assert_false_missing_contract(page, view, width)

    page.locator('a.tabx[href="#t-post1"]').click()
    publish = page.locator('#t-post1')
    assert publish.get_attribute('data-v38-publish-cards') == 'ready', (width, 'publish render contract not ready')
    assert (publish.get_attribute('data-v38-truth-source') or '').startswith('data/ui_view_model.json'), (
        width, 'Publish truth source is not live view model', publish.get_attribute('data-v38-truth-source'))
    frames = publish.locator('iframe.postframe')
    assert frames.count() >= 2, (width, 'Publish real cards missing', frames.count())
    srcdocs = []
    for index in range(2):
        srcdoc = frames.nth(index).get_attribute('srcdoc') or ''
        srcdocs.append(srcdoc)
        assert len(srcdoc.strip()) > 100, (width, index, 'Publish iframe srcdoc empty')
        assert 'SOURCE_UNAVAILABLE' not in srcdoc and 'MOCK DATA' not in srcdoc and 'canonical-publish' not in srcdoc.lower(), (
            width, index, 'Publish contains fixed/mock/internal content')
    first = srcdocs[0]
    assert str(view.get('session_date') or '') in first, (width, 'Publish session not current')
    assert metric_display(view, 'mc57') in first, (width, 'Publish MC57 not current')
    assert metric_display(view, 'market_mode') in first, (width, 'Publish market mode not current')
    assert metric_display(view, 'nqsar') in first, (width, 'Publish NQSAR not current')
    assert 'XLB' in srcdocs[1] and str(view.get('session_date') or '') in srcdocs[1], (width, 'Publish sector card not live/current')


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify production UI contains authoritative data only")
    parser.add_argument("--url", default="http://127.0.0.1:8000/")
    args = parser.parse_args()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            for width in WIDTHS:
                page = browser.new_page(viewport={"width": width, "height": 900})
                page.add_init_script(CANONICAL_SNAPSHOT_SCRIPT)
                page.goto(args.url, wait_until="networkidle")
                page.wait_for_function("document.body.dataset.v38BindingStatus === 'ready'")
                page.wait_for_function("document.body.dataset.v38TruthBinding === 'ready'")
                page.wait_for_function("document.body.dataset.v38AuthoritativeFinal === 'ready'")
                page.wait_for_function("document.body.dataset.v38PublicRenderContract === 'ready'")
                page.wait_for_timeout(300)

                view = fetch_json(page, 'data/ui_view_model.json')
                assert page.locator('#sarCol').inner_text().strip() == metric_display(view, 'nqsar')
                assert metric_display(view, 'market_mode') in page.locator('#sarPill').inner_text()
                assert_public_render_contract(page, view, width)

                for href in ALL_TABS:
                    page.locator(f'a.tabx[href="{href}"]').click()
                    section = page.locator(href)
                    assert section.is_visible()
                    visible_text = section.evaluate("root => String(root.innerText || '')")
                    if href in DYNAMIC_TABS:
                        assert 'MOCK DATA' not in visible_text.upper(), (width, href, 'MOCK DATA visible')
                        assert 'モック' not in visible_text, (width, href, 'mock label visible')
                        mock_match = MOCK_TICKER.search(visible_text)
                        assert not mock_match, (width, href, 'mock ticker visible', mock_match.group(0) if mock_match else None)
                        assert_truth_bound(section, href, width)
                    details = missing_details(section)
                    invalid = [row for row in details if not (
                        row.get("status") in {"DATA_REQUIRED", "STALE"}
                        or "DATA_REQUIRED" in row.get("text", "")
                        or "STALE" in row.get("text", "")
                        or row.get("className") == "mut"
                    )]
                    if invalid:
                        raise AssertionError((width, href, invalid))

                page.locator('a.tabx[href="#t-market"]').click()
                market_text = page.locator('#t-market').inner_text()
                assert metric_display(view, 'mc57') in market_text, (width, 'authoritative MC57 missing')
                assert metric_display(view, 'nqsar') in market_text, (width, 'authoritative NQSAR missing')

                positions = view.get('positions') or {}
                if positions.get('status') == 'READY' and not (positions.get('rows') or []):
                    pos_text = page.locator('#t-alloc').inner_text()
                    assert '現在の保有' in pos_text and 'なし' in pos_text, (width, pos_text[:800])

                weekly = view.get('weekly') or {}
                if weekly.get('state'):
                    assert str(weekly['state']) in page.locator('#t-weekly').inner_text()

                options_text = page.locator('#t-options').inner_text()
                assert 'Confidence' not in options_text
                assert '上方向' not in options_text and '下方向' not in options_text

                search = fetch_json(page, 'data/search_index.json')
                options = fetch_json(page, 'data/options/index.json')
                vwap = fetch_json(page, 'data/vwap_restore.json')
                assert_options_upward_rankings(page, options, width)
                local = set((options.get('chart_ohlc') or {}).keys()) | set((vwap.get('chart_ohlc') or {}).keys())
                uncached = next(
                    str(row.get('ticker') or '').upper()
                    for row in (search.get('rows') or [])
                    if str(row.get('ticker') or '').upper() and str(row.get('ticker') or '').upper() not in local
                )

                page.evaluate("ticker => window.V38OpenTickerChart(ticker)", uncached)
                modal = page.locator('#v38-options-chart-modal')
                assert modal.is_visible()
                page.wait_for_function(
                    "document.querySelector('#v38-options-chart-modal .v38-rc-chart')?.dataset.v38ChartSource === 'tradingview-live'"
                )
                modal_text = modal.inner_text()
                assert '未取得' not in modal_text, (width, uncached, modal_text)
                assert 'TradingView 実チャート' in modal_text
                chart_host = modal.locator('.v38-rc-chart')
                assert chart_host.get_attribute('data-v38-chart-source') == 'tradingview-live'
                assert chart_host.get_attribute('data-v38-tradingview-symbol')
                assert chart_host.locator('.tradingview-widget-container.v38-live-chart-fallback').count() == 1
                modal.locator('.v38-oc-close').click()

                failures = options.get('failures') or {}
                no_contract = next(
                    (ticker for ticker, reason in failures.items() if reason == 'NO_VALID_0_45_DTE_CONTRACTS'),
                    None,
                )
                if no_contract:
                    page.evaluate("ticker => window.V38OpenTickerChart(ticker)", no_contract)
                    assert modal.is_visible()
                    page.wait_for_function(
                        "document.querySelector('#v38-options-chart-modal .v38-rc-status')?.dataset.v38ContractSemantics === 'no-valid-0-45-dte-contracts'"
                    )
                    status = modal.locator('.v38-rc-status').inner_text()
                    assert '0–45 DTE 有効契約なし' in status
                    assert '未取得' not in status
                    modal.locator('.v38-oc-close').click()

                page.close()
        finally:
            browser.close()

    print('production truth browser acceptance: OK')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
