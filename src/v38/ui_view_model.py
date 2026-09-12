from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

CALCULATION_VERSION = "v38-ui-view-model-1.2.0"
SCHEMA_VERSION = "v38.ui_view_model.1"
READY = "READY"
STALE = "STALE"
DATA_REQUIRED = "DATA_REQUIRED"


class UIViewModelError(RuntimeError):
    """Raised when a required display-only input contract is invalid."""


def _read(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return obj if isinstance(obj, dict) else None


def _finite(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        x = float(value)
        return x if math.isfinite(x) else None
    return None


def _status(obj: dict[str, Any] | None, session: str) -> tuple[str, str]:
    if obj is None:
        return DATA_REQUIRED, "FILE_MISSING_OR_INVALID"
    actual = obj.get("session_date")
    if actual != session:
        return STALE, f"SESSION_MISMATCH:{actual}"
    declared = obj.get("status")
    if declared == STALE:
        return STALE, str(obj.get("reason") or "SHARD_DECLARED_STALE")
    if declared == DATA_REQUIRED:
        return DATA_REQUIRED, str(obj.get("reason") or "SHARD_DECLARED_DATA_REQUIRED")
    return READY, "CURRENT_SESSION"


def _metric(
    *,
    key: str,
    label: str,
    value: Any,
    status: str,
    reason: str,
    kind: str = "number",
    severity: str | None = None,
) -> dict[str, Any]:
    x = _finite(value)
    if x is None:
        display = "—"
    elif kind == "percent_fraction":
        display = f"{x * 100.0:.1f}%"
    elif kind == "percent_value":
        display = f"{x:.1f}%"
    elif kind == "price":
        display = f"{x:,.2f}"
    else:
        display = f"{x:.1f}"
    return {
        "key": key,
        "label": label,
        "value": x,
        "display": display,
        "status": status,
        "reason": reason,
        "severity": severity,
    }


def _text_metric(
    *,
    key: str,
    label: str,
    value: Any,
    status: str,
    reason: str,
) -> dict[str, Any]:
    text = value.strip() if isinstance(value, str) and value.strip() else None
    return {
        "key": key,
        "label": label,
        "value": text,
        "display": text or "—",
        "status": status if text is not None and status == READY else status,
        "reason": reason,
        "severity": None,
    }


def _f_metric(name: str, obj: dict[str, Any] | None, session: str) -> dict[str, Any]:
    file_status, file_reason = _status(obj, session)
    label = name.upper()
    if file_status != READY or obj is None:
        return _metric(
            key=name,
            label=label,
            value=None,
            status=file_status,
            reason=file_reason,
            kind="percent_fraction",
        )
    component = obj.get(name)
    if not isinstance(component, dict):
        return _metric(
            key=name,
            label=label,
            value=None,
            status=DATA_REQUIRED,
            reason=f"{label}_COMPONENT_MISSING",
            kind="percent_fraction",
        )
    raw_status = str(component.get("status") or DATA_REQUIRED)
    status = READY if raw_status in {"OK", "FULL", "PARTIAL"} and _finite(component.get("value")) is not None else DATA_REQUIRED
    reason = raw_status
    if status != READY:
        dependency = component.get("dependency")
        if isinstance(dependency, dict) and isinstance(dependency.get("reason"), str):
            reason = dependency["reason"]
    return _metric(
        key=name,
        label=label,
        value=component.get("value"),
        status=status,
        reason=reason,
        kind="percent_fraction",
        severity=str(component.get("severity")) if component.get("severity") is not None else None,
    )


def _latest_series_metric(
    market_inputs: dict[str, Any] | None,
    *,
    symbol: str,
    label: str,
    session: str,
) -> dict[str, Any]:
    file_status, file_reason = _status(market_inputs, session)
    if file_status != READY or market_inputs is None:
        return _metric(
            key=f"market_{symbol}",
            label=label,
            value=None,
            status=file_status,
            reason=file_reason,
            kind="price",
        )
    series = market_inputs.get("series")
    rows = series.get(symbol) if isinstance(series, dict) else None
    if not isinstance(rows, list):
        return _metric(
            key=f"market_{symbol}",
            label=label,
            value=None,
            status=DATA_REQUIRED,
            reason="SERIES_MISSING",
            kind="price",
        )
    row = next(
        (x for x in reversed(rows) if isinstance(x, dict) and x.get("date") == session),
        None,
    )
    if row is None:
        return _metric(
            key=f"market_{symbol}",
            label=label,
            value=None,
            status=DATA_REQUIRED,
            reason="SESSION_BAR_MISSING",
            kind="price",
        )
    close = _finite(row.get("close"))
    return _metric(
        key=f"market_{symbol}",
        label=label,
        value=close,
        status=READY if close is not None else DATA_REQUIRED,
        reason="CURRENT_SESSION_CLOSE" if close is not None else "CLOSE_MISSING",
        kind="price",
    )


def _market_rows(
    market_inputs: dict[str, Any] | None,
    symbol: str,
    session: str,
    *,
    limit: int = 260,
) -> list[dict[str, Any]]:
    series = market_inputs.get("series") if market_inputs else None
    raw = series.get(symbol) if isinstance(series, dict) else None
    if not isinstance(raw, list):
        return []
    rows: list[dict[str, Any]] = []
    for row in raw:
        if not isinstance(row, dict) or not isinstance(row.get("date"), str):
            continue
        close = _finite(row.get("close"))
        if row["date"] > session or close is None:
            continue
        item: dict[str, Any] = {"date": row["date"], "close": close}
        for key in ("open", "high", "low", "volume"):
            value = _finite(row.get(key))
            if value is not None:
                item[key] = value
        rows.append(item)
    rows.sort(key=lambda row: row["date"])
    return rows[-limit:]


def _pct_change(rows: list[dict[str, Any]], lag: int) -> float | None:
    if len(rows) <= lag:
        return None
    current = _finite(rows[-1].get("close"))
    previous = _finite(rows[-(lag + 1)].get("close"))
    if current is None or previous is None or previous <= 0:
        return None
    return current / previous - 1.0


def _market_summary(rows: list[dict[str, Any]], session: str) -> dict[str, Any]:
    latest = _finite(rows[-1].get("close")) if rows else None
    same_year = [row for row in rows if row["date"][:4] == session[:4]]
    ytd = None
    if latest is not None and same_year:
        first = _finite(same_year[0].get("close"))
        if first is not None and first > 0:
            ytd = latest / first - 1.0
    trailing = rows[-252:]
    highs = [_finite(row.get("high")) for row in trailing]
    highs = [value for value in highs if value is not None]
    high52 = max(highs) if highs else None
    position52 = latest / high52 if latest is not None and high52 and high52 > 0 else None
    return {
        "close": latest,
        "change_1d": _pct_change(rows, 1),
        "change_1w": _pct_change(rows, 5),
        "change_1m": _pct_change(rows, 21),
        "change_3m": _pct_change(rows, 63),
        "change_1y": _pct_change(rows, 252),
        "change_ytd": ytd,
        "position_52w": position52,
    }


def _history_rows(root: Path, session: str, current: dict[str, Any]) -> list[dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    sessions = root / "history" / "sessions"
    for path in sorted(sessions.glob("*.json")):
        obj = _read(path)
        day = obj.get("session_date") if obj else None
        daily = obj.get("daily") if obj else None
        publication = obj.get("publication") if obj else None
        if not isinstance(day, str) or day > session or not isinstance(daily, dict):
            continue
        f123 = daily.get("f123") if isinstance(daily.get("f123"), dict) else {}
        item: dict[str, Any] = {
            "date": day,
            "breadth50": _finite(daily.get("breadth50")),
            "breadth200": _finite(daily.get("breadth200")),
            "full_v38_ready": bool(publication.get("full_v38_ready")) if isinstance(publication, dict) else False,
        }
        for key in ("f1", "f2", "f3"):
            component = f123.get(key) if isinstance(f123, dict) else None
            item[key] = _finite(component.get("value")) if isinstance(component, dict) else None
        rows[day] = item
    rows[session] = {**rows.get(session, {}), **current, "date": session}
    return [rows[day] for day in sorted(rows)][-260:]


def _rs_display_row(raw: dict[str, Any], rank: int) -> dict[str, Any] | None:
    ticker = str(raw.get("ticker") or "").strip().upper()
    if not ticker:
        return None
    price = _finite(raw.get("price"))
    rs189 = _finite(raw.get("rs189"))
    rs126 = _finite(raw.get("rs126"))
    rs63 = _finite(raw.get("rs63"))
    ddv20 = _finite(raw.get("ddv20"))
    sparkline = []
    if isinstance(raw.get("sparkline"), list):
        for point in raw["sparkline"]:
            if isinstance(point, dict) and isinstance(point.get("date"), str):
                close = _finite(point.get("close"))
                if close is not None:
                    sparkline.append({"date": point["date"], "close": close})
    return {
        "rank": rank,
        "ticker": ticker,
        "name": str(raw.get("name") or ""),
        "sector": str(raw.get("sector") or ""),
        "industry": str(raw.get("industry") or ""),
        "price": price,
        "price_display": f"{price:,.2f}" if price is not None else "—",
        "rs189": rs189,
        "rs189_display": f"{rs189:.1f}" if rs189 is not None else "—",
        "rs126": rs126,
        "rs126_display": f"{rs126:.1f}" if rs126 is not None else "—",
        "rs63": rs63,
        "rs63_display": f"{rs63:.1f}" if rs63 is not None else "—",
        "ret1": _finite(raw.get("ret1")),
        "ret20": _finite(raw.get("ret20")),
        "ret63": _finite(raw.get("ret63")),
        "dist52": _finite(raw.get("dist52")),
        "ddv20": ddv20,
        "ddv20_display": f"${ddv20 / 1_000_000.0:.1f}M" if ddv20 is not None else "—",
        "sparkline": sparkline,
    }


def _optional_text_shard(
    root: Path,
    name: str,
    *,
    session: str,
    key: str,
    label: str,
    aliases: tuple[str, ...],
    missing_reason: str,
) -> dict[str, Any]:
    obj = _read(root / name)
    status, reason = _status(obj, session)
    if status != READY or obj is None:
        return _text_metric(
            key=key,
            label=label,
            value=None,
            status=status,
            reason=missing_reason if status == DATA_REQUIRED and obj is None else reason,
        )
    value = next((obj.get(alias) for alias in aliases if obj.get(alias) is not None), None)
    if value == DATA_REQUIRED:
        return _text_metric(
            key=key,
            label=label,
            value=None,
            status=DATA_REQUIRED,
            reason=str(obj.get("reason") or missing_reason),
        )
    return _text_metric(
        key=key,
        label=label,
        value=value,
        status=READY if isinstance(value, str) and value.strip() else DATA_REQUIRED,
        reason="CURRENT_SESSION" if value is not None else "VALUE_MISSING",
    )


def _optional_number_shard(
    root: Path,
    name: str,
    *,
    session: str,
    key: str,
    label: str,
    aliases: tuple[str, ...],
    missing_reason: str,
) -> dict[str, Any]:
    obj = _read(root / name)
    status, reason = _status(obj, session)
    if status != READY or obj is None:
        return _metric(
            key=key,
            label=label,
            value=None,
            status=status,
            reason=missing_reason if status == DATA_REQUIRED and obj is None else reason,
        )
    value = next((obj.get(alias) for alias in aliases if obj.get(alias) is not None), None)
    x = _finite(value)
    return _metric(
        key=key,
        label=label,
        value=x,
        status=READY if x is not None else DATA_REQUIRED,
        reason="CURRENT_SESSION" if x is not None else "VALUE_MISSING",
    )


def _section(
    root: Path,
    *,
    name: str,
    session: str,
    title: str,
    rows_key: str = "rows",
    note: str = "",
) -> dict[str, Any]:
    obj = _read(root / name)
    status, reason = _status(obj, session)
    rows: list[dict[str, Any]] = []
    if status == READY and obj is not None:
        raw_rows = obj.get(rows_key)
        if isinstance(raw_rows, list):
            rows = [dict(row) for row in raw_rows if isinstance(row, dict)]
    return {
        "status": status,
        "reason": reason,
        "title": title,
        "rows": rows,
        "coverage": _finite(obj.get("coverage")) if obj else None,
        "note": note or (str(obj.get("note")) if obj and obj.get("note") is not None else ""),
        "source": obj.get("source") if obj else None,
    }


def _flatten_rules(value: Any, prefix: str = "") -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            label = f"{prefix}.{key}" if prefix else str(key)
            rows.extend(_flatten_rules(child, label))
    elif isinstance(value, list):
        rows.append({"key": prefix, "value": " / ".join(str(x) for x in value)})
    else:
        rows.append({"key": prefix, "value": str(value)})
    return rows


def build_ui_view_model(data_dir: str | Path) -> dict[str, Any]:
    root = Path(data_dir)
    state = _read(root / "state.json")
    if state is None or not isinstance(state.get("session_date"), str):
        raise UIViewModelError("state.json with session_date is required")
    session = state["session_date"]

    breadth = _read(root / "breadth.json")
    f123 = _read(root / "f123.json")
    rs = _read(root / "rs.json")
    market_inputs = _read(root / "market_inputs.json")

    b_status, b_reason = _status(breadth, session)
    daily_metrics: list[dict[str, Any]] = [
        _optional_text_shard(
            root,
            "market_state.json",
            session=session,
            key="market_mode",
            label="Market Mode",
            aliases=("market_mode",),
            missing_reason="MARKET_STATE_MISSING",
        ),
        _optional_text_shard(
            root,
            "nqsar.json",
            session=session,
            key="nqsar",
            label="NQSAR",
            aliases=("state", "color", "nqsar"),
            missing_reason="NQSAR_AUTHORITATIVE_INPUT_MISSING",
        ),
        _metric(
            key="breadth50",
            label="Breadth 50",
            value=breadth.get("breadth50") if breadth else None,
            status=b_status if _finite(breadth.get("breadth50") if breadth else None) is not None else DATA_REQUIRED,
            reason=b_reason if b_status != READY else "CURRENT_SESSION",
            kind="percent_value",
        ),
        _metric(
            key="breadth200",
            label="Breadth 200",
            value=breadth.get("breadth200") if breadth else None,
            status=b_status if _finite(breadth.get("breadth200") if breadth else None) is not None else DATA_REQUIRED,
            reason=b_reason if b_status != READY else "CURRENT_SESSION",
            kind="percent_value",
        ),
        _optional_number_shard(
            root,
            "mc57.json",
            session=session,
            key="mc57",
            label="MC57",
            aliases=("mc57", "value"),
            missing_reason="MC57_FIXED57_GOLDEN_MISSING",
        ),
        _f_metric("f1", f123, session),
        _f_metric("f2", f123, session),
        _f_metric("f3", f123, session),
    ]

    market_labels = (
        ("QQQ", "QQQ"), ("TQQQ", "TQQQ"), ("SPY", "SPY"),
        ("RSP", "RSP"), ("QQQE", "QQQE"), ("SOXL", "SOXL"),
        ("^VIX", "VIX"), ("^VIX3M", "VIX3M"), ("^VXN", "VXN"),
        ("NQ=F", "NQ"), ("HYG", "HYG"), ("IEF", "IEF"),
        ("^TNX", "US10Y"), ("^FVX", "US5Y"), ("DX-Y.NYB", "DXY"),
        ("CL=F", "WTI"), ("GC=F", "Gold"),
        ("XLB", "Materials"), ("XLC", "Communication"),
        ("XLE", "Energy"), ("XLF", "Financials"),
        ("XLI", "Industrials"), ("XLK", "Technology"),
        ("XLP", "Staples"), ("XLRE", "Real Estate"),
        ("XLU", "Utilities"), ("XLV", "Health Care"),
        ("XLY", "Discretionary"),
    )
    for symbol, label in market_labels:
        daily_metrics.append(
            _latest_series_metric(
                market_inputs,
                symbol=symbol,
                label=label,
                session=session,
            )
        )

    market_series = {
        symbol: _market_rows(market_inputs, symbol, session)
        for symbol, _ in market_labels
    }
    market_summaries = {
        symbol: _market_summary(rows, session)
        for symbol, rows in market_series.items()
        if rows
    }
    authoritative_daily_keys = {
        "market_mode", "nqsar", "breadth50", "breadth200", "mc57",
        "f1", "f2", "f3", "market_QQQ", "market_TQQQ", "market_^VIX",
        "market_NQ=F", "market_SPY",
    }

    rs_status, rs_reason = _status(rs, session)
    rs_rows: list[dict[str, Any]] = []
    if rs_status == READY and rs is not None and isinstance(rs.get("rows"), list):
        for rank, raw in enumerate(rs["rows"][:24], start=1):
            if not isinstance(raw, dict):
                continue
            row = _rs_display_row(raw, rank)
            if row is not None:
                rs_rows.append(row)
    elif rs_status == READY:
        rs_status = DATA_REQUIRED
        rs_reason = "ROWS_MISSING"

    coverage = _finite(rs.get("coverage")) if rs else None
    breadth_coverage = _finite(breadth.get("coverage")) if breadth else None

    rs_windows: dict[str, list[dict[str, Any]]] = {}
    raw_all_rs_rows = rs.get("rows") if rs else []
    all_rs_rows = [
        row for row in (raw_all_rs_rows if isinstance(raw_all_rs_rows, list) else [])
        if isinstance(row, dict)
    ]
    for period in (63, 126, 189):
        key = f"rs{period}"
        ranked = sorted(
            (row for row in all_rs_rows if _finite(row.get(key)) is not None),
            key=lambda row: (-float(row[key]), str(row.get("ticker") or "")),
        )[:10]
        display_rows = []
        for rank, raw in enumerate(ranked, start=1):
            row = _rs_display_row(raw, rank)
            if row is not None:
                display_rows.append(row)
        rs_windows[str(period)] = display_rows

    ret1_values = [_finite(row.get("ret1")) for row in all_rs_rows]
    ret1_values = [value for value in ret1_values if value is not None]
    leader_diagnostics = {
        "advancing_1d_pct": (
            100.0 * sum(1 for value in ret1_values if value > 0) / len(ret1_values)
        ) if ret1_values else None,
        "triple_rs85_count": sum(
            1 for row in all_rs_rows
            if all((_finite(row.get(key)) or -1.0) >= 85.0 for key in ("rs63", "rs126", "rs189"))
        ),
        "near_52w_high_count": sum(
            1 for row in all_rs_rows
            if (_finite(row.get("dist52")) is not None and float(row["dist52"]) >= -0.05)
        ),
        "top_ret20": [
            row for row in sorted(
                (_rs_display_row(raw, 0) for raw in all_rs_rows),
                key=lambda row: -(row.get("ret20") if row and row.get("ret20") is not None else -1e100),
            )[:10] if row is not None
        ],
    }

    breadth_current = {
        "breadth50": _finite(breadth.get("breadth50")) if breadth else None,
        "breadth200": _finite(breadth.get("breadth200")) if breadth else None,
    }
    for key in ("f1", "f2", "f3"):
        component = f123.get(key) if f123 else None
        breadth_current[key] = _finite(component.get("value")) if isinstance(component, dict) else None
    history = _history_rows(root, session, breadth_current)

    positions = _section(root, name="positions.json", session=session, title="Positions")
    core12 = _section(root, name="core12.json", session=session, title="Core 12", rows_key="ranking")
    core_obj = _read(root / "core12.json")
    if core12["status"] == READY and core_obj is not None:
        ranking_status = core_obj.get("ranking_status")
        if ranking_status not in (None, "OK"):
            core12["status"] = DATA_REQUIRED
            core12["reason"] = str(core_obj.get("ranking_reason") or ranking_status)
        core12["market_mode"] = core_obj.get("market_mode")
        core12["max_new_total_slots"] = core_obj.get("max_new_total_slots")

    rotation = _section(root, name="rotation.json", session=session, title="Rotation")
    group_diagnostics: dict[str, list[dict[str, Any]]] = {}
    for group_key in ("sector", "industry"):
        grouped: dict[str, list[dict[str, Any]]] = {}
        for row in all_rs_rows:
            group = str(row.get(group_key) or "").strip()
            if group:
                grouped.setdefault(group, []).append(row)
        output_rows: list[dict[str, Any]] = []
        for group, members in grouped.items():
            if len(members) < 5:
                continue
            ret20 = [_finite(row.get("ret20")) for row in members]
            ret63 = [_finite(row.get("ret63")) for row in members]
            rs63_values = [_finite(row.get("rs63")) for row in members]
            ret20 = [value for value in ret20 if value is not None]
            ret63 = [value for value in ret63 if value is not None]
            rs63_values = [value for value in rs63_values if value is not None]
            above = [
                float(row["price"]) > float(row["sma50"])
                for row in members
                if _finite(row.get("price")) is not None
                and _finite(row.get("sma50")) is not None
            ]
            leaders = sorted(
                members,
                key=lambda row: (
                    -(_finite(row.get("rs63")) or -1.0),
                    str(row.get("ticker") or ""),
                ),
            )[:3]
            output_rows.append({
                "group": group,
                "member_count": len(members),
                "ret20_avg": sum(ret20) / len(ret20) if ret20 else None,
                "ret63_avg": sum(ret63) / len(ret63) if ret63 else None,
                "rs63_avg": sum(rs63_values) / len(rs63_values) if rs63_values else None,
                "above_sma50_pct": 100.0 * sum(above) / len(above) if above else None,
                "leaders": [str(row.get("ticker")) for row in leaders],
                "scope": "CURRENT_UNIVERSE_DIAGNOSTIC_NOT_PEER_THEME_SCORE",
            })
        output_rows.sort(
            key=lambda row: (
                -(row["ret20_avg"] if row["ret20_avg"] is not None else -1e100),
                row["group"],
            )
        )
        group_diagnostics[group_key] = output_rows[:30]
    rotation["diagnostic_status"] = (
        READY if any(group_diagnostics.values()) else DATA_REQUIRED
    )
    rotation["diagnostics"] = group_diagnostics
    weekly = _section(root, name="weekly.json", session=session, title="Weekly")
    weekly_obj = _read(root / "weekly.json")
    weekly["state"] = weekly_obj.get("state") if weekly_obj else None

    options = _section(root, name="options/index.json", session=session, title="Options")

    publish = _section(root, name="publish.json", session=session, title="Publish", rows_key="blockers")
    publish_obj = _read(root / "publish.json")
    if publish_obj:
        publish["full_v38_ready"] = publish_obj.get("full_v38_ready")
        publish["ready_count"] = publish_obj.get("ready_count")
        publish["required_count"] = publish_obj.get("required_count")

    rules_obj = _read(root / "rules.json")
    rules_status, rules_reason = _status(rules_obj, session)
    rules = {
        "status": rules_status,
        "reason": rules_reason,
        "title": "Rules",
        "rows": _flatten_rules(rules_obj.get("rules")) if rules_status == READY and rules_obj else [],
        "coverage": _finite(rules_obj.get("coverage")) if rules_obj else None,
        "note": "Code-owned adopted V38 rules only; unresolved execution details remain DATA_REQUIRED.",
        "source": rules_obj.get("source") if rules_obj else None,
    }

    return {
        "session_date": session,
        "generated_at": state.get("generated_at"),
        "source": "derived:authoritative-display-shards",
        "schema_version": SCHEMA_VERSION,
        "calculation_version": CALCULATION_VERSION,
        "daily": {
            "status": DATA_REQUIRED if any(
                x["status"] != READY
                for x in daily_metrics
                if x["key"] in authoritative_daily_keys
            ) else READY,
            "metrics": daily_metrics,
            "stock_data_coverage": coverage,
            "breadth_coverage": breadth_coverage,
            "market_series": market_series,
            "market_summaries": market_summaries,
            "history": history,
            "leader_diagnostics": leader_diagnostics,
            "market_diagnostics": (
                rs.get("market_diagnostics")
                if rs and isinstance(rs.get("market_diagnostics"), dict)
                else {
                    "status": DATA_REQUIRED,
                    "reason": "MARKET_DIAGNOSTIC_HISTORY_MISSING",
                    "series": [],
                }
            ),
        },
        "positions": positions,
        "core12": core12,
        "rotation": rotation,
        "rs": {
            "status": rs_status,
            "reason": rs_reason,
            "title": "RS189 Top 24",
            "rows": rs_rows,
            "windows": rs_windows,
            "coverage": coverage,
            "note": "Diagnostic RS ranking only; not Core 12 eligibility/ranking.",
        },
        "weekly": weekly,
        "options": options,
        "publish": publish,
        "rules": rules,
    }


def write_ui_view_model(data_dir: str | Path, output_path: str | Path) -> Path:
    out = build_ui_view_model(data_dir)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(out, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"
    path.write_text(text, encoding="utf-8")
    return path
