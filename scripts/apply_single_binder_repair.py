#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"pattern not found in {path}: {old[:100]!r}")
    text = text.replace(old, new, 1)
    p.write_text(text, encoding="utf-8")


# 1) Exact five style ETFs recovered from the canonical 09/05 source.
replace_once(
    "src/v38/live_acquisition.py",
    '    "QQQ", "TQQQ", "SPY", "RSP", "QQQE", "SOXL",\n',
    '    "QQQ", "TQQQ", "SPY", "RSP", "IWD", "IWF", "IWM", "MDY", "QQQE", "SOXL",\n',
)

# 2) Expose those series in the authoritative view model.
replace_once(
    "src/v38/ui_view_model.py",
    '        ("RSP", "RSP"), ("QQQE", "QQQE"), ("SOXL", "SOXL"),\n',
    '        ("RSP", "RSP"), ("IWD", "Value"), ("IWF", "Growth"),\n'
    '        ("IWM", "Small Cap"), ("MDY", "Mid Cap"),\n'
    '        ("QQQE", "QQQE"), ("SOXL", "SOXL"),\n',
)

# 3) Produce the canonical money-flow coordinates in Python. JS only renders them.
insert_anchor = '\ndef build_ui_view_model(data_dir: str | Path) -> dict[str, Any]:\n'
rrg_helper = r'''

def _rotation_money_flow(market_series: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    """Display-only RRG coordinates from completed daily bars.

    Canonical definition: GICS11 + five style ETFs, horizontal relative strength
    versus SPY with 100 neutral, vertical 10-session momentum of that relative
    strength with 100 neutral. This is diagnostic display data, never a trading gate.
    """
    labels = {
        "XLB": "素材", "XLC": "通信", "XLE": "エネルギー", "XLF": "金融",
        "XLI": "資本財", "XLK": "テクノロジー", "XLP": "生活必需品",
        "XLRE": "不動産", "XLU": "公益", "XLV": "ヘルスケア", "XLY": "一般消費財",
        "IWD": "バリュー", "IWF": "グロース", "IWM": "小型株",
        "MDY": "中型株", "RSP": "S&P等加重",
    }
    spy = market_series.get("SPY") or []
    spy_by_date = {str(row.get("date")): _finite(row.get("close")) for row in spy if isinstance(row, dict)}
    rows: list[dict[str, Any]] = []
    for ticker, label in labels.items():
        rel: list[tuple[str, float]] = []
        for row in market_series.get(ticker) or []:
            if not isinstance(row, dict):
                continue
            date = str(row.get("date") or "")
            close = _finite(row.get("close"))
            benchmark = spy_by_date.get(date)
            if date and close is not None and benchmark is not None and benchmark > 0:
                rel.append((date, close / benchmark))
        if len(rel) < 64:
            continue
        current = rel[-1][1]
        base63 = rel[-64][1]
        base10 = rel[-11][1]
        if base63 <= 0 or base10 <= 0:
            continue
        rows.append({
            "ticker": ticker,
            "label": label,
            "x": 100.0 * current / base63,
            "y": 100.0 * current / base10,
            "date": rel[-1][0],
            "source": "completed daily close / SPY; 63-session RS and 10-session RS momentum",
        })
    return {
        "status": READY if len(rows) == len(labels) else DATA_REQUIRED,
        "reason": "CURRENT_MARKET_SERIES" if len(rows) == len(labels) else "STYLE_OR_SECTOR_SERIES_INCOMPLETE",
        "rows": rows,
        "expected_count": len(labels),
        "definition": "x=100*(relative strength now / 63 sessions ago); y=100*(relative strength now / 10 sessions ago)",
        "trading_gate_eligible": False,
    }
'''
replace_once("src/v38/ui_view_model.py", insert_anchor, rrg_helper + insert_anchor)

# 4) Use full universe for Movers instead of the RS189 Top24 display slice.
replace_once(
    "src/v38/ui_view_model.py",
    '    mover_source = [row for row in rs_rows if _finite(row.get("ret1")) is not None]\n',
    '    mover_source = []\n'
    '    for rank, raw in enumerate(all_rs_rows, start=1):\n'
    '        row = _rs_display_row(raw, rank)\n'
    '        if row is not None and _finite(row.get("ret1")) is not None:\n'
    '            mover_source.append(row)\n',
)

