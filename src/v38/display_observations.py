from __future__ import annotations

import csv
import io
import json
import math
import re
import time
import urllib.request
from bisect import bisect_right
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .freshness import atomic_write_json
from .live_acquisition import select_yfinance_symbol_frame

CALCULATION_VERSION = "v38-display-observations-1.0.0"
SCHEMA_VERSION = "v38.display_observations.1"
NQSAR_HISTORY_SCHEMA = "v38.nqsar_observed_history.1"
VALID_NQSAR = {"Blue", "Green", "Yellow", "Red"}
FTD_PCT = 0.0125
SENTIMENT_TICKERS = ("TQQQ", "SQQQ", "SOXL", "SOXS", "^SKEW")
FRED_SERIES = ("WALCL", "RRPONTSYD", "WTREGEN")


def _load(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return obj if isinstance(obj, dict) else {}


def _finite(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _http_bytes(url: str, *, timeout: float = 20.0, attempts: int = 3) -> bytes:
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (v38-market-dashboard)",
                    "Accept": "application/json,text/csv,text/plain,*/*",
                },
            )
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read()
        except Exception as exc:
            last = exc
            if attempt + 1 < attempts:
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"external display source failed: {url}: {last}")


def _roll_pct(series: pd.Series, *, win: int = 504, minp: int = 120) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce").dropna().sort_index()
    if s.empty:
        return pd.Series(dtype=float)
    return s.rolling(win, min_periods=minp).apply(
        lambda values: float(pd.Series(values).rank(pct=True).iloc[-1] * 100.0),
        raw=False,
    )


def _fred_series(series_id: str, asof: str) -> list[tuple[pd.Timestamp, float]]:
    raw = _http_bytes(
        f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}",
        timeout=25.0,
    ).decode("utf-8", "ignore")
    rows: list[tuple[pd.Timestamp, float]] = []
    cutoff = pd.Timestamp(asof).normalize()
    for record in csv.DictReader(io.StringIO(raw)):
        date_text = record.get("DATE") or record.get("observation_date")
        value = record.get(series_id)
        if not date_text or value in (None, "", "."):
            continue
        try:
            day = pd.Timestamp(date_text).normalize()
            number = float(value)
        except Exception:
            continue
        if day <= cutoff and math.isfinite(number):
            rows.append((day, number))
    rows.sort(key=lambda item: item[0])
    return rows


def build_net_liquidity(
    fred: dict[str, list[tuple[pd.Timestamp, float]]],
    *,
    asof: str,
) -> dict[str, Any]:
    """Old source contract: WALCL/1e6 - RRPONTSYD/1e3 - WTREGEN/1e6.

    Components are as-of aligned to each WALCL observation. Missing RRP/TGA is
    never treated as zero.
    """
    cutoff = pd.Timestamp(asof).normalize()

    def mapped(series_id: str, divisor: float) -> list[tuple[pd.Timestamp, float]]:
        return [
            (day, value / divisor)
            for day, value in fred.get(series_id, [])
            if day <= cutoff and math.isfinite(value)
        ]

    walcl = mapped("WALCL", 1e6)
    rrp = mapped("RRPONTSYD", 1e3)
    tga = mapped("WTREGEN", 1e6)
    if len(walcl) < 4:
        return {"status": "DATA_REQUIRED", "reason": "WALCL_HISTORY_TOO_SHORT"}

    r_dates = [day for day, _ in rrp]
    r_values = [value for _, value in rrp]
    t_dates = [day for day, _ in tga]
    t_values = [value for _, value in tga]

    def asof_value(day: pd.Timestamp, dates: list[pd.Timestamp], values: list[float]) -> float | None:
        index = bisect_right(dates, day) - 1
        return values[index] if index >= 0 else None

    values: list[dict[str, Any]] = []
    for day, assets in walcl:
        reverse_repo = asof_value(day, r_dates, r_values)
        treasury = asof_value(day, t_dates, t_values)
        if reverse_repo is None or treasury is None:
            continue
        net = assets - reverse_repo - treasury
        if math.isfinite(net):
            values.append({
                "date": day.strftime("%Y-%m-%d"),
                "value_t": net,
                "walcl_t": assets,
                "rrp_t": reverse_repo,
                "tga_t": treasury,
            })

    if len(values) < 4:
        return {"status": "DATA_REQUIRED", "reason": "ALIGNED_FRED_HISTORY_TOO_SHORT"}
    current = float(values[-1]["value_t"])
    if not 1.0 < current < 15.0:
        return {"status": "DATA_REQUIRED", "reason": "NET_LIQUIDITY_UNIT_SANITY_FAILED"}
    prior4 = float(values[-5]["value_t"]) if len(values) >= 5 else float(values[0]["value_t"])
    prior13 = float(values[-14]["value_t"]) if len(values) >= 14 else float(values[0]["value_t"])
    return {
        "status": "READY",
        "current_t": current,
        "change_4w_t": current - prior4,
        "change_13w_t": current - prior13,
        "latest_observation": values[-1]["date"],
        "series": values[-260:],
        "formula": "WALCL/1e6 - RRPONTSYD/1e3 - WTREGEN/1e6",
        "units": "USD trillions",
        "trading_gate_eligible": False,
    }


