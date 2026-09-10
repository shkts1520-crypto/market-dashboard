# V38 Safe Site Build v9

Status date: 2026-09-10

`V38_Command_Center_mock_v5.html` remains the immutable visual authority. v9 pins the exact Git blob SHA and byte length before building.

v9 produces `index.html` as a **fail-closed production shell**:

- preserves the canonical v5 style blocks byte-for-byte
- preserves the exact 9-tab order and section IDs
- removes every canonical inline `<script>` block
- removes inline `on*=` event handlers
- injects only external UI runtimes (`assets/v38-runtime.js`, `assets/v38-site.js`)
- keeps all canonical Mock values shielded from view
- shows `DATA_REQUIRED` until authoritative card bindings are verified
- performs no trading calculation in browser JavaScript

This stage intentionally does not unshield canonical Mock content when a payload merely exists. The next binding stage must map verified server-produced shards into each card before any section can become visible as production data.
