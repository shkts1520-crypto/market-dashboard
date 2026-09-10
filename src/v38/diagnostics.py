from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from .mc57_engine import readiness as mc57_readiness
from .nqsar_engine import readiness as nqsar_readiness
from .reference_gates import (
    DATA_REQUIRED,
    READY,
    mc57_reference_gate,
    nqsar_reference_gate,
    overall_reference_status,
)

CALCULATION_VERSION = "v38-diagnostics-1.0.0"
SCHEMA_VERSION = "v38.diagnostics.1"


def build_diagnostics(
    *,
    session_date: str,
    generated_at: str,
    nqsar_reference: dict[str, Any] | None = None,
    mc57_reference: dict[str, Any] | None = None,
) -> dict[str, Any]:
    nq_gate = nqsar_reference_gate(nqsar_reference)
    mc_gate = mc57_reference_gate(mc57_reference)
    status = overall_reference_status(
        nq_gate,
        mc_gate,
    )

    return {
        "session_date": session_date,
        "generated_at": generated_at,
        "coverage": None,
        "source": "derived:reference-readiness",
        "schema_version": SCHEMA_VERSION,
        "calculation_version": CALCULATION_VERSION,
        "status": status,
        "production_ready": status == READY,
        "nqsar": nqsar_readiness(
            session_date=session_date,
            generated_at=generated_at,
            reference=nqsar_reference,
        ),
        "mc57": mc57_readiness(
            session_date=session_date,
            generated_at=generated_at,
            reference=mc57_reference,
        ),
        "blocked_components": [
            gate.name
            for gate in (nq_gate, mc_gate)
            if gate.status == DATA_REQUIRED
        ],
    }


def atomic_write_json(
    path: str | Path,
    obj: dict[str, Any],
) -> Path:
    p = Path(path)

    p.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    text = (
        json.dumps(
            obj,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
        + "\n"
    )

    fd, tmp = tempfile.mkstemp(
        prefix=p.name + ".",
        dir=p.parent,
    )

    try:
        with os.fdopen(
            fd,
            "w",
            encoding="utf-8",
        ) as f:
            f.write(text)

        os.replace(tmp, p)

    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)

    return p
