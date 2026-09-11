# V38 Live Site Build

Status date: 2026-09-10

`V38_Command_Center_mock_v5.html` remains the immutable visual authority. The builder pins the exact Git blob SHA and byte length before building.

The builder produces `index.html` as a **canonical-DOM live binding shell**:

- preserves the canonical v5 style blocks byte-for-byte
- preserves the exact 9-tab order and section IDs
- removes every canonical inline `<script>` block
- removes inline `on*=` event handlers
- injects only external UI runtimes (`assets/v38-runtime.js`, `assets/v38-site.js`)
- keeps the original canonical cards instead of replacing them with generated grids
- replaces canonical Mock values with current-session values or `DATA_REQUIRED`
- keeps the page non-interactive until the binding pass finishes, preventing a Mock-data flash
- performs no trading calculation in browser JavaScript

The external runtime owns only navigation and display binding. Missing inputs are neutralized inside the existing cards; no Mock number is allowed to remain visible as production data.
