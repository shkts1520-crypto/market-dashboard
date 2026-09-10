from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from .freshness import (
    DATA_REQUIRED,
    READY,
    STALE,
    assess_shard_file,
    atomic_write_json,
)

CALCULATION_VERSION = "v38-ui-payload-1.0.0"
SCHEMA_VERSION = "v38.ui_payload.1"

SECTION_REQUIREMENTS = (
    ("t-market", "Daily", ("market_state.json", "breadth.json", "mc57.json", "f123.json")),
    ("t-alloc", "Positions", ("positions.json",)),
    ("t-port", "Core 12", ("core12.json",)),
    ("t-rotation", "Rotation", ("rotation.json",)),
    ("t-rs", "RS", ("rs.json",)),
    ("t-weekly", "Weekly", ("weekly.json",)),
    ("t-options", "Options", ("options/index.json",)),
    ("t-post1", "Publish", ("publish.json",)),
    ("t-rules", "Rules", ("rules.json",)),
)


class UIPayloadError(RuntimeError):
    """Raised when the UI payload contract itself is invalid."""


def _iso_date(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    try:
        parsed = date.fromisoformat(text)
    except ValueError:
        return None
    return text if parsed.isoformat() == text else None


def _read_object(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return obj if isinstance(obj, dict) else None


def discover_target_session(data_dir: str | Path) -> dict[str, Any]:
    root = Path(data_dir)

    state = _read_object(root / "state.json")
    if state is not None:
        session = _iso_date(state.get("session_date"))
        if session is not None:
            return {
                "session_date": session,
                "source": "state.json",
                "status": READY,
                "reason": "STATE_AUTHORITY",
            }

    sessions: set[str] = set()
    for _, _, names in SECTION_REQUIREMENTS:
        for name in names:
            obj = _read_object(root / name)
            if obj is None:
                continue
            session = _iso_date(obj.get("session_date"))
            if session is not None:
                sessions.add(session)

    if len(sessions) == 1:
        session = next(iter(sessions))
        return {
            "session_date": session,
            "source": "single-session-consensus",
            "status": READY,
            "reason": "SINGLE_SESSION_CONSENSUS",
        }

    if len(sessions) > 1:
        return {
            "session_date": None,
            "source": "shard-scan",
            "status": STALE,
            "reason": "MULTIPLE_SHARD_SESSIONS",
            "sessions": sorted(sessions),
        }

    return {
        "session_date": None,
        "source": "shard-scan",
        "status": DATA_REQUIRED,
        "reason": "NO_AUTHORITATIVE_SESSION",
    }


def _status_from_components(components: list[dict[str, Any]]) -> str:
    statuses = [row["status"] for row in components]
    if STALE in statuses:
        return STALE
    if DATA_REQUIRED in statuses:
        return DATA_REQUIRED
    return READY


def _unresolved_component(root: Path, name: str) -> dict[str, Any]:
    path = root / name
    if not path.exists():
        reason = "FILE_MISSING"
    elif _read_object(path) is None:
        reason = "INVALID_JSON"
    else:
        reason = "SESSION_UNRESOLVED"
    return {
        "name": name,
        "status": DATA_REQUIRED,
        "reason": reason,
        "session_date": None,
        "coverage": None,
    }


def build_ui_payload(
    data_dir: str | Path,
    *,
    generated_at: str,
    target_session: str | None = None,
) -> dict[str, Any]:
    if not isinstance(generated_at, str) or not generated_at.strip():
        raise UIPayloadError("generated_at is required")

    root = Path(data_dir)

    if target_session is not None:
        session = _iso_date(target_session)
        if session is None:
            raise UIPayloadError("target_session must be YYYY-MM-DD")
        discovery = {
            "session_date": session,
            "source": "explicit",
            "status": READY,
            "reason": "EXPLICIT_TARGET",
        }
    else:
        discovery = discover_target_session(root)
        session = discovery.get("session_date")

    sections: dict[str, dict[str, Any]] = {}
    all_statuses: list[str] = []

    for section_id, label, names in SECTION_REQUIREMENTS:
        if session is None:
            components = [
                _unresolved_component(root, name)
                for name in names
            ]
            section_status = (
                STALE
                if discovery["status"] == STALE
                else DATA_REQUIRED
            )
        else:
            components = [
                assess_shard_file(
                    root / name,
                    name=name,
                    target_session=session,
                )
                for name in names
            ]
            section_status = _status_from_components(components)

        sections[section_id] = {
            "label": label,
            "status": section_status,
            "required_inputs": list(names),
            "components": components,
        }
        all_statuses.append(section_status)

    if STALE in all_statuses or discovery["status"] == STALE:
        overall = STALE
    elif DATA_REQUIRED in all_statuses:
        overall = DATA_REQUIRED
    else:
        overall = READY

    return {
        "session_date": session,
        "generated_at": generated_at,
        "coverage": (
            sum(1 for status in all_statuses if status == READY)
            / len(all_statuses)
        ),
        "source": "derived:ui-payload",
        "schema_version": SCHEMA_VERSION,
        "calculation_version": CALCULATION_VERSION,
        "status": overall,
        "session_discovery": discovery,
        "sections": sections,
    }


def write_ui_payload(
    data_dir: str | Path,
    output_path: str | Path,
    *,
    generated_at: str,
    target_session: str | None = None,
) -> Path:
    payload = build_ui_payload(
        data_dir,
        generated_at=generated_at,
        target_session=target_session,
    )
    return atomic_write_json(output_path, payload)
