from __future__ import annotations

from datetime import date, datetime
import json
import re
from typing import Any, Mapping

from .reference_gates import DATA_REQUIRED, nqsar_reference_gate

CALCULATION_VERSION = "v38-nqsar-diagnostics-1.1.0"
SCHEMA_VERSION = "v38.nqsar.readiness.1"
VALID_STATES = {"Blue", "Green", "Yellow", "Red"}

AUTHORITATIVE_SOURCE_PRIORITY = (
    "sar_state.txt",
    "EXP_STATE_ID",
)

EXP_STATE_ID_TO_STATE = {
    1: "Blue",
    2: "Yellow",
    3: "Red",
    4: "Green",
}

NQSAR_SPEC = {
    "inputs": ["NQ", "PSAR", "EMA21", "WILDER_RSI14"],
    "psar": {"step": 0.02, "increment": 0.02, "max": 0.08},
    "ema": {"span": 21, "adjust": False},
    "rsi": {"period": 14, "method": "Wilder"},
    "states": ["Blue", "Green", "Yellow", "Red"],
    "completed_bar_only": True,
    "exact_fsm_required": True,
}


class NQSARError(RuntimeError):
    """Raised when an NQSAR diagnostics or authoritative-input contract is invalid."""


def validate_state(state: Any) -> str:
    if state not in VALID_STATES:
        raise NQSARError("state must be one of Blue/Green/Yellow/Red")
    return str(state)


def _parse_iso_date(value: Any, field: str) -> date:
    if not isinstance(value, str) or not value.strip():
        raise NQSARError(f"{field} is required")
    text = value.strip()
    try:
        parsed = date.fromisoformat(text)
    except ValueError as exc:
        raise NQSARError(f"{field} must be YYYY-MM-DD") from exc
    if parsed.isoformat() != text:
        raise NQSARError(f"{field} must be YYYY-MM-DD")
    return parsed


