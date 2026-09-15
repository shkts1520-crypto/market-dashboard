# V38 Command Center source restoration audit

Baseline date: 2026-09-05  
Implementation date: 2026-09-15  
Visual authorities: source Production HTML for Setups/Movers; canonical v5 blob `966fe157e3d35344f6e373877b3de5689409dd67` for the remaining tabs; `assets/v38-rules-0905.html` for Rules.

## Baseline classification

| Tab | Card / surface | Classification | Before | Restored implementation |
|---|---|---|---|---|
| Daily | Market Summary, Change Log, MC57/history, Performance, Breadth, diagnostics, macro/rates/VIX/sentiment/FTD | BASELINE_0905 | Runtime neutralize/rebuild | Canonical DOM retained; selected live values bind in place |
| Positions | Holdings, expected positions, recovery candidates, equity curve | BASELINE_0905 | Generic one-card rendering | Canonical DOM retained; empty success displays `現在保有なし` |
| Core 12 | Regime, entrants, Core 12, bench | BASELINE_0905 | Generic one-card rendering | Canonical DOM retained |
| Setups | Search, Pre-Breakout, Put Wall, Confluence, Pocket Pivot, Today's Setups, patterns, VCP, 21EMA, Multi VWAP, pivots, signals, playbook, grades, status, cohort, entries, exits, leaders | REMOVED_AFTER_0905 | Empty section plus runtime scaffold | Exact source fragment restored at build time (20 cards) |
| Rotation | RRG/flow, heatmap, groups, leaders, sector ETFs, sub-theme RS, theme ETFs | BROKEN_AFTER_0905 | Neutralize + visual rebuild + owner loop | Canonical source DOM retained (7 cards); no owner/retry |
| Movers | Summary, three-window agreement, 1d/1w/1m gainers and losers | REMOVED_AFTER_0905 | Empty section plus runtime rebuild | Exact source fragment restored at build time (1 composite card) |
| RS | Multi-timeframe, IN/OUT, persistence, cross-window, RS63/126/189 | BROKEN_AFTER_0905 | Neutralize + generic rows | Canonical DOM retained; rank rows bind in place |
| Weekly | This Week, Next Week, macro, rates, pressure, diff, regime, movers, breadth, quality, leverage, My Week | BROKEN_AFTER_0905 | Generic reconstruction | Canonical DOM retained (12 cards) |
| Options | Four DTE buckets and chart levels | ADDED_AFTER_0905 | Working approved extension | Kept; no Direction/Confidence/synthetic values |
| Publish | Two post blocks | BASELINE_0905 | `postwrap.replaceChildren()` | Original blocks retained |
| Rules | 09/05 rule text | BASELINE_0905 | Risk of current-rule replacement | Restored from `assets/v38-rules-0905.html` |

## Data bindings

| Screen item | Source | Key |
|---|---|---|
| Daily status and breadth | `data/ui_view_model.json` | `daily.metrics[mc57,breadth50,breadth200]` |
| MC57 history | `data/ui_view_model.json` | `daily.mc57_detail`, `daily.display_history` |
| Positions | `data/ui_view_model.json` | `positions.status`, `positions.rows` |
| Core 12 | `data/ui_view_model.json` | `core12.rows` |
| Setups / VWAP | `data/vwap_restore.json` | `rows[].vwap63`, `vwap252`, `vwap_life` |
| Rotation | `data/ui_view_model.json` | `rotation.diagnostics`, `fine_theme_rows` |
| Movers | `data/ui_view_model.json` | `movers.summary`, `three_window`, `periods.{1d,1w,1m}` |
| RS | `data/ui_view_model.json` | `rs.windows.{63,126,189}`, `rs.rows` |
| Weekly | `data/ui_view_model.json` | `weekly`, `daily.market_summaries` |
| Options | `data/options/index.json` | `buckets`, `snapshots`, `failures`, `chart_ohlc` |
| Search | `data/search_index.json` | `rows` |
| Ticker chart | Options/VWAP chart payload, then TradingView | `chart_ohlc`; exchange-qualified live fallback |
| Rules | static 09/05 authority | `assets/v38-rules-0905.html` |

## Retired production layers

- `v38-observables.js`
- `v38-polish.js`
- `v38-recovery.js`
- `v38-final-ui.js`
- `v38-data-repair.js`
- `v38-visual-fidelity.js`
- `v38-detail-restore.js`
- `v38-data-completeness-fallback.js` (replaced by modal-only fallback)
- `v38-observation-ribbon-repair.js`
- `v38-status-truth.js`
- `v38-rotation-movers-visual.js`
- `v38-rotation-movers-owner.js`

Production external scripts are reduced from 17 to 7: baseline interaction, runtime, navigation/data loader, live binder, chart modal, approved extensions, and modal-only TradingView fallback.

## Local acceptance evidence

- Python: 385 passed.
- JavaScript syntax: active production assets passed `node --check`.
- Display completeness: READY; stock 3388/3388, Search 3388/3388, priority chart 145/145, VWAP pending 0, Options 119 valid plus 3 `NO_VALID_0_45_DTE_CONTRACTS`, fetch errors 0.
- Browser acceptance: 375/390/430 × 11 tabs passed; 33 section screenshots generated.
- Browser data completeness: passed.
- READY `.v38-bind-note` false `DATA_REQUIRED`: 0.

Production workflow/run and Pages deployment are recorded after merge only.
