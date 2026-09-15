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


def assert_source_visuals(page, view: dict, width: int) -> None:
    assert page.evaluate("document.body.dataset.v38SourceVisual") == 'ready', (width, 'source visual pass missing')

    daily = view.get('daily') or {}
    mc_detail = daily.get('mc57_detail') or {}
    if mc_detail.get('status') == 'READY' and len(((mc_detail.get('series') or {}).get('mc57') or [])) >= 3:
        assert page.locator('#t-market .v38-real-spark').count() >= 3, (
            width, 'daily source-style real sparklines missing'
        )

    core = view.get('core12') or {}
    if core.get('status') == 'READY' and core.get('rows'):
        expected = min(24, len(core.get('rows') or []))
        assert page.locator('#t-port .v38-core-row').count() == expected, (
            width, 'core source-style ranked rows missing', expected,
        )
        assert page.locator('#t-port .v38-core-row[data-v38-ticker]').count() == expected

    summaries = daily.get('market_summaries') or {}
    if all(symbol in summaries for symbol in ('XLB','XLC','XLE','XLF','XLI','XLK','XLP','XLRE','XLU','XLV','XLY')):
        assert page.locator('#t-rotation .v38-sector-cell').count() == 11, (
            width, 'rotation eleven-sector visual missing'
        )

    diagnostics = ((view.get('rotation') or {}).get('diagnostics') or {}).get('industry') or []
    if diagnostics:
        assert page.locator('#t-rotation .v38-group-row').count() > 0, (
            width, 'rotation industry leader visual missing'
        )

    history = daily.get('history') or []
    if len(history) >= 3:
        assert page.locator('#t-weekly .v38-real-spark').count() >= 1, (
            width, 'weekly real history sparkline missing'
        )


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
                page.wait_for_function("document.body.dataset.v38SourceVisual === 'ready'")
                page.wait_for_timeout(150)

                view = fetch_json(page, 'data/ui_view_model.json')
                assert page.locator('#sarCol').inner_text().strip() == metric_display(view, 'nqsar')
                assert metric_display(view, 'market_mode') in page.locator('#sarPill').inner_text()

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
                        or "SOURCE_UNAVAILABLE" in row.get("text", "")
                        or "DATA_REQUIRED" in row.get("text", "")
                        or "STALE" in row.get("text", "")
                        or row.get("className") == "mut"
                    )]
                    if invalid:
                        raise AssertionError((width, href, invalid))

                assert_source_visuals(page, view, width)

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

    print('production truth + source visual browser acceptance: OK')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
