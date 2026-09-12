from pathlib import Path


def test_polish_initializes_deterministic_navigation():
    js = Path("assets/v38-polish.js").read_text(encoding="utf-8")
    assert "function initNavigation()" in js
    assert "document.documentElement.dataset.v38NavReady = 'true'" in js
    assert "function init() {\n    initNavigation();\n    waitForBinding();" in js
    assert "section.style.display = id === valid ? 'block' : 'none'" in js
    assert "section.setAttribute('aria-hidden', id === valid ? 'false' : 'true')" in js
