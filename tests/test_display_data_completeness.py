from pathlib import Path


FALLBACK = Path("assets/v38-data-completeness-fallback.js")
BUILD = Path("scripts/build_site.py")
VALIDATOR = Path("scripts/validate_display_completeness.py")
MATERIALIZER = Path("scripts/materialize_restored_experience.py")
WORKFLOW = Path(".github/workflows/production.yml")


def test_uncached_search_tickers_use_live_tradingview_instead_of_missing_state():
    js = FALLBACK.read_text(encoding="utf-8")
    assert "embed-widget-advanced-chart.js" in js
    assert "tradingview-live" in js
    assert "TradingView 実チャート" in js
    assert "NO_VALID_0_45_DTE_CONTRACTS" in js
    assert "0–45 DTE 有効契約なし" in js
    assert "v38TradingviewSymbol" in js


def test_search_index_preserves_exchange_for_unambiguous_fallback_symbols():
    script = MATERIALIZER.read_text(encoding="utf-8")
    assert '"exchange": str(row.get("exchange") or "").strip().upper()' in script
    js = FALLBACK.read_text(encoding="utf-8")
    assert "exchange + ':' + ticker" in js


def test_fallback_loads_after_restored_chart_and_source_layers():
    script = BUILD.read_text(encoding="utf-8")
    restored = script.index('restored_chart = Path("assets/v38-restored-chart.js")')
    source = script.index('source_fidelity = Path("assets/v38-source-fidelity.js")')
    fallback = script.index('data_completeness_fallback = Path("assets/v38-data-completeness-fallback.js")')
    assert restored < source < fallback
    assert '"data_completeness_fallback_extension": data_completeness_fallback_enabled' in script


def test_validator_requires_full_stock_options_chart_and_vwap_completeness():
    script = VALIDATOR.read_text(encoding="utf-8")
    for token in (
        'target_session_coverage',
        'failed_tickers',
        'ticker_snapshot_coverage',
        'fetch_errors',
        'chart_ohlc_contract',
        'inception_pending',
        'search_uncached_chart_policy',
    ):
        assert token in script
    assert '== 1.0' in script
    assert 'NO_VALID_0_45_DTE_CONTRACTS' in script


def test_production_runs_strict_completeness_before_browser_acceptance():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    validator = 'PYTHONPATH=src python scripts/validate_display_completeness.py --data-dir data --site-dir _site'
    browser = 'python scripts/browser_data_completeness.py --url http://127.0.0.1:8000/'
    assert validator in workflow
    assert browser in workflow
    assert workflow.index(validator) < workflow.index(browser)
