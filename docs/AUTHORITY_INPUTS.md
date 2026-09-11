# V38 authoritative inputs

The production pipeline is fail-closed. External values become production inputs only after they pass `scripts/ingest_authority.py` / `V38 Authority Input`.

Supported authorities and production targets:

| kind | target | purpose |
|---|---|---|
| `nqsar` | `data/nqsar.json` | authoritative Blue/Green/Yellow/Red state; the unrecovered FSM is never guessed |
| `mc57` | `data/mc57.json` | exact fixed-57/golden-validated MC57 output |
| `classifications` | `data/classifications.json` | Structural Clinical Biotech classification authority |
| `theme_scores` | `data/theme_scores.json` | PIT strict-LOO Peer Theme scores |
| `options` | `data/options/index.json` | upstream Options Intelligence output |
| `positions` | `data/positions_ledger.json` | explicit holdings/cash ledger |

A promoted authority commit triggers the normal production workflow. The live acquisition step then uses the authority only when its `session_date` matches the completed production session; stale inputs cannot masquerade as current.

## NQSAR

```json
{
  "session_date": "2026-09-10",
  "generated_at": "2026-09-11T00:15:00Z",
  "source": "TradingView->Pipedream sar_state",
  "state": "Green",
  "authority_version": "onimine-production"
}
```

`exp_state_id` is also accepted with the frozen mapping `1=Blue, 2=Yellow, 3=Red, 4=Green`. The repository does not reconstruct the missing FSM from Yahoo bars.

## MC57

The payload must carry the exact 57 unique members, `member_set_version`, `golden_fixture_version`, all 12 canonical component scores, Raw, EMA2 Raw, prior 3780-session mean/population sigma, Z, and MC57. The validator independently checks the equal-weight Raw, Z equation and `100/(1+3**(-Z))`. A guessed member list cannot pass the authority contract.

## Structural Clinical Biotech

Each active-universe ticker must ultimately be covered by an effective-dated classification row:

```json
{
  "session_date": "2026-09-10",
  "generated_at": "2026-09-11T00:20:00Z",
  "source": "canonical-clinical-classifier",
  "coverage": 1.0,
  "classification_version": "clinical-vN",
  "rows": [
    {
      "ticker": "AAA",
      "structural_clinical_biotech": false,
      "rationale": "authoritative classifier output",
      "effective_from": "2026-01-01",
      "effective_to": null
    }
  ]
}
```

No Industry/Market Cap/Revenue threshold is invented in this repository. Until the canonical classifier/table is supplied, Core12 remains fail-closed.

## Peer Theme

The accepted upstream output must explicitly assert `pit=true` and `strict_loo=true`. Every ticker score must contain the three canonical components and the final score must equal their arithmetic mean:

```json
{
  "session_date": "2026-09-10",
  "generated_at": "2026-09-11T00:25:00Z",
  "source": "canonical-peer-theme-engine",
  "coverage": 1.0,
  "upstream_calculation_version": "peer-theme-vN",
  "pit": true,
  "strict_loo": true,
  "rows": [
    {
      "ticker": "AAA",
      "theme_id": "T100",
      "theme_rs63_percentile": 90.0,
      "rank_acceleration_percentile": 60.0,
      "ema21_breadth_score": 75.0,
      "peer_theme_score": 75.0
    }
  ]
}
```

Attack can become READY only when all otherwise-eligible candidates have an authoritative Peer Theme score. Selective remains RS189-only.

## Options

The upstream producer remains the computational authority. The dashboard does not recompute Direction/Confidence/Quality. Required top-level provenance includes `provider`, `upstream_calculation_version`, and `sign_model="calls_positive_puts_negative"`. Rows are keyed by ticker and one of `0-6`, `7-21`, `22-45`, `0-45` calendar-DTE buckets. Numeric Wall/Flip/GEX/Expected-Move fields may be null when the upstream quality state justifies no value; missing values render as `—`, never zero.

The canonical GEX convention stored in the normalized payload is `Gamma*OI*100*Spot^2*0.01` with calls positive and puts negative.

## Positions

Positions are never inferred from rankings. The ledger requires explicit cash plus explicit position rows. Normal-stock rows require `entry`, `close`, `peak_close`, and `partial_taken`; quantities and entry dates are mandatory. An actually empty portfolio must say `portfolio_empty=true`.

## Running the ingestion

Small payloads can be pasted into the `V38 Authority Input` workflow or sent as a `repository_dispatch` event of type `v38_authority` with `client_payload.kind` and an object in `client_payload.payload`.

For large classification/theme/positions/options payloads, keep the source JSON on a non-production ref such as `authority-inbox`, then run the workflow with `payload_ref=authority-inbox` and `payload_path=<path>`. The workflow reads that blob, validates it, and commits only the normalized production target to `main`.

The authority workflow rejects inputs older than the current production session. The normal production workflow remains responsible for same-session live prices, calculations, validation, browser acceptance and Pages deployment.
