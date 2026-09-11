from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from .authority_contracts import (
    AUTHORITY_TARGETS,
    AuthorityContractError,
    validate_authority,
)
from .nqsar_engine import NQSARError, parse_authoritative_input

FULL_AUTHORITY_TARGETS = {**AUTHORITY_TARGETS, "old_top24": "old_top24.json"}


def _date(value: Any, field: str) -> str:
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


def _generated_at(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AuthorityContractError("generated_at is required")
    text = value.strip()
    try:
        parsed = datetime.fromisoformat(text[:-1] + "+00:00" if text.endswith("Z") else text)
    except ValueError as exc:
        raise AuthorityContractError("generated_at must be ISO-8601") from exc
    if parsed.utcoffset() is None:
        raise AuthorityContractError("generated_at must include timezone")
    return text


def validate_old_top24(payload: dict[str, Any], expected_session: str | None = None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise AuthorityContractError("old_top24 payload must be an object")
    old_session = _date(payload.get("session_date"), "session_date")
    target_session = _date(payload.get("target_session_date"), "target_session_date")
    if expected_session is not None and target_session != expected_session:
        raise AuthorityContractError(
            f"target_session_date mismatch: {target_session} != {expected_session}"
        )
    generated_at = _generated_at(payload.get("generated_at"))
    source = payload.get("source")
    calendar_source = payload.get("calendar_source")
    upstream_version = payload.get("calculation_version")
    for field, value in (
        ("source", source),
        ("calendar_source", calendar_source),
        ("calculation_version", upstream_version),
    ):
        if not isinstance(value, str) or not value.strip():
            raise AuthorityContractError(f"{field} is required")
    if payload.get("lag_sessions") != 20:
        raise AuthorityContractError("lag_sessions must be 20")
    if payload.get("pit_frozen") is not True:
        raise AuthorityContractError("pit_frozen must be true")
    sequence = payload.get("session_sequence")
    if not isinstance(sequence, list) or len(sequence) != 21:
        raise AuthorityContractError("session_sequence must contain exactly 21 sessions")
    normalized_sequence = [_date(x, f"session_sequence[{i}]") for i, x in enumerate(sequence)]
    if len(set(normalized_sequence)) != 21 or normalized_sequence != sorted(normalized_sequence):
        raise AuthorityContractError("session_sequence must be unique and ascending")
    if normalized_sequence[0] != old_session or normalized_sequence[-1] != target_session:
        raise AuthorityContractError("session_sequence endpoints must match old and target sessions")
    rows = payload.get("rows")
    if not isinstance(rows, list) or len(rows) != 24:
        raise AuthorityContractError("rows must contain exactly 24 PIT Top24 members")
    tickers: list[str] = []
    normalized_rows: list[dict[str, str]] = []
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            raise AuthorityContractError(f"rows[{i}] must be an object")
        ticker = str(row.get("ticker") or "").strip().upper()
        if not ticker:
            raise AuthorityContractError(f"rows[{i}].ticker is required")
        tickers.append(ticker)
        normalized_rows.append({"ticker": ticker})
    if len(set(tickers)) != 24:
        raise AuthorityContractError("PIT Top24 tickers must be unique")
    return {
        "session_date": old_session,
        "target_session_date": target_session,
        "generated_at": generated_at,
        "coverage": 1.0,
        "source": source.strip(),
        "calendar_source": calendar_source.strip(),
        "schema_version": "v38.old_top24.pit.1",
        "calculation_version": upstream_version.strip(),
        "status": "READY",
        "lag_sessions": 20,
        "pit_frozen": True,
        "session_sequence": normalized_sequence,
        "rows": normalized_rows,
    }


def validate_full_authority(
    kind: str,
    payload: dict[str, Any],
    *,
    expected_session: str | None = None,
) -> tuple[str, dict[str, Any]]:
    name = str(kind or "").strip().lower()
    if name == "old_top24":
        return FULL_AUTHORITY_TARGETS[name], validate_old_top24(payload, expected_session)
    if name == "nqsar":
        session = _date(payload.get("session_date"), "session_date")
        if expected_session is not None and session != expected_session:
            raise AuthorityContractError(
                f"session_date mismatch: {session} != {expected_session}"
            )
        now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        try:
            normalized = parse_authoritative_input(
                payload,
                expected_session_date=session,
                as_of=now,
            )
        except NQSARError as exc:
            raise AuthorityContractError(str(exc)) from exc
        normalized["authority_version"] = str(
            payload.get("authority_version") or "recovered-authoritative-input"
        )
        normalized["fsm_recomputed"] = False
        return FULL_AUTHORITY_TARGETS[name], normalized
    return validate_authority(name, payload, expected_session=expected_session)
