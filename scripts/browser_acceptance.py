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


def _assert_status_notes_clean(section):
    for text in section.locator('.v38-bind-note').all_inner_texts():
        assert "DATA_REQUIRED" not in text
        assert "STALE" not in text
        assert "READY" not in text


def _assert_repaired_card(section, title):
    card = section.locator(".card").filter(has_text=title).first
    assert card.count() == 1, title
    assert card.get_attribute("data-v38-status") == "READY", title
    assert "データ未取得" not in card.inner_text(), title
    return card


def _assert_source_heading(card, japanese):
    h2 = card.locator("h2").first
    assert h2.count() == 1
    canonical = (
        card.get_attribute("data-v38-canonical-title")
        or card.get_attribute("data-v38-card-title")
        or ""
    ).strip()
    first_text = h2.evaluate(
        "el => (el.childNodes && el.childNodes.length && el.childNodes[0].textContent ? el.childNodes[0].textContent : '').trim()"
    )
    assert canonical
    assert japanese in canonical
    assert first_text == canonical
    en = h2.locator(".h2en").first
    assert en.count() == 1
    assert en.inner_text().strip()


def _assert_live_binding(page, view):
    page.wait_for_function("document.body.dataset.v38BindingStatus === 'ready'")
    page.wait_for_function("document.body.dataset.v38RecoveryStatus === 'ready'")
    page.wait_for_function("document.body.dataset.v38PolishStatus === 'ready'")
    page.wait_for_function("document.body.dataset.v38FinalUiStatus === 'ready'")
    page.wait_for_function("document.body.dataset.v38DataRepairStatus === 'ready'")
    page.wait_for_function("document.documentElement.dataset.v38NavReady === 'true'")
    page.wait_for_timeout(2100)
    page.wait_for_function("document.body.dataset.v38FinalUiStatus === 'ready'")
    page.wait_for_function("document.body.dataset.v38DataRepairStatus === 'ready'")

    body_text = page.locator("body").inner_text()
    assert "MOCK DATA" not in body_text
    assert "分析基準日 2026-09-08" not in body_text
    assert page.locator(".v38-production-state").count() == 0
    assert page.locator(".v38-live-grid,.v38-generic-row,.v38-rs-row").count() == 0

    daily = view["daily"]
    daily_section = page.locator("#t-market")
    daily_text = daily_section.inner_text()
    by_key = {row["key"]: row for row in daily["metrics"]}
    for key in ("breadth50", "breadth200", "f1", "f2", "f3", "market_QQQ"):
        row = by_key[key]
        assert row["display"] in daily_text

    for text in (
        "通常株PIT履歴", "遡及推計なし", "MC57 Raw", "MC57 EMA2 Raw", "MC57 Z",
        "MC57内部 12指標履歴", "日次保存済み履歴", "各指標は同一セッションの正本値のみ",
    ):
        assert text not in daily_text
    assert daily_section.locator(".v38-mc57-trend").count() == 0
    assert daily_section.locator('.v38-bind-note[data-v38-status="READY"]').count() == 0
    _assert_status_notes_clean(daily_section)

    mc57_card = _assert_repaired_card(daily_section, "MC57推移")
    assert int(mc57_card.get_attribute("data-v38-history-points") or "0") >= 21
    assert mc57_card.locator("svg.v38-live-spark").count() == 1

    for title in ("ブレッドス推移（50日線上の割合）", "ブレッドス推移（200日線上の割合）"):
        card = daily_section.locator(".card").filter(has_text=title).first
        assert card.count() == 1
        axis = card.locator(".v38-quarter-axis")
        assert axis.count() == 1
        assert axis.locator("span").count() >= 2
        assert card.locator("svg.v38-two-year-trend").count() == 1

    regime = daily_section.locator(".reg-card").filter(has_text="レジーム警戒灯").first
    assert regime.count() == 1
    assert regime.locator(".reg-grid .reg-cell").count() == 3
    assert "F1 リーダー脱落率" in regime.inner_text()
    assert "F2 勢い細り率" in regime.inner_text()
    assert "F3 キュー崩れ" in regime.inner_text()
    assert "算出不可" not in regime.inner_text()

    history_meta = daily.get("historical_reconstruction") or {}
    if history_meta.get("status") == "READY":
        assert history_meta.get("trading_gate_eligible") is False
        assert int(history_meta.get("session_count") or 0) >= 21
        f123_detail = daily.get("f123_detail") or {}
        assert f123_detail.get("status") == "READY"
        assert (f123_detail.get("f1") or {}).get("display_provenance") in {
            "CURRENT_SESSION_EXACT", "CURRENT_UNIVERSE_RECONSTRUCTED_DISPLAY_ONLY"
        }

    rs = view["rs"]
    page.locator('a.tabx[href="#t-rs"]').click()
    history = _rs_history(page)
    assert history["status"] == "READY"
    assert history["session_date"] == view["session_date"]
    if history.get("history_kind") == "CURRENT_UNIVERSE_RECONSTRUCTED":
        assert history.get("survivorship_warning") is True
        assert history.get("trading_gate_eligible") is False
        assert history.get("reconstructed_sessions", 0) > 0
    else:
        assert history.get("history_kind") in {None, "OBSERVED_ARCHIVE_ONLY"}
    for title in ("RSマルチタイムフレーム比較", "Top10 IN / OUT履歴", "三窓一致リーダー"):
        _assert_repaired_card(page.locator("#t-rs"), title)
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

        before_url = page.url
        link.click()
        modal = page.locator("#v38-options-chart-modal")
        assert modal.is_visible()
        assert modal.locator(".v38-oc-title").inner_text().strip() == first["ticker"]
        assert modal.locator(".v38-oc-tv .tradingview-widget-container").count() == 1
        page.wait_for_timeout(250)
        assert "Options" in modal.locator(".v38-oc-levels").inner_text()
        assert page.url == before_url
        modal.locator(".v38-oc-close").click()
        assert not modal.is_visible()

    core12 = view.get("core12") or {}
    core_rows = core12.get("rows") or []
    if core12.get("status") == "READY" and core_rows:
        page.locator('a.tabx[href="#t-port"]').click()
        core_section = page.locator("#t-port")
        for title in ("レジーム警戒灯", "RSリーダー控え"):
            _assert_repaired_card(core_section, title)

        core_rank_card = core_section.locator('.card[data-v38-binding-key="core12-main"]').first
        assert core_rank_card.count() == 1
        assert core_rank_card.get_attribute("data-v38-status") == "READY"
        assert "データ未取得" not in core_rank_card.inner_text()
        _assert_source_heading(core_rank_card, "個別株スリーブ")
        assert int(core_rank_card.get_attribute("data-v38-core-rows") or "0") > 0
        header_text = core_rank_card.locator("table tr").first.inner_text()
        for label in ("銘柄", "RS189", "RS63", "200MA乖離", "DDV20"):
            assert label in header_text

        ticker = str(core_rows[0].get("ticker") or core_rows[0].get("symbol") or "").upper()
        if ticker:
            row = core_rank_card.locator('tr[data-v38-ticker="' + ticker + '"]').first
            assert row.is_visible()
            assert ticker in row.inner_text()
            link = row.locator('a[data-v38-ticker="' + ticker + '"]').first
            assert link.is_visible()
            before_url = page.url
            link.click()
            modal = page.locator("#v38-options-chart-modal")
            assert modal.is_visible()
            assert modal.locator(".v38-oc-title").inner_text().strip() == ticker
            assert page.url == before_url
            modal.locator(".v38-oc-close").click()
            assert not modal.is_visible()

    positions = view.get("positions") or {}
    if positions.get("status") == "READY" and not positions.get("rows"):
        page.locator('a.tabx[href="#t-alloc"]').click()
        positions_section = page.locator("#t-alloc")
        assert "現在ポジションなし" in positions_section.inner_text()
        for title in (
            "現在の想定ポジション",
            "マーケット回復後のポジション入り銘柄",
            "エクイティカーブ",
        ):
            card = _assert_repaired_card(positions_section, title)
            _assert_source_heading(card, title)

    rotation = view.get("rotation") or {}
    if rotation.get("status") == "READY" and rotation.get("fine_theme_rows"):
        page.locator('a.tabx[href="#t-rotation"]').click()
        theme_card = _assert_repaired_card(page.locator("#t-rotation"), "サブテーマ別RS")
        assert int(theme_card.get_attribute("data-v38-theme-rows") or "0") > 0

    weekly = view.get("weekly") or {}
    if weekly.get("status") == "READY":
        page.locator('a.tabx[href="#t-weekly"]').click()
        weekly_section = page.locator("#t-weekly")
        for title in ("今週の結論", "今週の変化", "週次騰落ボード", "自分 vs QQQ円建て"):
            _assert_repaired_card(weekly_section, title)

    options = view.get("options") or {}
    if options.get("status") == "READY":
        page.locator('a.tabx[href="#t-options"]').click()
        options_section = page.locator("#t-options")
        expected = {
            "0–6 DTE": "0-6",
            "7–21 DTE": "7-21",
            "22–45 DTE": "22-45",
            "0–45 DTE": "0-45",
        }
        for title, bucket in expected.items():
            card = _assert_repaired_card(options_section, title)
            _assert_source_heading(card, title)
            assert card.get_attribute("data-v38-option-bucket") == bucket
            assert int(card.get_attribute("data-v38-option-rows") or "0") > 0
            rows = card.locator(".rsx-item")
            assert rows.count() > 0
            row_text = rows.first.inner_text()
            for label in ("Spot", "Call / Flip / Put", "Expected Move", "Quality"):
                assert label in row_text
            assert "Direction" not in row_text
            assert "Confidence" not in row_text

    diagnostics = daily.get("market_diagnostics") or {}
    if diagnostics.get("series"):
        page.locator('a.tabx[href="#t-market"]').click()
        assert page.locator("#t-market svg.v38-live-spark").count() >= 3

    for section_id, view_key in GENERIC_BINDINGS:
        page.locator(f'a.tabx[href="#{section_id}"]').click()
        section = page.locator("#" + section_id)
        expected = view[view_key]
        assert section.get_attribute("data-v38-status") == expected["status"]
        _assert_status_notes_clean(section)
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

                sentinel = "v38-tab-no-reload-" + str(width)
                page.evaluate("value => { window.__v38TabSentinel = value; }", sentinel)
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
                    assert page.evaluate("window.__v38TabSentinel") == sentinel
                    _assert_status_notes_clean(section)

                page.locator('a.tabx[href="#t-rs"]').click()
                page.locator('a.tabx[href="#t-weekly"]').click()
                assert page.url.endswith("#t-weekly")
                page.evaluate("history.back()")
                page.wait_for_function(
                    "location.hash === '#t-rs' && document.querySelector('#t-rs').classList.contains('on')"
                )
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