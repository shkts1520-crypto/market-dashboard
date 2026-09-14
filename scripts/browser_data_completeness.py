#!/usr/bin/env python3
from __future__ import annotations

import argparse

from playwright.sync_api import sync_playwright


WIDTHS = (375, 390, 430)


def fetch_json(page, path: str):
    return page.evaluate(
        """async (path) => {
          const r = await fetch(path, {cache: 'no-store'});
          if (!r.ok) throw new Error(path + ' HTTP ' + r.status);
          return r.json();
        }""",
        path,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify no false missing-data state in the production UI")
    parser.add_argument("--url", default="http://127.0.0.1:8000/")
    args = parser.parse_args()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            for width in WIDTHS:
                page = browser.new_page(viewport={"width": width, "height": 900})
                page.goto(args.url, wait_until="networkidle")
                page.wait_for_function("document.body.dataset.v38BindingStatus === 'ready'")
                page.wait_for_timeout(1200)

                for href in (
                    '#t-market', '#t-alloc', '#t-port', '#t-rotation', '#t-rs',
                    '#t-weekly', '#t-options', '#t-post1', '#t-rules',
                ):
                    page.locator(f'a.tabx[href="{href}"]').click()
                    section = page.locator(href)
                    assert section.is_visible()
                    text = section.inner_text()
                    assert 'データ未取得' not in text, (width, href)
                    assert 'DATA_REQUIRED' not in text, (width, href)
                    assert 'STALE' not in text, (width, href)

                search = fetch_json(page, 'data/search_index.json')
                options = fetch_json(page, 'data/options/index.json')
                vwap = fetch_json(page, 'data/vwap_restore.json')
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
                assert modal.locator('script[src*="embed-widget-advanced-chart.js"]').count() == 1
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

    print('display completeness browser acceptance: OK')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
