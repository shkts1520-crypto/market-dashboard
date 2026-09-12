from pathlib import Path


def test_options_chart_overlay_is_external_and_contains_required_levels():
    js = Path("assets/v38-options-chart.js").read_text(encoding="utf-8")
    assert "embed-widget-advanced-chart.js" in js
    assert "Call Wall" in js
    assert "Put Wall" in js
    assert "Gamma Flip" in js
    assert "Expected Upper" in js
    assert "Expected Lower" in js
    assert "Direction/Confidence" in js
    assert "data/options/index.json" in js
    assert "window.V38OpenTickerChart" in js


def test_options_chart_routes_rendered_tickers_inside_command_center():
    js = Path("assets/v38-options-chart.js").read_text(encoding="utf-8")
    assert "tickerFromGenericRow" in js
    assert "data-v38-rs-ticker" in js
    assert "data-v38-ticker" in js
    assert 'a[href*="tradingview.com/chart"]' in js
    assert "event.preventDefault()" in js
    assert "event.stopPropagation()" in js
    assert "前回実測" in js
    assert "現行チェーン未取得のため前回実測値を表示" in js


def test_options_rate_calculation_has_measured_non_yahoo_fallback():
    script = Path("scripts/calculate_options_live.py").read_text(encoding="utf-8")
    assert "FRED:DGS3MO" in script
    assert "risk_free_rate_source" in script
    assert "risk_free_rate_observed_date" in script
    assert "CACHED:" in script
    assert "RISK_FREE_MAX_AGE_DAYS" in script
    assert "fixed fallback" in script


def test_build_site_loads_options_chart_after_final_ui():
    script = Path("scripts/build_site.py").read_text(encoding="utf-8")
    assert 'Path("assets/v38-final-ui.js")' in script
    assert 'Path("assets/v38-options-chart.js")' in script
    assert script.index('Path("assets/v38-final-ui.js")') < script.index('Path("assets/v38-options-chart.js")')