# 5) Promote setup_restore into the view model instead of repairing it in the browser.
old_setup = '''    vwap = _read(root / "history" / "vwap_restore.json")
    vwap_rows = [dict(row) for row in ((vwap or {}).get("rows") or []) if isinstance(row, dict)]
    setups = {
        "status": READY if vwap_rows else DATA_REQUIRED,
        "reason": "RECOVERED_VWAP_AND_RS_INPUTS" if vwap_rows else "SETUP_PRODUCER_DATA_REQUIRED",
        "title": "Setups",
        "rows": vwap_rows,
        "source": "history/vwap_restore.json" if vwap_rows else None,
    }
'''
new_setup = '''    vwap = _read(root / "history" / "vwap_restore.json")
    vwap_rows = [dict(row) for row in ((vwap or {}).get("rows") or []) if isinstance(row, dict)]
    setup_restore = _read(root / "history" / "setup_restore.json")
    setup_status, setup_reason = _status(setup_restore, session)
    setups = {
        "status": setup_status,
        "reason": setup_reason,
        "title": "Setups",
        "rows": [dict(row) for row in ((setup_restore or {}).get("rows") or []) if isinstance(row, dict)],
        "prebreakout": [dict(row) for row in ((setup_restore or {}).get("prebreakout") or []) if isinstance(row, dict)],
        "confluence": [dict(row) for row in ((setup_restore or {}).get("confluence") or []) if isinstance(row, dict)],
        "pocket_pivots": [dict(row) for row in ((setup_restore or {}).get("pocket_pivots") or []) if isinstance(row, dict)],
        "todays_setups": [dict(row) for row in ((setup_restore or {}).get("todays_setups") or []) if isinstance(row, dict)],
        "vcp": [dict(row) for row in ((setup_restore or {}).get("vcp") or []) if isinstance(row, dict)],
        "ema21_touch": [dict(row) for row in ((setup_restore or {}).get("ema21_touch") or []) if isinstance(row, dict)],
        "patterns": dict((setup_restore or {}).get("patterns") or {}),
        "coverage": _finite((setup_restore or {}).get("coverage")),
        "source": (setup_restore or {}).get("source"),
        "vwap_rows": vwap_rows,
    }
'''
replace_once("src/v38/ui_view_model.py", old_setup, new_setup)

# 6) Attach Python-produced money-flow data to Rotation.
replace_once(
    "src/v38/ui_view_model.py",
    '    rotation["diagnostic_status"] = (\n        READY if any(group_diagnostics.values()) else DATA_REQUIRED\n    )\n    rotation["diagnostics"] = group_diagnostics\n',
    '    rotation["diagnostic_status"] = (\n        READY if any(group_diagnostics.values()) else DATA_REQUIRED\n    )\n'
    '    rotation["diagnostics"] = group_diagnostics\n'
    '    rotation["money_flow"] = _rotation_money_flow(market_series)\n',
)

# 7) Single rendering owner. Search/chart scripts may enhance interactions but never own cards.
old_ext = '''    live_binder_enabled = _inject_external_extension(out, Path("assets/v38-live-binder.js"))
    restored_chart_enabled = _inject_external_extension(out, Path("assets/v38-restored-chart.js"))
    options_chart_enabled = False if restored_chart_enabled else _inject_external_extension(out, Path("assets/v38-options-chart.js"))
    restored_experience_enabled = _inject_external_extension(out, Path("assets/v38-restored-experience.js"))
    tradingview_fallback_enabled = _inject_external_extension(out, Path("assets/v38-tradingview-fallback.js"))
    production_truth_enabled = _inject_external_extension(out, Path("assets/v38-production-truth.js"))
    production_label_truth_enabled = _inject_external_extension(out, Path("assets/v38-production-label-truth.js"))
    public_final_enabled = _inject_external_extension(out, Path("assets/v38-public-final.js"))
'''
new_ext = '''    live_binder_enabled = False
    restored_experience_enabled = False
    production_truth_enabled = False
    production_label_truth_enabled = False
    public_final_enabled = False
    canonical_binder_enabled = _inject_external_extension(out, Path("assets/v38-canonical-binder.js"))
    restored_chart_enabled = _inject_external_extension(out, Path("assets/v38-restored-chart.js"))
    options_chart_enabled = False if restored_chart_enabled else _inject_external_extension(out, Path("assets/v38-options-chart.js"))
    tradingview_fallback_enabled = _inject_external_extension(out, Path("assets/v38-tradingview-fallback.js"))
'''
replace_once("scripts/build_site.py", old_ext, new_ext)
replace_once(
    "scripts/build_site.py",
    '        "public_final_extension": public_final_enabled,\n',
    '        "public_final_extension": public_final_enabled,\n        "canonical_binder_extension": canonical_binder_enabled,\n',
)

print("single-binder architecture patch applied")
