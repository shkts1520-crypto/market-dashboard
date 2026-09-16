from pathlib import Path


FALLBACK = Path("assets/v38-data-completeness-fallback.js")
BUILD = Path("scripts/build_site.py")
VALIDATOR = Path("scripts/validate_display_completeness.py")
MATERIALIZER = Path("scripts/materialize_restored_experience.py")
WORKFLOW = Path(".github/workflows/production.yml")
BROWSER = Path("scripts/browser_data_completeness.py")


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


def test_destructive_display_patch_layers_are_retired():
    script = BUILD.read_text(encoding="utf-8")
    assert 'canonical_binder_enabled = _inject_external_extension(out, Path("assets/v38-canonical-binder.js"))' in script
    for flag in (
        'live_binder_enabled = False', 'restored_experience_enabled = False',
        'production_truth_enabled = False', 'production_label_truth_enabled = False',
        'public_final_enabled = False', 'data_completeness_fallback_enabled = False',
        'source_fidelity_enabled = False',
    ):
        assert flag in script


def test_validator_checks_consistency_without_duplicate_stock_threshold():
    script = VALIDATOR.read_text(encoding="utf-8")
    for token in (
        'target_session_received', 'target_session_coverage', 'failed_tickers',
        'ticker_snapshot_coverage', 'fetch_errors', 'chart_ohlc_contract',
        'inception_pending', 'search_uncached_chart_policy', 'search_coverage',
    ):
        assert token in script
    assert 'MIN_STOCK_COVERAGE' not in script
    assert 'NO_VALID_0_45_DTE_CONTRACTS' in script


def test_browser_gate_checks_user_visible_failures_not_ui_shape():
    script = BROWSER.read_text(encoding="utf-8")
    assert 'v38CanonicalBinder' in script
    assert 'v38TruthBinding' not in script
    assert 'v38AuthoritativeFinal' not in script
    assert 'v38PublicRenderContract' not in script
    for token in ('SOURCE_DEFINED_', 'SOURCE_UNAVAILABLE', 'producer未復元', 'full_v38_ready:'):
        assert token in script
    assert 'visible tab is empty' in script
    assert 'unexpected horizontal overflow' in script
    assert 'REPAIRED_CARD_CONTRACT' not in script
    assert 'data-v38-truth-source' not in script


def test_production_runs_completeness_before_browser_smoke_acceptance():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    validator = 'PYTHONPATH=src python scripts/validate_display_completeness.py --data-dir data --site-dir _site'
    browser = 'python scripts/browser_data_completeness.py --url http://127.0.0.1:8000/'
    assert validator in workflow
    assert browser in workflow
    assert workflow.index(validator) < workflow.index(browser)
