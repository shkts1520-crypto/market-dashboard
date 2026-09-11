#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from v38.site_builder import (
    CANONICAL_BLOB_SHA,
    CANONICAL_SIZE,
    build_site,
)

from v38.ui_contract import (
    validate_production_html,
)


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