def fetch_net_liquidity(*, session: str) -> dict[str, Any]:
    series = {series_id: _fred_series(series_id, session) for series_id in FRED_SERIES}
    return build_net_liquidity(series, asof=session)


def _cnn_points(raw: Any, *, session: str) -> pd.Series:
    cutoff = pd.Timestamp(session).normalize()
    values: dict[pd.Timestamp, float] = {}
    if isinstance(raw, dict):
        raw = raw.get("data") or raw.get("values") or raw.get("historical") or []
    if not isinstance(raw, list):
        return pd.Series(dtype=float)
    for item in raw:
        if not isinstance(item, dict):
            continue
        number = _finite(item.get("y") if item.get("y") is not None else item.get("value"))
        stamp = item.get("x") if item.get("x") is not None else item.get("date")
        if number is None or stamp is None:
            continue
        try:
            if isinstance(stamp, (int, float)):
                day = pd.to_datetime(stamp, unit="ms", utc=True).tz_convert(None).normalize()
            else:
                day = pd.Timestamp(str(stamp)).tz_localize(None).normalize()
        except Exception:
            continue
        if day <= cutoff:
            values[day] = number
    return pd.Series(values, dtype=float).sort_index()


def _fetch_cnn(session: str) -> tuple[pd.Series, pd.Series]:
    try:
        obj = json.loads(
            _http_bytes(
                "https://production.dataviz.cnn.io/index/fearandgreed/graphdata",
                timeout=15.0,
                attempts=2,
            ).decode("utf-8", "ignore")
        )
    except Exception:
        return pd.Series(dtype=float), pd.Series(dtype=float)
    fear_greed = _cnn_points(obj.get("fear_and_greed_historical"), session=session)
    put_call = _cnn_points(obj.get("put_call_options"), session=session)
    return fear_greed, put_call


def _fetch_naaim(session: str) -> pd.Series:
    """Use the old public CSV path only when it is still actually public.

    NAAIM moved current data behind authenticated access in 2026. No delayed or
    guessed value is substituted when the original public CSV is unavailable.
    """
    try:
        page = _http_bytes(
            "https://naaim.org/programs/naaim-exposure-index/",
            timeout=12.0,
            attempts=2,
        ).decode("utf-8", "ignore")
        match = re.search(r'href=["\']([^"\']+\.csv[^"\']*)["\']', page, re.I)
        if not match:
            return pd.Series(dtype=float)
        url = match.group(1)
        if url.startswith("/"):
            url = "https://naaim.org" + url
        raw = _http_bytes(url, timeout=12.0, attempts=2).decode("utf-8", "ignore")
    except Exception:
        return pd.Series(dtype=float)
    cutoff = pd.Timestamp(session).normalize()
    values: dict[pd.Timestamp, float] = {}
    for line in raw.splitlines()[1:]:
        parts = [part.strip() for part in line.split(",")]
        if len(parts) < 2:
            continue
        try:
            day = pd.Timestamp(parts[0]).normalize()
            value = float(parts[1])
        except Exception:
            continue
        if day <= cutoff and math.isfinite(value):
            values[day] = value
    return pd.Series(values, dtype=float).sort_index()


