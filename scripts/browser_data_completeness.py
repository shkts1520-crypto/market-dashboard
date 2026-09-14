#!/usr/bin/env python3
from __future__ import annotations

import argparse

from playwright.sync_api import sync_playwright


WIDTHS = (375, 390, 430)


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
        }).slice(0, 30).map((el) => {
          const card = el.closest('.card');
          const heading = card && card.querySelector('h2,.hdr h2,.chd h2');
          const allCards = Array.from(document.querySelectorAll('section .card'));
          const cardIndex = card ? allCards.indexOf(card) : -1;
          const source = Array.isArray(window.__v38CanonicalCardSnapshot)
            ? window.__v38CanonicalCardSnapshot.find((row) => row && row.index === cardIndex)
            : null;
          return {
            tag: el.tagName,
            className: String(el.className || ''),
            text: String(el.textContent || '').trim().slice(0, 300),
            status: String(el.dataset && el.dataset.v38Status || ''),
            cardIndex,
            cardClass: card ? String(card.className || '') : '',
            cardId: card ? String(card.id || '') : '',
            cardTitle: heading ? String(heading.textContent || '').trim().slice(0, 160) : '',
            cardBinding: card ? String(card.dataset.v38BindingKey || '') : '',
            rememberedTitle: card ? String(card.dataset.v38CardTitle || '') : '',
            canonicalTitle: card ? String(card.dataset.v38CanonicalTitle || '') : '',
            source: source || null
          };
        })"""
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
                page.add_init_script(CANONICAL_SNAPSHOT_SCRIPT)
                page.goto(args.url, wait_until="networkidle")
                page.wait_for_function("document.body.dataset.v38BindingStatus === 'ready'")
                page.wait_for_timeout(4000)

                for href in (
                    '#t-market', '#t-alloc', '#t-port', '#t-today', '#t-rotation', '#t-movers', '#t-rs',
                    '#t-weekly', '#t-options', '#t-post1', '#t-rules',
                ):
                    page.locator(f'a.tabx[href="{href}"]').click()
                    section = page.locator(href)
                    assert section.is_visible()
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

    print('display completeness browser acceptance: OK')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
