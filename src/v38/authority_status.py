from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .freshness import atomic_write_json

CALCULATION_VERSION = "v38-authority-status-1.0.0"


def _current_ready(path: Path, session: str) -> tuple[bool, str]:
    if not path.exists():
        return False, "FILE_MISSING"
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return False, "INVALID_JSON"
    if not isinstance(obj, dict):
        return False, "EXPECTED_JSON_OBJECT"
    if obj.get("session_date") != session:
        return False, f"SESSION_MISMATCH:{obj.get('session_date')}"
    if obj.get("status") in {"DATA_REQUIRED", "STALE"}:
        return False, str(obj.get("reason") or obj.get("status"))
    return True, "CURRENT_SESSION_AUTHORITY"


def sync_acquisition_manifest(data_dir: str | Path) -> Path:
    root = Path(data_dir)
    state_path = root / "state.json"
    manifest_path = root / "acquisition_manifest.json"
    if not state_path.exists() or not manifest_path.exists():
        raise RuntimeError("state.json and acquisition_manifest.json are required")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    session = state.get("session_date")
    if not isinstance(session, str) or not session:
        raise RuntimeError("state.session_date is required")

    checks: dict[str, tuple[str, str | None]] = {
        "nqsar_status": ("nqsar.json", None),
        "mc57_status": ("mc57.json", "mc57_reason"),
        "structural_clinical_biotech_status": ("classifications.json", "structural_clinical_biotech_reason"),
        "peer_theme_status": ("theme_scores.json", "peer_theme_reason"),
        "options_status": ("options/index.json", "options_reason"),
        "positions_status": ("positions_ledger.json", "positions_reason"),
    }
    details: dict[str, Any] = {}
    for status_key, (relative, reason_key) in checks.items():
        ready, reason = _current_ready(root / relative, session)
        manifest[status_key] = "READY" if ready else "DATA_REQUIRED"
        if reason_key:
            if ready:
                manifest.pop(reason_key, None)
            else:
                manifest[reason_key] = reason
        details[status_key] = {
            "path": relative,
            "status": manifest[status_key],
            "reason": reason,
        }

    manifest["authority_status_version"] = CALCULATION_VERSION
    manifest["authority_status"] = details
    return atomic_write_json(manifest_path, manifest)
