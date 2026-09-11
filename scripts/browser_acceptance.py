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
GENERIC_BINDINGS = (
    ("t-alloc", "positions"),
    ("t-port", "core12"),
    ("t-rotation", "rotation"),
    ("t-weekly", "weekly"),
    ("t-options", "options"),
    ("t-post1", "publish"),
    ("t-rules", "rules"),
)


def _view_model(page):
    return page.evaluate(
        """async () => {
          const response = await fetch('data/ui_view_model.json', {cache: 'no-store'});
          if (!response.ok) throw new Error('ui_view_model HTTP ' + response.status);
          return response.json();
        }"""
    )


def _assert_live_binding(page, view):
    daily = view["daily"]
    daily_card = page.locator(
        '.v38-production-state[data-v38-section="t-market"]'
    )
    daily_text = daily_card.inner_text()
    assert "Daily • " + view["session_date"] in daily_text

    by_key = {row["key"]: row for row in daily["metrics"]}
    for key in ("breadth50", "breadth200", "f2", "market_QQQ"):
        row = by_key[key]
        assert row["label"] in daily_text
        assert row["display"] in daily_text

    rs = view["rs"]
    page.locator('a.tabx[href="#t-rs"]').click()
    rs_card = page.locator(
        '.v38-production-state[data-v38-section="t-rs"]'
    )
    rs_text = rs_card.inner_text()
    assert "not Core 12" in rs_text
    assert str(rs["status"]) in rs_text

    if rs["rows"]:
        first = rs["rows"][0]
        row = page.locator(
            '[data-v38-rs-ticker="' + first["ticker"] + '"]'
        ).first
        assert row.is_visible()
        text = row.inner_text()
        assert first["ticker"] in text
        assert first["rs189_display"] in text

    for section_id, view_key in GENERIC_BINDINGS:
        page.locator(f'a.tabx[href="#{section_id}"]').click()
        card = page.locator(
            f'.v38-production-state[data-v38-section="{section_id}"]'
        )
        text = card.inner_text()
        section = view[view_key]
        assert str(section["status"]) in text
        assert str(section.get("title") or view_key) in text
        assert view["session_date"] in text
        if section.get("reason") and section["status"] != "READY":
            assert str(section["reason"]) in text
        rows = section.get("rows") or []
        if rows:
            assert card.locator('[data-v38-row="1"]').count() == 1


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

                view = _view_model(page)
                _assert_live_binding(page, view)

                for i in range(9):
                    tab = tabs.nth(i)
                    href = tab.get_attribute("href")
                    assert href and href.startswith("#")
                    section_id = href[1:]
                    tab.click()
                    section = page.locator("#" + section_id)
                    assert section.is_visible()
                    assert tab.evaluate("el => el.classList.contains('on')")
                    assert section.evaluate("el => el.classList.contains('on')")
                    assert section.locator(".v38-production-state").count() == 1
                    visible_mock = section.locator(
                        ':scope > :not(.v38-production-state):visible'
                    ).count()
                    assert visible_mock == 0

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
