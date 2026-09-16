#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def finite(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        value = float(value)
        return value if math.isfinite(value) else None
    return None


def f1_display(data_dir: Path, session: str, f123: dict[str, Any]) -> dict[str, Any]:
    strict = f123.get("f1") if isinstance(f123.get("f1"), dict) else {}
    strict_value = finite(strict.get("value"))
    if strict_value is not None:
        return {
            "status": "READY",
            "value": strict_value,
            "display_only": False,
            "source": "data/f123.json:f1",
            "coverage": finite(strict.get("coverage")),
            "drop_count": strict.get("drop_count"),
            "denominator": strict.get("observable_count") or strict.get("old_top24_count"),
        }

    history = read_json(data_dir / "history" / "rs_history.json")
    snapshots = history.get("snapshots") if isinstance(history, dict) else None
    if not isinstance(snapshots, list):
        return {"status": "DATA_REQUIRED", "value": None, "display_only": True, "source": "rs_history", "reason": "RS_HISTORY_MISSING"}

    rows = [row for row in snapshots if isinstance(row, dict) and isinstance(row.get("date"), str) and row["date"] <= session]
    rows.sort(key=lambda row: row["date"])
    current_index = next((i for i in range(len(rows) - 1, -1, -1) if rows[i].get("date") == session), len(rows) - 1)
    if current_index < 20:
        return {"status": "DATA_REQUIRED", "value": None, "display_only": True, "source": "rs_history", "reason": "20_SESSION_BASELINE_MISSING"}

    current = rows[current_index]
    prior = rows[current_index - 20]
    cur_rows = ((current.get("windows") or {}).get("189") or [])
    old_rows = ((prior.get("windows") or {}).get("189") or [])
    if not isinstance(cur_rows, list) or not isinstance(old_rows, list):
        return {"status": "DATA_REQUIRED", "value": None, "display_only": True, "source": "rs_history", "reason": "RS189_WINDOWS_MISSING"}

    old_top24 = []
    for row in old_rows:
        if not isinstance(row, dict):
            continue
        rank = finite(row.get("rank"))
        ticker = str(row.get("ticker") or "").strip().upper()
        if ticker and rank is not None and rank <= 24:
            old_top24.append(ticker)
    current_rank = {}
    for row in cur_rows:
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker") or "").strip().upper()
        rank = finite(row.get("rank"))
        if ticker and rank is not None:
            current_rank[ticker] = int(rank)

    observable = [ticker for ticker in old_top24 if ticker in current_rank]
    dropped = [ticker for ticker in observable if current_rank[ticker] > 36]
    denominator = len(observable)
    value = (len(dropped) / denominator) if denominator else None
    coverage = (denominator / len(old_top24)) if old_top24 else None
    return {
        "status": "READY" if value is not None and (coverage or 0) >= 0.70 else "DATA_REQUIRED",
        "value": value,
        "display_only": True,
        "source": "data/history/rs_history.json:20-session current-universe rank reconstruction",
        "reason": "STRICT_PIT_UNAVAILABLE_DISPLAY_ONLY",
        "baseline_session": prior.get("date"),
        "current_session": current.get("date"),
        "old_top24_count": len(old_top24),
        "denominator": denominator,
        "drop_count": len(dropped),
        "coverage": coverage,
        "dropped": dropped,
    }


def find_vix_rows(node: Any) -> list[dict[str, Any]]:
    best: list[dict[str, Any]] = []

    def walk(value: Any) -> None:
        nonlocal best
        if isinstance(value, list):
            candidates = [row for row in value if isinstance(row, dict) and isinstance(row.get("date"), str)]
            if len(candidates) > len(best) and any(
                finite(row.get("vix")) is not None or finite(row.get("close")) is not None or finite(row.get("value")) is not None
                for row in candidates[:20]
            ):
                best = candidates
            for item in value[:5]:
                if isinstance(item, (dict, list)):
                    walk(item)
        elif isinstance(value, dict):
            for child in value.values():
                if isinstance(child, (dict, list)):
                    walk(child)

    walk(node)
    return best


def lwma(values: list[float | None], window: int) -> list[float | None]:
    weights = list(range(1, window + 1))
    denom = float(sum(weights))
    out: list[float | None] = []
    for i in range(len(values)):
        if i + 1 < window:
            out.append(None)
            continue
        part = values[i + 1 - window:i + 1]
        if any(value is None for value in part):
            out.append(None)
            continue
        out.append(sum(float(value) * weight for value, weight in zip(part, weights)) / denom)
    return out


def vix_display(data_dir: Path) -> dict[str, Any]:
    cycle = read_json(data_dir / "history" / "vix_fear_cycle.json")
    if not isinstance(cycle, dict):
        return {"status": "DATA_REQUIRED", "current": {}, "rows": []}
    current = cycle.get("current") if isinstance(cycle.get("current"), dict) else {}
    rows = find_vix_rows(cycle)

    if len(rows) < 20:
        market = read_json(data_dir / "market_inputs.json")
        series = market.get("series") if isinstance(market, dict) else None
        raw = series.get("^VIX") if isinstance(series, dict) else None
        if isinstance(raw, list):
            rows = [row for row in raw if isinstance(row, dict) and isinstance(row.get("date"), str)]

    normalized: list[dict[str, Any]] = []
    for row in rows:
        value = finite(row.get("vix"))
        if value is None:
            value = finite(row.get("close"))
        if value is None:
            value = finite(row.get("value"))
        if value is None:
            continue
        normalized.append({"date": row["date"], "vix": value})
    normalized.sort(key=lambda row: row["date"])
    normalized = normalized[-2520:]
    values = [finite(row.get("vix")) for row in normalized]
    w5 = lwma(values, 5)
    w10 = lwma(values, 10)
    for index, row in enumerate(normalized):
        row["lwma5"] = w5[index]
        row["lwma10"] = w10[index]

    state = cycle.get("state") or cycle.get("phase") or cycle.get("status") or "NORMAL"
    return {
        "status": "READY" if normalized else "DATA_REQUIRED",
        "state": str(state),
        "session_date": cycle.get("session_date"),
        "current": {key: finite(current.get(key)) for key in ("vix", "high", "lwma5", "lwma10", "plus1_sigma", "plus2_sigma")},
        "distribution": cycle.get("distribution") if isinstance(cycle.get("distribution"), dict) else {},
        "rows": normalized,
        "source": "data/history/vix_fear_cycle.json + data/market_inputs.json fallback",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="data")
    args = parser.parse_args()
    data_dir = Path(args.data_dir)
    f123 = read_json(data_dir / "f123.json")
    f123 = f123 if isinstance(f123, dict) else {}
    session = str(f123.get("session_date") or "")
    output = {
        "schema_version": "v38.py_source_display.1",
        "session_date": session,
        "ui_source": "build_dashboard(2).py",
        "trading_logic_changed": False,
        "f1_display": f1_display(data_dir, session, f123) if session else {"status": "DATA_REQUIRED", "value": None},
        "f2": f123.get("f2") if isinstance(f123.get("f2"), dict) else {},
        "f3": (f123.get("display_overrides") or {}).get("f3") if isinstance((f123.get("display_overrides") or {}).get("f3"), dict) else (f123.get("f3") or {}),
        "vix_fear_cycle": vix_display(data_dir),
    }
    target = data_dir / "py_source_display.json"
    target.write_text(json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": "OK", "output": str(target), "session_date": session, "f1": output["f1_display"].get("value"), "vix_rows": len(output["vix_fear_cycle"].get("rows") or [])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
