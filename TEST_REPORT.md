# V38 recovered calculate-slice validation report

Date: 2026-09-10

## Result

- pytest: **48 passed**
- Python compileall: **passed**
- end-to-end CLI smoke: **passed**
- fixed-input whole-pipeline determinism: **passed**
- staged failure/no partial publish fixture: **passed**

## Stock/PIT gates verified

- exact PIT snapshot / interval / event membership handling
- static current Universe rejected as non-PIT
- future OHLCV ignored
- forming target bar rejected
- unresolved historical incomplete-bar bridge rejected
- split status unknown/anomaly rejected
- invalid OHLCV excluded
- Ret20/63/126/189 formula verified
- High52 = latest 252 completed daily High maximum; <252 -> null
- RS Price>=5 and DDV20>=10M base verified
- Breadth missing-SMA denominator handling verified
- Breadth50 3/4 = 75% fixture verified
- Breadth200 max(30, ceil(60% active)) gate verified

## F1/F2/F3 fixtures verified

- F1: old Top24=24, observable=20, drops=5 -> 25%; coverage=83.33% -> PARTIAL
- F1: coverage <70% -> null / DATA_INCOMPLETE
- F1: unverified/static old Top24 provenance -> DATA_REQUIRED
- F2: observable Top24 subset=20, RS63<85=8 -> 40% / SEVERE
- F3: queue=10, breaks=6 -> 60% / SEVERE
- F3: queue<3 -> NO_JUDGMENT
- F3: missing Ret20/Dist52 in a 3+ queue -> DATA_INCOMPLETE

## Market/Ranking fixtures verified

- Red -> DEFENSE; Yellow -> STOP
- Blue/Green Breadth thresholds -> ATTACK / SELECTIVE / STOP
- Selective does not imply forced trim
- exact normal-stock Eligibility criteria
- Attack 70/30 ranking and tiebreak
- Selective RS189-only ranking
- missing Clinical Biotech classification / Peer Theme input -> DATA_REQUIRED rather than fabricated values
- shard session mismatch -> STALE error

## Calculate pipeline verified

Current implemented output set:

`rs.json`, `breadth.json`, `f123.json`, `market_state.json`, `core12.json`

All five must share the target `session_date` and `generated_at` and contain the common metadata contract before any staged result is published.

## Still intentionally blocked by missing authoritative inputs

- NQSAR exact FSM/golden fixture
- MC57 fixed 57-ETF set + golden fixture
- production PIT old Top24 / historical PIT Universe needed for F1
- Structural Clinical Biotech classification table/source/version
- fine-grained PIT Theme membership + strict-LOO Peer Theme upstream
- Options upstream engine
- Positions/current-holdings authoritative schema and remaining dashboard shards

## GitHub status

The new repository can be read, but an actual Contents API create returned HTTP 403 `Resource not accessible by integration`. No GitHub file was changed. This package therefore remains a local, validated recovery artifact ready for a write-capable GitHub/Codex path.

## Recovery limitation

The previous Work session's claimed full 111-test repository tree is not present in the new GitHub repository. File Library contains important artifacts including the v5 build script and master handoff, but this package does **not** claim those 111 tests were rerun. The count above is the independently rebuilt test suite in this recovery package.