def _download_sentiment_market(session: str) -> dict[str, pd.DataFrame]:
    try:
        import yfinance as yf
    except ImportError:
        return {}
    frames: dict[str, pd.DataFrame] = {}
    raw = pd.DataFrame()
    for attempt in range(3):
        try:
            raw = yf.download(
                list(SENTIMENT_TICKERS),
                period="5y",
                interval="1d",
                progress=False,
                auto_adjust=True,
                group_by="ticker",
                threads=True,
                timeout=30,
            )
            if not raw.empty:
                break
        except Exception:
            pass
        time.sleep(1.5 * (attempt + 1))
    cutoff = pd.Timestamp(session)
    for symbol in SENTIMENT_TICKERS:
        try:
            frame = select_yfinance_symbol_frame(raw, symbol).copy()
            if frame.empty:
                continue
            frame.index = pd.to_datetime(frame.index, errors="coerce").tz_localize(None)
            frame = frame[frame.index.notna() & (frame.index <= cutoff)]
            if not frame.empty:
                frames[symbol] = frame
        except Exception:
            continue
    return frames


def _load_parabolic_history(root: Path, session: str) -> pd.Series:
    obj = _load(root / "history" / "parabolic_rate_2y.json")
    rows = obj.get("series") if isinstance(obj, dict) else None
    if not isinstance(rows, list):
        return pd.Series(dtype=float)
    cutoff = pd.Timestamp(session).normalize()
    values: dict[pd.Timestamp, float] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        value = _finite(row.get("value"))
        try:
            day = pd.Timestamp(str(row.get("date"))).normalize()
        except Exception:
            continue
        if value is not None and day <= cutoff:
            values[day] = value
    return pd.Series(values, dtype=float).sort_index()


