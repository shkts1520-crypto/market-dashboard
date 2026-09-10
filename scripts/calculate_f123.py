#!/usr/bin/env python3
from __future__ import annotations

import argparse

from v38.f123_engine import calculate_f123_from_files


def main() -> int:
    p = argparse.ArgumentParser(description="Calculate audited V38 F1/F2/F3")
    p.add_argument("--rs", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--generated-at", required=True)
    p.add_argument("--old-top24")
    a = p.parse_args()
    calculate_f123_from_files(
        a.rs,
        a.output,
        generated_at=a.generated_at,
        old_top24_path=a.old_top24,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
