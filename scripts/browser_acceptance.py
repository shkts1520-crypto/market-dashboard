#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright


WIDTHS = (375, 390, 430)
TAB_LABELS = (
    "Daily", "Positions", "Core 12", "Setups", "Rotation", "Movers", "RS",
    "Weekly", "Options", "Publish", "Rules",
)


def _assert_interactions(page):
    page.locator('a.tabx[href="#t-today"]').click()
    search = page.locator("#tksearch")
    assert search.count() == 1
    search.fill("NVDA")
    page.wait_for_timeout(100)
    assert "NVDA" in page.locator("#tkresults").inner_text()

    ticker = page.locator("#t-today [data-tkone]").first
    if ticker.count():
        expected = ticker.get_attribute("data-tkone")
        ticker.click()
        modal = page.locator("#v38-options-chart-modal")
        assert modal.is_visible()
        assert modal.locator(".v38-oc-title").inner_text().strip() == expected
        modal.locator(".v38-oc-close").click()
        assert not modal.is_visible()

    page.locator('a.tabx[href="#t-options"]').click()
    options = page.locator("#t-options")
    for bucket in ("0-6", "7-21", "22-45", "0-45"):
        assert options.locator(f'[data-v38-option-bucket="{bucket}"]').count() == 1
    text = options.inner_text()
    assert "Direction" not in text and "Confidence" not in text


def _assert_canonical_binder(page) -> None:
    page.wait_for_function("document.documentElement.dataset.v38CanonicalBinder !== undefined")
    state = page.evaluate("document.documentElement.dataset.v38CanonicalBinder")
    if state != "ready":
        raise AssertionError(f"canonical binder state={state}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8000/")
    parser.add_argument("--screenshot-dir")
    args = parser.parse_args()
    screenshot_dir = Path(args.screenshot_dir) if args.screenshot_dir else None
    if screenshot_dir:
        screenshot_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            for width in WIDTHS:
                page = browser.new_page(viewport={"width": width, "height": 900})
                errors: list[str] = []
                page.on("pageerror", lambda exc: errors.append(str(exc)))
                page.goto(args.url, wait_until="networkidle")
                page.wait_for_function("document.body.dataset.v38BindingStatus === 'ready'")
                _assert_canonical_binder(page)
                page.wait_for_function("document.body.dataset.v38PySourceFinal === 'ready'")

                tabs = page.locator("a.tabx")
                assert tabs.count() == 11
                assert [tabs.nth(i).inner_text().strip() for i in range(11)] == list(TAB_LABELS)

                sentinel = f"v38-no-reload-{width}"
                page.evaluate("value => window.__v38Sentinel = value", sentinel)
                for i in range(11):
                    tab = tabs.nth(i)
                    href = tab.get_attribute("href")
                    assert href and href.startswith("#")
                    section_id = href[1:]
                    tab.click()
                    page.wait_for_timeout(120)
                    section = page.locator("#" + section_id)
                    assert section.is_visible()
                    assert page.locator("section.on").count() == 1
                    assert page.evaluate("window.__v38Sentinel") == sentinel
                    assert section.inner_text().strip() or section.locator("iframe:visible").count() > 0, (
                        width,
                        section_id,
                        "visible section is empty",
                    )
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 3"), section_id

                    if screenshot_dir:
                        image = section.screenshot(path=str(screenshot_dir / f"{width}-{section_id}.png"))
                        assert len(image) > 5000, (
                            width,
                            section_id,
                            "visual evidence is effectively blank",
                            len(image),
                        )

                _assert_interactions(page)
                page.locator('a.tabx[href="#t-rs"]').click()
                page.locator('a.tabx[href="#t-weekly"]').click()
                page.evaluate("history.back()")
                page.wait_for_function("location.hash === '#t-rs'")
                assert page.locator("#t-rs").is_visible()
                page.wait_for_function("window.scrollY === 0")
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 3")
                assert not errors, errors
                page.close()
        finally:
            browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
