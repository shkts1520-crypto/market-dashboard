from pathlib import Path


PRODUCTION = Path(".github/workflows/production.yml")
SOURCE = Path(".github/workflows/source-mc57-clone.yml")
LIVE = Path("src/v38/live_acquisition.py")


def test_production_uses_distinct_80pct_acquisition_and_98pct_publication_guards():
    live = LIVE.read_text(encoding="utf-8")
    workflow = PRODUCTION.read_text(encoding="utf-8")
    assert "MIN_CURRENT_FETCH_COVERAGE = 0.80" in live
    assert "MIN_PUBLICATION_STOCK_COVERAGE = 0.98" in live
    assert "assert float(rs['coverage']) >= 0.98" in workflow


def test_retain_mode_does_not_mutate_live_data():
    workflow = PRODUCTION.read_text(encoding="utf-8")
    for step in (
        "Calculate fixed-57 MC57",
        "Recover remaining non-options live inputs",
        "Calculate live options positioning",
        "Commit scheduled or manually acquired data",
    ):
        start = workflow.index(f"- name: {step}")
        tail = workflow[start : start + 420]
        assert "steps.session-mode.outputs.mode == 'acquire'" in tail, (step, tail)


def test_publication_requires_full_v38_ready_and_zero_blockers():
    workflow = PRODUCTION.read_text(encoding="utf-8")
    assert "assert publish.get('full_v38_ready') is True" in workflow
    assert "assert publish.get('blockers') == []" in workflow


def test_production_rechecks_latest_main_after_concurrency_wait():
    workflow = PRODUCTION.read_text(encoding="utf-8")
    assert "cancel-in-progress: ${{ github.event_name == 'push' }}" in workflow
    assert "ref: ${{ github.event_name == 'pull_request' && github.event.pull_request.head.sha || 'main' }}" in workflow


def test_source_mc57_has_no_independent_schedule_or_push_deploy():
    workflow = SOURCE.read_text(encoding="utf-8")
    trigger = workflow.split("permissions:", 1)[0]
    assert "\n  workflow_run:" in trigger
    assert "\n  workflow_dispatch:" in trigger
    assert "\n  schedule:" not in trigger
    assert "\n  push:" not in trigger


def test_source_mc57_never_falls_back_to_full_universe_yahoo_download():
    workflow = SOURCE.read_text(encoding="utf-8")
    assert "download_stock_ohlcv(" not in workflow
    assert "Refusing a duplicate full-universe Yahoo acquisition" in workflow
    assert "prepare_source_clone_from_production.py" in workflow
    assert "reused same-session preservation" in workflow


def test_source_mc57_has_js_and_real_browser_gates():
    workflow = SOURCE.read_text(encoding="utf-8")
    for asset in (
        "assets/source-mc57-options-tab.js",
        "assets/source-mc57-restored-chart.js",
        "assets/source-mc57-tradingview-fallback.js",
    ):
        assert f"node --check {asset}" in workflow
    assert "browser_source_mc57_acceptance.py" in workflow
    assert "playwright install --with-deps chromium" in workflow


def test_production_checks_canonical_and_source_extension_javascript():
    workflow = PRODUCTION.read_text(encoding="utf-8")
    assert "node --check assets/v38-canonical-binder.js" in workflow
    assert "node --check assets/source-mc57-options-tab.js" in workflow


def test_retain_rebuild_recovers_exact_session_display_observations():
    workflow = PRODUCTION.read_text(encoding="utf-8")
    assert "Restore retained display observations" in workflow
    assert "validate_retained_display_observations" in workflow
    assert "display_observations.json" in workflow
    assert "github-pages" in workflow
    assert "ui_view_model.json" in workflow


def test_acquire_commit_persists_display_observations_and_rejects_stale_main():
    workflow = PRODUCTION.read_text(encoding="utf-8")
    assert "data/display_observations.json" in workflow
    assert 'BASE_SHA="$(git rev-parse HEAD)"' in workflow
    assert 'git fetch --no-tags --depth=1 origin main' in workflow
    assert 'REMOTE_SHA="$(git rev-parse origin/main)"' in workflow
    assert 'if [ "$REMOTE_SHA" != "$BASE_SHA" ]; then' in workflow
    assert "refusing stale data commit/push" in workflow
