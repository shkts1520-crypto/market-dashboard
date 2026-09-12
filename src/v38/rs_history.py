from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from .freshness import atomic_write_json

CALCULATION_VERSION = "v38-rs-history-1.1.0"
SCHEMA_VERSION = "v38.rs_history.1"
MAX_SNAPSHOTS = 320
RS_WINDOWS = (63, 126, 189)
COMPARISON_LAGS = ((1, "1日", "前営業日"), (5, "1週", "約5営業日前"), (21, "1か月", "約21営業日前"))
RECONSTRUCTED_HISTORY_NAME = "reconstructed_stock_metrics.json"


class RSHistoryError(RuntimeError):
    pass


def _load(path: str | Path) -> dict[str, Any] | None:
    p = Path(path)
    if not p.is_file():
        return None
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return obj if isinstance(obj, dict) else None


def _finite(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _clean_record(raw: dict[str, Any], rank: int) -> dict[str, Any]:
    return {
        "rank": rank,
        "ticker": str(raw.get("ticker") or "").strip().upper(),
        "rs63": _finite(raw.get("rs63")),
        "rs126": _finite(raw.get("rs126")),
        "rs189": _finite(raw.get("rs189")),
    }


def _rank_rows(rows: list[dict[str, Any]], key: str, limit: int) -> list[dict[str, Any]]:
    eligible = [
        row for row in rows
        if isinstance(row, dict)
        and str(row.get("ticker") or "").strip()
        and _finite(row.get(key)) is not None
    ]
    eligible.sort(
        key=lambda row: (-float(row[key]), str(row.get("ticker") or "").strip().upper())
    )
    return [_clean_record(row, rank) for rank, row in enumerate(eligible[:limit], start=1)]


def _current_snapshot(rs: dict[str, Any], session_date: str) -> dict[str, Any]:
    rows = rs.get("rows")
    if not isinstance(rows, list) or not rows:
        raise RSHistoryError("rs.rows is required")
    return {
        "date": session_date,
        "windows": {
            "63": _rank_rows(rows, "rs63", 10),
            "126": _rank_rows(rows, "rs126", 10),
            "189": _rank_rows(rows, "rs189", 100),
        },
        "window_source": {
            "63": "CURRENT_RS_FULL_UNIVERSE",
            "126": "CURRENT_RS_FULL_UNIVERSE",
            "189": "CURRENT_RS_FULL_UNIVERSE",
        },
    }


def _seed_from_reconstruction(history_dir: Path) -> dict[str, dict[str, Any]]:
    """Seed display history from the same downloaded OHLC used by production.

    The reconstructed file deliberately uses the current universe for old dates.
    It is therefore valid for display/history diagnostics, but is not PIT evidence
    and must never be promoted into a normal-stock trading gate.
    """
    obj = _load(history_dir / RECONSTRUCTED_HISTORY_NAME)
    if not obj or obj.get("status") != "READY" or obj.get("history_kind") != "CURRENT_UNIVERSE_RECONSTRUCTED":
        return {}
    raw_rows = obj.get("rows")
    if not isinstance(raw_rows, list):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for raw in raw_rows:
        if not isinstance(raw, dict) or not isinstance(raw.get("date"), str):
            continue
        day = raw["date"]
        rs_top = raw.get("rs_top")
        rs_windows = raw.get("rs_windows")
        if not isinstance(rs_top, list):
            continue
        windows: dict[str, list[dict[str, Any]]] = {"63": [], "126": [], "189": []}
        if isinstance(rs_windows, dict):
            for period in (63, 126):
                rows = rs_windows.get(str(period))
                if isinstance(rows, list):
                    windows[str(period)] = [
                        _clean_record(row, rank)
                        for rank, row in enumerate(rows[:10], start=1)
                        if isinstance(row, dict) and str(row.get("ticker") or "").strip()
                    ]
        windows["189"] = [
            _clean_record(row, rank)
            for rank, row in enumerate(rs_top[:100], start=1)
            if isinstance(row, dict) and str(row.get("ticker") or "").strip()
        ]
        if any(windows.values()):
            out[day] = {
                "date": day,
                "windows": windows,
                "window_source": {
                    "63": "CURRENT_UNIVERSE_RECONSTRUCTED_OHLC",
                    "126": "CURRENT_UNIVERSE_RECONSTRUCTED_OHLC",
                    "189": "CURRENT_UNIVERSE_RECONSTRUCTED_OHLC",
                },
            }
    return out


def _seed_from_archive(history_dir: Path) -> dict[str, dict[str, Any]]:
    """Recover only what the legacy observed archive actually proves.

    Session snapshots stored RS189-sorted top rows, not complete RS63/126
    rankings. Therefore only RS189 is seeded here. Exact RS63/126 snapshots from
    dates when this dashboard was already running are preserved separately.
    """
    out: dict[str, dict[str, Any]] = {}
    sessions = history_dir / "sessions"
    if not sessions.is_dir():
        return out
    for path in sorted(sessions.glob("*.json")):
        obj = _load(path)
        if not obj:
            continue
        day = obj.get("session_date")
        rs_top = obj.get("rs_top")
        if not isinstance(day, str) or not isinstance(rs_top, list) or not rs_top:
            continue
        records: list[dict[str, Any]] = []
        for rank, raw in enumerate(rs_top[:100], start=1):
            if not isinstance(raw, dict) or not str(raw.get("ticker") or "").strip():
                continue
            records.append(_clean_record(raw, rank))
        if records:
            out[day] = {
                "date": day,
                "windows": {"63": [], "126": [], "189": records},
                "window_source": {
                    "63": "UNAVAILABLE_IN_LEGACY_ARCHIVE",
                    "126": "UNAVAILABLE_IN_LEGACY_ARCHIVE",
                    "189": "LEGACY_ARCHIVE_RS189_TOP100",
                },
            }
    return out


def _preserved_observed_snapshots(existing: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    """Keep only previously captured exact current-session RS windows.

    Reconstructed sessions are regenerated from OHLC every run and are not kept
    from the previous output. This prevents stale reconstructions from overriding
    a refreshed historical calculation.
    """
    out: dict[str, dict[str, Any]] = {}
    raw = existing.get("snapshots") if isinstance(existing, dict) else None
    if not isinstance(raw, list):
        return out
    for snapshot in raw:
        if not isinstance(snapshot, dict) or not isinstance(snapshot.get("date"), str):
            continue
        source_map = snapshot.get("window_source")
        if not isinstance(source_map, dict) or "CURRENT_RS_FULL_UNIVERSE" not in set(source_map.values()):
            continue
        windows = snapshot.get("windows")
        if not isinstance(windows, dict):
            continue
        clean_windows: dict[str, list[dict[str, Any]]] = {}
        for period in RS_WINDOWS:
            rows = windows.get(str(period))
            clean: list[dict[str, Any]] = []
            if isinstance(rows, list):
                for rank, row in enumerate(rows, start=1):
                    if not isinstance(row, dict) or not str(row.get("ticker") or "").strip():
                        continue
                    clean.append(_clean_record(row, int(row.get("rank") or rank)))
            clean_windows[str(period)] = clean
        out[snapshot["date"]] = {
            "date": snapshot["date"],
            "windows": clean_windows,
            "window_source": dict(source_map),
        }
    return out


def _record_map(snapshot: dict[str, Any], period: int) -> dict[str, dict[str, Any]]:
    windows = snapshot.get("windows")
    rows = windows.get(str(period)) if isinstance(windows, dict) else None
    if not isinstance(rows, list):
        return {}
    return {
        str(row.get("ticker") or "").strip().upper(): row
        for row in rows
        if isinstance(row, dict) and str(row.get("ticker") or "").strip()
    }


def _period_snapshots(snapshots: list[dict[str, Any]], period: int) -> list[dict[str, Any]]:
    return [snapshot for snapshot in snapshots if _record_map(snapshot, period)]


def _comparison(period_snapshots: list[dict[str, Any]], lag: int, label: str, detail: str) -> dict[str, Any]:
    current = period_snapshots[-1]
    current_rows = list(_record_map(current, int(current.get("_period") or 189)).values())[:10]
    current_tickers = [str(row["ticker"]) for row in current_rows]
    if len(period_snapshots) <= lag:
        return {
            "lag": lag,
            "label": label,
            "detail": detail,
            "status": "ACCUMULATING",
            "available_sessions": len(period_snapshots),
            "required_sessions": lag + 1,
            "target_session": None,
            "continuing": None,
            "replacement_count": None,
            "in": [],
            "out": [],
        }
    prior = period_snapshots[-(lag + 1)]
    prior_rows = list(_record_map(prior, int(prior.get("_period") or 189)).values())[:10]
    prior_tickers = [str(row["ticker"]) for row in prior_rows]
    current_set = set(current_tickers)
    prior_set = set(prior_tickers)
    incoming = [ticker for ticker in current_tickers if ticker not in prior_set]
    outgoing = [ticker for ticker in prior_tickers if ticker not in current_set]
    return {
        "lag": lag,
        "label": label,
        "detail": detail,
        "status": "READY",
        "available_sessions": len(period_snapshots),
        "required_sessions": lag + 1,
        "target_session": prior.get("date"),
        "continuing": len(current_set & prior_set),
        "replacement_count": len(incoming),
        "in": incoming,
        "out": outgoing,
    }


def _window_output(snapshots: list[dict[str, Any]], period: int) -> dict[str, Any]:
    available = _period_snapshots(snapshots, period)
    if not available:
        return {
            "period": period,
            "status": "ACCUMULATING",
            "available_sessions": 0,
            "current": [],
            "comparisons": [],
        }
    tagged: list[dict[str, Any]] = []
    for snapshot in available:
        copy = dict(snapshot)
        copy["_period"] = period
        tagged.append(copy)
    current_rows = list(_record_map(tagged[-1], period).values())[:10]
    return {
        "period": period,
        "status": "READY",
        "available_sessions": len(tagged),
        "current": current_rows,
        "comparisons": [
            _comparison(tagged, lag, label, detail)
            for lag, label, detail in COMPARISON_LAGS
        ],
    }


def _delta(current: dict[str, Any], old: dict[str, Any] | None, key: str) -> float | None:
    now = _finite(current.get(key))
    before = _finite(old.get(key)) if isinstance(old, dict) else None
    return now - before if now is not None and before is not None else None


def _classify_persistence(
    *,
    current_rank: int,
    ranks: list[int | None],
    top10_days: int,
    top24_pct: float,
    consecutive_top10: int,
    rank_change: int | None,
    delta63: float | None,
    delta126: float | None,
    delta189: float | None,
    classification_ready: bool,
) -> str:
    if not classification_ready:
        return "蓄積中"
    was_outside_top24 = any(rank is None or rank > 24 for rank in ranks[:-1])
    if current_rank <= 10 and top10_days <= 2:
        return "一日急騰型"
    if (rank_change is not None and rank_change <= -8) or (
        delta63 is not None and delta126 is not None and delta63 < 0 and delta126 < 0
    ):
        return "失速中"
    if current_rank <= 10 and consecutive_top10 >= 5 and was_outside_top24:
        return "再浮上"
    if current_rank <= 10 and rank_change is not None and rank_change >= 10 and top10_days < 15:
        return "新規急浮上"
    if (
        top10_days >= 15
        and top24_pct >= 75.0
        and delta189 is not None
        and round(delta189, 1) >= 0.0
    ):
        return "定着"
    return "継続"


def _persistence_output(snapshots: list[dict[str, Any]]) -> dict[str, Any]:
    available = _period_snapshots(snapshots, 189)
    if not available:
        return {"status": "ACCUMULATING", "observed_sessions": 0, "required_sessions": 21, "rows": []}
    window = available[-21:]
    classification_ready = len(window) >= 21
    current_map = _record_map(available[-1], 189)
    current_rows = sorted(current_map.values(), key=lambda row: int(row.get("rank") or 10**9))[:24]
    rows: list[dict[str, Any]] = []
    for current in current_rows:
        ticker = str(current["ticker"])
        window_records = [_record_map(snapshot, 189).get(ticker) for snapshot in window]
        ranks = [int(record["rank"]) if record is not None and record.get("rank") is not None else None for record in window_records]
        top10_days = sum(1 for rank in ranks if rank is not None and rank <= 10)
        top24_days = sum(1 for rank in ranks if rank is not None and rank <= 24)
        top24_pct = 100.0 * top24_days / len(window)

        consecutive = 0
        for snapshot in reversed(available):
            record = _record_map(snapshot, 189).get(ticker)
            rank = int(record["rank"]) if record is not None and record.get("rank") is not None else None
            if rank is not None and rank <= 10:
                consecutive += 1
            else:
                break

        oldest = window_records[0] if window_records else None
        oldest_rank = int(oldest["rank"]) if oldest is not None and oldest.get("rank") is not None else None
        current_rank = int(current["rank"])
        rank_change = oldest_rank - current_rank if oldest_rank is not None else None
        d63 = _delta(current, oldest, "rs63")
        d126 = _delta(current, oldest, "rs126")
        d189 = _delta(current, oldest, "rs189")
        classification = _classify_persistence(
            current_rank=current_rank,
            ranks=ranks,
            top10_days=top10_days,
            top24_pct=top24_pct,
            consecutive_top10=consecutive,
            rank_change=rank_change,
            delta63=d63,
            delta126=d126,
            delta189=d189,
            classification_ready=classification_ready,
        )
        rows.append({
            "rank": current_rank,
            "ticker": ticker,
            "rs189": _finite(current.get("rs189")),
            "top10_days": top10_days,
            "top24_days": top24_days,
            "top24_pct": top24_pct,
            "window_sessions": len(window),
            "consecutive_top10_observed": consecutive,
            "rank_change": rank_change,
            "rank_change_sessions": len(window) - 1,
            "delta_rs63": d63,
            "delta_rs126": d126,
            "delta_rs189": d189,
            "classification": classification,
        })
    return {
        "status": "READY" if classification_ready else "ACCUMULATING",
        "observed_sessions": len(window),
        "required_sessions": 21,
        "classification_ready": classification_ready,
        "definition": {
            "定着": "Top10>=15/21 and Top24>=75% and long-term RS not deteriorating",
            "継続": "Top24 leadership maintained / fallback",
            "失速中": "21-session rank worsens >=8 or both RS63 and RS126 decline",
            "再浮上": "previously outside Top24 and current Top10 streak >=5",
            "新規急浮上": "21-session rank improves >=10 and recently enters Top10",
            "一日急騰型": "Top10 presence <=2 sessions",
        },
        "rows": rows,
    }


def build_rs_history(
    history_dir: str | Path,
    rs: dict[str, Any],
    *,
    session_date: str,
    generated_at: str,
    existing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if rs.get("session_date") != session_date:
        raise RSHistoryError(f"rs session mismatch: {rs.get('session_date')} != {session_date}")
    root = Path(history_dir)
    reconstructed = _seed_from_reconstruction(root)
    snapshots = dict(reconstructed)
    snapshots.update(_seed_from_archive(root))
    snapshots.update(_preserved_observed_snapshots(existing))
    snapshots[session_date] = _current_snapshot(rs, session_date)
    ordered = [snapshots[day] for day in sorted(snapshots) if day <= session_date][-MAX_SNAPSHOTS:]
    windows = {str(period): _window_output(ordered, period) for period in RS_WINDOWS}
    persistence = _persistence_output(ordered)
    session_count = len(ordered)
    reconstructed_count = sum(
        1 for snapshot in ordered
        if "CURRENT_UNIVERSE_RECONSTRUCTED_OHLC" in set((snapshot.get("window_source") or {}).values())
    )
    has_reconstruction = reconstructed_count > 0
    return {
        "session_date": session_date,
        "generated_at": generated_at,
        "coverage": min(1.0, persistence["observed_sessions"] / 21.0),
        "source": (
            "Yahoo adjusted OHLC current-universe reconstruction + observed V38 session archive + current RS universe"
            if has_reconstruction
            else "observed V38 session archive + current RS universe"
        ),
        "schema_version": SCHEMA_VERSION,
        "calculation_version": CALCULATION_VERSION,
        "status": "READY",
        "history_kind": "CURRENT_UNIVERSE_RECONSTRUCTED" if has_reconstruction else "OBSERVED_ARCHIVE_ONLY",
        "observed_sessions": session_count,
        "reconstructed_sessions": reconstructed_count,
        "first_observed_session": ordered[0]["date"] if ordered else session_date,
        "latest_observed_session": ordered[-1]["date"] if ordered else session_date,
        "survivorship_warning": has_reconstruction,
        "trading_gate_eligible": False,
        "history_policy": (
            "Historical RS ranks are recomputed from downloaded split-adjusted Yahoo OHLC using the current universe; exact PIT membership is unavailable for reconstructed dates. Exact observed sessions override reconstructed windows."
            if has_reconstruction
            else "Only actually archived sessions are used. Missing pre-recovery history is not filled."
        ),
        "windows": windows,
        "persistence": persistence,
        "snapshots": ordered,
    }


def write_rs_history(
    history_dir: str | Path,
    rs_path: str | Path,
    output_path: str | Path,
    *,
    session_date: str,
    generated_at: str,
) -> Path:
    rs = _load(rs_path)
    if rs is None:
        raise RSHistoryError(f"rs input missing or invalid: {rs_path}")
    existing = _load(output_path)
    out = build_rs_history(
        history_dir,
        rs,
        session_date=session_date,
        generated_at=generated_at,
        existing=existing,
    )
    return atomic_write_json(output_path, out)
