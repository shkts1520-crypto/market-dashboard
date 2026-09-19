# V38 Market Dashboard — recovered calculate slice

This package rebuilds the currently auditable calculation path without changing the v5 UI.

Implemented:

- PIT OHLCV + PIT Universe -> `rs.json`, `breadth.json`
- audited F1/F2/F3 -> `f123.json`
- upstream NQSAR + Breadth -> `market_state.json`
- normal-stock Eligibility + Attack/Selective ranking contract -> `core12.json`
- staged calculate pipeline: calculate all outputs first, validate common contract/session, then publish files
- compact session archive under `data/history/` for Breadth, market closes, F1/F2/F3, RS Top 100, acquisition quality, and authority readiness
- automatic frozen `old_top24.json` materialization: authoritative archived session snapshots are preferred; while that archive is still accumulating, retained historical OHLC reconstruction supplies the original current-universe F1 baseline with explicit survivorship provenance

Deliberately not invented:

- NQSAR FSM calculation (golden fixture still required)
- MC57 value (fixed 57-ETF membership + golden fixture still required)
- F1 old Top24 when neither archived session snapshots nor retained historical OHLC can prove a complete 20-session-lag Top24
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

Optional verified dependencies can be supplied with `--old-top24`, `--classifications`, and `--theme-scores`. Production may recover `old_top24` from retained historical OHLC using the original F1 formula and records that reconstruction provenance; classifications and theme scores are never fabricated from current/static substitutes.

Each successful live run writes one idempotent `data/history/sessions/YYYY-MM-DD.json` snapshot and rebuilds `data/history/index.json`. Re-running the same session replaces that session instead of duplicating it. Position rows are deliberately excluded from this public historical archive.
