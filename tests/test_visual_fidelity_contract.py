from pathlib import Path

BINDER = Path("assets/v38-canonical-binder.js").read_text(encoding="utf-8")


def test_sparklines_keep_source_format_contract():
    assert "const W = 680, H = 68, P = 6" in BINDER
    assert "classList.add('spark', 'v38-canonical-spark')" in BINDER
    assert "stop-opacity','0.28'" in BINDER
    assert "stroke-width','2'" in BINDER
    assert "dot.setAttribute('r','3.2')" in BINDER
    assert ".v38-canonical-spark{width:100%;height:34px" in BINDER


def test_publish_cards_are_fixed_1680_by_1080_live_cards():
    assert "width:1680px;height:1080px" in BINDER
    assert "aspect-ratio:1680/1080" in BINDER
    assert "publishOverviewHtml(view)" in BINDER
    assert "publishRotationHtml(view)" in BINDER
    assert "ensurePublishControls" in BINDER
    assert "frame.srcdoc=srcdoc" in BINDER
    assert "wraps[index].replaceChildren()" not in BINDER
    assert "V38 MARKET OVERVIEW" not in BINDER
    assert ".postwrap.fs .pfsbtn{visibility:hidden;opacity:0;pointer-events:none}" in BINDER
    assert ".postwrap.fs .pfsbtn{display:none}" not in BINDER


def test_ticker_links_do_not_use_browser_button_chrome():
    assert ".v38-ticker-link{appearance:none;-webkit-appearance:none;border:0;background:transparent" in BINDER


def test_missing_core_rank_is_not_fabricated_or_printed_as_rank_dash():
    assert "Rank ${r.rank ?? '—'}" not in BINDER
    assert "Rank ${r.rank??'—'}" not in BINDER


def test_core12_liquidity_utility_is_bound_not_left_as_blank_card():
    assert "function bindLiquidityUtility(sectionId, source)" in BINDER
    assert "bindLiquidityUtility('t-port','data/ui_view_model.json.core12.rows')" in BINDER
    assert "bindLiquidityUtility('t-today','data/ui_view_model.json.setups')" in BINDER
    assert "ddv20:r.ddv20" in BINDER
