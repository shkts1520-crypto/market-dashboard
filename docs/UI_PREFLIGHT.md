# V38 UI Preflight

Status date: 2026-09-10

This layer deliberately does **not** redesign or regenerate the V38 Command Center.
The only visual authority remains `V38_Command_Center_mock_v5.html`.

Implemented in this stage:

- exact 9-tab contract: Daily / Positions / Core 12 / Rotation / RS / Weekly / Options / Publish / Rules
- required v5 visual vocabulary guard
- Setups / Movers rejection in the navigation
- shard `session_date` freshness assessment
- missing/corrupt shard -> `DATA_REQUIRED`
- mismatched shard date -> `STALE`
- null/undefined/empty/NaN display helper -> `—`
- small browser runtime that only loads/validates/formats data; it contains no trading rule engine

Not implemented in this stage:

- no alternate UI
- no fabricated `index.html`
- no promotion of v5 mock numbers into production
- no inferred MC57 value
- no inferred NQSAR FSM
- no renderer-side trading decisions

The next build stage may run only after the canonical v5 HTML exists in the repository. The production build must preserve its DOM/CSS and remove/disconnect legacy trading logic before publishing.
