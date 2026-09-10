# V38 Live UI Binding

Status date: 2026-09-11

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

No browser-side threshold or trading calculation is performed.

### RS

The first 24 rows of `rs.json` are displayed in their source order. The browser does not rank, sort, filter, or reinterpret them. This is explicitly a diagnostic RS189 leaderboard and is not Core 12 eligibility/ranking.

## Fail-closed behavior

Missing or cross-session inputs render `—`, `DATA_REQUIRED`, or `STALE`. The canonical Mock cards remain hidden. Positions, Core 12, Rotation, Weekly, Options, Publish, and Rules remain fail-closed until their authoritative shards exist.

## Mobile acceptance

Production CI compares rendered Daily and RS values to `ui_view_model.json` and re-runs the full tab/overflow checks at 375, 390, and 430 CSS pixels.
