from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

CALCULATION_VERSION = "v38-ui-view-model-1.1.0"
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

    for symbol, label in (
        ("QQQ", "QQQ"),
        ("TQQQ", "TQQQ"),
        ("^VIX", "VIX"),
        ("NQ=F", "NQ"),
        ("SPY", "SPY"),
    ):
        daily_metrics.append(
            _latest_series_metric(
                market_inputs,
                symbol=symbol,
                label=label,
                session=session,
            )
        )

    rs_status, rs_reason = _status(rs, session)
    rs_rows: list[dict[str, Any]] = []
    if rs_status == READY and rs is not None and isinstance(rs.get("rows"), list):
        for rank, raw in enumerate(rs["rows"][:24], start=1):
            if not isinstance(raw, dict):
                continue
            ticker = str(raw.get("ticker") or "").strip().upper()
            if not ticker:
                continue
            price = _finite(raw.get("price"))
            rs189 = _finite(raw.get("rs189"))
            rs63 = _finite(raw.get("rs63"))
            ddv20 = _finite(raw.get("ddv20"))
            rs_rows.append(
                {
                    "rank": rank,
                    "ticker": ticker,
                    "price": price,
                    "price_display": f"{price:,.2f}" if price is not None else "—",
                    "rs189": rs189,
                    "rs189_display": f"{rs189:.1f}" if rs189 is not None else "—",
                    "rs63": rs63,
                    "rs63_display": f"{rs63:.1f}" if rs63 is not None else "—",
                    "ddv20": ddv20,
                    "ddv20_display": f"${ddv20 / 1_000_000.0:.1f}M" if ddv20 is not None else "—",
                }
            )
    elif rs_status == READY:
        rs_status = DATA_REQUIRED
        rs_reason = "ROWS_MISSING"

    coverage = _finite(rs.get("coverage")) if rs else None
    breadth_coverage = _finite(breadth.get("coverage")) if breadth else None

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
            "status": DATA_REQUIRED if any(x["status"] != READY for x in daily_metrics) else READY,
            "metrics": daily_metrics,
            "stock_data_coverage": coverage,
            "breadth_coverage": breadth_coverage,
        },
        "positions": positions,
        "core12": core12,
        "rotation": rotation,
        "rs": {
            "status": rs_status,
            "reason": rs_reason,
            "title": "RS189 Top 24",
            "rows": rs_rows,
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
