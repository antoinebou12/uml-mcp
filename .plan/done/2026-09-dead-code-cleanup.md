# Dead code and duplication cleanup

- **Priority:** P2   **Size:** M
- **Done when:** unused modules/functions removed (vulture + coverage), repeated helpers consolidated, tests still green, no public API change.

- **Done (first pass):** removed unused `lulu_ads_enabled` flag and the legacy `_rate_limited` wrapper; dropped lint rules duplicated by the protocol rules; folded sync/async bodies of `instrument()` around one span/audit path; vulture shows only framework-registered handlers left.
