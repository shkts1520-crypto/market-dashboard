# V38 Command Center 2026-09-05 UI baseline audit

Status: Steps 1-15 complete on the restoration branch; main/Pages confirmation is recorded after deployment. This document records the pre-change audit and the verified implementation result.

## 1. Baseline authority

The 2026-09-05 baseline is reconstructed from three mutually consistent sources, in this order:

1. Production implementation commit `95626ac868558386a61af561d1b3aaf54134cab7` (recorded 2026-09-06, as-of 2026-09-04).
2. Last successful Pages head `83cbba88253e45f726880613fc675695f1427c13`.
3. Preserved full Production HTML `command-center(1).html`, corroborated by the preserved August Production PDFs.

The current `V38_Command_Center_mock_v5.html` is not the sole baseline. Its Git blob is `966fe157e3d35344f6e373877b3de5689409dd67`; it was first added to the new repository on 2026-09-10 and omits Setups and Movers.

The preserved Production HTML proves this baseline navigation:

`Daily / Positions / Core 12 / Setups / Rotation / Movers / RS / Weekly / Publish / Rules`

Options is classified as `ADDED_AFTER_0905` and must be retained after Weekly.

## 2. Navigation classification

| Tab | Classification | Baseline DOM | Current DOM | Required action |
|---|---|---|---|---|
| Daily | BASELINE_0905 | `#t-market` | `#t-market` | Preserve and repair bindings only |
| Positions | BASELINE_0905 | `#t-alloc` | `#t-alloc` | Restore baseline DOM |
| Core 12 | BASELINE_0905 | `#t-port` | `#t-port` | Restore baseline DOM |
| Setups | REMOVED_AFTER_0905 | `#t-today` | missing | Restore before Rotation |
| Rotation | BROKEN_AFTER_0905 | `#t-rotation` | `#t-rotation` | Restore baseline DOM; no section replacement |
| Movers | REMOVED_AFTER_0905 | `#t-movers` | missing | Restore before RS |
| RS | BROKEN_AFTER_0905 | `#t-rs` | `#t-rs` | Preserve baseline cards and local bindings |
| Weekly | BASELINE_0905 | `#t-weekly` | `#t-weekly` | Preserve baseline cards and local bindings |
| Options | ADDED_AFTER_0905 | n/a | `#t-options` | Freeze; non-regression only |
| Publish | BASELINE_0905 | `#t-post1` | `#t-post1` | Restore original post blocks/iframes |
| Rules | BROKEN_AFTER_0905 | `#t-rules` | `#t-rules` | Restore 09/05 text/order; no later-rule substitution |

## 3. Card inventory

### Daily

| Card | Classification | Current | Required action |
|---|---|---|---|
| Market Summary | BASELINE_0905 | present | preserve DOM |
| Change Log | BASELINE_0905 | present | preserve DOM |
| Regime History | BASELINE_0905 | repurposed around MC57 | restore baseline card; keep MC57 separately |
| Performance | BASELINE_0905 | present | preserve DOM |
| 50MA Breadth | ADDED_AFTER_0905 | present | keep |
| 200MA Breadth Trend | BASELINE_0905 | present | preserve DOM |
| Volume Participation | BASELINE_0905 | present | preserve DOM |
| Accumulation/Distribution | BASELINE_0905 | present | preserve DOM |
| Leader Temperature | BASELINE_0905 | present | preserve DOM |
| Leader Momentum | BASELINE_0905 | present | preserve DOM |
| McClellan Oscillator | BASELINE_0905 | present | preserve DOM |
| Risk-On/Off Rotation | BASELINE_0905 | present | preserve DOM |
| Regime Early-Warning | ADDED_AFTER_0905 | present | keep without replacing baseline cards |
| Net Liquidity | ADDED_AFTER_0905 | present | keep |
| Credit & Rates | ADDED_AFTER_0905 | present | keep |
| Credit Spread | BASELINE_0905 | present | preserve DOM |
| VIX Fear Cycle | BASELINE_0905 | present | preserve DOM |
| VIX Term Structure | ADDED_AFTER_0905 | present | keep |
| Expected Move | BASELINE_0905 | present | preserve DOM |
| Distribution Days | BASELINE_0905 | present | preserve DOM |
| Sentiment | BASELINE_0905 | present | preserve DOM |
| Reversal Leaders | BASELINE_0905 | present | preserve DOM |
| FTD proxy | ADDED_AFTER_0905 | present | keep |
| MC57 current/history/trend/detail | ADDED_AFTER_0905 | present | freeze and retain |

