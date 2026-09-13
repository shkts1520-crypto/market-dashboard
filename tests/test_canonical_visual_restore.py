from pathlib import Path


JS = Path("assets/v38-restored-experience.js").read_text(encoding="utf-8")


def test_rotation_uses_canonical_v5_dom_vocabulary():
    for token in (
        "v38-canonical-rotation",
        "'div','hd'",
        "'span','bar'",
        "'div','read'",
        "'div','grid'",
        "prgMaj",
        "prgMin",
        "rrgwrap",
        "bump",
        "flowbody",
        "majflow",
        "leaders",
        "fnote",
        "Major Sectors · Rank by Period",
        "Rank Flow",
        "Sub-themes · Rank by Period",
        "Money Flow",
    ):
        assert token in JS


def test_rotation_no_longer_uses_bolted_on_panel_skin():
    for token in ("v38-rpanel", "v38-rgrid", "v38-cols", "v38-options-grid", "v38-opt-table"):
        assert token not in JS


def test_options_use_native_rsx_cards_without_direction_confidence():
    for token in ("card rsx-card", "rsx-item", "rsx-row", "rsx-name", "rsx-score", "rsx-sub"):
        assert token in JS
    assert "Spot・Wall・Flip・Expected Move・Quality" in JS
    assert "Direction / Confidence" not in JS


def test_vwap_scope_remains_63_252_all_time_only():
    assert "63 / 252 / All-time VWAP" in JS
    assert "63-252-all-time" in JS
    assert "189 VWAP" not in JS


def test_search_uses_original_ticker_search_vocabulary():
    for token in ("銘柄検索", "Ticker Search", "tksearch", "tkresults", "ティッカーで全ユニバースを検索（タップで詳細）"):
        assert token in JS
