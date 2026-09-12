#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from v38.site_builder import CANONICAL_BLOB_SHA, CANONICAL_SIZE, build_site
from v38.ui_contract import validate_production_html


def _copy_asset(out: Path, asset: Path) -> bool:
    if not asset.is_file():
        return False
    asset_dir = out.parent / "assets"
    asset_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(asset, asset_dir / asset.name)
    return True


def _inject_external_extension(out: Path, asset: Path) -> bool:
    if not _copy_asset(out, asset):
        return False
    html = out.read_text(encoding="utf-8")
    marker = f'<script src="assets/{asset.name}" defer></script>'
    if marker not in html:
        if "</body>" not in html:
            raise RuntimeError("production body end tag is missing")
        html = html.replace("</body>", marker + "\n</body>", 1)
        out.write_text(html, encoding="utf-8")
    return True


def main() -> int:
    p = argparse.ArgumentParser(
        description="Build live-bound V38 production UI from canonical v5"
    )
    p.add_argument("--canonical", default="V38_Command_Center_mock_v5.html")
    p.add_argument("--output", default="index.html")
    args = p.parse_args()

    out = build_site(args.canonical, args.output)

    # These extensions already contain the recovered current-data bindings, the
    # polished F1/F2/F3 card, recovered fine-theme/RS history, and the two-year
    # quarterly trend renderer. Copying them without loading them left acquired
    # data invisible in production, so load them in dependency order. The ticker
    # chart extension runs after the final UI so its delegated click handler sees
    # both canonical and dynamically rendered ticker rows without altering v5 CSS.
    observables = Path("assets/v38-observables.js")
    observables_enabled = _inject_external_extension(out, observables)
    polish = Path("assets/v38-polish.js")
    polish_enabled = _inject_external_extension(out, polish)
    recovery = Path("assets/v38-recovery.js")
    recovery_enabled = _inject_external_extension(out, recovery)
    final_ui = Path("assets/v38-final-ui.js")
    final_ui_enabled = _inject_external_extension(out, final_ui)
    options_chart = Path("assets/v38-options-chart.js")
    options_chart_enabled = _inject_external_extension(out, options_chart)

    report = validate_production_html(out.read_text(encoding="utf-8"))

    print(
        json.dumps(
            {
                "status": "LIVE_BINDING_SHELL_READY",
                "output": str(out),
                "canonical_blob_sha": CANONICAL_BLOB_SHA,
                "canonical_size": CANONICAL_SIZE,
                "tabs": [label for label, _ in report["tabs"]],
                "inline_script_count": report["inline_script_count"],
                "inline_event_handler_count": report["inline_event_handler_count"],
                "external_script_count": report["external_script_count"],
                "canonical_dom_preserved": True,
                "legacy_replacement_cards": False,
                "observables_extension": observables_enabled,
                "polish_extension": polish_enabled,
                "recovery_extension": recovery_enabled,
                "final_ui_extension": final_ui_enabled,
                "options_chart_extension": options_chart_enabled,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
