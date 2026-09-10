from __future__ import annotations

import argparse

from v38.market_engine import calculate_market_from_files


def main() -> int:
    p = argparse.ArgumentParser(description="Calculate V38 market mode and Core12 from validated shards")
    p.add_argument("--rs", required=True)
    p.add_argument("--breadth", required=True)
    p.add_argument("--nqsar", required=True)
    p.add_argument("--output-dir", default="data")
    p.add_argument("--generated-at", required=True)
    p.add_argument("--classifications")
    p.add_argument("--theme-scores")
    a = p.parse_args()
    paths = calculate_market_from_files(
        a.rs,
        a.breadth,
        a.nqsar,
        a.output_dir,
        generated_at=a.generated_at,
        classifications_path=a.classifications,
        theme_scores_path=a.theme_scores,
    )
    for path in paths:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