### Setups

All entries below are `REMOVED_AFTER_0905`; their baseline parent is `#t-today`.

| Card/feature | Evidence | Required action |
|---|---|---|
| Ticker Search | Production HTML + PDFs | restore |
| Pre-Breakout | Production HTML + PDFs | restore |
| Put Wall Touch | Production HTML + PDFs | restore |
| Confluence | PDFs | restore |
| Pocket Pivots (10D) | Production HTML | restore |
| Today's Setups | Production HTML | restore |
| Chart Patterns / VCP | Production HTML + PDFs | restore |
| 21EMA Touch | Production HTML | restore |
| Multi VWAP | Production HTML | restore here; remove RS placement |
| Structure Pivot | Production HTML + PDFs | restore |
| Signals | Production HTML | restore |
| Playbook | Production HTML + PDFs | restore |
| Grades | Production HTML + PDFs | restore |
| Status | Production HTML | restore |
| Cohort | Production HTML | restore |
| Entries | Production HTML | restore |
| Exits | Production HTML | restore |
| Leaders | Production HTML + PDFs | restore |

### Rotation

| Card | Classification | Current problem | Required action |
|---|---|---|---|
| RRG / GICS11 + Style Flow | BROKEN_AFTER_0905 | section replaced by generic Period Ranking/Rank Flow UI | restore original SVG/card |
| Sector Heatmap | BROKEN_AFTER_0905 | lost during section replacement | restore original DOM |
| Index vs Breadth | REMOVED_AFTER_0905 | missing | restore original DOM |
| Leading Groups | BROKEN_AFTER_0905 | genericized | restore original DOM |
| Leaders in Strong Groups | BROKEN_AFTER_0905 | genericized | restore original DOM |
| Sector ETF Strength | BROKEN_AFTER_0905 | genericized | restore original DOM |
| Sub-Theme RS | BROKEN_AFTER_0905 | genericized | restore original DOM |
| Theme ETF | BROKEN_AFTER_0905 | genericized | restore original DOM |

### Movers

| Card | Classification | Current problem | Required action |
|---|---|---|---|
| Movers top/bottom board | REMOVED_AFTER_0905 | tab and payload section absent | restore `#t-movers`; bind baseline return/RS fields |

### RS

All seven cards are `BROKEN_AFTER_0905` where destructive renderers replace baseline content: RS Multi Timeframe, Top10 IN/OUT, RS189 Persistence, Cross-Window Leaders, RS63 Top10, RS126 Top10, and RS189 Top10. Restore the baseline card DOM and update only row/chart containers.

### Positions, Core 12, Weekly, Publish, Rules

| Area | Baseline inventory | Classification / action |
|---|---|---|
| Positions | Rebalance/holdings/account/equity/emergency-brake structures | BROKEN_AFTER_0905; restore original DOM and show no-position state inside it |
| Core 12 | defense/regime, entrants, core/holdings, bench, moonshot/radar where present | BROKEN_AFTER_0905; restore original DOM; do not change 09/05 rules |
| Weekly | This Week, Next Week, Rates, Macro Pressure, Weekly Diff, Regime History, Weekly Movers, Market Breadth, Data Quality, Leverage Conditions, My Week | BASELINE_0905; preserve. Structural Macro is ADDED_AFTER_0905 and may remain |
| Publish | original `#t-post1` postwrap/iframe blocks | BROKEN_AFTER_0905; retain templates and bind fields only |
| Rules | 09/05 rule text and order | BROKEN_AFTER_0905; later Normal Stock/TQQQ rewrite is not authority |

## 4. Destructive renderer findings

The repository-wide scan found 532 raw occurrences of DOM creation/replacement terms. The following are confirmed section/card destruction points, not harmless table-body or chart-host updates:

