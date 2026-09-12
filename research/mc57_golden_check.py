#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from mc57_nqsar_shadow import CANDIDATE_57, calculate_mc57, download_adjusted_closes, finite_or_none

TARGET_DATE = pd.Timestamp("2026-08-28")
EXPECTED_MC57 = 56.438985
EXPECTED_COVERAGE = 57
OUT = Path("research_out")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    closes = download_adjusted_closes(CANDIDATE_57)
    panel, diag = calculate_mc57(closes, CANDIDATE_57)
    if TARGET_DATE not in panel.index:
        raise RuntimeError(f"target date missing: {TARGET_DATE.date()}")
    close_count = sum(int(TARGET_DATE in closes[t].index and pd.notna(closes[t].loc[TARGET_DATE])) for t in CANDIDATE_57 if t in closes)
    row = panel.loc[TARGET_DATE]
    actual = finite_or_none(row["mc57"])
    diff = None if actual is None else actual - EXPECTED_MC57
    payload = {
        "research_only": True,
        "production_authority": False,
        "reference": {
            "session_date": "2026-08-28",
            "expected_mc57": EXPECTED_MC57,
            "expected_coverage": EXPECTED_COVERAGE,
            "reference_run": 33379823471,
        },
        "universe": CANDIDATE_57,
        "universe_size": len(CANDIDATE_57),
        "downloaded": diag["downloaded"],
        "target_close_count": close_count,
        "target_close_coverage": close_count / len(CANDIDATE_57),
        "actual": {
            "raw": finite_or_none(row["raw"]),
            "ema2_raw": finite_or_none(row["ema2_raw"]),
            "mu_prior": finite_or_none(row["mu_prior"]),
            "sigma_prior": finite_or_none(row["sigma_prior"]),
            "z": finite_or_none(row["z"]),
            "mc57": actual,
        },
        "difference_points": diff,
        "absolute_difference": None if diff is None else abs(diff),
        "exact_6dp_match": actual is not None and round(actual, 6) == round(EXPECTED_MC57, 6),
        "notes": [
            "Recovered prior V38 reference: 2026-08-28 MC57=56.438985 with 57/57 coverage.",
            "Recovered universe identity: 56 theme/sector ETFs plus QQQE.",
            "This check intentionally uses the recovered final formula and Yahoo adjusted close history; a mismatch means another production detail remains unrecovered and must not be guessed.",
        ],
    }
    (OUT / "mc57_golden_20260828.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
