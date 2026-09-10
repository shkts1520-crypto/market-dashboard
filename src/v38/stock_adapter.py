from __future__ import annotations

import argparse
import json
import math
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

CALCULATION_VERSION = "v38-stock-adapter-1.1.0"
RS_SCHEMA_VERSION = "v38.rs.1"
BREADTH_SCHEMA_VERSION = "v38.breadth.1"
REQUIRED_OHLCV = {"ticker", "date", "high", "low", "close", "volume"}
RS_PERIODS = (63, 126, 189)
RETURN_PERIODS = (5, 20, 21, 63, 126, 189, 252)
MIN_PRICE = 5.0
MIN_DDV20 = 10_000_000.0


class StockAdapterError(RuntimeError):
    """Raised when a production-safety input contract is not satisfied."""


@dataclass(frozen=True)
class QualityResult:
    ticker: str
    reasons: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.reasons


def _normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [str(c).strip().lower().replace(" ", "_") for c in out.columns]
    aliases = {
        "symbol": "ticker",
        "datetime": "date",
        "timestamp": "date",
        "as_of_date": "session_date",
        "asof_date": "session_date",
        "effective_date": "effective_from",
        "member": "in_universe",
        "active": "in_universe",
        "complete": "is_complete",
        "completed": "is_complete",
        "split_validated": "split_checked",
    }
    out = out.rename(columns={k: v for k, v in aliases.items() if k in out.columns and v not in out.columns})
    return out


def _parse_bool(v: Any) -> bool | None:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    if isinstance(v, (bool, np.bool_)):
        return bool(v)
    if isinstance(v, (int, np.integer)) and v in (0, 1):
        return bool(v)
    s = str(v).strip().lower()
    if s in {"1", "true", "t", "yes", "y", "complete", "completed", "closed", "final", "ok", "checked"}:
        return True
    if s in {"0", "false", "f", "no", "n", "partial", "forming", "open", "unknown", "unchecked"}:
        return False
    return None


def _date_only(series: pd.Series, label: str) -> pd.Series:
    parsed = pd.to_datetime(series, errors="coerce", utc=True)
    if parsed.isna().any():
        bad = int(parsed.isna().sum())
        raise StockAdapterError(f"{label}: {bad} invalid date/timestamp values")
    return parsed.dt.strftime("%Y-%m-%d")


def load_tabular(path: str | Path) -> pd.DataFrame:
    p = Path(path)
    if not p.exists():
        raise StockAdapterError(f"input not found: {p}")
    suffix = p.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(p)
    if suffix in {".jsonl", ".ndjson"}:
        return pd.read_json(p, lines=True)
    if suffix == ".json":
        obj = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(obj, list):
            return pd.DataFrame(obj)
        if isinstance(obj, dict):
            for key in ("rows", "data", "records"):
                if isinstance(obj.get(key), list):
                    return pd.DataFrame(obj[key])
        raise StockAdapterError(f"unsupported JSON table shape: {p}")
    raise StockAdapterError(f"unsupported input format: {p.suffix}; use csv/json/jsonl")


def resolve_active_universe(universe: pd.DataFrame, session_date: str) -> list[str]:
    """Resolve membership strictly point-in-time.

    Accepted PIT forms:
      1) Snapshot: ticker + session_date/date [+ in_universe], exact target snapshot required.
      2) Interval: ticker + effective_from [+ effective_to]. effective_to is inclusive.
      3) Event log: ticker + effective_from + in_universe; latest event <= target wins.

    A ticker-only current list is intentionally rejected: it is not PIT evidence.
    """
    u = _normalise_columns(universe)
    if "ticker" not in u.columns:
        raise StockAdapterError("universe: ticker column is required")
    u["ticker"] = u["ticker"].astype(str).str.strip().str.upper()
    u = u[u["ticker"] != ""]
    if u.empty:
        raise StockAdapterError("universe: no tickers")

    if "session_date" in u.columns or ("date" in u.columns and "effective_from" not in u.columns):
        dcol = "session_date" if "session_date" in u.columns else "date"
        u[dcol] = _date_only(u[dcol], f"universe.{dcol}")
        snap = u[u[dcol] == session_date].copy()
        if snap.empty:
            raise StockAdapterError(
                f"universe: exact PIT snapshot for {session_date} is missing; refusing current-list/previous-snapshot backfill"
            )
        if "in_universe" in snap.columns:
            flags = snap["in_universe"].map(_parse_bool)
            if flags.isna().any():
                raise StockAdapterError("universe.in_universe contains unparseable values")
            snap = snap[flags == True]  # noqa: E712
        return sorted(snap["ticker"].drop_duplicates().tolist())

    if "effective_from" in u.columns:
        u["effective_from"] = _date_only(u["effective_from"], "universe.effective_from")
        eligible = u[u["effective_from"] <= session_date].copy()
        if eligible.empty:
            raise StockAdapterError(f"universe: no membership evidence effective on/before {session_date}")

        if "in_universe" in eligible.columns:
            eligible["_flag"] = eligible["in_universe"].map(_parse_bool)
            if eligible["_flag"].isna().any():
                raise StockAdapterError("universe.in_universe contains unparseable values")
            latest = (
                eligible.sort_values(["ticker", "effective_from"], kind="mergesort")
                .groupby("ticker", as_index=False, sort=False)
                .tail(1)
            )
            latest = latest[latest["_flag"] == True]  # noqa: E712
            return sorted(latest["ticker"].tolist())

        if "effective_to" in eligible.columns:
            raw_end = eligible["effective_to"]
            blank = raw_end.isna() | raw_end.astype(str).str.strip().isin({"", "none", "null", "nat"})
            end = pd.to_datetime(raw_end.where(~blank), errors="coerce", utc=True)
            invalid_end = (~blank) & end.isna()
            if invalid_end.any():
                raise StockAdapterError("universe.effective_to contains invalid nonblank dates")
            end_s = end.dt.strftime("%Y-%m-%d")
            # Blank means still active. effective_to is inclusive by contract.
            active = eligible[blank | (end_s >= session_date)]
            return sorted(active["ticker"].drop_duplicates().tolist())

        raise StockAdapterError(
            "universe effective_from-only membership is insufficient PIT evidence; require effective_to or in_universe events"
        )

    raise StockAdapterError(
        "universe is not PIT: require session_date/date snapshot or effective_from interval/event fields"
    )


