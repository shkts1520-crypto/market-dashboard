# V38 NQSAR / MC57 Diagnostics

This package is intentionally isolated from the production trading path.

## Implemented from the 2026-09-10 master specification

- MC57 mathematical contract:
  - fixed 57-ETF design contract; the actual ticker set is **not guessed**
  - 12 equal-weight participation metrics
  - binary metrics: True=100 / False=0; missing observations excluded
  - DD52 continuous score: `clip((DD52 + 0.30) / 0.25 * 100, 0, 100)`
  - Raw = equal-weight mean of all 12 metric scores
  - EMA2: `span=2, adjust=False`
  - calibration: immediately preceding 3780 sessions, current day excluded, `ddof=0`
  - `MC57 = 100 / (1 + 3**(-Z))`
- NQSAR known contract metadata:
  - NQ, PSAR(step=.02, increment=.02, max=.08), EMA21, Wilder RSI14
  - Blue / Green / Yellow / Red
  - completed bars only
- Explicit readiness gates.

## Intentionally DATA_REQUIRED

The following are never inferred:

1. NQSAR exact FSM / `_onimine_state` transition logic and golden fixture.
2. MC57 exact fixed 57-ETF ticker universe, replacement policy, and golden fixture.

Until those references are frozen, diagnostics return `DATA_REQUIRED` and never publish a fabricated NQSAR state or MC57 value.

## CLI

```bash
PYTHONPATH=src python scripts/calculate_diagnostics.py \
  --session-date 2026-09-08 \
  --generated-at 2026-09-10T19:00:00+09:00 \
  --reference-dir reference \
  --output-dir data
```

Optional reference files:

- `reference/nqsar_reference.json`
- `reference/mc57_reference.json`

Use `--require-ready` when CI should fail until both authoritative reference packages are present.

This module does not alter Normal Stock, TQQQ, Panic Reset, F1/F2/F3, ranking, positions, or any production shard.
