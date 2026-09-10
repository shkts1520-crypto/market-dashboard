from __future__ import annotations

import json
import math
import os
import tempfile
from datetime import date
from pathlib import Path
from typing import Any, Iterable

CALCULATION_VERSION = "v38-freshness-1.0.0"
SCHEMA_VERSION = "v38.freshness.1"

READY = "READY"
STALE = "STALE"
DATA_REQUIRED = "DATA_REQUIRED"

DEFAULT_UI_SHARDS = (
    "market_state.json",
    "breadth.json",
    "mc57.json",
    "f123.json",
    "core12.json",
    "positions.json",
    "rotation.json",
    "rs.json",
    "weekly.json",
    "options/index.json",
)

REQUIRED_META = (
    "session_date",
    "generated_at",
    "coverage",
    "source",
    "schema_version",
    "calculation_version",
)


class FreshnessError(RuntimeError):
    """Raised when the freshness contract itself is invalid."""


def _date(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise FreshnessError(f"{field} is required")

    text = value.strip()

    try:
        parsed = date.fromisoformat(text)
    except ValueError as exc:
        raise FreshnessError(
            f"{field} must be YYYY-MM-DD"
        ) from exc

    if parsed.isoformat() != text:
        raise FreshnessError(
            f"{field} must be YYYY-MM-DD"
        )

    return text


def _finite_or_none(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        x = float(value)
        return x if math.isfinite(x) else None

    return None


def assess_shard_object(
    obj: Any,
    *,
    name: str,
    target_session: str,
) -> dict[str, Any]:
    target = _date(
        target_session,
        "target_session",
    )

    if not isinstance(obj, dict):
        return {
            "name": name,
            "status": DATA_REQUIRED,
            "reason": "EXPECTED_JSON_OBJECT",
            "session_date": None,
            "coverage": None,
        }

    missing = [
        key
        for key in REQUIRED_META
        if key not in obj
    ]

    if missing:
        return {
            "name": name,
            "status": DATA_REQUIRED,
            "reason": "MISSING_METADATA",
            "missing": missing,
            "session_date": obj.get(
                "session_date"
            ),
            "coverage": _finite_or_none(
                obj.get("coverage")
            ),
        }

    session = obj.get("session_date")

    try:
        session = _date(
            session,
            f"{name}.session_date",
        )
    except FreshnessError:
        return {
            "name": name,
            "status": DATA_REQUIRED,
            "reason": "INVALID_SESSION_DATE",
            "session_date": session,
            "coverage": _finite_or_none(
                obj.get("coverage")
            ),
        }

    base = {
        "name": name,
        "session_date": session,
        "generated_at": obj.get(
            "generated_at"
        ),
        "coverage": _finite_or_none(
            obj.get("coverage")
        ),
        "source": obj.get("source"),
        "schema_version": obj.get(
            "schema_version"
        ),
        "calculation_version": obj.get(
            "calculation_version"
        ),
    }

    if session != target:
        return {
            **base,
            "status": STALE,
            "reason": "SESSION_MISMATCH",
            "target_session": target,
        }

    for key in (
        "generated_at",
        "source",
        "schema_version",
        "calculation_version",
    ):
        if (
            not isinstance(
                obj.get(key),
                str,
            )
            or not obj[key].strip()
        ):
            return {
                **base,
                "status": DATA_REQUIRED,
                "reason": (
                    f"INVALID_{key.upper()}"
                ),
            }

    return {
        **base,
        "status": READY,
        "reason": "CURRENT_SESSION",
    }


def assess_shard_file(
    path: str | Path,
    *,
    name: str | None = None,
    target_session: str,
) -> dict[str, Any]:
    p = Path(path)
    label = name or p.as_posix()

    if not p.exists():
        return {
            "name": label,
            "status": DATA_REQUIRED,
            "reason": "FILE_MISSING",
            "session_date": None,
            "coverage": None,
        }

    try:
        obj = json.loads(
            p.read_text(
                encoding="utf-8"
            )
        )
    except (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ):
        return {
            "name": label,
            "status": DATA_REQUIRED,
            "reason": "INVALID_JSON",
            "session_date": None,
            "coverage": None,
        }

    return assess_shard_object(
        obj,
        name=label,
        target_session=target_session,
    )


def build_freshness(
    data_dir: str | Path,
    *,
    target_session: str,
    generated_at: str,
    shard_names: Iterable[str] = DEFAULT_UI_SHARDS,
) -> dict[str, Any]:
    target = _date(
        target_session,
        "target_session",
    )

    if (
        not isinstance(
            generated_at,
            str,
        )
        or not generated_at.strip()
    ):
        raise FreshnessError(
            "generated_at is required"
        )

    root = Path(data_dir)

    names = tuple(
        str(x)
        for x in shard_names
    )

    if not names:
        raise FreshnessError(
            "at least one shard is required"
        )

    if (
        len(set(names))
        != len(names)
    ):
        raise FreshnessError(
            "duplicate shard names are not allowed"
        )

    shards = [
        assess_shard_file(
            root / name,
            name=name,
            target_session=target,
        )
        for name in names
    ]

    statuses = [
        row["status"]
        for row in shards
    ]

    if STALE in statuses:
        overall = STALE
    elif DATA_REQUIRED in statuses:
        overall = DATA_REQUIRED
    else:
        overall = READY

    return {
        "session_date": target,
        "generated_at": generated_at,
        "coverage": (
            sum(
                1
                for row in shards
                if row["status"] == READY
            )
            / len(shards)
        ),
        "source": "derived:shard-freshness",
        "schema_version": SCHEMA_VERSION,
        "calculation_version": CALCULATION_VERSION,
        "status": overall,
        "ready_count": sum(
            1
            for row in shards
            if row["status"] == READY
        ),
        "stale_count": sum(
            1
            for row in shards
            if row["status"] == STALE
        ),
        "data_required_count": sum(
            1
            for row in shards
            if row["status"]
            == DATA_REQUIRED
        ),
        "shards": shards,
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

        os.replace(
            tmp,
            p,
        )

    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)

    return p