def _prepare_ohlcv(ohlcv: pd.DataFrame) -> pd.DataFrame:
    d = _normalise_columns(ohlcv)
    missing = sorted(REQUIRED_OHLCV - set(d.columns))
    if missing:
        raise StockAdapterError(f"ohlcv missing required columns: {', '.join(missing)}")
    if "is_complete" not in d.columns:
        raise StockAdapterError("ohlcv.is_complete is required; forming bars must never be assumed complete")
    if "split_checked" not in d.columns:
        raise StockAdapterError("ohlcv.split_checked is required; unknown split status must never enter normal data")

    d["ticker"] = d["ticker"].astype(str).str.strip().str.upper()
    d["date"] = _date_only(d["date"], "ohlcv.date")
    for c in ("open", "high", "low", "close", "volume"):
        if c in d.columns:
            d[c] = pd.to_numeric(d[c], errors="coerce")
    d["_complete"] = d["is_complete"].map(_parse_bool)
    d["_split_checked"] = d["split_checked"].map(_parse_bool)
    if "split_anomaly" in d.columns:
        d["_split_anomaly"] = d["split_anomaly"].map(_parse_bool)
    else:
        d["_split_anomaly"] = False
    return d


def _ticker_metrics(group: pd.DataFrame, session_date: str) -> tuple[dict[str, Any], QualityResult]:
    t = str(group["ticker"].iloc[0])
    g = group[group["date"] <= session_date].copy()
    reasons: list[str] = []
    if g.empty:
        return {"ticker": t}, QualityResult(t, ("NO_HISTORY",))

    # Incomplete rows are never used. If a historical date has rows but none is
    # complete, do not bridge over it and pretend the return horizon is intact.
    complete = g[g["_complete"] == True].copy()  # noqa: E712
    if complete.empty or complete["date"].max() != session_date:
        reasons.append("NO_COMPLETED_SESSION_BAR")
    complete_dates = set(complete["date"].tolist())
    unresolved_dates = sorted(set(g.loc[g["_complete"] != True, "date"].tolist()) - complete_dates)  # noqa: E712
    if unresolved_dates:
        # Only unresolved dates within the recent dependency span matter. The raw
        # input has no exchange calendar, so bound by the 253 most recent distinct dates.
        recent_dates = set(sorted(g["date"].unique())[-253:])
        if any(x in recent_dates for x in unresolved_dates):
            reasons.append("INCOMPLETE_BAR_IN_DEPENDENCY")

    if complete.duplicated(subset=["date"]).any():
        reasons.append("DUPLICATE_COMPLETED_DATE")

    complete = complete.sort_values(["date"], kind="mergesort").drop_duplicates("date", keep="last")
    if complete.empty:
        return {"ticker": t}, QualityResult(t, tuple(sorted(set(reasons or ["NO_HISTORY"]))))

    # Current calculations require at most 253 observations (Ret252). Validate that
    # full dependency window rather than silently skipping corrupt rows.
    dep = complete.tail(253)
    finite_cols = [c for c in ("high", "low", "close", "volume") if c in dep.columns]
    if dep[finite_cols].isna().any().any():
        reasons.append("NON_NUMERIC_OHLCV")
    if (dep["close"] <= 0).any():
        reasons.append("CLOSE_NON_POSITIVE")
    if (dep["high"] < dep["low"]).any():
        reasons.append("HIGH_BELOW_LOW")
    if (dep["volume"] < 0).any():
        reasons.append("VOLUME_NEGATIVE")
    if dep["_split_checked"].isna().any() or (~dep["_split_checked"].fillna(False)).any():
        reasons.append("SPLIT_STATUS_UNKNOWN")
    if dep["_split_anomaly"].fillna(False).any():
        reasons.append("SPLIT_ANOMALY")

    # If any dependency is invalid, do not produce apparently-normal metrics.
    if reasons:
        return {"ticker": t}, QualityResult(t, tuple(sorted(set(reasons))))

    close = complete["close"].astype(float)
    high = complete["high"].astype(float)
    volume = complete["volume"].astype(float)
    out: dict[str, Any] = {"ticker": t, "price": float(close.iloc[-1])}

    def sma(n: int) -> float | None:
        return float(close.tail(n).mean()) if len(close) >= n else None

    out["sma20"] = sma(20)
    out["sma50"] = sma(50)
    out["sma200"] = sma(200)
    out["ddv20"] = float((close.tail(20) * volume.tail(20)).mean()) if len(close) >= 20 else None
    for p in RETURN_PERIODS:
        out[f"ret{p}"] = float(close.iloc[-1] / close.iloc[-(p + 1)] - 1.0) if len(close) >= p + 1 else None
    # Final audited V38 definition: 52-week high is the maximum intraday High
    # over the latest 252 completed trading sessions. Fewer than 252 -> null.
    out["high52"] = float(high.tail(252).max()) if len(high) >= 252 else None
    out["dist52"] = (
        float(close.iloc[-1] / out["high52"] - 1.0)
        if out["high52"] is not None and out["high52"] > 0
        else None
    )
    return out, QualityResult(t, ())


