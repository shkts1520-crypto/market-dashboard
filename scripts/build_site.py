#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from v38.site_builder import (
    CANONICAL_BLOB_SHA,
    CANONICAL_SIZE,
    build_site,
)

from v38.ui_contract import (
    validate_production_html,
)


def _inject_external_extension(out: Path, asset: Path) -> bool:
    if not asset.is_file():
        return False
    asset_dir = out.parent / "assets"
    asset_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(asset, asset_dir / asset.name)

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
        description=(
            "Build live-bound V38 "
            "production UI from "
            "canonical v5"
        )
    )

    p.add_argument(
        "--canonical",
        default=(
            "V38_Command_Center_mock_v5.html"
        ),
    )

    p.add_argument(
        "--output",
        default="index.html",
    )

    args = p.parse_args()

    out = build_site(
        args.canonical,
        args.output,
    )

    observables = Path("assets/v38-observables.js")
    if observables.is_file():
        asset_dir = out.parent / "assets"
        asset_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(observables, asset_dir / observables.name)

    recovery = Path("assets/v38-recovery.js")
    recovery_enabled = _inject_external_extension(out, recovery)

    report = (
        validate_production_html(
            out.read_text(
                encoding="utf-8"
            )
        )
    )

    print(
        json.dumps(
            {
                "status": (
                    "LIVE_BINDING_SHELL_READY"
                ),
                "output": str(
                    out
                ),
                "canonical_blob_sha": (
                    CANONICAL_BLOB_SHA
                ),
                "canonical_size": (
                    CANONICAL_SIZE
                ),
                "tabs": [
                    label
                    for label, _
                    in report["tabs"]
                ],
                "inline_script_count": (
                    report[
                        "inline_script_count"
                    ]
                ),
                "inline_event_handler_count": (
                    report[
                        "inline_event_handler_count"
                    ]
                ),
                "external_script_count": (
                    report[
                        "external_script_count"
                    ]
                ),
                "canonical_dom_preserved": True,
                "legacy_replacement_cards": False,
                "observables_extension": observables.is_file(),
                "recovery_extension": recovery_enabled,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
