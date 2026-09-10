# V38 Authoritative Reference Recovery

Status date: 2026-09-10

This document records only source hierarchy and contracts recovered from prior V38 materials. It does not promote reconstructed logic into production.

## NQSAR

Recovered authoritative hierarchy:

1. `sar_state.txt` produced by the TradingView -> Pipedream path is the preferred direct state source.
2. `EXP_STATE_ID` in the NQ CSV is a deeper fallback direct label source.
3. Reconstructed `_onimine_state` logic is research/recovery material only and is not authoritative production logic.

Recovered `EXP_STATE_ID` mapping:

- 1 = Blue
- 2 = Yellow
- 3 = Red
- 4 = Green

Known frozen indicator metadata remains:

- instrument: NQ
- PSAR step 0.02 / increment 0.02 / max 0.08
- EMA21
- Wilder RSI14
- states: Blue / Green / Yellow / Red
- completed bars only

The exact authoritative FSM and golden fixture are still missing. Therefore the NQSAR readiness gate remains `DATA_REQUIRED` until a verified reference package supplies `fsm_version` and `golden_fixture_sha256`.

`parse_authoritative_input()` validates already-authoritative labels only. It does not calculate PSAR, EMA, RSI, or state transitions. It rejects missing session metadata, stale/future session dates, future generation timestamps, missing sources, invalid state IDs, and conflicting state labels.

Recovered production code also establishes the accepted dated `sar_state.txt` parsing contract. `parse_sar_state_text()` accepts:

- JSON objects using `color` / `state` / `sar` and `asof` / `date` / `session` aliases.
- CSV-ish/plain text containing a `YYYY-MM-DD` date and one Blue/Green/Yellow/Red token, including `2026-07-10,Blue`.

Unlike the legacy compatibility path, the recovered production guard is kept fail-closed here: an embedded session date is mandatory. Undated plain-color files are not enabled.

## MC57

The mathematical contract is frozen in `mc57_engine.py`, but the exact fixed 57-ETF universe and golden fixture remain unrecovered. No older MRI/MC15 ETF list is promoted or substituted.

Required before MC57 can become `READY`:

- verified exact 57 unique ETF tickers
- authoritative source/provenance
- golden fixture SHA-256

Until then MC57 stays `DATA_REQUIRED` and production values remain null rather than guessed.

## Production safety

This recovery work does not change Normal Stock, Panic Reset, TQQQ Panic, F1/F2/F3, portfolio allocation, exits, ranking, or any production shard. NQSAR and MC57 readiness gates are intentionally unchanged.
