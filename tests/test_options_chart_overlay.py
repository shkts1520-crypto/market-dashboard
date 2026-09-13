from pathlib import Path


def test_options_chart_uses_lightweight_candles_and_contains_required_levels():
    js = Path("assets/v38-options-chart.js").read_text(encoding="utf-8")
    assert "lightweight-charts" in js
    assert "addCandlestickSeries" in js
    assert "createPriceLine" in js
    assert "chart_ohlc" in js
    assert "embed-widget-advanced-chart.js" not in js
    assert "Call Wall" in js
    assert "Put Wall" in js
    assert "Gamma Flip" in js
    assert "Expected Upper" in js
    assert "Expected Lower" in js
    assert "Direction/Confidence" not in js
    assert "data/options/index.json" in js
    assert "window.V38OpenTickerChart" in js
    for bucket in ("0-45", "22-45", "7-21", "0-6"):
        assert bucket in js


def test_options_chart_routes_rendered_tickers_inside_command_center():
    js = Path("assets/v38-options-chart.js").read_text(encoding="utf-8")
    assert "tickerFromGenericRow" in js
    assert "data-v38-rs-ticker" in js
    assert "data-v38-ticker" in js
    assert 'a[href*="tradingview.com/chart"]' in js
    assert "event.preventDefault()" in js
    assert "event.stopPropagation()" in js
    assert "前回実測" in js
    assert "現行チェーン未取得" in js


def test_options_rate_calculation_has_measured_non_yahoo_fallback():
    script = Path("scripts/calculate_options_live.py").read_text(encoding="utf-8")
    assert "FRED:DGS3MO" in script
    assert "risk_free_rate_source" in script
    assert "risk_free_rate_observed_date" in script
    assert "CACHED:" in script
    assert "RISK_FREE_MAX_AGE_DAYS" in script
    assert "fixed fallback" in script


def test_build_site_loads_visual_fidelity_after_data_repair_and_options_last():
    script = Path("scripts/build_site.py").read_text(encoding="utf-8")
    assert 'Path("assets/v38-final-ui.js")' in script
    assert 'Path("assets/v38-data-repair.js")' in script
    assert 'Path("assets/v38-visual-fidelity.js")' in script
    assert 'Path("assets/v38-options-chart.js")' in script
    assert script.index('Path("assets/v38-final-ui.js")') < script.index('Path("assets/v38-data-repair.js")')
    assert script.index('Path("assets/v38-data-repair.js")') < script.index('Path("assets/v38-visual-fidelity.js")')
    assert script.index('Path("assets/v38-visual-fidelity.js")') < script.index('Path("assets/v38-options-chart.js")')


def test_visual_fidelity_restores_mc57_bands_robust_diagnostics_and_vix_sequence():
    js = Path("assets/v38-visual-fidelity.js").read_text(encoding="utf-8")
    for threshold in ("25", "40", "55", "70"):
        assert threshold in js
    for label in ("弱気", "弱含み", "中立", "やや強気", "強気"):
        assert label in js
    assert "robust-p02-p98" in js
    assert "EVENT" in js and "ROLLOVER" in js and "BOTTOM" in js
    assert "Raw" not in js
    assert "EMA2 Raw" not in js
    assert "MC57 Z" not in js
