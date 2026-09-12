from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .freshness import atomic_write_json

CALCULATION_VERSION = "v38-history-archive-1.1.0"
SNAPSHOT_SCHEMA_VERSION = "v38.history.snapshot.1"
INDEX_SCHEMA_VERSION = "v38.history.index.1"
OLD_TOP24_SCHEMA_VERSION = "v38.old_top24.1"


class HistoryArchiveError(RuntimeError):
    pass


def _read(path: Path) -> dict[str, Any] | None:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return obj if isinstance(obj, dict) else None


def _same_session(root: Path, name: str, session: str) -> dict[str, Any] | None:
    obj = _read(root / name)
    return obj if obj is not None and obj.get("session_date") == session else None


def _market_closes(obj: dict[str, Any] | None, session: str) -> dict[str, float | None]:
    out: dict[str, float | None] = {}
    series = obj.get("series") if obj else None
    if not isinstance(series, dict):
        return out
    for symbol, rows in series.items():
        if not isinstance(rows, list):
            continue
        row = next(
            (x for x in reversed(rows) if isinstance(x, dict) and x.get("date") == session),
            None,
        )
        value = row.get("close") if row else None
        out[str(symbol)] = float(value) if isinstance(value, (int, float)) else None
    return out


def build_session_snapshot(data_dir: str | Path, *, top_n: int = 100) -> dict[str, Any]:
    root = Path(data_dir)
    state = _read(root / "state.json")
    if state is None or not isinstance(state.get("session_date"), str):
        raise HistoryArchiveError("state.json with session_date is required")
    session = state["session_date"]

    rs = _same_session(root, "rs.json", session)
    breadth = _same_session(root, "breadth.json", session)
    f123 = _same_session(root, "f123.json", session)
    market = _same_session(root, "market_inputs.json", session)
    manifest = _same_session(root, "acquisition_manifest.json", session)
    publish = _same_session(root, "publish.json", session)
    if rs is None or breadth is None or f123 is None or market is None or manifest is None:
        raise HistoryArchiveError("current-session acquisition outputs are incomplete")

    rows = rs.get("rows")
    if not isinstance(rows, list):
        raise HistoryArchiveError("rs.rows must be a list")
    keep = (
        "ticker", "price", "rs189", "rs126", "rs63", "ddv20",
        "sma50", "sma200", "high52", "dist52", "ret20", "ret63",
        "ret126", "ret189",
    )
    rs_top = [
        {key: row.get(key) for key in keep if key in row}
        for row in rows[:top_n]
        if isinstance(row, dict)
    ]

    f_summary: dict[str, Any] = {}
    for key in ("f1", "f2", "f3"):
        component = f123.get(key)
        if isinstance(component, dict):
            f_summary[key] = {
                name: component.get(name)
                for name in ("status", "value", "severity", "reason", "observable_count")
                if name in component
            }

    authority = manifest.get("authority_status")
    if not isinstance(authority, dict):
        authority = {}
    if not authority:
        for key, path in (
            ("nqsar_status", "nqsar.json"),
            ("mc57_status", "mc57.json"),
            ("structural_clinical_biotech_status", "classifications.json"),
            ("peer_theme_status", "theme_scores.json"),
            ("options_status", "options/index.json"),
            ("positions_status", "positions_ledger.json"),
        ):
            authority[key] = {
                "path": path,
                "status": str(manifest.get(key) or "DATA_REQUIRED"),
                "reason": manifest.get(key.replace("_status", "_reason")),
            }
    return {
        "session_date": session,
        "generated_at": state.get("generated_at"),
        "coverage": state.get("coverage"),
        "source": "derived:validated-current-session-acquisition",
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "calculation_version": CALCULATION_VERSION,
        "status": "READY",
        "acquisition": {
            "universe": manifest.get("universe"),
            "yahoo": manifest.get("yahoo"),
            "authority_status": authority,
        },
        "daily": {
            "breadth50": breadth.get("breadth50"),
            "breadth200": breadth.get("breadth200"),
            "market_closes": _market_closes(market, session),
            "f123": f_summary,
        },
        "rs_top": rs_top,
        "publication": {
            "full_v38_ready": publish.get("full_v38_ready") if publish else False,
            "ready_count": publish.get("ready_count") if publish else None,
            "required_count": publish.get("required_count") if publish else None,
        },
    }


