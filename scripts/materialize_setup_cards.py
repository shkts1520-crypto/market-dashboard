#!/usr/bin/env python3
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yfinance as yf

from v38.live_acquisition import select_yfinance_symbol_frame, yahoo_symbol
from v38.vwap_restore import add_vwap_columns, normalize_ohlcv

SCHEMA_VERSION = "v38.setup_restore.1"
CALCULATION_VERSION = "v38-setup-restore-1.0.0"
DDV_FLOOR = 10_000_000.0
PRICE_FLOOR = 5.0


def read_json(path: Path) -> dict[str, Any]:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return obj if isinstance(obj, dict) else {}


def finite(v: Any) -> float | None:
    if isinstance(v, bool):
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def download(symbols: list[str], *, period: str = "2y", threads: int | bool = 12) -> pd.DataFrame:
    if not symbols:
        return pd.DataFrame()
    return yf.download(
        tickers=symbols,
        period=period,
        interval="1d",
        group_by="ticker",
        auto_adjust=False,
        actions=False,
        progress=False,
        threads=threads,
        timeout=30,
    )


def frame_for(raw: pd.DataFrame, ticker: str) -> pd.DataFrame:
    if raw is None or raw.empty:
        return pd.DataFrame()
    f = select_yfinance_symbol_frame(raw, yahoo_symbol(ticker))
    if f is None or f.empty:
        return pd.DataFrame()
    return add_vwap_columns(normalize_ohlcv(f))


def fetch_frames(tickers: list[str], chunk_size: int = 60) -> tuple[dict[str, pd.DataFrame], list[str]]:
    frames: dict[str, pd.DataFrame] = {}
    failed: list[str] = []
    for offset in range(0, len(tickers), chunk_size):
        chunk = tickers[offset: offset + chunk_size]
        symbols = [yahoo_symbol(x) for x in chunk]
        try:
            raw = download(symbols)
        except Exception:
            raw = pd.DataFrame()
        missing: list[str] = []
        for ticker in chunk:
            f = frame_for(raw, ticker)
            if len(f) >= 63:
                frames[ticker] = f
            else:
                missing.append(ticker)
        for ticker in missing:
            try:
                retry = download([yahoo_symbol(ticker)], threads=False)
            except Exception:
                retry = pd.DataFrame()
            f = frame_for(retry, ticker)
            if len(f) >= 63:
                frames[ticker] = f
            else:
                failed.append(ticker)
    return frames, failed