def build_sentiment(
    market: dict[str, pd.DataFrame],
    *,
    session: str,
    fear_greed: pd.Series | None = None,
    put_call: pd.Series | None = None,
    naaim: pd.Series | None = None,
    parabolic: pd.Series | None = None,
) -> dict[str, Any]:
    """Faithful old-source available-component sentiment composite."""
    parts: dict[str, pd.Series] = {}
    rows: list[dict[str, Any]] = []

    def dollar_volume(symbol: str) -> pd.Series | None:
        frame = market.get(symbol)
        if frame is None or "Close" not in frame or "Volume" not in frame:
            return None
        series = (pd.to_numeric(frame["Close"], errors="coerce") * pd.to_numeric(frame["Volume"], errors="coerce")).dropna()
        return series if len(series) > 60 else None

    bulls = [series for series in (dollar_volume("TQQQ"), dollar_volume("SOXL")) if series is not None]
    bears = [series for series in (dollar_volume("SQQQ"), dollar_volume("SOXS")) if series is not None]
    if bulls and bears:
        bull = pd.concat(bulls, axis=1).sum(axis=1)
        bear = pd.concat(bears, axis=1).sum(axis=1)
        ratio = (bull / (bull + bear)).rolling(5).mean().dropna()
        pct = _roll_pct(ratio)
        valid = pct.dropna()
        if not valid.empty:
            parts["lever"] = pct
            rows.append({
                "key": "lever",
                "label": "レバETF資金熱",
                "raw": float(ratio.iloc[-1]),
                "raw_display": f"ブル比率 {float(ratio.iloc[-1]) * 100.0:.0f}%",
                "percentile": float(valid.iloc[-1]),
                "in_composite": True,
                "note": "TQQQ+SOXL÷(ブル+ベア3x)売買代金・5日平均",
            })

    parabolic = parabolic if isinstance(parabolic, pd.Series) else pd.Series(dtype=float)
    if len(parabolic.dropna()) >= 60:
        pct = _roll_pct(parabolic, win=756, minp=60)
        valid = pct.dropna()
        if not valid.empty:
            parts["parab"] = pct
            rows.append({
                "key": "parab",
                "label": "パラボリック銘柄率",
                "raw": float(parabolic.dropna().iloc[-1]),
                "raw_display": f"{float(parabolic.dropna().iloc[-1]):.1f}%",
                "percentile": float(valid.iloc[-1]),
                "in_composite": True,
                "note": "200日線から+45%超で走る銘柄の割合（ユニバース）",
            })

    fear_greed = fear_greed if isinstance(fear_greed, pd.Series) else pd.Series(dtype=float)
    if len(fear_greed.dropna()) >= 30:
        series = fear_greed.dropna().sort_index()
        parts["fng"] = series
        raw = float(series.iloc[-1])
        label = "Extreme Greed" if raw >= 75 else "Greed" if raw >= 55 else "Neutral" if raw >= 45 else "Fear" if raw >= 25 else "Extreme Fear"
        rows.append({
            "key": "fng",
            "label": "CNN Fear & Greed",
            "raw": raw,
            "raw_display": f"{raw:.0f} {label}",
            "percentile": raw,
            "in_composite": True,
            "note": "CNN historical Fear & Greed raw score 0–100",
        })

    put_call = put_call if isinstance(put_call, pd.Series) else pd.Series(dtype=float)
    if len(put_call.dropna()) >= 60:
        smoothed = put_call.dropna().sort_index().rolling(10).mean().dropna()
        pct = _roll_pct(smoothed)
        greed_pct = 100.0 - pct
        valid = greed_pct.dropna()
        if not valid.empty:
            parts["pc"] = greed_pct
            rows.append({
                "key": "pc",
                "label": "Equity Put/Call",
                "raw": float(smoothed.iloc[-1]),
                "raw_display": f"10日平均 {float(smoothed.iloc[-1]):.2f}",
                "percentile": float(valid.iloc[-1]),
                "in_composite": True,
                "note": "10日平均。低P/Cほど強欲なのでtrailing percentileを反転",
            })

    naaim = naaim if isinstance(naaim, pd.Series) else pd.Series(dtype=float)
    if len(naaim.dropna()) >= 52:
        pct = _roll_pct(naaim, win=260, minp=52)
        valid = pct.dropna()
        if not valid.empty:
            parts["naaim"] = pct
            rows.append({
                "key": "naaim",
                "label": "NAAIM エクスポージャー",
                "raw": float(naaim.iloc[-1]),
                "raw_display": f"{float(naaim.iloc[-1]):.0f}",
                "percentile": float(valid.iloc[-1]),
                "in_composite": True,
                "note": "アクティブ運用者の実際の株式露出（週次）",
            })

    skew = market.get("^SKEW")
    if skew is not None and "Close" in skew:
        series = pd.to_numeric(skew["Close"], errors="coerce").dropna()
        pct = _roll_pct(series)
        valid = pct.dropna()
        if not valid.empty:
            rows.append({
                "key": "skew",
                "label": "SKEW",
                "raw": float(series.iloc[-1]),
                "raw_display": f"{float(series.iloc[-1]):.0f}",
                "percentile": float(valid.iloc[-1]),
                "in_composite": False,
                "note": "テールリスク保険需要。旧仕様どおり合成外",
            })

    if not parts:
        return {"status": "DATA_REQUIRED", "reason": "NO_SENTIMENT_COMPONENTS"}

    base_index: pd.DatetimeIndex | None = None
    for key in ("parab", "lever"):
        if key in parts and not parts[key].dropna().empty:
            base_index = pd.DatetimeIndex(parts[key].dropna().index)
            break
    if base_index is None:
        indexes: set[pd.Timestamp] = set()
        for series in parts.values():
            indexes.update(pd.DatetimeIndex(series.dropna().index).tolist())
        base_index = pd.DatetimeIndex(sorted(indexes))
    aligned = pd.DataFrame({key: series.reindex(base_index).ffill() for key, series in parts.items()})
    composite = aligned.mean(axis=1, skipna=True).dropna()
    if composite.empty:
        return {"status": "DATA_REQUIRED", "reason": "SENTIMENT_ALIGNMENT_EMPTY"}
    current = float(composite.iloc[-1])
    band = "過熱🔥" if current >= 85 else "強欲寄り" if current >= 65 else "中立" if current >= 35 else "弱気寄り" if current > 15 else "総悲観🧊"
    history = [
        {"date": pd.Timestamp(day).strftime("%Y-%m-%d"), "value": float(value)}
        for day, value in composite.iloc[-504:].items()
        if math.isfinite(float(value))
    ]
    return {
        "status": "READY",
        "current": current,
        "band": band,
        "components": rows,
        "composite_component_keys": sorted(parts),
        "component_count": len(parts),
        "series": history,
        "method": "available-component trailing-percentile average from recovered source",
        "trading_gate_eligible": False,
    }


