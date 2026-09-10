# V38 Market Dashboard — recovered calculate slice

This package rebuilds the currently auditable calculation path without changing the v5 UI.

Implemented:

- PIT OHLCV + PIT Universe -> `rs.json`, `breadth.json`
- audited F1/F2/F3 -> `f123.json`
- upstream NQSAR + Breadth -> `market_state.json`
- normal-stock Eligibility + Attack/Selective ranking contract -> `core12.json`
- staged calculate pipeline: calculate all outputs first, validate common contract/session, then publish files

Deliberately not invented:

- NQSAR FSM calculation (golden fixture still required)
- MC57 value (fixed 57-ETF membership + golden fixture still required)
- F1 old Top24 when a verified 20-session PIT snapshot is absent
- Structural Clinical Biotech classifications when source/version is absent
- Peer Theme scores when fine-grained PIT theme membership/LOO inputs are absent
- Options upstream engine, Positions upstream schema, and the remaining dashboard shards

Run the validated suite:

```bash
PYTHONPATH=src pytest -q
python -m compileall -q src scripts
```

Run the current calculate slice:

```bash
PYTHONPATH=src python scripts/calculate_all.py \
  --ohlcv inputs/pit/ohlcv.csv \
  --universe inputs/pit/universe.csv \
  --nqsar inputs/nqsar.json \
  --output-dir data \
  --session-date 2026-09-08 \
  --generated-at 2026-09-09T05:00:00+09:00 \
  --stock-source PIT_PROVIDER_NAME
```

Optional verified dependencies can be supplied with `--old-top24`, `--classifications`, and `--theme-scores`. Missing optional dependencies result in `DATA_REQUIRED`; they are not backfilled from current/static data.