def _parse_aware_datetime(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise NQSARError(f"{field} is required")
    text = value.strip()
    normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise NQSARError(f"{field} must be an ISO-8601 datetime") from exc
    if parsed.utcoffset() is None:
        raise NQSARError(f"{field} must include a timezone offset")
    return parsed


def _normalize_recovered_color(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    normalized = text[:1].upper() + text[1:].lower()
    return normalized if normalized in VALID_STATES else None


def parse_sar_state_text(
    raw: str,
    *,
    generated_at: str,
    expected_session_date: str,
    as_of: str,
    source: str = "sar_state.txt",
) -> dict[str, Any]:
    """Parse the recovered dated sar_state.txt formats and fail closed.

    Recovered accepted shapes are a JSON object carrying color/state/sar plus
    asof/date/session, or CSV-ish/plain text containing one YYYY-MM-DD date
    and one Blue/Green/Yellow/Red token. An embedded date is mandatory.
    """
    text = (raw or "").strip()
    if not text:
        raise NQSARError("sar_state text is empty")

    state: str | None = None
    session_date: str | None = None

    try:
        obj = json.loads(text)
    except Exception:
        obj = None

    if isinstance(obj, dict):
        state = _normalize_recovered_color(
            obj.get("color") or obj.get("state") or obj.get("sar")
        )
        raw_date = obj.get("asof") or obj.get("date") or obj.get("session")
        if raw_date is not None:
            session_date = str(raw_date).strip()
    else:
        date_match = re.search(r"([0-9]{4}-[0-9]{2}-[0-9]{2})", text)
        color_match = re.search(r"\b(Blue|Green|Yellow|Red)\b", text, re.I)
        if date_match:
            session_date = date_match.group(1)
        if color_match:
            state = _normalize_recovered_color(color_match.group(1))

    if state is None:
        raise NQSARError("sar_state text has no valid state")
    if not session_date:
        raise NQSARError("sar_state text has no embedded session date")

    return parse_authoritative_input(
        {
            "session_date": session_date,
            "generated_at": generated_at,
            "source": source,
            "state": state,
        },
        expected_session_date=expected_session_date,
        as_of=as_of,
    )


def readiness(
    *,
    session_date: str,
    generated_at: str,
    reference: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not session_date:
        raise NQSARError("session_date is required")
    if not generated_at:
        raise NQSARError("generated_at is required")

    gate = nqsar_reference_gate(reference)
    return {
        "session_date": session_date,
        "generated_at": generated_at,
        "coverage": None,
        "source": "reference-gate:nqsar",
        "schema_version": SCHEMA_VERSION,
        "calculation_version": CALCULATION_VERSION,
        "status": gate.status,
        "state": None,
        "data_required": gate.as_dict()["missing"],
        "spec": NQSAR_SPEC,
        "reason": (
            "Exact NQSAR FSM/golden fixture is not frozen; production state must not be inferred."
            if gate.status == DATA_REQUIRED
            else "Reference package is present; exact FSM implementation may be validated against it."
        ),
    }


def authoritative_state(
    state: Any,
    *,
    session_date: str,
    generated_at: str,
    source: str,
) -> dict[str, Any]:
    if not source:
        raise NQSARError("authoritative source is required")
    return {
        "session_date": session_date,
        "generated_at": generated_at,
        "coverage": 1.0,
        "source": source,
        "schema_version": "v38.nqsar.1",
        "calculation_version": CALCULATION_VERSION,
        "status": "AUTHORITATIVE_INPUT",
        "state": validate_state(state),
    }


def parse_authoritative_input(
    record: Mapping[str, Any],
    *,
    expected_session_date: str,
    as_of: str,
) -> dict[str, Any]:
    """Validate a direct NQSAR label without reconstructing or inferring the FSM."""
    if not isinstance(record, Mapping):
        raise NQSARError("authoritative input must be a mapping")

    expected = _parse_iso_date(expected_session_date, "expected_session_date")
    session = _parse_iso_date(record.get("session_date"), "session_date")
    if session != expected:
        relation = "stale" if session < expected else "future"
        raise NQSARError(
            f"{relation} session_date: expected {expected.isoformat()}, got {session.isoformat()}"
        )

    generated = _parse_aware_datetime(record.get("generated_at"), "generated_at")
    cutoff = _parse_aware_datetime(as_of, "as_of")
    if generated > cutoff:
        raise NQSARError("generated_at is in the future relative to as_of")

    source_value = record.get("source")
    if not isinstance(source_value, str) or not source_value.strip():
        raise NQSARError("source is required")
    source = source_value.strip()

    has_state = record.get("state") not in (None, "")
    has_exp_id = record.get("exp_state_id") not in (None, "")
    if not has_state and not has_exp_id:
        raise NQSARError("authoritative input requires state or exp_state_id")

    state_from_label: str | None = None
    if has_state:
        state_from_label = validate_state(record.get("state"))

    state_from_id: str | None = None
    exp_state_id: int | None = None
    if has_exp_id:
        raw_id = record.get("exp_state_id")
        if isinstance(raw_id, bool) or not isinstance(raw_id, int):
            raise NQSARError("exp_state_id must be an integer 1..4")
        if raw_id not in EXP_STATE_ID_TO_STATE:
            raise NQSARError("exp_state_id must be one of 1,2,3,4")
        exp_state_id = raw_id
        state_from_id = EXP_STATE_ID_TO_STATE[raw_id]

    if state_from_label is not None and state_from_id is not None:
        if state_from_label != state_from_id:
            raise NQSARError("state conflicts with exp_state_id")

    state = state_from_label or state_from_id
    if state is None:
        raise NQSARError("authoritative state is unavailable")

    out = authoritative_state(
        state,
        session_date=session.isoformat(),
        generated_at=record["generated_at"].strip(),
        source=source,
    )
    out["input_kind"] = (
        "state"
        if state_from_label is not None
        else "EXP_STATE_ID"
    )
    if exp_state_id is not None:
        out["exp_state_id"] = exp_state_id
    return out
