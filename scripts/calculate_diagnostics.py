from __future__ import annotations

import argparse
import json
from pathlib import Path

from v38.diagnostics import (
    atomic_write_json,
    build_diagnostics,
)


def _load_optional(path: Path) -> dict | None:
    if not path.exists():
        return None

    obj = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    if not isinstance(obj, dict):
        raise SystemExit(
            f"expected JSON object: {path}"
        )

    return obj


def main() -> int:
    ap = argparse.ArgumentParser(
        description=(
            "Build isolated V38 "
            "NQSAR/MC57 readiness diagnostics."
        )
    )

    ap.add_argument(
        "--session-date",
        required=True,
    )

    ap.add_argument(
        "--generated-at",
        required=True,
    )

    ap.add_argument(
        "--reference-dir",
        default="reference",
    )

    ap.add_argument(
        "--output-dir",
        default="data",
    )

    ap.add_argument(
        "--require-ready",
        action="store_true",
    )

    args = ap.parse_args()

    ref_dir = Path(args.reference_dir)
    out_dir = Path(args.output_dir)

    result = build_diagnostics(
        session_date=args.session_date,
        generated_at=args.generated_at,
        nqsar_reference=_load_optional(
            ref_dir / "nqsar_reference.json"
        ),
        mc57_reference=_load_optional(
            ref_dir / "mc57_reference.json"
        ),
    )

    atomic_write_json(
        out_dir / "nqsar_readiness.json",
        result["nqsar"],
    )

    atomic_write_json(
        out_dir / "mc57_readiness.json",
        result["mc57"],
    )

    atomic_write_json(
        out_dir / "diagnostics.json",
        result,
    )

    print(
        json.dumps(
            {
                "status": result["status"],
                "production_ready": result[
                    "production_ready"
                ],
                "blocked_components": result[
                    "blocked_components"
                ],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )

    return (
        2
        if args.require_ready
        and not result["production_ready"]
        else 0
    )


if __name__ == "__main__":
    raise SystemExit(main())
