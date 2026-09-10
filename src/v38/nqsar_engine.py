from __future__ import annotations

from typing import Any

from .reference_gates import DATA_REQUIRED, nqsar_reference_gate

CALCULATION_VERSION = "v38-nqsar-diagnostics-1.0.0"
SCHEMA_VERSION = "v38.nqsar.readiness.1"
VALID_STATES = {"Blue", "Green", "Yellow", "Red"}

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
    """Raised when an NQSAR diagnostics contract is invalid."""


def validate_state(state: Any) -> str:
    if state not in VALID_STATES:
        raise NQSARError("state must be one of Blue/Green/Yellow/Red")
    return str(state)


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
