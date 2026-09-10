from pathlib import Path

from v38.ui_contract import (
    EXPECTED_TABS,
)


def canonical_text():
    nav = (
        "<nav>"
        + "".join(
            (
                '<a class="tabx" '
                f'href="{href}">'
                f"{label}</a>"
            )
            for label, href
            in EXPECTED_TABS
        )
        + "</nav>"
    )

    sections = "".join(
        (
            '<section id="'
            f'{href[1:]}">'
            "</section>"
        )
        for _, href
        in EXPECTED_TABS
    )

    return (
        "<style>"
        ".card{}"
        ".chart{}"
        ".rsx-card{}"
        ".rsx-item{}"
        ".mrow{}"
        ".bflags{}"
        "</style>"
        + nav
        + sections
    )


def test_preflight_script_exists_and_is_not_a_renderer():
    script = Path(
        "scripts/preflight_ui.py"
    ).read_text(
        encoding="utf-8"
    )

    assert (
        "validate_canonical_shell"
        in script
    )

    assert (
        "CANONICAL_V5_MISSING"
        in script
    )

    assert (
        "replace("
        not in script
    )


def test_runtime_has_no_trading_rule_engine():
    js = Path(
        "assets/v38-runtime.js"
    ).read_text(
        encoding="utf-8"
    )

    for forbidden in (
        "0.92",
        "1.24",
        "0.70",
        "RS189",
        "MC57",
        "panic_seed",
    ):
        assert (
            forbidden
            not in js
        )


def test_runtime_missing_values_use_dash_not_fake_zero():
    js = Path(
        "assets/v38-runtime.js"
    ).read_text(
        encoding="utf-8"
    )

    assert (
        "return '—'"
        in js
    )

    assert (
        "|| 0"
        not in js
    )
