#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

from v38.ui_payload import write_ui_payload


def main() -> int:
    p = argparse.ArgumentParser(
        description="Build fail-closed V38 browser payload from authoritative shards."
    )
    p.add_argument("--data-dir", default="data")
    p.add_argument("--output", default="data/ui_payload.json")
    p.add_argument("--generated-at")
    p.add_argument("--target-session")
    args = p.parse_args()

    generated_at = args.generated_at or datetime.now(timezone.utc).isoformat()
    out = write_ui_payload(
        args.data_dir,
        args.output,
        generated_at=generated_at,
        target_session=args.target_session,
    )
    payload = json.loads(out.read_text(encoding="utf-8"))
    print(json.dumps(
        {
            "status": payload["status"],
            "session_date": payload["session_date"],
            "output": str(out),
            "section_statuses": {
                section_id: section["status"]
                for section_id, section in payload["sections"].items()
            },
        },
        ensure_ascii=False,
        sort_keys=True,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
