from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .freshness import atomic_write_json


def _load(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return obj if isinstance(obj, dict) else {}


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number and abs(number) != float("inf") else None


def append_current_from_rs(data_dir: str | Path, *, session: str, generated_at: str) -> tuple[Path | None, Path | None]:
    """Append the exact current observed RS63 Top20 and parabolic rate.

    This is deliberately lightweight: once the historical seed exists, subsequent
    sessions use the authoritative current rs.json rather than redownloading the
    entire universe history.
    """
    root = Path(data_dir)
    rs = _load(root / "rs.json")
    if rs.get("session_date") != session or not isinstance(rs.get("rows"), list):
        return None, None
    rows = [row for row in rs["rows"] if isinstance(row, dict)]

    reversal_path = root / "history" / "reversal_rs63_2y.json"
    reversal = _load(reversal_path)
    reversal_out: Path | None = None
    if isinstance(reversal.get("series"), list):
        ranked = [
            row for row in rows
            if str(row.get("ticker") or "").strip() and _finite(row.get("rs63")) is not None
        ]
        ranked.sort(key=lambda row: (-float(row["rs63"]), str(row.get("ticker") or "")))
        top20 = [
            {
                "ticker": str(row.get("ticker") or "").strip().upper(),
                "rs63": float(row["rs63"]),
                "ret63": _finite(row.get("ret63")),
            }
            for row in ranked[:20]
        ]
        if len(top20) == 20:
            by_date = {
                str(row.get("date")): dict(row)
                for row in reversal["series"]
                if isinstance(row, dict) and row.get("date")
            }
            by_date[session] = {"date": session, "pool_count": len(ranked), "top20": top20}
            reversal["series"] = [by_date[day] for day in sorted(by_date)][-756:]
            reversal["session_date"] = session
            reversal["generated_at"] = generated_at
            reversal["status"] = "READY"
            reversal["coverage"] = 1.0
            atomic_write_json(reversal_path, reversal)
            reversal_out = reversal_path

    parabolic_path = root / "history" / "parabolic_rate_2y.json"
    parabolic = _load(parabolic_path)
    parabolic_out: Path | None = None
    if isinstance(parabolic.get("series"), list):
        valid = [
            row for row in rows
            if _finite(row.get("price")) is not None and _finite(row.get("sma200")) is not None and float(row["sma200"]) > 0
        ]
        if valid:
            count = sum(float(row["price"]) >= float(row["sma200"]) * 1.45 for row in valid)
            current = {
                "date": session,
                "value": 100.0 * count / len(valid),
                "count": int(count),
                "denominator": len(valid),
            }
            by_date = {
                str(row.get("date")): dict(row)
                for row in parabolic["series"]
                if isinstance(row, dict) and row.get("date")
            }
            by_date[session] = current
            parabolic["series"] = [by_date[day] for day in sorted(by_date)][-756:]
            parabolic["session_date"] = session
            parabolic["generated_at"] = generated_at
            parabolic["status"] = "READY" if len(parabolic["series"]) >= 60 else "DATA_REQUIRED"
            parabolic["coverage"] = 1.0 if parabolic["status"] == "READY" else 0.0
            atomic_write_json(parabolic_path, parabolic)
            parabolic_out = parabolic_path

    return reversal_out, parabolic_out
