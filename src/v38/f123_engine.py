from __future__ import annotations

import json
import math
import os
import tempfile
from pathlib import Path
from typing import Any

CALCULATION_VERSION = "v38-f123-engine-1.0.0"
SCHEMA_VERSION = "v38.f123.1"

PRICE_MIN = 5.0
DDV20_MIN = 10_000_000.0
LEADER_RS = 85.0
TOP_N = 24
DROP_RANK = 36
F1_COV_FULL = 0.90
F1_COV_MIN = 0.70


class F123Error(RuntimeError):
    """Raised when an F1/F2/F3 input contract is violated."""


def load_json(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise F123Error(f"input not found: {p}")
    obj = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise F123Error(f"expected JSON object: {p}")
    return obj


def _finite(v: Any) -> float | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        x = float(v)
        if math.isfinite(x):
            return x
    return None


def _session(obj: dict[str, Any], label: str) -> str:
    s = obj.get("session_date")
    if not isinstance(s, str) or len(s) != 10:
        raise F123Error(f"{label}.session_date is required")
    return s


def _base_pool_row(row: dict[str, Any]) -> bool:
    price = _finite(row.get("price"))
    ddv20 = _finite(row.get("ddv20"))
    sma50 = _finite(row.get("sma50"))
    sma200 = _finite(row.get("sma200"))
    rs189 = _finite(row.get("rs189"))
    return bool(
        price is not None
        and price >= PRICE_MIN
        and ddv20 is not None
        and ddv20 >= DDV20_MIN
        and sma50 is not None
        and sma200 is not None
        and sma50 > sma200
        and rs189 is not None
    )


def _observable_f1(row: dict[str, Any] | None) -> bool:
    if row is None:
        return False
    # Current observation is usable only when the inputs needed to evaluate the
    # historical leader today are all present. Missing/invalid names are UNKNOWN,
    # never silently counted as drops.
    return all(
        _finite(row.get(k)) is not None
        for k in ("price", "ddv20", "sma50", "sma200", "rs189")
    )


def _rank_pool(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    pool = [r for r in rows if _base_pool_row(r)]
    pool.sort(key=lambda r: (-float(r["rs189"]), str(r.get("ticker", ""))))
    ranks = {str(r["ticker"]): i + 1 for i, r in enumerate(pool)}
    return pool, ranks


def _severity(value: float | None, warn: float, severe: float) -> str:
    if value is None:
        return "NO_JUDGMENT"
    if value >= severe:
        return "SEVERE"
    if value >= warn:
        return "CAUTION"
    return "NORMAL"


def _old_top24_tickers(old_top24: dict[str, Any] | None) -> tuple[list[str], dict[str, Any]]:
    if old_top24 is None:
        return [], {"status": "DATA_REQUIRED", "reason": "PIT_OLD_TOP24_MISSING"}
    if old_top24.get("lag_sessions") != 20 or old_top24.get("pit_frozen") is not True:
        return [], {
            "status": "DATA_REQUIRED",
            "reason": "PIT_OLD_TOP24_PROVENANCE_UNVERIFIED",
            "required": {"lag_sessions": 20, "pit_frozen": True},
        }
    rows = old_top24.get("rows")
    if not isinstance(rows, list):
        raise F123Error("old_top24.rows must be a list")
    tickers: list[str] = []
    seen: set[str] = set()
    for row in rows:
        if isinstance(row, str):
            t = row.strip().upper()
        elif isinstance(row, dict):
            t = str(row.get("ticker", "")).strip().upper()
        else:
            continue
        if t and t not in seen:
            tickers.append(t)
            seen.add(t)
    if not tickers:
        return [], {"status": "DATA_REQUIRED", "reason": "PIT_OLD_TOP24_EMPTY"}
    if len(tickers) > TOP_N:
        raise F123Error("old_top24 contains more than 24 unique tickers")
    return tickers, {
        "status": "OK",
        "session_date": old_top24.get("session_date"),
        "source": old_top24.get("source"),
        "calculation_version": old_top24.get("calculation_version"),
        "count": len(tickers),
    }


def calculate_f123(
    rs: dict[str, Any],
    *,
    generated_at: str,
    old_top24: dict[str, Any] | None = None,
) -> dict[str, Any]:
    session_date = _session(rs, "rs")
    if not generated_at:
        raise F123Error("generated_at is required")
    raw_rows = rs.get("rows")
    if not isinstance(raw_rows, list):
        raise F123Error("rs.rows must be a list")

    rows: list[dict[str, Any]] = []
    by_ticker: dict[str, dict[str, Any]] = {}
    for raw in raw_rows:
        if not isinstance(raw, dict):
            continue
        t = str(raw.get("ticker", "")).strip().upper()
        if not t:
            continue
        row = dict(raw)
        row["ticker"] = t
        rows.append(row)
        by_ticker[t] = row

    pool, rank_now = _rank_pool(rows)

    # F1: requires an explicit PIT-frozen old Top24 artifact. We intentionally do
    # not synthesize it from today's universe or from a previous static snapshot.
    old_names, old_meta = _old_top24_tickers(old_top24)
    if not old_names:
        f1 = {
            "value": None,
            "status": "DATA_REQUIRED",
            "severity": "NO_JUDGMENT",
            "coverage": None,
            "old_top24_count": 0,
            "observable_count": 0,
            "drop_count": 0,
            "rank_drop_count": 0,
            "eligibility_drop_count": 0,
            "unknown_count": 0,
            "dropped": [],
            "unknown": [],
            "dependency": old_meta,
        }
    else:
        observable: list[str] = []
        unknown: list[str] = []
        rank_drop: list[str] = []
        elig_drop: list[str] = []
        for t in old_names:
            current = by_ticker.get(t)
            if not _observable_f1(current):
                unknown.append(t)
                continue
            observable.append(t)
            if not _base_pool_row(current):
                elig_drop.append(t)
            elif rank_now.get(t, 10**9) > DROP_RANK:
                rank_drop.append(t)
        dropped = sorted(set(rank_drop) | set(elig_drop), key=lambda t: (rank_now.get(t, 10**9), t))
        coverage = len(observable) / len(old_names) if old_names else None
        if coverage is None or coverage < F1_COV_MIN or not observable:
            value = None
            status = "DATA_INCOMPLETE"
        else:
            value = len(dropped) / len(observable)
            status = "FULL" if coverage >= F1_COV_FULL else "PARTIAL"
        f1 = {
            "value": value,
            "status": status,
            "severity": _severity(value, 0.20, 0.30),
            "coverage": coverage,
            "old_top24_count": len(old_names),
            "observable_count": len(observable),
            "drop_count": len(dropped),
            "rank_drop_count": len(rank_drop),
            "eligibility_drop_count": len(elig_drop),
            "unknown_count": len(unknown),
            "dropped": dropped[:8],
            "unknown": sorted(unknown),
            "dependency": old_meta,
        }

    # F2: current base-pool RS189 Top24; names without RS63 are excluded from the
    # denominator rather than interpreted as weak.
    top24 = pool[:TOP_N]
    f2_obs = [r for r in top24 if _finite(r.get("rs63")) is not None]
    f2_weak = [r for r in f2_obs if float(r["rs63"]) < LEADER_RS]
    f2_value = len(f2_weak) / len(f2_obs) if f2_obs else None
    f2 = {
        "value": f2_value,
        "status": "OK" if f2_value is not None else "DATA_INCOMPLETE",
        "severity": _severity(f2_value, 0.25, 0.40),
        "top24_count": len(top24),
        "observable_count": len(f2_obs),
        "weak_count": len(f2_weak),
        "weak": [str(r["ticker"]) for r in sorted(f2_weak, key=lambda r: rank_now[str(r["ticker"])])][:8],
    }

    # F3: base pool -> RS189>=85 and Close>SMA200. Ret20/Dist52 missing does not
    # turn into False/zero; it makes that queue member unobservable for a valid
    # F3 value, because the break condition cannot be evaluated safely.
    queue = [
        r for r in pool
        if float(r["rs189"]) >= LEADER_RS
        and _finite(r.get("price")) is not None
        and _finite(r.get("sma200")) is not None
        and float(r["price"]) > float(r["sma200"])
    ]
    queue_obs = [r for r in queue if _finite(r.get("ret20")) is not None and _finite(r.get("dist52")) is not None]
    broken = [r for r in queue_obs if float(r["ret20"]) <= 0.0 or float(r["dist52"]) < -0.15]
    if len(queue) < 3:
        f3_value = None
        f3_status = "NO_JUDGMENT"
    elif len(queue_obs) != len(queue):
        f3_value = None
        f3_status = "DATA_INCOMPLETE"
    else:
        f3_value = len(broken) / len(queue)
        f3_status = "OK"
    broken_sorted = sorted(
        broken,
        key=lambda r: (float(r["dist52"]), str(r["ticker"])),
    )
    f3 = {
        "value": f3_value,
        "status": f3_status,
        "severity": _severity(f3_value, 0.40, 0.60),
        "queue_count": len(queue),
        "observable_count": len(queue_obs),
        "break_count": len(broken),
        "broken": [str(r["ticker"]) for r in broken_sorted[:8]],
    }

    return {
        "session_date": session_date,
        "generated_at": generated_at,
        "coverage": rs.get("coverage"),
        "source": "derived:rs+pit_old_top24",
        "schema_version": SCHEMA_VERSION,
        "calculation_version": CALCULATION_VERSION,
        "base_pool_count": len(pool),
        "f1": f1,
        "f2": f2,
        "f3": f3,
        "rules": {
            "base_pool": "SMA50>SMA200 AND Price>=5 AND DDV20>=10M AND RS189 observable",
            "f1": "20-session-ago PIT Top24; denominator=current observable old Top24; drop=current base-pool loss OR current RS189 rank>36; missing is unknown",
            "f1_coverage": ">=90% FULL; 70%-<90% PARTIAL; <70% DATA_INCOMPLETE",
            "f2": "current base-pool RS189 Top24; fraction of RS63-observable names with RS63<85",
            "f3": "queue=base pool AND RS189>=85 AND Close>SMA200; break=Ret20<=0 OR Dist52<-15%; queue<3 no judgment",
            "f123_normal_stock_hard_gate": False,
        },
    }


def _atomic_json(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def calculate_f123_from_files(
    rs_path: str | Path,
    output_path: str | Path,
    *,
    generated_at: str,
    old_top24_path: str | Path | None = None,
) -> Path:
    obj = calculate_f123(
        load_json(rs_path),
        generated_at=generated_at,
        old_top24=load_json(old_top24_path) if old_top24_path else None,
    )
    out = Path(output_path)
    _atomic_json(out, obj)
    return out
