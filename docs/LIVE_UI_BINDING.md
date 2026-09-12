# V38 Live UI Binding

Status date: 2026-09-12

This stage connects already validated acquisition outputs to the production UI without changing the canonical V5 DOM/CSS authority or any trading rule.

## Live-bound sections

### Daily

The display-only view model exposes, for the authoritative `state.json` session only:

- Market Mode: only when an authoritative current-session `market_state.json` exists
- NQSAR: only when an authoritative current-session `nqsar.json` exists
- Breadth 50 / Breadth 200 from `breadth.json`
- MC57: only when a current-session `mc57.json` exists
- F1 / F2 / F3 from `f123.json`; missing PIT dependencies stay `DATA_REQUIRED`
- QQQ / TQQQ / VIX / NQ / SPY current-session closes from `market_inputs.json`
- performance horizons and live charts for broad/equal-weight, volatility, credit/rates, macro, commodities, SOXL, and sector ETFs when their completed bars are available
- saved Breadth/F1-F3 history, plus display-only volume participation, up/down dollar volume, A/D, and McClellan history

No browser-side threshold or trading calculation is performed.

### RS

The first 24 RS189 rows are displayed in their source order. Separate RS63/RS126/RS189 cards use ranks calculated in the Python view model from the already calculated percentile fields; the browser never recalculates RS. Top rows include a 63-session live SVG sparkline, price/return context, sector/industry metadata, and a TradingView link. This remains diagnostic and is not Core 12 eligibility/ranking.

Rotation and Weekly reuse their original canonical cards. Available market and stock-universe diagnostics are inserted into those cards; unresolved Peer Theme and other rule-authority values stay `DATA_REQUIRED` and are never replaced by diagnostic proxies.

## Fail-closed behavior

Missing or cross-session inputs render `—`, `DATA_REQUIRED`, or `STALE` inside the original canonical cards. The old replacement grids and whole-section visibility shield are not used. Positions, Core 12, Rotation, Weekly, Options, Publish, and Rules remain fail-closed until their authoritative shards exist.

## Mobile acceptance

Production CI compares rendered Daily and RS values to `ui_view_model.json`, verifies TradingView targets and any expected SVG sparklines, and re-runs the full tab/hash/history/overflow checks at 375, 390, and 430 CSS pixels.
