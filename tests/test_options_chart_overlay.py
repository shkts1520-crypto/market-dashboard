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


def test_build_site_loads_options_chart_after_final_ui():
    script = Path("scripts/build_site.py").read_text(encoding="utf-8")
    assert 'Path("assets/v38-final-ui.js")' in script
    assert 'Path("assets/v38-options-chart.js")' in script
    assert script.index('Path("assets/v38-final-ui.js")') < script.index('Path("assets/v38-options-chart.js")')
