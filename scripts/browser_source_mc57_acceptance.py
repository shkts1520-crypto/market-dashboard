#!/usr/bin/env python3
from __future__ import annotations

import argparse

from playwright.sync_api import sync_playwright


WIDTHS = (375, 390, 430)
FORBIDDEN_PUBLIC_TEXT = (
    "SOURCE_DEFINED_",
    "SOURCE_UNAVAILABLE",
    "MOCK DATA",
    "producer未復元",
    "正本producer",
    "full_v38_ready:",
    "blockers:",
)


def assert_no_overflow(page, width: int, href: str) -> None:
    overflow = page.evaluate(
        """() => {
          const root=document.documentElement;
          return Math.max(root.scrollWidth, document.body.scrollWidth) - root.clientWidth;
        }"""
    )
    assert overflow <= 3, (width, href, "unexpected horizontal overflow", overflow)


def assert_no_internal_text(page, width: int) -> None:
    body = page.locator("body").inner_text()
    for token in FORBIDDEN_PUBLIC_TEXT:
        assert token not in body, (width, "internal token exposed", token)


def main() -> int:
    parser = argparse.ArgumentParser(description="Browser acceptance for source-mc57.html")
    parser.add_argument("--url", default="http://127.0.0.1:8000/source-mc57.html")
    args = parser.parse_args()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            for width in WIDTHS:
                page = browser.new_page(viewport={"width": width, "height": 900})
                errors: list[str] = []
                page.on("pageerror", lambda exc: errors.append(str(exc)))
                page.goto(args.url, wait_until="domcontentloaded")
                page.wait_for_selector('nav a.tabx[href="#t-options"]')
                page.locator('nav a.tabx[href="#t-options"]').click()
                page.wait_for_selector("#t-options .v38-canonical-options")
                page.wait_for_timeout(250)

                section = page.locator("#t-options")
                assert section.is_visible(), (width, "options tab hidden")
                assert section.get_attribute("data-v38-options-restore-status") == "canonical-v5-layout-ready"
                assert section.locator('.v38-upward-card[data-v38-card-title="上方向配置"]').count() == 1
                assert section.locator(".v38-upward-group").count() == 4
                assert page.evaluate("() => typeof window.V38OpenTickerChart === 'function'")
                assert_no_internal_text(page, width)
                assert_no_overflow(page, width, "#t-options")

                hrefs = page.locator("nav a.tabx[href^='#']").evaluate_all(
                    """nodes => nodes.map(n => n.getAttribute('href')).filter(
                      h => h && document.getElementById(h.slice(1))
                    )"""
                )
                assert "#t-options" in hrefs, (width, hrefs)
                assert len(hrefs) >= 2, (width, "too few navigable tabs", hrefs)
                for href in hrefs:
                    page.locator(f'nav a.tabx[href="{href}"]').click()
                    page.wait_for_timeout(80)
                    target = page.locator(href)
                    assert target.is_visible(), (width, href, "tab did not become visible")
                    assert bool(target.inner_text().strip()) or target.locator("iframe:visible").count() > 0, (
                        width,
                        href,
                        "visible tab is empty",
                    )
                    assert_no_overflow(page, width, href)
                    assert_no_internal_text(page, width)

                assert not errors, (width, errors)
                page.close()
        finally:
            browser.close()

    print("source-mc57 browser acceptance: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
