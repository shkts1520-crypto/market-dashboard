# V38 Production Deploy v10

This stage preserves `V38_Command_Center_mock_v5.html` as the immutable visual authority and does not change any trading rule.

Production behavior:

- the 9 canonical tabs are driven from their existing `href="#section"` targets
- canonical cards remain the visible layout and receive current-session values directly
- unsupported canonical card values are neutralized to `DATA_REQUIRED`
- `data/ui_payload.json` is generated from authoritative shards only
- missing or corrupt inputs show `DATA_REQUIRED`
- mismatched sessions show `STALE`
- no browser-side trading calculation is introduced
- Pages deployment runs only after the complete Python/JavaScript suite and real-browser checks at 375, 390, and 430 px pass
- if no authoritative data directory exists, the deployed site remains usable but fail-closed with `DATA_REQUIRED`; no values are invented
- every successful acquisition stores a compact session snapshot in `data/history/`; F1 prefers 20-session-lag archived snapshots, and before 21 snapshots accumulate it recovers the original current-universe historical-OHLC Top24 from retained history with explicit survivorship provenance

Section input contract:

- Daily: `market_state.json`, `breadth.json`, `mc57.json`, `f123.json`
- Positions: `positions.json`
- Core 12: `core12.json`
- Rotation: `rotation.json`
- RS: `rs.json`
- Weekly: `weekly.json`
- Options: `options/index.json`
- Publish: `publish.json`
- Rules: `rules.json`


F1/F3 restoration contract:

- F1 uses the original 20-session leader-drop formula. Missing current observations remain unknown and are excluded from its observable denominator.
- F3 uses the original full qualified-queue denominator. Missing constituent Ret20/Dist52 values do not invalidate the whole F3; they are exposed through observation coverage and do not count as breaks.
- Current F2/F3 values are never silently recomputed in the browser/display layer. `f123.json` is the canonical source.