def pool_rows(rs: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for row in rs.get("rows") or []:
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker") or "").strip().upper()
        price, ddv = finite(row.get("price")), finite(row.get("ddv20"))
        r63, r189 = finite(row.get("rs63")), finite(row.get("rs189"))
        if not ticker or price is None or ddv is None or price < PRICE_FLOOR or ddv < DDV_FLOOR:
            continue
        if max(r63 if r63 is not None else -1, r189 if r189 is not None else -1) < 70:
            continue
        out.append(dict(row))
    out.sort(key=lambda r: (-float(finite(r.get("rs189")) or -1), str(r.get("ticker") or "")))
    return out


def recent_pocket_pivot(c: pd.Series, v: pd.Series) -> tuple[int | None, float | None]:
    if len(c) < 61 or len(v) != len(c):
        return None, None
    sma10 = c.rolling(10).mean()
    sma50 = c.rolling(50).mean()
    up = c > c.shift(1)
    for back in range(0, 10):
        i = len(c) - 1 - back
        if i < 12 or not bool(up.iloc[i]):
            continue
        win_c = c.iloc[i - 11:i]
        win_v = v.iloc[i - 10:i]
        dn_mask = (win_c.diff() < 0).to_numpy()[1:]
        dn = win_v[dn_mask]
        vv = finite(v.iloc[i])
        if len(dn) == 0 or vv is None:
            continue
        dn_max = finite(dn.max())
        if dn_max is None or dn_max <= 0:
            continue
        if finite(sma10.iloc[i]) is None or c.iloc[i] <= sma10.iloc[i]:
            continue
        if finite(sma50.iloc[i]) is None or c.iloc[i] <= sma50.iloc[i]:
            continue
        if vv > dn_max:
            return back, vv / dn_max
    return None, None


def cup_metrics(c: pd.Series, h: pd.Series, l: pd.Series, v: pd.Series) -> dict[str, Any]:
    if len(c) < 90:
        return {"ready": False, "breakout": False, "depth": None, "handle_depth": None}
    n = min(190, len(c))
    start = len(c) - n
    rim_window = h.iloc[start: len(c) - 12]
    if rim_window.empty:
        return {"ready": False, "breakout": False, "depth": None, "handle_depth": None}
    rim_pos = int(np.nanargmax(rim_window.to_numpy(float))) + start
    if len(c) - 1 - rim_pos < 35:
        return {"ready": False, "breakout": False, "depth": None, "handle_depth": None}
    rim = finite(h.iloc[rim_pos])
    if rim is None or rim <= 0:
        return {"ready": False, "breakout": False, "depth": None, "handle_depth": None}
    body_low = finite(l.iloc[rim_pos: len(c)-11].min())
    if body_low is None:
        return {"ready": False, "breakout": False, "depth": None, "handle_depth": None}
    depth = 1.0 - body_low / rim
    handle_hi = finite(h.iloc[-11:-1].max())
    handle_lo = finite(l.iloc[-11:-1].min())
    handle_depth = (1.0 - handle_lo / handle_hi) if handle_hi and handle_lo is not None else None
    midpoint = body_low + (rim - body_low) * 0.5
    old_vol = finite(v.iloc[-62:-12].mean()) if len(v) >= 62 else None
    handle_vol = finite(v.iloc[-11:-1].mean())
    dry = old_vol is not None and old_vol > 0 and handle_vol is not None and handle_vol / old_vol <= 0.95
    duration = len(c) - 1 - rim_pos
    close = finite(c.iloc[-1]); prev = finite(c.iloc[-2])
    near = close is not None and -0.06 <= close / rim - 1.0 <= 0.035
    ready = bool(0.12 <= depth <= 0.38 and handle_depth is not None and handle_depth <= 0.12
                 and handle_lo is not None and handle_lo > midpoint and handle_hi is not None
                 and handle_hi >= rim * 0.90 and dry and 30 <= duration <= 190 and near)
    rvol50 = finite(v.iloc[-1] / v.iloc[-51:-1].mean()) if len(v) >= 51 and finite(v.iloc[-51:-1].mean()) not in (None, 0) else None
    breakout = bool(ready and close is not None and prev is not None and prev <= rim and close > rim
                    and rvol50 is not None and rvol50 >= 1.35)
    return {"ready": ready, "breakout": breakout, "depth": depth, "handle_depth": handle_depth}


def technical(row: dict[str, Any], frame: pd.DataFrame) -> dict[str, Any] | None:
    if frame is None or len(frame) < 63:
        return None
    c = pd.to_numeric(frame["close"], errors="coerce")
    h = pd.to_numeric(frame["high"], errors="coerce")
    l = pd.to_numeric(frame["low"], errors="coerce")
    v = pd.to_numeric(frame["volume"], errors="coerce")
    if any(x.isna().all() for x in (c,h,l,v)):
        return None
    close, prev = finite(c.iloc[-1]), finite(c.iloc[-2])
    if close is None or prev is None:
        return None
    sma10 = c.rolling(10).mean(); sma50 = c.rolling(50).mean(); sma200 = c.rolling(200).mean()
    ema21 = c.ewm(span=21, adjust=False).mean()
    s50, s200, e21 = finite(sma50.iloc[-1]), finite(sma200.iloc[-1]), finite(ema21.iloc[-1])
    s50_old = finite(sma50.iloc[-11]) if len(c) >= 61 else None
    s200_old = finite(sma200.iloc[-21]) if len(c) >= 220 else None
    stage2 = bool(s50 is not None and s200 is not None and s50_old is not None and s200_old is not None
                  and close > s50 > s200 and s50 > s50_old and s200 >= s200_old)
    up50 = bool(s50 is not None and close > s50)
    up200 = bool(s200 is not None and close > s200)
    pivot40 = finite(h.iloc[-41:-1].max()) if len(h) >= 41 else None
    pivot_dist = close / pivot40 - 1.0 if pivot40 and pivot40 > 0 else None

    def rng(k: int) -> float | None:
        if len(h) < k + 1:
            return None
        hh, ll = finite(h.iloc[-k-1:-1].max()), finite(l.iloc[-k-1:-1].min())
        return hh / ll - 1.0 if hh is not None and ll and ll > 0 else None
    r40, r20, r10, r5 = rng(40), rng(20), rng(10), rng(5)
    contractions = int(r20 is not None and r10 is not None and r10 <= r20*0.80) + int(r10 is not None and r5 is not None and r5 <= r10*0.80)
    hl10 = len(l)>=21 and finite(l.iloc[-11:-1].min()) is not None and finite(l.iloc[-21:-11].min()) is not None and float(l.iloc[-11:-1].min()) > float(l.iloc[-21:-11].min())*1.002
    hl5 = len(l)>=11 and finite(l.iloc[-6:-1].min()) is not None and finite(l.iloc[-11:-6].min()) is not None and float(l.iloc[-6:-1].min()) > float(l.iloc[-11:-6].min())*1.002
    higher_lows = bool(hl10 and hl5)
    pivot_touches = int(((h.iloc[-21:-1] >= pivot40*0.985)&(h.iloc[-21:-1] <= pivot40*1.005)).sum()) if pivot40 and len(h)>=21 else 0
    base_depth40 = 1.0-float(l.iloc[-41:-1].min())/pivot40 if pivot40 and len(l)>=41 else None
    base_depth25 = 1.0-float(l.iloc[-26:-1].min())/float(h.iloc[-26:-1].max()) if len(l)>=26 and float(h.iloc[-26:-1].max())>0 else None
    pc=c.shift(1); tr=pd.concat([(h-l).abs(),(h-pc).abs(),(l-pc).abs()],axis=1).max(axis=1)
    atr20=finite(tr.iloc[-21:-1].mean()) if len(tr)>=21 else None; atr5=finite(tr.iloc[-6:-1].mean()) if len(tr)>=6 else None
    atr_contract=atr5/atr20 if atr5 is not None and atr20 and atr20>0 else None
    atr14=finite(frame["atr14"].iloc[-1]) if "atr14" in frame.columns else None
    v20=finite(v.iloc[-21:-1].mean()) if len(v)>=21 else None
    rvol_pre=finite(v.iloc[-1]/v20) if v20 and v20>0 else None
    vdry_pre=finite(v.iloc[-6:-1].mean()/v20) if v20 and v20>0 and len(v)>=21 else None
    rr=c.pct_change(fill_method=None).iloc[-21:-1]; vv=v.reindex(rr.index)
    upv=finite(vv[rr>0].mean()); dnv=finite(vv[rr<0].mean()); uvdv20=upv/dnv if upv is not None and dnv and dnv>0 else None
    high52=finite(h.iloc[-253:-1].max()) if len(h)>=253 else finite(h.iloc[:-1].max()) if len(h)>1 else None
    dist52=close/high52-1.0 if high52 and high52>0 else None
    near52=dist52 is not None and dist52>=-0.10
    prebase_ret=finite(c.iloc[-41]/c.iloc[-101]-1.0) if len(c)>=101 and finite(c.iloc[-101]) not in (None,0) else None
    day_range=finite(h.iloc[-1]-l.iloc[-1]); close_pos=(close-float(l.iloc[-1]))/day_range if day_range and day_range>0 else None
    pp_days, pp_ratio = recent_pocket_pivot(c,v)
    cup=cup_metrics(c,h,l,v)
    breakout40=bool(pivot40 is not None and prev<=pivot40 and close>pivot40)
    breakout52=bool(high52 is not None and prev<=high52 and close>high52)
    shape_ok=bool(contractions>=1 or higher_lows or pivot_touches>=2 or cup["breakout"])
    volume_ok=bool((vdry_pre is not None and vdry_pre<=1.0) or (uvdv20 is not None and uvdv20>=1.05) or (pp_days is not None and pp_days<=10))
    true_breakout=bool(stage2 and (breakout40 or breakout52 or cup["breakout"])
                       and rvol_pre is not None and rvol_pre>=1.40 and close_pos is not None and close_pos>=0.60
                       and base_depth40 is not None and 0.05<=base_depth40<=0.35
                       and prebase_ret is not None and prebase_ret>=0.15 and near52 and shape_ok and volume_ok)
    recent_break = false_recent = False
    # We do not synthesize a historical breakout date here. The display-only VCP producer
    # therefore relies on current base structure and excludes a current true breakout below.
    rs189=finite(row.get("rs189")); rs63=finite(row.get("rs63")); ddv=finite(row.get("ddv20"))
    rsline_newhigh=False
    vcp_score=(15*int(stage2)+10*min(contractions,2)+15*int(higher_lows)+10*int(vdry_pre is not None and vdry_pre<=0.85)
               +10*int(atr_contract is not None and atr_contract<=0.75)+10*int(pivot_dist is not None and -0.08<=pivot_dist<=0.01)
               +5*int(rs189 is not None and rs189>=85)+5*int(rsline_newhigh)+5*int(uvdv20 is not None and uvdv20>=1.05))
    vcp_ready=bool(stage2 and vcp_score>=65 and pivot_dist is not None and -0.12<=pivot_dist<=0.02
                   and base_depth40 is not None and 0.05<=base_depth40<=0.35 and not true_breakout and not cup["breakout"])
    ucr=False
    if len(c)>=24:
        lo20=finite(c.iloc[-24:-3].min()); recent=finite(c.iloc[-3:].min())
        ucr=bool(lo20 is not None and recent is not None and recent<lo20 and close>lo20 and close>prev)
    tc3=(float(c.iloc[-3:].max())/float(c.iloc[-3:].min())-1.0) if len(c)>=3 and float(c.iloc[-3:].min())>0 else None
    flat=bool(stage2 and near52 and base_depth25 is not None and base_depth25<=0.15 and r20 is not None and r20<=0.15 and vdry_pre is not None and vdry_pre<=0.95 and rs189 is not None and rs189>=80)
    htf=bool(finite(row.get("ret20")) is not None and finite(row.get("ret63")) is not None and float(row["ret20"])>=0.20 and float(row["ret63"])>=0.70 and base_depth25 is not None and base_depth25<=0.20 and up50 and rs189 is not None and rs189>=85)
    ema_touch=bool(e21 is not None and atr14 is not None and atr14>0 and close>=e21 and close-e21<=0.5*atr14 and rs189 is not None and rs189>=80)
    prebreak=bool(stage2 and rs189 is not None and rs189>=85 and pivot_dist is not None and -0.08<=pivot_dist<0 and contractions>=1 and vdry_pre is not None and vdry_pre<=0.95)
    confluence=[]
    if rs189 is not None and rs189>=95:
        if pivot_dist is not None and abs(pivot_dist)<=0.03: confluence.append("Pivot±3%")
        if e21 is not None and atr14 and abs(close-e21)<=0.5*atr14: confluence.append("21EMA近接")
        for key,label in (("vwap63","VWAP63"),("vwap252","VWAP252")):
            vv0=finite(frame[key].iloc[-1]) if key in frame.columns else None
            if vv0 is not None and atr14 and abs(close-vv0)<=0.5*atr14: confluence.append(label)
    return {
        "ticker": str(row.get("ticker") or "").upper(), "name": str(row.get("name") or ""),
        "sector": str(row.get("sector") or ""), "industry": str(row.get("industry") or ""),
        "price": close, "ddv20": ddv, "rs63": rs63, "rs189": rs189,
        "stage2": stage2, "pivot": pivot40, "pivot_dist": pivot_dist, "pp_days": pp_days, "pp_ratio": pp_ratio,
        "contractions": contractions, "higher_lows": higher_lows, "vdry_pre": vdry_pre, "atr_contract": atr_contract,
        "base_depth40": base_depth40, "base_depth25": base_depth25, "vcp_score": float(vcp_score), "vcp_ready": vcp_ready,
        "true_breakout": true_breakout, "ucr": ucr, "tight3": bool(tc3 is not None and tc3<=0.015 and vdry_pre is not None and vdry_pre<=0.90 and up50 and rs189 is not None and rs189>=80),
        "flat_base": flat, "cup_handle": bool(cup["ready"] or cup["breakout"]), "high_tight_flag": htf,
        "ema21_touch": ema_touch, "prebreakout": prebreak, "confluence": confluence,
    }


def main() -> int:
    root=Path("data")
    state=read_json(root/"state.json"); rs=read_json(root/"rs.json")
    session=str(state.get("session_date") or "")
    if not session:
        raise SystemExit("state session_date required")
    pool=pool_rows(rs); tickers=[str(r["ticker"]).upper() for r in pool]
    frames,failed=fetch_frames(tickers)
    rows=[]
    by={str(r["ticker"]).upper():r for r in pool}
    for ticker,frame in frames.items():
        item=technical(by[ticker],frame)
        if item: rows.append(item)
    rows.sort(key=lambda r:(-(r.get("rs189") if r.get("rs189") is not None else -1),r["ticker"]))
    def take(pred, key="rs189", limit=16):
        z=[r for r in rows if pred(r)]
        z.sort(key=lambda r:(-(r.get(key) if r.get(key) is not None else -1),r["ticker"]))
        return z[:limit]
    payload={
        "session_date":session,
        "generated_at":datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z"),
        "status":"READY" if rows else "DATA_REQUIRED",
        "source":"Yahoo Finance 2y daily OHLCV + current rs.json; recovered 09/05 setup definitions; display-only, not a trading gate",
        "schema_version":SCHEMA_VERSION,"calculation_version":CALCULATION_VERSION,
        "coverage":len(rows)/len(pool) if pool else 0.0,"requested":len(pool),"received":len(rows),"failed":failed,
        "prebreakout":take(lambda r:r["prebreakout"],limit=12),
        "confluence":take(lambda r:bool(r["confluence"]),limit=16),
        "pocket_pivots":take(lambda r:r["pp_days"] is not None and r["rs189"] is not None and r["rs189"]>=85,key="pp_ratio",limit=10),
        "todays_setups":take(lambda r:r["true_breakout"] and r["rs63"] is not None and r["rs63"]>=90,limit=12),
        "vcp":take(lambda r:r["vcp_ready"] and r["rs189"] is not None and r["rs189"]>=80,key="vcp_score",limit=12),
        "ema21_touch":take(lambda r:r["ema21_touch"],limit=12),
        "patterns":{
            "undercut_rally":take(lambda r:r["ucr"],limit=10),
            "tight3":take(lambda r:r["tight3"],limit=10),
            "flat_base":take(lambda r:r["flat_base"],limit=10),
            "cup_handle":take(lambda r:r["cup_handle"],limit=10),
            "high_tight_flag":take(lambda r:r["high_tight_flag"],limit=10),
        },
        "rows":rows,
    }
    out=root/"history"/"setup_restore.json";out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(payload,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps({"session_date":session,"requested":len(pool),"received":len(rows),"coverage":payload["coverage"],"prebreakout":len(payload["prebreakout"]),"confluence":len(payload["confluence"]),"pocket_pivots":len(payload["pocket_pivots"]),"todays_setups":len(payload["todays_setups"]),"vcp":len(payload["vcp"])},sort_keys=True))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