def fetch_sentiment(root: Path, *, session: str) -> dict[str, Any]:
    market = _download_sentiment_market(session)
    fear_greed, put_call = _fetch_cnn(session)
    naaim = _fetch_naaim(session)
    parabolic = _load_parabolic_history(root, session)
    return build_sentiment(
        market,
        session=session,
        fear_greed=fear_greed,
        put_call=put_call,
        naaim=naaim,
        parabolic=parabolic,
    )


def _market_frame(rows: Any) -> pd.DataFrame:
    if not isinstance(rows, list):
        return pd.DataFrame()
    frame = pd.DataFrame([row for row in rows if isinstance(row, dict)])
    if frame.empty or "date" not in frame or "close" not in frame:
        return pd.DataFrame()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame = frame.dropna(subset=["date", "close"]).sort_values("date").set_index("date")
    for key in ("open", "high", "low", "close", "volume"):
        if key in frame:
            frame[key] = pd.to_numeric(frame[key], errors="coerce")
    return frame


def build_ftd_proxy(series: dict[str, Any]) -> dict[str, Any]:
    output: list[dict[str, Any]] = []
    for ticker, label in (("QQQ", "NASDAQ 100"), ("SPY", "S&P 500")):
        frame = _market_frame(series.get(ticker))
        if len(frame) < 252:
            continue
        close = frame["close"].dropna()
        frame = frame.loc[close.index]
        low = frame["low"] if "low" in frame else frame["close"]
        volume = frame["volume"] if "volume" in frame else None
        sma50 = close.rolling(50).mean()
        high252 = close.rolling(252, min_periods=252).max()
        correction = ((close < sma50) | ((close / high252 - 1.0) <= -0.08)).fillna(False)

        count = min(500, len(close))
        dates = close.index[-count:]
        cc = close.iloc[-count:].to_numpy(dtype=float)
        ll = low.reindex(dates).to_numpy(dtype=float)
        vv = volume.reindex(dates).to_numpy(dtype=float) if volume is not None else None
        corr = correction.iloc[-count:].to_numpy(dtype=bool)
        sm50 = sma50.iloc[-count:].to_numpy(dtype=float)

        low_value = low_index = day1 = None
        ftd_index = ftd_pct = ftd_low = ftd_day = None
        armed = False
        post_max = np.nan
        below50 = 0
        failed_ago = None
        invalidation = None

        for index in range(1, count):
            current = cc[index]
            previous = cc[index - 1]
            intraday_low = ll[index]
            if ftd_index is not None:
                post_max = current if not np.isfinite(post_max) else max(post_max, current)
                ma = sm50[index]
                if np.isfinite(ma):
                    below50 = below50 + 1 if current < ma else 0
                    if current >= ma:
                        armed = True
                deep = np.isfinite(post_max) and (current / post_max - 1.0) <= -0.08
                if current < ftd_low:
                    failed_ago = (count - 1) - index
                    invalidation = "FTD日安値を終値で割れ"
                elif armed and (deep or below50 >= 5):
                    failed_ago = (count - 1) - index
                    invalidation = "新規調整入り: FTD後高値−8%" if deep else "新規調整入り: 50日線下5日連続"
                else:
                    continue
                ftd_index = ftd_pct = ftd_low = ftd_day = None
                armed = False
                below50 = 0
                post_max = np.nan
                day1, low_value, low_index = None, intraday_low, index
                continue

            if day1 is not None:
                if intraday_low < low_value:
                    low_value, low_index, day1 = intraday_low, index, None
                    continue
                attempt_day = index - day1 + 1
                if attempt_day >= 4 and vv is not None and np.isfinite(vv[index]) and np.isfinite(vv[index - 1]):
                    change = current / previous - 1.0
                    if change >= FTD_PCT and vv[index] > vv[index - 1]:
                        ftd_index, ftd_pct, ftd_low, ftd_day = index, change, intraday_low, attempt_day
                        armed = False
                        below50 = 0
                        post_max = current
                        failed_ago = invalidation = None
                continue

            if not corr[index]:
                low_value = low_index = None
                continue
            if low_value is None or intraday_low < low_value:
                low_value, low_index = intraday_low, index
                if current > previous:
                    day1 = index
            elif current > previous:
                day1 = index

        last = float(close.iloc[-1])
        last_sma50 = sma50.iloc[-1]
        sma200 = close.rolling(200).mean().iloc[-1]
        above50 = bool(pd.notna(last_sma50) and last >= float(last_sma50))
        above200 = bool(pd.notna(sma200) and last >= float(sma200))
        correction_now = bool(corr[-1])
        attempt_day = ((count - 1) - day1 + 1) if day1 is not None else 0

        record: dict[str, Any] = {
            "ticker": ticker,
            "label": label,
            "rally_start": dates[day1].strftime("%Y-%m-%d") if day1 is not None else None,
            "rally_day": attempt_day or None,
            "ftd_date": dates[ftd_index].strftime("%Y-%m-%d") if ftd_index is not None else None,
            "ftd_age": (count - 1) - ftd_index if ftd_index is not None else None,
            "ftd_day": int(ftd_day) if ftd_day is not None else None,
            "ftd_low": round(float(ftd_low), 2) if ftd_low is not None else None,
            "ftd_gain": float(ftd_pct) if ftd_pct is not None else None,
            "invalidation": invalidation,
            "above50": above50,
            "above200": above200,
        }
        if ftd_index is not None:
            age = int((count - 1) - ftd_index)
            record["state"] = "FTD_ACTIVE"
            if not above50:
                record["display"] = f"点灯後に50日線割れ（{record['ftd_date']} Day{ftd_day} / {age}日前）"
            elif age > 40 and above200:
                record["display"] = f"上昇継続中（{record['ftd_date']}以来{age}日）"
            else:
                quality = "" if ftd_day <= 7 else "・やや遅い" if ftd_day <= 10 else "・信頼度低"
                record["display"] = f"点灯 {record['ftd_date']} Day{ftd_day}{quality}・{age}日前 +{float(ftd_pct) * 100.0:.1f}%"
        elif failed_ago is not None and failed_ago <= 20 and not (day1 is not None and attempt_day <= failed_ago):
            record["state"] = "FTD_FAILED"
            record["display"] = f"FTD無効（{failed_ago}日前・{invalidation}）"
        elif day1 is not None:
            record["state"] = "RALLY_ATTEMPT"
            record["display"] = f"試行 {attempt_day}日目・確認待ち（安値 {record['rally_start']}〜）"
        elif correction_now:
            record["state"] = "CORRECTION"
            record["display"] = "調整局面・試行未開始（安値模索）"
        else:
            record["state"] = "NO_CORRECTION"
            record["display"] = "上昇継続中（FTD非対象）" if above50 and above200 else "FTD非対象"
        output.append(record)

    return {
        "status": "READY" if len(output) == 2 else "DATA_REQUIRED",
        "reason": "SOURCE_DEFINED_QQQ_SPY_PROXY" if len(output) == 2 else "QQQ_SPY_HISTORY_INCOMPLETE",
        "rows": output,
        "ftd_threshold": FTD_PCT,
        "trading_gate_eligible": False,
    }