def build_history_index(
    history_dir: str | Path,
    current_snapshot: dict[str, Any],
) -> dict[str, Any]:
    root = Path(history_dir)
    snapshots: dict[str, dict[str, Any]] = {}
    for path in sorted((root / "sessions").glob("*.json")):
        obj = _read(path)
        if obj is not None and isinstance(obj.get("session_date"), str):
            snapshots[obj["session_date"]] = obj
    snapshots[current_snapshot["session_date"]] = current_snapshot

    rows = []
    for session in sorted(snapshots):
        obj = snapshots[session]
        authority = obj.get("acquisition", {}).get("authority_status", {})
        ready_authorities = sum(
            1 for row in authority.values()
            if isinstance(row, dict) and row.get("status") == "READY"
        ) if isinstance(authority, dict) else 0
        rows.append({
            "session_date": session,
            "generated_at": obj.get("generated_at"),
            "coverage": obj.get("coverage"),
            "rs_top_count": len(obj.get("rs_top") or []),
            "ready_authority_count": ready_authorities,
            "path": f"sessions/{session}.json",
        })

    return {
        "session_date": current_snapshot["session_date"],
        "generated_at": current_snapshot.get("generated_at"),
        "coverage": current_snapshot.get("coverage"),
        "source": "derived:history-session-snapshots",
        "schema_version": INDEX_SCHEMA_VERSION,
        "calculation_version": CALCULATION_VERSION,
        "status": "READY",
        "first_session": rows[0]["session_date"] if rows else None,
        "latest_session": rows[-1]["session_date"] if rows else None,
        "session_count": len(rows),
        "rows": rows,
    }


def stage_session_snapshot(
    data_dir: str | Path,
    existing_history_dir: str | Path,
    staged_history_dir: str | Path,
) -> tuple[Path, Path]:
    snapshot = build_session_snapshot(data_dir)
    staged = Path(staged_history_dir)
    session_path = staged / "sessions" / f"{snapshot['session_date']}.json"
    index_path = staged / "index.json"
    atomic_write_json(session_path, snapshot)
    atomic_write_json(index_path, build_history_index(existing_history_dir, snapshot))
    return session_path, index_path


def materialize_old_top24_from_history(
    history_dir: str | Path,
    current_rs_path: str | Path,
    output_path: str | Path,
    *,
    target_session: str,
    generated_at: str,
) -> Path | None:
    root = Path(history_dir)
    sessions: dict[str, dict[str, Any]] = {}
    for path in sorted((root / "sessions").glob("*.json")):
        obj = _read(path)
        if obj is not None and isinstance(obj.get("session_date"), str):
            sessions[obj["session_date"]] = obj
    current = _read(Path(current_rs_path))
    if current is None or current.get("session_date") != target_session:
        raise HistoryArchiveError("current rs session does not match target")

    sequence = sorted({*sessions.keys(), target_session})
    sequence = [day for day in sequence if day <= target_session]
    if len(sequence) < 21 or sequence[-1] != target_session:
        return None
    sequence = sequence[-21:]
    old_session = sequence[0]
    old = sessions.get(old_session)
    rows = old.get("rs_top") if old else None
    if not isinstance(rows, list) or len(rows) < 24:
        return None
    tickers = []
    for row in rows[:24]:
        ticker = row.get("ticker") if isinstance(row, dict) else None
        if not isinstance(ticker, str) or not ticker.strip():
            return None
        tickers.append(ticker.strip().upper())
    if len(set(tickers)) != 24:
        return None

    payload = {
        "session_date": old_session,
        "target_session_date": target_session,
        "generated_at": generated_at,
        "coverage": old.get("coverage"),
        "source": "derived:validated-history-session-snapshot",
        "calendar_source": "observed archived completed QQQ/SPY sessions",
        "schema_version": OLD_TOP24_SCHEMA_VERSION,
        "calculation_version": CALCULATION_VERSION,
        "lag_sessions": 20,
        "pit_frozen": True,
        "session_sequence": sequence,
        "rows": [{"ticker": ticker} for ticker in tickers],
    }
    return atomic_write_json(output_path, payload)
