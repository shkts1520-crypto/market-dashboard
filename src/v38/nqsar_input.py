from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from .nqsar_engine import NQSARError, parse_authoritative_input, parse_sar_state_text

CALCULATION_VERSION = "v38-nqsar-input-1.0.0"

class NQSARInputError(RuntimeError):
    """Raised when an upstream NQSAR label cannot be normalized safely."""


def _atomic_json(path: Path, obj: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return path


def normalize_nqsar_text(
    raw: str,
    *,
    expected_session_date: str,
    as_of: str,
    source_name: str,
) -> dict[str, Any]:
    text = (raw or "").strip()
    if not text:
        raise NQSARInputError("NQSAR input is empty")

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = None

    try:
        if isinstance(parsed, dict):
            if parsed.get("status") == "DATA_REQUIRED" and not parsed.get("state"):
                raise NQSARInputError("NQSAR upstream is DATA_REQUIRED")

            has_direct_contract = (
                "session_date" in parsed
                and "generated_at" in parsed
                and "source" in parsed
                and ("state" in parsed or "exp_state_id" in parsed)
            )
            if has_direct_contract:
                out = parse_authoritative_input(
                    parsed,
                    expected_session_date=expected_session_date,
                    as_of=as_of,
                )
            else:
                out = parse_sar_state_text(
                    text,
                    generated_at=as_of,
                    expected_session_date=expected_session_date,
                    as_of=as_of,
                    source=source_name,
                )
        else:
            out = parse_sar_state_text(
                text,
                generated_at=as_of,
                expected_session_date=expected_session_date,
                as_of=as_of,
                source=source_name,
            )
    except NQSARError as exc:
        raise NQSARInputError(str(exc)) from exc

    out["input_adapter_version"] = CALCULATION_VERSION
    return out


def normalize_nqsar_file(
    input_path: str | Path,
    output_path: str | Path,
    *,
    expected_session_date: str,
    as_of: str,
) -> Path:
    src = Path(input_path)
    if not src.exists():
        raise NQSARInputError(f"NQSAR input not found: {src}")
    out = normalize_nqsar_text(
        src.read_text(encoding="utf-8"),
        expected_session_date=expected_session_date,
        as_of=as_of,
        source_name=src.name,
    )
    return _atomic_json(Path(output_path), out)
