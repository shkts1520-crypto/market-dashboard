from __future__ import annotations

import json
import math
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

from .f123_engine import calculate_f123_from_files
from .market_engine import MarketEngineError, calculate_market_from_files
from .nqsar_input import NQSARInputError, normalize_nqsar_file
from .stock_adapter import calculate_from_files

CALCULATION_VERSION = "v38-calculate-pipeline-1.1.0"
REQUIRED_META = (
    "session_date",
    "generated_at",
    "coverage",
    "source",
    "schema_version",
    "calculation_version",
)
OUTPUT_NAMES = ("rs.json", "breadth.json", "f123.json", "market_state.json", "core12.json")


class CalculatePipelineError(RuntimeError):
    """Raised when the staged calculate output fails its publication contract."""


def _load(path: Path) -> dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise CalculatePipelineError(f"{path.name}: expected JSON object")
    return obj


def _walk_finite(v: Any, path: str = "$") -> None:
    if isinstance(v, float) and not math.isfinite(v):
        raise CalculatePipelineError(f"non-finite JSON number at {path}")
    if isinstance(v, dict):
        for k, x in v.items():
            _walk_finite(x, f"{path}.{k}")
    elif isinstance(v, list):
        for i, x in enumerate(v):
            _walk_finite(x, f"{path}[{i}]")


def validate_staged_outputs(stage: str | Path, *, session_date: str, generated_at: str) -> dict[str, Any]:
    root = Path(stage)
    loaded: dict[str, Any] = {}
    for name in OUTPUT_NAMES:
        p = root / name
        if not p.exists():
            raise CalculatePipelineError(f"missing staged output: {name}")
        obj = _load(p)
        missing = [k for k in REQUIRED_META if k not in obj]
        if missing:
            raise CalculatePipelineError(f"{name}: missing metadata: {', '.join(missing)}")
        if obj["session_date"] != session_date:
            raise CalculatePipelineError(
                f"STALE staged session mismatch: {name}={obj['session_date']} target={session_date}"
            )
        if obj["generated_at"] != generated_at:
            raise CalculatePipelineError(
                f"generated_at mismatch: {name}={obj['generated_at']} target={generated_at}"
            )
        if not isinstance(obj.get("source"), str) or not obj["source"]:
            raise CalculatePipelineError(f"{name}: source is required")
        if not isinstance(obj.get("schema_version"), str) or not obj["schema_version"]:
            raise CalculatePipelineError(f"{name}: schema_version is required")
        if not isinstance(obj.get("calculation_version"), str) or not obj["calculation_version"]:
            raise CalculatePipelineError(f"{name}: calculation_version is required")
        _walk_finite(obj)
        loaded[name] = obj
    return loaded


def calculate_pipeline(
    *,
    ohlcv_path: str | Path,
    universe_path: str | Path,
    nqsar_path: str | Path,
    output_dir: str | Path,
    session_date: str,
    generated_at: str,
    stock_source: str,
    old_top24_path: str | Path | None = None,
    classifications_path: str | Path | None = None,
    theme_scores_path: str | Path | None = None,
) -> tuple[Path, ...]:
    """Run the auditable calculate slice, validate, then publish atomically.

    NQSAR may be a dated sar_state.txt, authoritative NQSAR JSON shard, or
    EXP_STATE_ID JSON record. It is normalized and freshness-checked before any
    market output can be published. The missing exact FSM is never reconstructed.
    """
    out = Path(output_dir)
    out.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".v38-calc-stage-", dir=out.parent))
    try:
        try:
            normalized_nqsar = normalize_nqsar_file(
                nqsar_path,
                stage / "_nqsar_authoritative.json",
                expected_session_date=session_date,
                as_of=generated_at,
            )
        except NQSARInputError as exc:
            msg = str(exc)
            if "stale session_date" in msg or "future session_date" in msg:
                raise MarketEngineError(
                    f"STALE shard session mismatch: nqsar authoritative input rejected: {msg}"
                ) from exc
            raise MarketEngineError(f"NQSAR authoritative input rejected: {msg}") from exc

        rs_path, breadth_path = calculate_from_files(
            ohlcv_path,
            universe_path,
            stage,
            session_date=session_date,
            generated_at=generated_at,
            source=stock_source,
        )
        calculate_f123_from_files(
            rs_path,
            stage / "f123.json",
            generated_at=generated_at,
            old_top24_path=old_top24_path,
        )
        calculate_market_from_files(
            rs_path,
            breadth_path,
            normalized_nqsar,
            stage,
            generated_at=generated_at,
            classifications_path=classifications_path,
            theme_scores_path=theme_scores_path,
        )
        validate_staged_outputs(stage, session_date=session_date, generated_at=generated_at)

        out.mkdir(parents=True, exist_ok=True)
        published: list[Path] = []
        for name in OUTPUT_NAMES:
            src = stage / name
            dst = out / name
            os.replace(src, dst)
            published.append(dst)
        return tuple(published)
    finally:
        shutil.rmtree(stage, ignore_errors=True)
