from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .freshness import READY, assess_shard_file, atomic_write_json

CALCULATION_VERSION = "v38-publish-tqqq-extension-1.0.0"


class PublishExtensionError(RuntimeError):
    pass


def _load(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return obj if isinstance(obj, dict) else {}


def include_tqqq_panic_readiness(data_dir: str | Path, *, session_date: str) -> Path:
    root = Path(data_dir)
    path = root / "publish.json"
    publish = _load(path)
    if publish.get("session_date") != session_date:
        raise PublishExtensionError("publish.json session mismatch")

    components = [
        dict(row) for row in (publish.get("components") or [])
        if isinstance(row, dict) and row.get("name") != "tqqq_panic.json"
    ]
    tqqq = assess_shard_file(
        root / "tqqq_panic.json",
        name="tqqq_panic.json",
        target_session=session_date,
    )
    components.append(tqqq)
    blockers = [
        {"name": row["name"], "status": row["status"], "reason": row["reason"]}
        for row in components
        if row.get("status") != READY
    ]
    ready = sum(1 for row in components if row.get("status") == READY)
    publish["components"] = components
    publish["blockers"] = blockers
    publish["ready_count"] = ready
    publish["required_count"] = len(components)
    publish["coverage"] = ready / len(components) if components else 0.0
    publish["full_v38_ready"] = not blockers
    publish["tqqq_panic_readiness"] = {
        "required": True,
        "status": tqqq.get("status"),
        "reason": tqqq.get("reason"),
    }
    publish["publish_extension_version"] = CALCULATION_VERSION
    return atomic_write_json(path, publish)
