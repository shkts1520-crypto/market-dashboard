import pytest

from v38.ui_contract import (
    UIContractError,
    scan_production_forbidden_logic,
    validate_production_html,
)

from test_site_builder import (
    shell,
)


def test_visible_rules_text_is_not_treated_as_active_logic():
    html = shell().replace(
        "</body>",
        (
            "<p>"
            "SOXLは使わない。"
            "ATR2も使わない。"
            "</p>"
            "</body>"
        ),
    )

    assert (
        scan_production_forbidden_logic(
            html
        )
        == []
    )


def test_inline_forbidden_logic_is_detected():
    html = shell(
        (
            "<script>"
            "const x = "
            "Entry * 0.75;"
            "</script>"
        )
    )

    assert (
        scan_production_forbidden_logic(
            html
        )
    )


def test_production_validator_rejects_even_benign_inline_script():
    with pytest.raises(
        UIContractError,
        match="inline script",
    ):
        validate_production_html(
            shell(
                (
                    "<script>"
                    'console.log("ui")'
                    "</script>"
                )
            )
        )


def test_production_validator_rejects_inline_event_handler():
    with pytest.raises(
        UIContractError,
        match=(
            "inline event handlers"
        ),
    ):
        validate_production_html(
            shell(
                extra_attr=(
                    ' onclick="tab()"'
                )
            )
        )
