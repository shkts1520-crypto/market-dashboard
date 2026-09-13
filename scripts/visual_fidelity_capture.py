#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

WIDTHS = (375, 390, 430)
TARGETS = {
    "rotation": ("#t-rotation", ".v38-source-rotation-wrap"),
    "options": ("#t-options", ".card.rsx-card"),
    "vwap": ("#t-rs", ".v38-vwap-card"),
}


def open_tab(page, section_id: str) -> None:
    tab = page.locator(f'a.tabx[href="{section_id}"]')
    assert tab.count() == 1, section_id
    tab.click()
    page.wait_for_function(
        "id => document.querySelector(id) && document.querySelector(id).classList.contains('on')",
        arg=section_id,
    )
    page.wait_for_timeout(250)


def box_dict(locator) -> dict[str, float | None]:
    box = locator.bounding_box() or {}
    return {key: box.get(key) for key in ("x", "y", "width", "height")}


def computed(locator, properties: tuple[str, ...]) -> dict[str, str]:
    return locator.evaluate(
        """(el, properties) => {
          const style = getComputedStyle(el);
          return Object.fromEntries(properties.map((p) => [p, style.getPropertyValue(p)]));
        }""",
        list(properties),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture V38 source-fidelity mobile screenshots")
    parser.add_argument("--url", default="http://127.0.0.1:8000/")
    parser.add_argument("--output", default="visual-fidelity")
    args = parser.parse_args()

    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, dict] = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            for width in WIDTHS:
                page = browser.new_page(viewport={"width": width, "height": 900}, device_scale_factor=1)
                errors: list[str] = []
                page.on("pageerror", lambda exc: errors.append(str(exc)))
                page.goto(args.url, wait_until="networkidle")
                page.wait_for_function("document.body.dataset.v38BindingStatus === 'ready'")
                page.wait_for_function("document.body.dataset.v38SourceFidelity === 'canonical-v5'")
                page.wait_for_timeout(5200)

                width_data: dict[str, object] = {
                    "viewport": width,
                    "page_errors": errors,
                    "document_scroll_width": page.evaluate("document.documentElement.scrollWidth"),
                    "inner_width": page.evaluate("window.innerWidth"),
                }

                search = page.locator("#v38-universe-search")
                assert search.count() == 1
                input_box = search.locator(".tksearch")
                input_box.fill("NV")
                page.wait_for_timeout(250)
                search.screenshot(path=str(out / f"search-{width}.png"))
                width_data["search"] = {
                    "box": box_dict(search),
                    "input": computed(input_box, ("font-size", "padding", "border-radius", "background-color")),
                    "result_count": search.locator(".v38-search-result").count(),
                }
                input_box.fill("")

                for name, (section_id, selector) in TARGETS.items():
                    open_tab(page, section_id)
                    target = page.locator(f"{section_id} {selector}").first
                    assert target.count() == 1, (name, selector)
                    target.scroll_into_view_if_needed()
                    page.wait_for_timeout(150)
                    target.screenshot(path=str(out / f"{name}-{width}.png"))
                    width_data[name] = {
                        "box": box_dict(target),
                        "style": computed(target, ("font-size", "padding", "border-radius", "background-color")),
                    }

                rotation_scaler = page.locator("#t-rotation .v38-source-scaler").first
                if rotation_scaler.count():
                    width_data["rotation_scaler"] = {
                        "box": box_dict(rotation_scaler),
                        "transform": rotation_scaler.evaluate("el => getComputedStyle(el).transform"),
                    }

                vwap_table = page.locator("#t-rs .v38-vwap-card table").first
                if vwap_table.count():
                    width_data["vwap_headers"] = vwap_table.locator("th").all_inner_texts()
                    width_data["vwap_table"] = computed(vwap_table, ("font-size", "table-layout", "width"))

                options_root = page.locator("#t-options .v38-canonical-options").first
                if options_root.count():
                    width_data["options_card_count"] = options_root.locator(":scope > .card.rsx-card").count()

                manifest[str(width)] = width_data
                if errors:
                    raise AssertionError(f"page errors at {width}: {errors!r}")
                assert width_data["document_scroll_width"] <= width_data["inner_width"] + 1
                page.close()
        finally:
            browser.close()

    (out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps({"status": "OK", "output": str(out), "widths": WIDTHS}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
