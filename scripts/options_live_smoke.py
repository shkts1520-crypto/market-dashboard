#!/usr/bin/env python3
from __future__ import annotations

import argparse
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright


REQUIRED_LEVEL_LABELS = (
    "Call Wall",
    "Put Wall",
    "Gamma Flip",
    "Expected Upper",
    "Expected Lower",
    "Spot",
)


def _fetch_json(page, relative_path: str):
    return page.evaluate(
        """async (path) => {
          const response = await fetch(path, {cache: 'no-store'});
          if (!response.ok) throw new Error(path + ' HTTP ' + response.status);
          return response.json();
        }""",
        relative_path,
    )


def _first_current_row(options: dict) -> dict | None:
    buckets = options.get("buckets") if isinstance(options, dict) else None
    if isinstance(buckets, dict):
        for bucket in ("0-45", "22-45", "7-21", "0-6"):
            rows = buckets.get(bucket)
            if isinstance(rows, list):
                for row in rows:
                    if isinstance(row, dict) and row.get("ticker"):
                        return row
    rows = options.get("rows") if isinstance(options, dict) else None
    if isinstance(rows, list):
        for row in rows:
            if isinstance(row, dict) and row.get("ticker"):
                return row
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-test deployed V38 Options overlay")
    parser.add_argument("--url", required=True)
    args = parser.parse_args()
    target_url = args.url if args.url.endswith("/") else args.url + "/"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 390, "height": 900})
            page_errors: list[str] = []
            page.on("pageerror", lambda exc: page_errors.append(str(exc)))
            page.goto(target_url, wait_until="networkidle")
            page.wait_for_function("document.body.dataset.v38BindingStatus === 'ready'")
            page.wait_for_function("document.documentElement.dataset.v38NavReady === 'true'")

            options = _fetch_json(page, "data/options/index.json")
            assert options.get("status") == "READY", options.get("status")
            assert float(options.get("coverage") or 0.0) >= 0.25
            assert len(options.get("rows") or []) >= 3
            assert options.get("session_date")

            row = _first_current_row(options)
            assert row is not None, "no current options row available for overlay smoke"
            ticker = str(row.get("ticker") or "").strip().upper()
            assert ticker

            page.wait_for_function("typeof window.V38OpenTickerChart === 'function'")
            page.evaluate("ticker => window.V38OpenTickerChart(ticker)", ticker)
            modal = page.locator("#v38-options-chart-modal")
            assert modal.is_visible()
            assert modal.locator(".v38-oc-title").inner_text().strip() == ticker
            assert modal.locator(".v38-oc-tv .tradingview-widget-container").count() == 1

            levels = modal.locator(".v38-oc-levels")
            page.wait_for_function(
                """() => {
                  const el = document.querySelector('#v38-options-chart-modal .v38-oc-levels');
                  return el && !el.textContent.includes('loading') && el.textContent.includes('Call Wall');
                }"""
            )
            text = levels.inner_text()
            for label in REQUIRED_LEVEL_LABELS:
                assert label in text, (label, text)
            assert "未取得" not in text
            assert "Direction/Confidenceは推測表示しません" in text

            values = [value.strip() for value in levels.locator(".v38-oc-level-grid b").all_inner_texts()]
            assert len(values) == len(REQUIRED_LEVEL_LABELS)
            assert sum(value not in {"", "—"} for value in values) >= 4, values
            assert not page_errors, page_errors

            print({
                "url": target_url,
                "session_date": options.get("session_date"),
                "status": options.get("status"),
                "coverage": options.get("coverage"),
                "rows": len(options.get("rows") or []),
                "ticker": ticker,
                "overlay_values": values,
            })
            page.close()
        finally:
            browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
