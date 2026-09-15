from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_setups_and_movers_are_restored_at_build_time():
    build = (ROOT / "scripts" / "build_site.py").read_text(encoding="utf-8")
    assert 'out, "t-today", Path("assets/baseline-0905/setups.html")' in build
    assert 'out, "t-movers", Path("assets/baseline-0905/movers.html")' in build
    assert "assets/baseline-0905/setups.html" in build
    assert "assets/baseline-0905/movers.html" in build


def test_source_fragments_preserve_card_inventory():
    setups = (ROOT / "assets/baseline-0905/setups.html").read_text(encoding="utf-8")
    movers = (ROOT / "assets/baseline-0905/movers.html").read_text(encoding="utf-8")
    assert setups.count('class="card') >= 20
    for title in ("Pre-Breakout", "Confluence", "Multi VWAP", "Leaders"):
        assert title in setups
    for title in ("3窓一致", "前日", "1週間", "1ヶ月"):
        assert title in movers
    assert 'class="mv-wrap"' in movers


def test_ready_render_path_never_calls_destructive_renderers():
    site = (ROOT / "assets/v38-site.js").read_text(encoding="utf-8")
    body = site[site.index("function renderLiveView"):site.index("function renderAllUnavailable")]
    for forbidden in (
        "neutralizeCards(", "renderDaily(", "renderRs(",
        "renderGenericSection(", "renderRotation(", "renderWeekly(",
        ".replaceChildren(",
    ):
        assert forbidden not in body


def test_runtime_repair_and_owner_layers_are_not_shipped():
    build = (ROOT / "scripts" / "build_site.py").read_text(encoding="utf-8")
    for asset in (
        "v38-polish.js", "v38-recovery.js", "v38-final-ui.js",
        "v38-visual-fidelity.js", "v38-status-truth.js",
        "v38-rotation-movers-visual.js", "v38-rotation-movers-owner.js",
    ):
        assert f'_inject_external_extension(out, Path("assets/{asset}"))' not in build
