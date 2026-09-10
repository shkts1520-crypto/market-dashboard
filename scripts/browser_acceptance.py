#!/usr/bin/env python3
from __future__ import annotations

import argparse

from playwright.sync_api import sync_playwright

WIDTHS = (375, 390, 430)
TAB_LABELS = (
    "Daily",
    "Positions",
    "Core 12",
    "Rotation",
    "RS",
    "Weekly",
    "Options",
    "Publish",
    "Rules",
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8000/")
    args = parser.parse_args()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            for width in WIDTHS:
                page = browser.new_page(
                    viewport={"width": width, "height": 900}
                )
                page_errors: list[str] = []
                page.on("pageerror", lambda exc: page_errors.append(str(exc)))
                page.goto(args.url, wait_until="networkidle")

                tabs = page.locator("a.tabx")
                assert tabs.count() == 9

                labels = [
                    tabs.nth(i).inner_text().strip()
                    for i in range(9)
                ]
                assert labels == list(TAB_LABELS)

                for i in range(9):
                    tab = tabs.nth(i)
                    href = tab.get_attribute("href")
                    assert href and href.startswith("#")
                    section_id = href[1:]
                    tab.click()
                    section = page.locator("#" + section_id)
                    assert section.is_visible()
                    assert (
                        section.locator(
                            ".v38-production-state"
                        ).count()
                        == 1
                    )

                metrics = page.evaluate(
                    """() => ({
                      innerWidth: window.innerWidth,
                      scrollWidth: document.documentElement.scrollWidth
                    })"""
                )
                assert metrics["scrollWidth"] <= metrics["innerWidth"] + 1
                assert not page_errors
                page.close()
        finally:
            browser.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
