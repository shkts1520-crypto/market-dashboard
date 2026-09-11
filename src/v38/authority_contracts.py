from __future__ import annotations

import copy
import math
from datetime import date, datetime
from typing import Any

from .mc57_engine import MC57_METRICS, mc57_logistic

CALCULATION_VERSION = "v38-authority-contracts-1.0.0"
VALID_NQSAR = {"Blue", "Green", "Yellow", "Red"}
AUTHORITY_TARGETS = {
    "nqsar": "nqsar.json",
    "mc57": "mc57.json",
    "classifications": "classifications.json",
    "theme_scores": "theme_scores.json",
    "options": "options/index.json",
    "positions": "positions_ledger.json",
}


class AuthorityContractError(RuntimeError):
    """Raised when an external authority payload cannot be promoted safely."""


def _required_text(obj: dict[str, Any], key: str) -> str:
    value = obj.get(key)
    if not isinstance(value, str) or not value.strip():
        raise AuthorityContractError(f"{key} is required")
    return value.strip()


def _iso_date(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AuthorityContractError(f"{field} is required")
    text = value.strip()
    try:
        parsed = date.fromisoformat(text)
    except ValueError as exc:
        raise AuthorityContractError(f"{field} must be YYYY-MM-DD") from exc
    if parsed.isoformat() != text:
        raise AuthorityContractError(f"{field} must be YYYY-MM-DD")
    return text


def _iso_datetime(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AuthorityContractError(f"{field} is required")
    text = value.strip()
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AuthorityContractError(f"{field} must be ISO-8601") from exc
    return text


def _finite(value: Any, field: str, *, low: float | None = None, high: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AuthorityContractError(f"{field} must be finite numeric")
    x = float(value)
    if not math.isfinite(x):
        raise AuthorityContractError(f"{field} must be finite numeric")
    if low is not None and x < low:
        raise AuthorityContractError(f"{field} must be >= {low}")
    if high is not None and x > high:
        raise AuthorityContractError(f"{field} must be <= {high}")
    return x


def _optional_finite(value: Any, field: str) -> float | None:
    if value is None:
        return None
    return _finite(value, field)


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise AuthorityContractError(f"{field} must be boolean")
    return value


def _session(payload: dict[str, Any], expected_session: str | None) -> str:
    session = _iso_date(payload.get("session_date"), "session_date")
    if expected_session is not None and session != expected_session:
        raise AuthorityContractError(
            f"session_date mismatch: {session} != {expected_session}"
        )
    return session


def _common(payload: dict[str, Any], expected_session: str | None) -> tuple[str, str, str, float | None]:
    session = _session(payload, expected_session)
    generated_at = _iso_datetime(payload.get("generated_at"), "generated_at")
    source = _required_text(payload, "source")
    coverage = payload.get("coverage")
    if coverage is not None:
        coverage = _finite(coverage, "coverage", low=0.0, high=1.0)
    return session, generated_at, source, coverage


def _rows(payload: dict[str, Any], *, allow_empty: bool = False) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    if not isinstance(rows, list):
        raise AuthorityContractError("rows must be a list")
    clean = [dict(row) for row in rows if isinstance(row, dict)]
    if len(clean) != len(rows):
        raise AuthorityContractError("every rows item must be an object")
    if not allow_empty and not clean:
        raise AuthorityContractError("rows must not be empty")
    return clean


def _unique_tickers(rows: list[dict[str, Any]]) -> None:
    seen: set[str] = set()
    for i, row in enumerate(rows):
        ticker = str(row.get("ticker") or "").strip().upper()
        if not ticker:
            raise AuthorityContractError(f"rows[{i}].ticker is required")
        if ticker in seen:
            raise AuthorityContractError(f"duplicate ticker: {ticker}")
        seen.add(ticker)
        row["ticker"] = ticker


def validate_nqsar(payload: dict[str, Any], expected_session: str | None = None) -> dict[str, Any]:
    session, generated_at, source, _ = _common(payload, expected_session)
    state = payload.get("state", payload.get("color", payload.get("nqsar")))
    if state is None and payload.get("exp_state_id") is not None:
        mapping = {1: "Blue", 2: "Yellow", 3: "Red", 4: "Green"}
        try:
            state = mapping[int(payload["exp_state_id"])]
        except (ValueError, TypeError, KeyError) as exc:
            raise AuthorityContractError("exp_state_id must be 1..4") from exc
    if state not in VALID_NQSAR:
        raise AuthorityContractError("state must be Blue/Green/Yellow/Red")
    input_kind = str(payload.get("input_kind") or "AUTHORITATIVE_STATE").strip()
    return {
        "session_date": session,
        "generated_at": generated_at,
        "coverage": 1.0,
        "source": source,
        "schema_version": "v38.nqsar.authority.1",
        "calculation_version": CALCULATION_VERSION,
        "status": "READY",
        "state": state,
        "input_kind": input_kind,
        "authority_version": str(payload.get("authority_version") or "external-current-state"),
        "fsm_recomputed": False,
    }


def validate_classifications(payload: dict[str, Any], expected_session: str | None = None) -> dict[str, Any]:
    session, generated_at, source, coverage = _common(payload, expected_session)
    version = _required_text(payload, "classification_version")
    rows = _rows(payload)
    _unique_tickers(rows)
    for i, row in enumerate(rows):
        _bool(row.get("structural_clinical_biotech"), f"rows[{i}].structural_clinical_biotech")
        _required_text(row, "rationale")
        start = _iso_date(row.get("effective_from"), f"rows[{i}].effective_from")
        end_raw = row.get("effective_to")
        end = _iso_date(end_raw, f"rows[{i}].effective_to") if end_raw is not None else None
        if session < start or (end is not None and session > end):
            raise AuthorityContractError(f"rows[{i}] is not effective on {session}")
    out = copy.deepcopy(payload)
    out.update({
        "session_date": session,
        "generated_at": generated_at,
        "coverage": coverage,
        "source": source,
        "schema_version": "v38.classifications.1",
        "calculation_version": CALCULATION_VERSION,
        "classification_version": version,
        "status": "READY",
        "rows": rows,
    })
    return out


def validate_theme_scores(payload: dict[str, Any], expected_session: str | None = None) -> dict[str, Any]:
    session, generated_at, source, coverage = _common(payload, expected_session)
    upstream_version = _required_text(payload, "upstream_calculation_version")
    if payload.get("pit") is not True:
        raise AuthorityContractError("pit must be true")
    if payload.get("strict_loo") is not True:
        raise AuthorityContractError("strict_loo must be true")
    rows = _rows(payload)
    _unique_tickers(rows)
    components = (
        "theme_rs63_percentile",
        "rank_acceleration_percentile",
        "ema21_breadth_score",
    )
    for i, row in enumerate(rows):
        _required_text(row, "theme_id")
        values = [_finite(row.get(k), f"rows[{i}].{k}", low=0.0, high=100.0) for k in components]
        score = _finite(row.get("peer_theme_score"), f"rows[{i}].peer_theme_score", low=0.0, high=100.0)
        expected = sum(values) / 3.0
        if not math.isclose(score, expected, rel_tol=0.0, abs_tol=1e-6):
            raise AuthorityContractError(
                f"rows[{i}].peer_theme_score must equal the three-component mean"
            )
    out = copy.deepcopy(payload)
    out.update({
        "session_date": session,
        "generated_at": generated_at,
        "coverage": coverage,
        "source": source,
        "schema_version": "v38.peer_theme.1",
        "calculation_version": upstream_version,
        "status": "READY",
        "pit": True,
        "strict_loo": True,
        "rows": rows,
        "ingest_version": CALCULATION_VERSION,
    })
    return out


def validate_mc57(payload: dict[str, Any], expected_session: str | None = None) -> dict[str, Any]:
    session, generated_at, source, coverage = _common(payload, expected_session)
    member_set_version = _required_text(payload, "member_set_version")
    golden_fixture_version = _required_text(payload, "golden_fixture_version")
    members = payload.get("members")
    if not isinstance(members, list) or len(members) != 57:
        raise AuthorityContractError("members must contain exactly 57 tickers")
    normalized_members = [str(x).strip().upper() for x in members]
    if any(not x for x in normalized_members) or len(set(normalized_members)) != 57:
        raise AuthorityContractError("members must be 57 unique non-empty tickers")
    metric_scores = payload.get("metric_scores")
    if not isinstance(metric_scores, dict) or set(metric_scores) != set(MC57_METRICS):
        raise AuthorityContractError("metric_scores must contain the canonical 12 metrics exactly")
    values = [_finite(metric_scores[k], f"metric_scores.{k}", low=0.0, high=100.0) for k in MC57_METRICS]
    raw = _finite(payload.get("raw"), "raw", low=0.0, high=100.0)
    if not math.isclose(raw, sum(values) / len(values), rel_tol=0.0, abs_tol=1e-6):
        raise AuthorityContractError("raw must equal the equal-weight mean of 12 metric scores")
    ema2_raw = _finite(payload.get("ema2_raw"), "ema2_raw")
    mu = _finite(payload.get("mu_prior"), "mu_prior")
    sigma = _finite(payload.get("sigma_prior"), "sigma_prior", low=0.0)
    if sigma <= 0:
        raise AuthorityContractError("sigma_prior must be >0")
    z = _finite(payload.get("z"), "z")
    expected_z = (ema2_raw - mu) / sigma
    if not math.isclose(z, expected_z, rel_tol=0.0, abs_tol=1e-6):
        raise AuthorityContractError("z must equal (ema2_raw-mu_prior)/sigma_prior")
    mc57 = _finite(payload.get("mc57"), "mc57", low=0.0, high=100.0)
    if not math.isclose(mc57, mc57_logistic(z), rel_tol=0.0, abs_tol=1e-6):
        raise AuthorityContractError("mc57 must equal 100/(1+3**(-z))")
    if payload.get("calibration_lookback_sessions") != 3780:
        raise AuthorityContractError("calibration_lookback_sessions must be 3780")
    out = copy.deepcopy(payload)
    out.update({
        "session_date": session,
        "generated_at": generated_at,
        "coverage": coverage,
        "source": source,
        "schema_version": "v38.mc57.1",
        "calculation_version": str(payload.get("upstream_calculation_version") or "v38-mc57-authoritative"),
        "status": "READY",
        "members": normalized_members,
        "member_set_version": member_set_version,
        "golden_fixture_version": golden_fixture_version,
        "metric_scores": {k: values[i] for i, k in enumerate(MC57_METRICS)},
        "fixed_member_count": 57,
        "metric_count": 12,
        "calibration_lookback_sessions": 3780,
        "ingest_version": CALCULATION_VERSION,
    })
    return out


def validate_options(payload: dict[str, Any], expected_session: str | None = None) -> dict[str, Any]:
    session, generated_at, source, coverage = _common(payload, expected_session)
    provider = _required_text(payload, "provider")
    upstream_version = _required_text(payload, "upstream_calculation_version")
    if payload.get("sign_model") != "calls_positive_puts_negative":
        raise AuthorityContractError("sign_model must be calls_positive_puts_negative")
    rows = _rows(payload)
    allowed_buckets = {"0-6", "7-21", "22-45", "0-45"}
    seen: set[tuple[str, str]] = set()
    for i, row in enumerate(rows):
        ticker = str(row.get("ticker") or "").strip().upper()
        bucket = str(row.get("dte_bucket") or "").strip()
        if not ticker:
            raise AuthorityContractError(f"rows[{i}].ticker is required")
        if bucket not in allowed_buckets:
            raise AuthorityContractError(f"rows[{i}].dte_bucket is invalid")
        key = (ticker, bucket)
        if key in seen:
            raise AuthorityContractError(f"duplicate options row: {ticker}/{bucket}")
        seen.add(key)
        row["ticker"] = ticker
        row["dte_bucket"] = bucket
        _finite(row.get("spot"), f"rows[{i}].spot", low=0.0)
        for field in ("call_wall", "put_wall", "gamma_flip", "net_gex", "expected_move"):
            _optional_finite(row.get(field), f"rows[{i}].{field}")
        for field in ("direction", "confidence", "quality"):
            _required_text(row, field)
    out = copy.deepcopy(payload)
    out.update({
        "session_date": session,
        "generated_at": generated_at,
        "coverage": coverage,
        "source": source,
        "schema_version": "v38.options.index.1",
        "calculation_version": upstream_version,
        "status": "READY",
        "provider": provider,
        "sign_model": "calls_positive_puts_negative",
        "gex_formula": "Gamma*OI*100*Spot^2*0.01",
        "rows": rows,
        "ingest_version": CALCULATION_VERSION,
    })
    return out


def validate_positions(payload: dict[str, Any], expected_session: str | None = None) -> dict[str, Any]:
    session, generated_at, source, coverage = _common(payload, expected_session)
    ledger_version = _required_text(payload, "ledger_version")
    cash = _finite(payload.get("cash"), "cash", low=0.0)
    rows = _rows(payload, allow_empty=True)
    portfolio_empty = payload.get("portfolio_empty") is True
    if not rows and not portfolio_empty:
        raise AuthorityContractError("empty rows require portfolio_empty=true")
    valid_sleeves = {"NORMAL_STOCK", "RSI30_PANIC_RESET", "TQQQ_NORMAL", "TQQQ_PANIC"}
    ids: set[str] = set()
    for i, row in enumerate(rows):
        position_id = str(row.get("position_id") or "").strip()
        ticker = str(row.get("ticker") or "").strip().upper()
        sleeve = str(row.get("sleeve") or "").strip().upper()
        if not position_id or position_id in ids:
            raise AuthorityContractError(f"rows[{i}].position_id must be unique")
        ids.add(position_id)
        if not ticker:
            raise AuthorityContractError(f"rows[{i}].ticker is required")
        if sleeve not in valid_sleeves:
            raise AuthorityContractError(f"rows[{i}].sleeve is invalid")
        row["ticker"] = ticker
        row["sleeve"] = sleeve
        _finite(row.get("quantity"), f"rows[{i}].quantity", low=0.0)
        if float(row["quantity"]) <= 0:
            raise AuthorityContractError(f"rows[{i}].quantity must be >0")
        _iso_date(row.get("entry_date"), f"rows[{i}].entry_date")
        if sleeve == "NORMAL_STOCK":
            for field in ("entry", "close", "peak_close"):
                x = _finite(row.get(field), f"rows[{i}].{field}", low=0.0)
                if x <= 0:
                    raise AuthorityContractError(f"rows[{i}].{field} must be >0")
            _bool(row.get("partial_taken"), f"rows[{i}].partial_taken")
    flows = payload.get("flows", [])
    if not isinstance(flows, list) or any(not isinstance(x, dict) for x in flows):
        raise AuthorityContractError("flows must be a list of objects")
    out = copy.deepcopy(payload)
    out.update({
        "session_date": session,
        "generated_at": generated_at,
        "coverage": coverage if coverage is not None else 1.0,
        "source": source,
        "schema_version": "v38.positions_ledger.1",
        "calculation_version": CALCULATION_VERSION,
        "status": "READY",
        "ledger_version": ledger_version,
        "cash": cash,
        "rows": rows,
        "flows": flows,
    })
    return out


VALIDATORS = {
    "nqsar": validate_nqsar,
    "mc57": validate_mc57,
    "classifications": validate_classifications,
    "theme_scores": validate_theme_scores,
    "options": validate_options,
    "positions": validate_positions,
}


def validate_authority(kind: str, payload: dict[str, Any], *, expected_session: str | None = None) -> tuple[str, dict[str, Any]]:
    name = str(kind or "").strip().lower()
    if name not in VALIDATORS:
        raise AuthorityContractError(f"unsupported authority kind: {kind}")
    if not isinstance(payload, dict):
        raise AuthorityContractError("payload must be a JSON object")
    normalized = VALIDATORS[name](payload, expected_session)
    return AUTHORITY_TARGETS[name], normalized
