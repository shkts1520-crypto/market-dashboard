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
- every successful acquisition stores a compact session snapshot in `data/history/`; after 20 prior sessions exist it can produce the PIT old Top24 needed by F1

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