| File | Function/pattern | Scope | Classification | Required action |
|---|---|---|---|---|
| `assets/v38-site.js` | `resetCard`, `neutralizeCards`, `card.replaceChildren()` | non-Options cards | BROKEN_AFTER_0905 | remove from active non-Options path |
| `assets/v38-restored-experience.js` | `renderRotation`, `section.replaceChildren(root)` | Rotation | BROKEN_AFTER_0905 | delete full-section replacement |
| `assets/v38-restored-experience.js` | `renderVwap`, append to `#t-rs` | RS/Setups | BROKEN_AFTER_0905 | bind to restored Setups card |
| `assets/v38-recovery.js` | repeated `card.replaceChildren()` | Positions/RS | BROKEN_AFTER_0905 | replace with local bindings |
| `assets/v38-observables.js` | `card.replaceChildren()` generic rows | Options-related cards | inspect against frozen Options boundary |
| `assets/v38-source-fidelity.js` | `root.replaceChildren(header, wrap)` | Publish | BROKEN_AFTER_0905 | retain original postwrap/iframe DOM |
| `assets/v38-visual-fidelity.js` | whole-card rebuilds | Daily MC57/VIX | mixed | keep MC57 addition; stop replacing baseline cards |
| `assets/v38-detail-restore.js` | card/host replacement | Rotation/RS details | mixed | allow chart host only; prohibit card replacement |
| `assets/v38-data-completeness-fallback.js` | `card.innerHTML = html` | missing-data fallback | BROKEN_AFTER_0905 | write state into designated value/status nodes |

Allowed replacements are limited to local row/series hosts such as `tbody`, a dedicated search-results list, a sparkline SVG host, chart canvas/SVG series, and the frozen Options modal internals.

## 5. Step 3 completion gate

- Baseline Production identity recorded: yes.
- Full pre-reconstruction DOM recovered: yes.
- Visual corroboration from Production PDFs: yes.
- All baseline tabs classified: yes.
- All removed/broken primary cards classified: yes.
- Confirmed destructive renderer list recorded: yes.
- Production HTML/JS changed during Steps 1-3: no.

The next permitted change is Step 4: restore Navigation, Setups, and Movers from the preserved Production DOM, then wire existing producers without inventing new ranking logic.

## 6. Implementation result

| Tab | Card | 09/05 state | Current problem | Repair | Data source | Code |
|---|---|---|---|---|---|---|
| Daily | MC57 | ADDED_AFTER_0905 | healthy | retained without replacing baseline inventory | `mc57.json` / view model | existing Daily repair layers |
| Setups | full setup inventory | BASELINE_0905 | tab and cards removed | restored in baseline order; explicit unavailable states retained | `history/vwap_restore.json`, `search_index.json` | `assets/v38-baseline-shell.js` |
| Setups | Multi VWAP | BASELINE_0905 | incorrectly appended to RS | restored to Setups; logic retained | `history/vwap_restore.json` | `assets/v38-baseline-shell.js`, `assets/v38-restored-experience.js` |
| Rotation | RRG / GICS flow | BASELINE_0905 | whole section replaced | destructive replacement disabled; source DOM retained | rotation payload | `assets/v38-restored-experience.js` |
| Rotation | Index vs Breadth | BASELINE_0905 | removed | baseline card slot restored | explicit `SOURCE_UNAVAILABLE` until producer exists | `assets/v38-baseline-shell.js` |
| Movers | gainers / losers | BASELINE_0905 | tab and payload absent | restored from existing one-day return field | `rs.json:ret1` | `src/v38/ui_view_model.py`, `assets/v38-baseline-shell.js` |
| RS | Multi-timeframe inventory | BASELINE_0905 | Multi VWAP injected here | original RS inventory retained; VWAP relocated | RS payload | `assets/v38-restored-experience.js` |
| Options | all DTE buckets/modal/chart | ADDED_AFTER_0905 | competing repair layer rebuilt cards | competing repair disabled; Options owner frozen | `options/index.json` | `assets/v38-data-repair.js`, `assets/v38-site.js` |
| All | Navigation | BASELINE_0905 + Options | Setups/Movers missing | restored to 11 tabs | static contract | `src/v38/site_builder.py`, `src/v38/ui_contract.py` |

Verified production artifact inventory: 84 rendered cards, 19 Setups cards, four frozen Options bucket cards, and 19 explicit `SOURCE_UNAVAILABLE` states. The unavailable states are visible and reasoned rather than inferred or fabricated.

Verification completed with 371 Python tests, JavaScript syntax checks, production-shell validation, and real Chromium acceptance at 375, 390, and 430 pixels. Each width covered all eleven tabs, tab reset-to-top behavior, overflow/layout checks, chart and sparkline presence, ticker modal open/close, and TradingView live fallback.
