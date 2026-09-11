from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .freshness import DATA_REQUIRED, READY, atomic_write_json


class MarketStatusError(RuntimeError):
    pass


def _read(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return obj if isinstance(obj, dict) else None


def normalize_market_statuses(data_dir: str | Path, *, session_date: str) -> tuple[Path, ...]:
    root = Path(data_dir)
    changed: list[Path] = []

    market_path = root / "market_state.json"
    market = _read(market_path)
    if market is not None and market.get("session_date") == session_date:
        mode = market.get("market_mode")
        desired = DATA_REQUIRED if mode == DATA_REQUIRED else READY
        reason = str(market.get("mode_reason") or "MARKET_MODE_UNRESOLVED") if desired == DATA_REQUIRED else None
        if market.get("status") != desired or (desired == DATA_REQUIRED and market.get("reason") != reason):
            market["status"] = desired
            if reason:
                market["reason"] = reason
            else:
                market.pop("reason", None)
            changed.append(atomic_write_json(market_path, market))

    core_path = root / "core12.json"
    core = _read(core_path)
    if core is not None and core.get("session_date") == session_date:
        ranking_status = core.get("ranking_status")
        desired = READY if ranking_status == "OK" else DATA_REQUIRED
        reason = str(core.get("ranking_reason") or ranking_status or "CORE12_RANKING_UNRESOLVED") if desired == DATA_REQUIRED else None
        if core.get("status") != desired or (desired == DATA_REQUIRED and core.get("reason") != reason):
            core["status"] = desired
            if reason:
                core["reason"] = reason
            else:
                core.pop("reason", None)
            changed.append(atomic_write_json(core_path, core))

    return tuple(changed)
