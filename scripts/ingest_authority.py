#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from v38.authority_contracts import AuthorityContractError, validate_authority
from v38.freshness import atomic_write_json


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate and atomically promote one authoritative V38 upstream payload"
    )
    parser.add_argument(
        "--kind",
        required=True,
        choices=("nqsar", "mc57", "classifications", "theme_scores", "options", "positions"),
    )
    parser.add_argument("--payload", required=True, help="JSON payload path")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--expected-session")
    args = parser.parse_args()

    src = Path(args.payload)
    if not src.is_file():
        raise SystemExit(f"authority payload not found: {src}")
    try:
        payload = json.loads(src.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid authority JSON: {exc}") from exc

    try:
        relative, normalized = validate_authority(
            args.kind,
            payload,
            expected_session=args.expected_session,
        )
    except AuthorityContractError as exc:
        raise SystemExit(f"authority rejected: {exc}") from exc

    target = Path(args.data_dir) / relative
    atomic_write_json(target, normalized)
    print(
        json.dumps(
            {
                "status": "PROMOTED",
                "kind": args.kind,
                "target": target.as_posix(),
                "session_date": normalized["session_date"],
                "source": normalized["source"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
