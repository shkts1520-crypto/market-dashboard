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
    'SOURCE_DEFINED_', 'SOURCE_UNAVAILABLE', 'MOCK DATA', 'producer未復元',
    '正本producer', 'full_v38_ready:', 'blockers:',
)


def assert_public_text(page, width: int) -> None:
    text = page.locator('body').inner_text()
    for token in FORBIDDEN_PUBLIC_TEXT:
        assert token not in text, (width, 'internal token exposed', token)


def assert_mobile_geometry(page, href: str, width: int) -> None:
    overflow = page.evaluate("""() => {
      const root=document.documentElement;
      return Math.max(root.scrollWidth, document.body.scrollWidth) - root.clientWidth;
    }""")
    assert overflow <= 3, (width, href, 'unexpected horizontal overflow', overflow)


def main() -> int:
    parser = argparse.ArgumentParser(description='Validate user-visible V38 rendering')
    parser.add_argument('--url', default='http://127.0.0.1:8000/')
    args = parser.parse_args()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            for width in WIDTHS:
                page = browser.new_page(viewport={'width': width, 'height': 900})
                errors: list[str] = []
                page.on('pageerror', lambda exc: errors.append(str(exc)))
                page.goto(args.url, wait_until='networkidle')
                page.wait_for_function("document.body.dataset.v38BindingStatus === 'ready'")
                page.wait_for_function("document.documentElement.dataset.v38CanonicalBinder === 'ready'")
                page.wait_for_function("document.body.dataset.v38PySourceFinal === 'ready'")
                assert_public_text(page, width)

                for href in ALL_TABS:
                    page.locator(f'a.tabx[href="{href}"]').click()
                    page.wait_for_timeout(120)
                    section = page.locator(href)
                    assert section.is_visible(), (width, href, 'tab did not become visible')
                    has_content = bool(section.inner_text().strip()) or section.locator('iframe:visible').count() > 0
                    assert has_content, (width, href, 'visible tab is empty')
                    assert_mobile_geometry(page, href, width)
                    assert_public_text(page, width)

                assert not errors, (width, errors)
                page.close()
        finally:
            browser.close()

    print('rendered product smoke acceptance: OK')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
