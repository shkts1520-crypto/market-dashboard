#!/usr/bin/env python3
from __future__ import annotations

import argparse

from v38.calculate_pipeline import calculate_pipeline


def main() -> int:
    p = argparse.ArgumentParser(description="Run the auditable V38 calculate slice")
    p.add_argument("--ohlcv", required=True)
    p.add_argument("--universe", required=True)
    p.add_argument("--nqsar", required=True)
    p.add_argument("--output-dir", default="data")
    p.add_argument("--session-date", required=True)
    p.add_argument("--generated-at", required=True)
    p.add_argument("--stock-source", required=True)
    p.add_argument("--old-top24")
    p.add_argument("--classifications")
    p.add_argument("--theme-scores")
    a = p.parse_args()
    for path in calculate_pipeline(
        ohlcv_path=a.ohlcv,
        universe_path=a.universe,
        nqsar_path=a.nqsar,
        output_dir=a.output_dir,
        session_date=a.session_date,
        generated_at=a.generated_at,
        stock_source=a.stock_source,
        old_top24_path=a.old_top24,
        classifications_path=a.classifications,
        theme_scores_path=a.theme_scores,
    ):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
