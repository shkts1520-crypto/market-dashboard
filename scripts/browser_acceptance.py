#!/usr/bin/env python3
from __future__ import annotations

import argparse

from playwright.sync_api import sync_playwright

WIDTHS = (375, 390, 430)
TAB_LABELS = (
    "Daily", "Positions", "Core 12", "Rotation", "RS",
    "Weekly", "Options", "Publish", "Rules",
)
GENERIC_BINDINGS = (
    ("t-alloc", "positions"), ("t-port", "core12"),
    ("t-rotation", "rotation"), ("t-weekly", "weekly"),
    ("t-options", "options"), ("t-post1", "publish"),
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


def _rs_history(page):
    return page.evaluate(
        """async () => {
          const response = await fetch('data/rs_history.json', {cache: 'no-store'});
          if (!response.ok) throw new Error('rs_history HTTP ' + response.status);
          return response.json();
        }"""
    )


def _assert_live_binding(page, view):
    page.wait_for_function("document.body.dataset.v38BindingStatus === 'ready'")
    page.wait_for_function("document.body.dataset.v38RecoveryStatus === 'ready'")
    body_text = page.locator("body").inner_text()
    assert "MOCK DATA" not in body_text
    assert "分析基準日 2026-09-08" not in body_text
    assert page.locator(".v38-production-state").count() == 0
    assert page.locator(".v38-live-grid,.v38-generic-row,.v38-rs-row").count() == 0

    daily = view["daily"]
    daily_text = page.locator("#t-market").inner_text()
    by_key = {row["key"]: row for row in daily["metrics"]}
    for key in ("breadth50", "breadth200", "f2", "market_QQQ"):
        row = by_key[key]
        assert row["label"].split()[0] in daily_text
        assert row["display"] in daily_text

    mc57_detail = daily.get("mc57_detail") or {}
    if mc57_detail.get("status") == "READY":
        page.locator('a.tabx[href="#t-market"]').click()
        page.wait_for_function(
            "document.querySelectorAll('#t-market svg.v38-mc57-spark').length >= 12"
        )
        assert page.locator("#t-market svg.v38-mc57-spark").count() >= 12
        assert "57ETF 50MA上" in page.locator("#t-market").inner_text()
        assert "MC57内部 12指標履歴" in page.locator("#t-market").inner_text()

    rs = view["rs"]
    page.locator('a.tabx[href="#t-rs"]').click()
    rs_text = page.locator("#t-rs").inner_text()
    assert "存在しない過去履歴は補完しません" in rs_text
    assert str(rs["status"]) in rs_text
    assert "OBSERVED_ARCHIVE_ONLY" in rs_text
    assert "保存開始前の履歴は推測しません" in rs_text
    history = _rs_history(page)
    assert history["status"] == "READY"
    assert history["session_date"] == view["session_date"]
    assert history["history_policy"].startswith("Only actually archived sessions")
    if rs["rows"]:
        first = rs["rows"][0]
        row = page.locator('[data-v38-rs-ticker="' + first["ticker"] + '"]').first
        assert row.is_visible()
        text = row.inner_text()
        assert first["ticker"] in text
        assert first["rs189_display"] in text
        link = row.locator("a.v38-ticker-link").first
        assert link.get_attribute("target") == "_blank"
        assert "tradingview.com/chart/?symbol=" in (link.get_attribute("href") or "")
        if first.get("sparkline"):
            assert row.locator("svg.v38-live-spark").count() == 1

    positions = view.get("positions") or {}
    if positions.get("status") == "READY" and not positions.get("rows"):
        page.locator('a.tabx[href="#t-alloc"]').click()
        assert "現在ポジションなし" in page.locator("#t-alloc").inner_text()

    diagnostics = daily.get("market_diagnostics") or {}
    if diagnostics.get("series"):
        page.locator('a.tabx[href="#t-market"]').click()
        assert page.locator("#t-market svg.v38-live-spark").count() >= 3

    for section_id, view_key in GENERIC_BINDINGS:
        page.locator(f'a.tabx[href="#{section_id}"]').click()
        section = page.locator("#" + section_id)
        expected = view[view_key]
        assert str(expected["status"]) in section.inner_text()
        assert section.get_attribute("data-v38-status") == expected["status"]
        if section_id != "t-post1":
            assert section.locator(".card:visible").count() > 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8000/")
    args = parser.parse_args()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            for width in WIDTHS:
                page = browser.new_page(viewport={"width": width, "height": 900})
                page_errors: list[str] = []
                page.on("pageerror", lambda exc: page_errors.append(str(exc)))
                page.goto(args.url, wait_until="networkidle")

                tabs = page.locator("a.tabx")
                assert tabs.count() == 9
                assert [tabs.nth(i).inner_text().strip() for i in range(9)] == list(TAB_LABELS)

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
                    assert page.locator("section.on").count() == 1

                page.locator('a.tabx[href="#t-rs"]').click()
                page.locator('a.tabx[href="#t-weekly"]').click()
                assert page.url.endswith("#t-weekly")
                page.go_back(wait_until="networkidle")
                assert page.url.endswith("#t-rs")
                assert page.locator("#t-rs").is_visible()
                page.wait_for_function("window.scrollY === 0")

                metrics = page.evaluate(
                    """() => ({
                      innerWidth: window.innerWidth,
                      scrollWidth: document.documentElement.scrollWidth,
                      scrollY: window.scrollY
                    })"""
                )
                assert metrics["scrollWidth"] <= metrics["innerWidth"] + 1
                assert metrics["scrollY"] == 0
                assert not page_errors
                page.close()
        finally:
            browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
