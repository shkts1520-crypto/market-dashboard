#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from v38.freshness import (
    atomic_write_json,
    build_freshness,
)

from v38.ui_contract import (
    UIContractError,
    validate_canonical_shell,
)


def main() -> int:
    p = argparse.ArgumentParser(
        description=(
            "Validate V38 canonical UI shell "
            "and shard freshness before "
            "renderer work"
        )
    )

    p.add_argument(
        "--canonical",
        default=(
            "V38_Command_Center_mock_v5.html"
        ),
    )

    p.add_argument(
        "--data-dir",
        default="data",
    )

    p.add_argument(
        "--session-date",
        required=True,
    )

    p.add_argument(
        "--generated-at",
        required=True,
    )

    p.add_argument(
        "--freshness-output",
    )

    p.add_argument(
        "--require-all-ready",
        action="store_true",
    )

    a = p.parse_args()

    canonical = Path(
        a.canonical
    )

    if not canonical.exists():
        print(
            json.dumps(
                {
                    "status": (
                        "DATA_REQUIRED"
                    ),
                    "reason": (
                        "CANONICAL_V5_MISSING"
                    ),
                    "path": str(
                        canonical
                    ),
                },
                sort_keys=True,
            )
        )

        return 3

    try:
        shell = (
            validate_canonical_shell(
                canonical.read_text(
                    encoding="utf-8"
                )
            )
        )

    except (
        OSError,
        UnicodeDecodeError,
        UIContractError,
    ) as exc:
        print(
            json.dumps(
                {
                    "status": "FAILED",
                    "reason": (
                        "CANONICAL_V5_INVALID"
                    ),
                    "detail": str(exc),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )

        return 4

    freshness = build_freshness(
        a.data_dir,
        target_session=(
            a.session_date
        ),
        generated_at=(
            a.generated_at
        ),
    )

    if a.freshness_output:
        atomic_write_json(
            a.freshness_output,
            freshness,
        )

    result = {
        "status": freshness[
            "status"
        ],
        "canonical": "OK",
        "tabs": [
            label
            for label, _
            in shell["tabs"]
        ],
        "freshness": freshness,
    }

    print(
        json.dumps(
            result,
            ensure_ascii=False,
            sort_keys=True,
            allow_nan=False,
        )
    )

    if (
        a.require_all_ready
        and freshness["status"]
        != "READY"
    ):
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
