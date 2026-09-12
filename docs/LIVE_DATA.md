# V38 Live Data Acquisition

Status: production acquisition layer.

This layer only acquires/normalizes inputs and runs the already-audited stock/F1-F3 calculators. It does not change V38 trading rules, the canonical v5 UI, ranking weights, or exit logic.

## Sources and current-session contract

- Universe: TradingView `america/scan` current US stock snapshot.
- Universe scope: NYSE / NASDAQ / AMEX, market cap >= $200M, scanner price >= $1.
- Transport cleanup: preferred/warrant/right/unit/subordinated-note descriptions, slash/space symbols, and only the six historically explicit duplicate share-class pairs are removed.
- The old heuristic "healthcare and market cap < $10B" biotech deletion is intentionally **not** used. Structural Clinical Biotech remains `DATA_REQUIRED` until its authoritative classification table is recovered.
- Prices: Yahoo Finance through `yfinance==0.2.66`, requested with `auto_adjust=False`; OHLC is normalized by the `Adj Close / Close` factor. A bar is marked `split_checked=true` only when that factor is finite and positive.
- Display market history: the five required symbols plus broad/equal-weight, volatility-term, credit/rates, macro, commodity, leveraged-semiconductor, and 11 sector ETF series are requested in bounded chunks. Missing diagnostic symbols remain unavailable, while any missing required current-session symbol aborts the run.
- Session authority: latest common completed QQQ/SPY daily session. A manual run before 16:10 America/New_York does not promote the current forming US daily bar.
- Yahoo current-session coverage must be >=80%. TradingView universe count must not fall below 80% of the preceding successful active-universe count. Failure aborts before publication.

The TradingView snapshot is valid evidence for the current calculation session only. It is not retroactively used as a historical PIT universe for backtests.

## Published files

A successful acquisition atomically publishes:

- `data/rs.json`
- `data/breadth.json`
- `data/f123.json`
- `data/market_inputs.json`
- `data/state.json`
- `data/acquisition_manifest.json`
- `data/nqsar.json` only when an authoritative `sar_state.txt` is present and passes the strict same-session adapter

Large transient universe/OHLCV tables are not committed; they exist only inside the Actions runner for the calculation run.

`rs.json` retains 63 completed-session closes for the union of the Top 100 RS63/RS126/RS189 rows. It also stores 126 sessions of explicitly display-only current-universe diagnostics: advancing participation, aggregate volume versus its prior 200-session average, up/down dollar-volume ratio, A/D line, and McClellan EMA19 minus EMA39. These series do not enter any V38 trading gate.

## Deliberately unresolved / fail-closed

The acquisition manifest continues to report `DATA_REQUIRED` for inputs that do not have an authoritative recovered source/fixture:

- MC57 fixed 57-ETF membership and golden fixture
- Structural Clinical Biotech classification
- Fine-grained PIT Peer Theme / strict LOO input
- Options upstream
- Positions authoritative ledger/schema
- QQQ 4H Stage56 fixture (therefore the exact TQQQ Panic 4H trigger is not reconstructed)

No current value is inferred for any of these.

## Schedule

`V38 Live Data Acquisition` runs at the recovered production cadence:

- 22:17 UTC Monday-Friday (07:17 JST Tuesday-Saturday)
- 04:17 UTC Tuesday-Saturday (13:17 JST Tuesday-Saturday retry)

It can also be dispatched manually.
