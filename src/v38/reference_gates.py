from __future__ import annotations

from dataclasses import dataclass
from typing import Any

DATA_REQUIRED = "DATA_REQUIRED"
READY = "READY"


@dataclass(frozen=True)
class ReferenceGate:
    name: str
    status: str
    missing: tuple[str, ...]
    details: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "missing": list(self.missing),
            "details": dict(self.details),
        }


def nqsar_reference_gate(
    reference: dict[str, Any] | None,
) -> ReferenceGate:
    missing: list[str] = []
    ref = (
        reference
        if isinstance(reference, dict)
        else {}
    )

    if not ref.get("verified"):
        missing.append("VERIFIED_REFERENCE")

    if not ref.get("fsm_version"):
        missing.append("FSM_VERSION")

    if not ref.get("golden_fixture_sha256"):
        missing.append("GOLDEN_FIXTURE_SHA256")

    return ReferenceGate(
        name="NQSAR",
        status=(
            READY
            if not missing
            else DATA_REQUIRED
        ),
        missing=tuple(missing),
        details={
            "requires_exact_fsm": True,
            "requires_golden_fixture": True,
            "source": ref.get("source"),
        },
    )


def mc57_reference_gate(
    reference: dict[str, Any] | None,
) -> ReferenceGate:
    missing: list[str] = []
    ref = (
        reference
        if isinstance(reference, dict)
        else {}
    )

    tickers = ref.get("etf_universe")

    if not ref.get("verified"):
        missing.append("VERIFIED_REFERENCE")

    if (
        not isinstance(tickers, list)
        or len(tickers) != 57
    ):
        missing.append("FIXED_57_ETF_UNIVERSE")

    elif len(
        {
            str(x).strip().upper()
            for x in tickers
            if str(x).strip()
        }
    ) != 57:
        missing.append(
            "FIXED_57_ETF_UNIVERSE_UNIQUE"
        )

    if not ref.get("golden_fixture_sha256"):
        missing.append("GOLDEN_FIXTURE_SHA256")

    return ReferenceGate(
        name="MC57",
        status=(
            READY
            if not missing
            else DATA_REQUIRED
        ),
        missing=tuple(missing),
        details={
            "requires_fixed_57_etfs": True,
            "requires_golden_fixture": True,
            "source": ref.get("source"),
        },
    )


def overall_reference_status(
    *gates: ReferenceGate,
) -> str:
    return (
        READY
        if gates
        and all(
            gate.status == READY
            for gate in gates
        )
        else DATA_REQUIRED
    )