def _percentile(values: pd.Series) -> pd.Series:
    # Equal returns receive the same percentile (average rank); deterministic row
    # ordering is ticker-ascending downstream. This avoids arbitrary tie inflation.
    return values.rank(method="average", pct=True) * 100.0


def calculate_stock_outputs(
    ohlcv: pd.DataFrame,
    universe: pd.DataFrame,
    *,
    session_date: str,
    generated_at: str,
    source: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    # Validate target date once and keep exact YYYY-MM-DD in all shards.
    try:
        session_date = pd.Timestamp(session_date).strftime("%Y-%m-%d")
    except Exception as exc:  # pragma: no cover - defensive
        raise StockAdapterError(f"invalid session_date: {session_date}") from exc
    if not generated_at:
        raise StockAdapterError("generated_at is required for deterministic/auditable output")
    if not source:
        raise StockAdapterError("source is required")

    active = resolve_active_universe(universe, session_date)
    if not active:
        raise StockAdapterError(f"universe: zero active tickers at {session_date}")

    d = _prepare_ohlcv(ohlcv)
    d = d[d["ticker"].isin(active)].copy()
    grouped = {t: g for t, g in d.groupby("ticker", sort=False)}

    metrics: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for ticker in active:
        if ticker not in grouped:
            excluded.append({"ticker": ticker, "reasons": ["NO_OHLCV"]})
            metrics.append({"ticker": ticker})
            continue
        m, q = _ticker_metrics(grouped[ticker], session_date)
        metrics.append(m)
        if not q.ok:
            excluded.append({"ticker": ticker, "reasons": list(q.reasons)})

    frame = pd.DataFrame(metrics).set_index("ticker", drop=False)
    quality_ok = frame["price"].notna() if "price" in frame.columns else pd.Series(False, index=frame.index)
    observed_current = int(quality_ok.sum())
    active_count = len(active)
    data_coverage = observed_current / active_count if active_count else 0.0

    period_counts: dict[str, int] = {}
    for p in RS_PERIODS:
        ret_col = f"ret{p}"
        base = quality_ok.copy()
        if ret_col not in frame.columns:
            base &= False
        else:
            base &= frame[ret_col].notna()
        base &= frame.get("price", pd.Series(index=frame.index, dtype=float)).ge(MIN_PRICE).fillna(False)
        base &= frame.get("ddv20", pd.Series(index=frame.index, dtype=float)).ge(MIN_DDV20).fillna(False)
        period_counts[str(p)] = int(base.sum())
        frame[f"rs{p}"] = np.nan
        if base.any():
            frame.loc[base, f"rs{p}"] = _percentile(frame.loc[base, ret_col])

    def num(v: Any) -> float | None:
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return None
        return float(v)

    rows: list[dict[str, Any]] = []
    for ticker in active:
        r = frame.loc[ticker]
        if num(r.get("price")) is None:
            continue
        row = {
            "ticker": ticker,
            "price": num(r.get("price")),
            "ddv20": num(r.get("ddv20")),
            "sma50": num(r.get("sma50")),
            "sma200": num(r.get("sma200")),
            "ret20": num(r.get("ret20")),
            "high52": num(r.get("high52")),
            "dist52": num(r.get("dist52")),
            "ret63": num(r.get("ret63")),
            "ret126": num(r.get("ret126")),
            "ret189": num(r.get("ret189")),
            "rs63": num(r.get("rs63")),
            "rs126": num(r.get("rs126")),
            "rs189": num(r.get("rs189")),
        }
        rows.append(row)

    rows.sort(
        key=lambda x: (
            -(x["rs189"] if x["rs189"] is not None else -1e100),
            -(x["rs63"] if x["rs63"] is not None else -1e100),
            x["ticker"],
        )
    )

    valid50 = frame["sma50"].notna() & quality_ok if "sma50" in frame.columns else pd.Series(False, index=frame.index)
    above50 = valid50 & (frame["price"] > frame["sma50"])
    valid50_count = int(valid50.sum())
    breadth50 = (100.0 * int(above50.sum()) / valid50_count) if valid50_count else None

    valid200 = frame["sma200"].notna() & quality_ok if "sma200" in frame.columns else pd.Series(False, index=frame.index)
    above200 = valid200 & (frame["price"] > frame["sma200"])
    valid200_count = int(valid200.sum())
    min200 = max(30, int(math.ceil(0.60 * active_count)))
    breadth200 = (100.0 * int(above200.sum()) / valid200_count) if valid200_count >= min200 else None

    common = {
        "session_date": session_date,
        "generated_at": generated_at,
        "source": source,
        "calculation_version": CALCULATION_VERSION,
    }
    rs_out: dict[str, Any] = {
        **common,
        "schema_version": RS_SCHEMA_VERSION,
        "coverage": data_coverage,
        "coverage_detail": {
            "active_universe": active_count,
            "current_valid_ohlcv": observed_current,
            "rs63_universe": period_counts["63"],
            "rs126_universe": period_counts["126"],
            "rs189_universe": period_counts["189"],
        },
        "rules": {
            "price_min": MIN_PRICE,
            "ddv20_min": MIN_DDV20,
            "percentile_method": "average_rank_pct",
            "tie_order": "ticker_asc",
            "pit_universe_required": True,
            "completed_bar_required": True,
            "split_checked_required": True,
        },
        "rows": rows,
        "excluded": sorted(excluded, key=lambda x: x["ticker"]),
    }
    breadth_out: dict[str, Any] = {
        **common,
        "schema_version": BREADTH_SCHEMA_VERSION,
        "coverage": data_coverage,
        "coverage_detail": {
            "active_universe": active_count,
            "current_valid_ohlcv": observed_current,
            "valid_sma50_count": valid50_count,
            "valid_sma200_count": valid200_count,
            "min_sma200_count": min200,
        },
        "breadth50": breadth50,
        "breadth200": breadth200,
        "breadth200_status": "FULL" if breadth200 is not None else "DATA_INCOMPLETE",
        "rules": {
            "missing_sma_excluded_from_denominator": True,
            "breadth200_min_valid": "max(30, ceil(0.60*active_universe))",
            "pit_universe_required": True,
        },
        "excluded": sorted(excluded, key=lambda x: x["ticker"]),
    }
    return rs_out, breadth_out


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


def calculate_from_files(
    ohlcv_path: str | Path,
    universe_path: str | Path,
    output_dir: str | Path,
    *,
    session_date: str,
    generated_at: str,
    source: str,
) -> tuple[Path, Path]:
    rs, breadth = calculate_stock_outputs(
        load_tabular(ohlcv_path),
        load_tabular(universe_path),
        session_date=session_date,
        generated_at=generated_at,
        source=source,
    )
    out = Path(output_dir)
    rs_path = out / "rs.json"
    breadth_path = out / "breadth.json"
    _atomic_json(rs_path, rs)
    _atomic_json(breadth_path, breadth)
    return rs_path, breadth_path


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Calculate V38 stock RS and breadth from PIT inputs")
    p.add_argument("--ohlcv", required=True)
    p.add_argument("--universe", required=True)
    p.add_argument("--output-dir", default="data")
    p.add_argument("--session-date", required=True)
    p.add_argument("--generated-at", required=True)
    p.add_argument("--source", required=True)
    return p


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    rs_path, breadth_path = calculate_from_files(
        args.ohlcv,
        args.universe,
        args.output_dir,
        session_date=args.session_date,
        generated_at=args.generated_at,
        source=args.source,
    )
    print(rs_path)
    print(breadth_path)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