def _current_rs_map(root: Path) -> dict[str, dict[str, Any]]:
    obj = _load(root / "rs.json")
    rows = obj.get("rows") if isinstance(obj, dict) else None
    if not isinstance(rows, list):
        return {}
    return {
        str(row.get("ticker") or "").strip().upper(): row
        for row in rows
        if isinstance(row, dict) and str(row.get("ticker") or "").strip()
    }


def _old_rs63_leaders(root: Path, *, lag: int = 42) -> tuple[str | None, list[dict[str, Any]]]:
    obj = _load(root / "history" / "reconstructed_stock_metrics.json")
    rows = obj.get("rows") if isinstance(obj, dict) else None
    if not isinstance(rows, list) or len(rows) <= lag:
        return None, []
    historical = rows[-(lag + 1)]
    windows = historical.get("rs_windows") if isinstance(historical, dict) else None
    old = windows.get("63") if isinstance(windows, dict) else None
    leaders = [dict(row) for row in old if isinstance(row, dict)] if isinstance(old, list) else []
    return str(historical.get("date") or "") or None, leaders[:20]


def _fetch_reversal_current(tickers: list[str], session: str) -> dict[str, dict[str, float]]:
    if not tickers:
        return {}
    try:
        import yfinance as yf
    except ImportError:
        return {}
    try:
        raw = yf.download(
            tickers,
            period="6mo",
            interval="1d",
            progress=False,
            auto_adjust=True,
            group_by="ticker",
            threads=True,
            timeout=30,
        )
    except Exception:
        return {}
    cutoff = pd.Timestamp(session)
    out: dict[str, dict[str, float]] = {}
    for ticker in tickers:
        frame = select_yfinance_symbol_frame(raw, ticker).copy()
        if frame.empty or "Close" not in frame or "Volume" not in frame:
            continue
        frame.index = pd.to_datetime(frame.index, errors="coerce").tz_localize(None)
        frame = frame[frame.index.notna() & (frame.index <= cutoff)].dropna(subset=["Close", "Volume"])
        if len(frame) < 51:
            continue
        close = pd.to_numeric(frame["Close"], errors="coerce").dropna()
        volume = pd.to_numeric(frame["Volume"], errors="coerce").reindex(close.index)
        if len(close) < 51:
            continue
        ema21 = close.ewm(span=21, adjust=False).mean().iloc[-1]
        vol50 = volume.iloc[-50:].mean()
        current_volume = volume.iloc[-1]
        if not math.isfinite(float(ema21)) or not math.isfinite(float(vol50)) or vol50 <= 0:
            continue
        out[ticker] = {
            "close": float(close.iloc[-1]),
            "ema21": float(ema21),
            "rvol": float(current_volume / vol50) if math.isfinite(float(current_volume)) else float("nan"),
        }
    return out


