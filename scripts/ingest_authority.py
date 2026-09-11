#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from v38.authority_contracts import AuthorityContractError
from v38.extended_authority_contracts import validate_full_authority
from v38.freshness import atomic_write_json

KINDS = (
    "nqsar",
    "mc57",
    "classifications",
    "theme_scores",
    "options",
    "positions",
    "old_top24",
)


def _require_aware_generated_at(payload: object) -> datetime:
    if not isinstance(payload, dict):
        raise SystemExit("authority payload must be a JSON object")
    value = payload.get("generated_at")
    if not isinstance(value, str) or not value.strip():
        raise SystemExit("authority generated_at is required")
    text = value.strip()
    try:
        parsed = datetime.fromisoformat(text[:-1] + "+00:00" if text.endswith("Z") else text)
    except ValueError as exc:
        raise SystemExit("authority generated_at must be ISO-8601") from exc
    if parsed.utcoffset() is None:
        raise SystemExit("authority generated_at must include a timezone offset")
    if parsed > datetime.now(timezone.utc):
        raise SystemExit("authority generated_at must not be in the future")
    return parsed


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate and atomically promote one authoritative V38 upstream payload"
    )
    parser.add_argument("--kind", required=True, choices=KINDS)
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

    _require_aware_generated_at(payload)
    try:
        relative, normalized = validate_full_authority(
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
                "session_date": normalized.get("session_date"),
                "target_session_date": normalized.get("target_session_date"),
                "source": normalized["source"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
