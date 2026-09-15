from __future__ import annotations

import json
import math
from pathlib import Path
from statistics import median
from typing import Any

READY = "READY"
DATA_REQUIRED = "DATA_REQUIRED"
CALCULATION_VERSION = "v38-movers-display-1.0.0"


def _finite(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        x = float(value)
        return x if math.isfinite(x) else None
    return None


def _read(path: Path) -> dict[str, Any] | None:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return obj if isinstance(obj, dict) else None


def _spark_return(raw: dict[str, Any], lag: int) -> float | None:
    points = raw.get("sparkline")
    if not isinstance(points, list):
        return None
    closes: list[float] = []
    for point in points:
        if not isinstance(point, dict):
            continue
        value = _finite(point.get("close"))
        if value is not None and value > 0:
            closes.append(value)
    if len(closes) <= lag:
        return None
    previous = closes[-(lag + 1)]
    current = closes[-1]
    return current / previous - 1.0 if previous > 0 else None


def _compact(raw: dict[str, Any]) -> dict[str, Any] | None:
    ticker = str(raw.get("ticker") or "").strip().upper()
    if not ticker:
        return None
    ret1 = _finite(raw.get("ret1"))
    ret5 = _spark_return(raw, 5)
    ret20 = _finite(raw.get("ret20"))
    if ret20 is None:
        ret20 = _spark_return(raw, 20)
    return {
        "ticker": ticker,
        "name": str(raw.get("name") or ""),
        "sector": str(raw.get("sector") or ""),
        "industry": str(raw.get("industry") or ""),
        "rs189": _finite(raw.get("rs189")),
        "ddv20": _finite(raw.get("ddv20")),
        "ret1": ret1,
        "ret5": ret5,
        "ret20": ret20,
    }


def _summary(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    values = [float(row[key]) for row in rows if _finite(row.get(key)) is not None]
    if not values:
        return {"count": 0, "median": None, "advancing_pct": None, "up3_count": 0, "down3_count": 0}
    return {
        "count": len(values),
        "median": median(values),
        "advancing_pct": sum(1 for value in values if value > 0) / len(values),
        "up3_count": sum(1 for value in values if value >= 0.03),
        "down3_count": sum(1 for value in values if value <= -0.03),
    }


def _rank(rows: list[dict[str, Any]], key: str, *, reverse: bool) -> list[dict[str, Any]]:
    eligible = [row for row in rows if _finite(row.get(key)) is not None]
    if reverse:
        eligible.sort(key=lambda row: (-float(row[key]), row["ticker"]))
    else:
        eligible.sort(key=lambda row: (float(row[key]), row["ticker"]))
    return eligible[:20]


def _three_window(periods: dict[str, dict[str, Any]], side: str) -> list[dict[str, Any]]:
    lists = [periods[key][side] for key in ("1d", "1w", "1m")]
    if not all(lists):
        return []
    sets = [{row["ticker"] for row in rows} for rows in lists]
    common = set.intersection(*sets)
    if not common:
        return []
    rank_maps = [{row["ticker"]: index for index, row in enumerate(rows, start=1)} for rows in lists]
    by_ticker = {row["ticker"]: row for rows in lists for row in rows}
    return [
        by_ticker[ticker]
        for ticker in sorted(common, key=lambda ticker: (sum(rank_map[ticker] for rank_map in rank_maps), ticker))
    ]


def attach_movers_ui(view: dict[str, Any], data_dir: str | Path) -> dict[str, Any]:
    """Attach source-shaped Movers display data without changing any trading contract."""
    root = Path(data_dir)
    rs = _read(root / "rs.json")
    session = str(view.get("session_date") or "")
    if rs is None or rs.get("session_date") != session or rs.get("status") not in {None, READY}:
        view["movers"] = {
            "status": DATA_REQUIRED,
            "reason": "CURRENT_SESSION_RS_ROWS_MISSING",
            "title": "Movers",
            "calculation_version": CALCULATION_VERSION,
        }
        return view

    source_rows = rs.get("rows") if isinstance(rs.get("rows"), list) else []
    rows = [item for raw in source_rows if isinstance(raw, dict) for item in [_compact(raw)] if item is not None]
    rows = [row for row in rows if any(_finite(row.get(key)) is not None for key in ("ret1", "ret5", "ret20"))]
    specs = {"1d": ("前日", "ret1"), "1w": ("1週間", "ret5"), "1m": ("1ヶ月", "ret20")}
    periods: dict[str, dict[str, Any]] = {}
    summaries: dict[str, dict[str, Any]] = {}
    for period, (label, key) in specs.items():
        gainers = _rank(rows, key, reverse=True)
        losers = _rank(rows, key, reverse=False)
        periods[period] = {"label": label, "key": key, "gainers": gainers, "losers": losers}
        summaries[period] = {"label": label, **_summary(rows, key)}

    ready = all(summaries[key]["count"] > 0 for key in specs)
    view["movers"] = {
        "status": READY if ready else DATA_REQUIRED,
        "reason": "CURRENT_SESSION_FULL_UNIVERSE_RETURNS" if ready else "RETURN_WINDOWS_INCOMPLETE",
        "title": "Movers",
        "source": "rs.json full universe; 1d=ret1, 1w=5-session sparkline return, 1m=ret20",
        "calculation_version": CALCULATION_VERSION,
        "universe_count": len(rows),
        "summary": summaries,
        "periods": periods,
        "three_window": {
            "gainers": _three_window(periods, "gainers"),
            "losers": _three_window(periods, "losers"),
        },
        "gainers": periods["1d"]["gainers"][:10],
        "losers": periods["1d"]["losers"][:10],
        "rows": [],
    }
    return view