def build_reversal_leaders(root: Path, market_series: dict[str, Any], *, session: str) -> dict[str, Any]:
    qqq = _market_frame(market_series.get("QQQ"))
    if len(qqq) < 60:
        return {"status": "DATA_REQUIRED", "reason": "QQQ_HISTORY_TOO_SHORT"}
    close = qqq["close"].dropna()
    window = close.iloc[-90:] if len(close) >= 90 else close
    high = float(window.cummax().iloc[-1])
    low = float(window.min())
    low_index = int(np.argmin(window.to_numpy(dtype=float)))
    current = float(close.iloc[-1])
    prior_peak = float(window.iloc[: low_index + 1].cummax().iloc[-1])
    dd_at_low = low / prior_peak - 1.0
    off_low = current / low - 1.0 if low > 0 else 0.0
    dd_now = current / high - 1.0
    active = bool(dd_at_low <= -0.10 and off_low >= 0.05 and low_index < len(window) - 2)

    old_date, old = _old_rs63_leaders(root, lag=42)
    base = {
        "status": "READY",
        "active": active,
        "dd_now": dd_now,
        "off_low": off_low,
        "dd_at_low": dd_at_low,
        "old_leader_date": old_date,
        "trading_gate_eligible": False,
        "scope": "DISPLAY_OBSERVATION_ONLY",
    }
    if not active:
        base.update({"leaders": [], "ready_count": 0, "candidate_count": 0})
        return base
    if len(old) < 20:
        return {
            **base,
            "status": "DATA_REQUIRED",
            "reason": f"OLD_RS63_TOP20_INCOMPLETE:{len(old)}",
            "leaders": [],
        }

    tickers = [str(row.get("ticker") or "").strip().upper() for row in old[:20]]
    current_data = _fetch_reversal_current(tickers, session)
    rs_now = _current_rs_map(root)
    leaders: list[dict[str, Any]] = []
    for old_row in old[:20]:
        ticker = str(old_row.get("ticker") or "").strip().upper()
        obs = current_data.get(ticker)
        if not ticker or obs is None:
            continue
        reclaim = bool(obs["close"] > obs["ema21"])
        rvol = _finite(obs.get("rvol"))
        volrec = bool(rvol is not None and rvol >= 1.0)
        now = rs_now.get(ticker, {})
        leaders.append({
            "ticker": ticker,
            "old_rs63": _finite(old_row.get("rs63")),
            "rs63": _finite(now.get("rs63")),
            "rs189": _finite(now.get("rs189")),
            "reclaim21": reclaim,
            "volume_recovered": volrec,
            "rvol": rvol,
            "score": (2 if reclaim else 0) + (1 if volrec else 0),
        })
    if len(leaders) != 20:
        return {
            **base,
            "status": "DATA_REQUIRED",
            "reason": f"CURRENT_OLD_LEADER_OBSERVATIONS_INCOMPLETE:{len(leaders)}",
            "leaders": leaders,
        }
    leaders.sort(key=lambda row: (-int(row["score"]), -float(row.get("rs63") or 0.0), row["ticker"]))
    base.update({
        "leaders": leaders,
        "ready_count": sum(1 for row in leaders if row["reclaim21"] and row["volume_recovered"]),
        "candidate_count": len(leaders),
    })
    return base


