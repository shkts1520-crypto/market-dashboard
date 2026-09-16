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
BASELINE_COUNTS = {
    "t-market": 19, "t-alloc": 4, "t-port": 5, "t-today": 20,
    "t-rotation": 7, "t-movers": 1, "t-rs": 7, "t-weekly": 11,
}
VIEW_KEYS = {
    "t-market": "daily", "t-alloc": "positions", "t-port": "core12",
    "t-today": "setups", "t-rotation": "rotation", "t-movers": "movers",
    "t-rs": "rs", "t-weekly": "weekly", "t-options": "options",
    "t-post1": "publish", "t-rules": "rules",
}


def _view_model(page):
    return page.evaluate(
        """async () => {
          const response = await fetch('data/ui_view_model.json', {cache: 'no-store'});
          if (!response.ok) throw new Error('ui_view_model HTTP ' + response.status);
          return response.json();
        }"""
    )


def _assert_ready_has_no_false_missing(section, expected):
    if expected.get("status") != "READY":
        return
    for text in section.locator(".v38-bind-note").all_inner_texts():
        assert "DATA_REQUIRED" not in text
        assert "STALE" not in text
        assert "READY" not in text


def _assert_source_specialized(page):
    # These exact source-py displays previously regressed while generic card-count CI stayed green.
    daily_regime = page.locator("#t-market .reg-card")
    core_regime = page.locator("#t-port .reg-card")
    assert daily_regime.count() == 1
    assert core_regime.count() == 1
    assert daily_regime.locator(".reg-cell").count() == 3
    assert core_regime.locator(".reg-cell").count() == 3
    for regime in (daily_regime, core_regime):
        text = regime.inner_text()
        for label in ("F1", "F2", "F3"):
            assert label in text
        assert "NQSAR" not in text

    defense = page.locator("#t-port .def-card")
    assert defense.count() == 1
    assert "防御チェックリスト" in defense.inner_text()
    assert "Hard Gate" in defense.inner_text()

    vix = page.locator("#t-market .vixcy")
    assert vix.count() == 1
    assert vix.locator(".vixvals > div").count() == 6
    vix_text = vix.inner_text()
    for label in ("VIX", "High", "LWMA5", "LWMA10", "+1σ", "+2σ"):
        assert label in vix_text
    assert vix.locator(".vixwtabs button").count() == 4
    assert vix.locator(".vixchart svg").count() == 1

    ftd = page.locator("#t-market .card").filter(has_text="フォロースルー・デイ").first
    assert ftd.count() == 1
    ftd_text = ftd.inner_text()
    for machine_token in ("SOURCE_DEFINED_", "SOURCE_UNAVAILABLE"):
        assert machine_token not in ftd_text

    rules = page.locator("#t-rules")
    rules_text = rules.inner_text()
    for heading in ("配分", "市場モード", "通常個別株", "RSI30 Panic Reset", "TQQQ Panic"):
        assert heading in rules_text
    for machine_prefix in ("allocation.", "market_mode.", "normal_stock.", "panic_reset.", "tqqq_panic."):
        assert machine_prefix not in rules_text


def _assert_source_dom(page):
    for section_id, minimum in BASELINE_COUNTS.items():
        assert page.locator(f"#{section_id} .card").count() >= minimum, section_id
    setups = page.locator("#t-today").inner_text()
    for title in ("Pre-Breakout", "Confluence", "Multi VWAP", "Leaders"):
        assert title in setups
    movers = page.locator("#t-movers")
    assert movers.locator(".mv-wrap").count() == 1
    for title in ("3窓一致", "前日", "1週間", "1ヶ月"):
        assert title in movers.inner_text()
    rotation = page.locator("#t-rotation").inner_text()
    for title in ("強い業種の主導株", "セクターETF強弱", "サブテーマ別RS"):
        assert title in rotation
    assert page.locator(".v38-live-grid,.v38-generic-row,.v38-rs-row").count() == 0
    _assert_source_specialized(page)


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
    error_count = page.evaluate("document.body.dataset.v38CanonicalBinderErrors || '0'")
    if state != "ready" or error_count != "0":
        failures = page.evaluate(
            """() => Array.from(document.querySelectorAll('section .card[data-v38-reason="UNBOUND_VISIBLE_CARD"]'))
              .map(card => ({
                section: card.closest('section')?.id || '',
                title: (card.querySelector('h2,.hdr h2,.chd h2')?.textContent || '').replace(/\s+/g,' ').trim()
              }))"""
        )
        raise AssertionError(f"canonical binder state={state} errors={error_count} unbound={failures}")


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
                # The source finalizer explicitly runs after the canonical binder. Do not inspect
                # or capture screenshots until the specialized cards have won the render race.
                page.wait_for_function("document.body.dataset.v38PySourceFinal === 'ready'")
                tabs = page.locator("a.tabx")
                assert tabs.count() == 11
                assert [tabs.nth(i).inner_text().strip() for i in range(11)] == list(TAB_LABELS)
                view = _view_model(page)
                _assert_source_dom(page)

                sentinel = f"v38-no-reload-{width}"
                page.evaluate("value => window.__v38Sentinel = value", sentinel)
                for i in range(11):
                    tab = tabs.nth(i)
                    href = tab.get_attribute("href")
                    assert href and href.startswith("#")
                    section_id = href[1:]
                    tab.click()
                    section = page.locator("#" + section_id)
                    assert section.is_visible()
                    assert page.locator("section.on").count() == 1
                    assert page.evaluate("window.__v38Sentinel") == sentinel
                    if section_id == "t-post1":
                        assert section.get_attribute("data-v38-publish-cards") == "ready"
                        frames = section.locator("iframe.postframe:visible")
                        assert frames.count() >= 2
                    else:
                        assert section.locator(".card:visible,.postwrap:visible").count() > 0
                    _assert_ready_has_no_false_missing(section, view.get(VIEW_KEYS[section_id]) or {})
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 2"), section_id

                    page.wait_for_timeout(120)
                    assert section.inner_text().strip(), (width, section_id, "visible section has no text")
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
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 2")
                assert not errors, errors
                page.close()
        finally:
            browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