def update_nqsar_history(root: Path, *, session: str, generated_at: str) -> dict[str, Any]:
    current = _load(root / "nqsar.json")
    state = str(current.get("state") or "").strip()
    if current.get("session_date") != session or state not in VALID_NQSAR:
        return {"status": "DATA_REQUIRED", "reason": "CURRENT_AUTHORITATIVE_NQSAR_MISSING"}
    path = root / "history" / "nqsar_state_history.json"
    previous = _load(path)
    records: dict[str, dict[str, Any]] = {}
    raw_records = previous.get("records") if isinstance(previous, dict) else None
    if isinstance(raw_records, list):
        for row in raw_records:
            if not isinstance(row, dict) or not isinstance(row.get("date"), str):
                continue
            old_state = str(row.get("state") or "")
            if old_state in VALID_NQSAR:
                records[row["date"]] = dict(row)
    records[session] = {
        "date": session,
        "state": state,
        "source": str(current.get("source") or "authoritative:nqsar.json"),
        "generated_at": str(current.get("generated_at") or generated_at),
    }
    ordered = [records[day] for day in sorted(records)][-504:]
    obj = {
        "session_date": session,
        "generated_at": generated_at,
        "coverage": 1.0,
        "source": "observed-authoritative-nqsar-only; no historical state inference",
        "schema_version": NQSAR_HISTORY_SCHEMA,
        "calculation_version": CALCULATION_VERSION,
        "status": "READY",
        "history_kind": "AUTHORITATIVE_OBSERVED_ONLY",
        "records": ordered,
    }
    atomic_write_json(path, obj)
    return {
        "status": "READY",
        "history_kind": obj["history_kind"],
        "records": ordered[-60:],
        "observation_count": len(ordered),
        "trading_gate_eligible": False,
    }


def _market_series(root: Path) -> dict[str, Any]:
    history = _load(root / "history" / "market_series_2y.json")
    series = history.get("series") if isinstance(history, dict) else None
    if isinstance(series, dict) and series:
        return series
    current = _load(root / "market_inputs.json")
    series = current.get("series") if isinstance(current, dict) else None
    return series if isinstance(series, dict) else {}


def materialize_display_observations(
    data_dir: str | Path,
    *,
    session_date: str,
    generated_at: str,
) -> Path:
    root = Path(data_dir)
    market_series = _market_series(root)
    regime = update_nqsar_history(root, session=session_date, generated_at=generated_at)
    net_liquidity = fetch_net_liquidity(session=session_date)
    sentiment = fetch_sentiment(root, session=session_date)
    ftd = build_ftd_proxy(market_series)
    reversal = build_reversal_leaders(root, market_series, session=session_date)

    sections = {
        "regime_history": regime,
        "net_liquidity": net_liquidity,
        "sentiment": sentiment,
        "reversal_leaders": reversal,
        "ftd_proxy": ftd,
    }
    blocked = [name for name, section in sections.items() if section.get("status") != "READY"]
    obj = {
        "session_date": session_date,
        "generated_at": generated_at,
        "coverage": (len(sections) - len(blocked)) / len(sections),
        "source": "recovered source-defined display observations",
        "schema_version": SCHEMA_VERSION,
        "calculation_version": CALCULATION_VERSION,
        "status": "READY" if not blocked else "DATA_REQUIRED",
        "trading_gate_eligible": False,
        "blocked_sections": blocked,
        **sections,
    }
    path = root / "display_observations.json"
    atomic_write_json(path, obj)
    if blocked:
        reasons = {name: sections[name].get("reason") for name in blocked}
        raise RuntimeError(f"display observations incomplete: {reasons}")
    return path


def attach_display_observations(view: dict[str, Any], data_dir: str | Path) -> dict[str, Any]:
    root = Path(data_dir)
    obj = _load(root / "display_observations.json")
    session = str(view.get("session_date") or "")
    if obj.get("session_date") != session or obj.get("status") != "READY":
        view.setdefault("daily", {})["display_observations"] = {
            "status": "DATA_REQUIRED",
            "reason": "CURRENT_DISPLAY_OBSERVATIONS_MISSING",
        }
        return view
    view.setdefault("daily", {})["display_observations"] = obj
    return view
