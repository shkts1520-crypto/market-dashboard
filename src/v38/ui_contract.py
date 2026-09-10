from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Any

EXPECTED_TABS = (
    ("Daily", "#t-market"),
    ("Positions", "#t-alloc"),
    ("Core 12", "#t-port"),
    ("Rotation", "#t-rotation"),
    ("RS", "#t-rs"),
    ("Weekly", "#t-weekly"),
    ("Options", "#t-options"),
    ("Publish", "#t-post1"),
    ("Rules", "#t-rules"),
)

FORBIDDEN_TABS = {
    "Setups",
    "Movers",
}

REQUIRED_VISUAL_TOKENS = (
    ".card",
    ".chart",
    ".rsx-card",
    ".rsx-item",
    ".mrow",
    ".bflags",
)

PRODUCTION_FORBIDDEN_PATTERNS = (
    r"Entry\s*\*\s*0\.75",
    r"entry\s*\*\s*0\.75",
    r"TQQQ\s*/\s*SOXL",
    r"隔週リバランス",
    r"21EMA.*Exit",
    r"10SMA.*Exit",
    r"ATR2",
    r"建値Stop",
)

_SCRIPT_RE = re.compile(
    (
        r"<script\b"
        r"(?P<attrs>[^>]*)>"
        r"(?P<body>.*?)"
        r"</script\s*>"
    ),
    re.I | re.S,
)

_EVENT_RE = re.compile(
    (
        r"\s+on[a-zA-Z0-9_-]+"
        r"\s*=\s*"
        r"(?:"
        r"\"[^\"]*\""
        r"|'[^']*'"
        r"|[^\s>]+"
        r")"
    ),
    re.I | re.S,
)

_SRC_RE = re.compile(
    r"\bsrc\s*=",
    re.I,
)


class UIContractError(RuntimeError):
    pass


class _NavParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(
            convert_charrefs=True
        )

        self.in_nav = 0
        self.capture_anchor = False
        self.anchor_href: str | None = None
        self.anchor_text: list[str] = []
        self.tabs: list[
            tuple[str, str | None]
        ] = []
        self.section_ids: set[str] = set()

    def handle_starttag(
        self,
        tag: str,
        attrs: list[
            tuple[str, str | None]
        ],
    ) -> None:
        amap = dict(attrs)

        if tag == "nav":
            self.in_nav += 1

        elif (
            tag == "section"
            and amap.get("id")
        ):
            self.section_ids.add(
                str(amap["id"])
            )

        elif (
            tag == "a"
            and self.in_nav
        ):
            classes = set(
                (
                    amap.get("class")
                    or ""
                ).split()
            )

            if "tabx" in classes:
                self.capture_anchor = True
                self.anchor_href = (
                    amap.get("href")
                )
                self.anchor_text = []

    def handle_data(
        self,
        data: str,
    ) -> None:
        if self.capture_anchor:
            self.anchor_text.append(
                data
            )

    def handle_endtag(
        self,
        tag: str,
    ) -> None:
        if (
            tag == "a"
            and self.capture_anchor
        ):
            label = " ".join(
                "".join(
                    self.anchor_text
                ).split()
            )

            self.tabs.append(
                (
                    label,
                    self.anchor_href,
                )
            )

            self.capture_anchor = False
            self.anchor_href = None
            self.anchor_text = []

        elif (
            tag == "nav"
            and self.in_nav
        ):
            self.in_nav -= 1


def inspect_shell(
    html: str,
) -> dict[str, Any]:
    if (
        not isinstance(
            html,
            str,
        )
        or not html.strip()
    ):
        raise UIContractError(
            "HTML is empty"
        )

    parser = _NavParser()
    parser.feed(html)

    expected = list(
        EXPECTED_TABS
    )

    missing_visual = [
        token
        for token
        in REQUIRED_VISUAL_TOKENS
        if token not in html
    ]

    missing_sections = [
        href[1:]
        for _, href
        in EXPECTED_TABS
        if href[1:]
        not in parser.section_ids
    ]

    forbidden_present = [
        label
        for label, _
        in parser.tabs
        if label
        in FORBIDDEN_TABS
    ]

    return {
        "tabs": parser.tabs,
        "tabs_exact": (
            parser.tabs
            == expected
        ),
        "forbidden_tabs": (
            forbidden_present
        ),
        "missing_sections": (
            missing_sections
        ),
        "missing_visual_tokens": (
            missing_visual
        ),
    }


def validate_canonical_shell(
    html: str,
) -> dict[str, Any]:
    report = inspect_shell(
        html
    )

    problems: list[str] = []

    if not report["tabs_exact"]:
        problems.append(
            "tabs must equal "
            f"{list(EXPECTED_TABS)!r}; "
            f"got {report['tabs']!r}"
        )

    if report["forbidden_tabs"]:
        problems.append(
            "forbidden tabs present: "
            f"{report['forbidden_tabs']}"
        )

    if report["missing_sections"]:
        problems.append(
            "missing tab sections: "
            f"{report['missing_sections']}"
        )

    if report[
        "missing_visual_tokens"
    ]:
        problems.append(
            "missing v5 visual tokens: "
            f"{report['missing_visual_tokens']}"
        )

    if problems:
        raise UIContractError(
            "; ".join(
                problems
            )
        )

    return report


def active_logic_fragments(
    html: str,
) -> list[str]:
    """
    Return executable inline fragments only.

    Visible document prose is deliberately
    excluded from legacy-logic scanning.
    """
    fragments: list[str] = []

    for match in (
        _SCRIPT_RE.finditer(
            html
        )
    ):
        if not _SRC_RE.search(
            match.group(
                "attrs"
            )
            or ""
        ):
            fragments.append(
                match.group(
                    "body"
                )
                or ""
            )

    for match in (
        _EVENT_RE.finditer(
            html
        )
    ):
        fragments.append(
            match.group(0)
        )

    return fragments


def inspect_active_logic(
    html: str,
) -> dict[str, int]:
    inline_scripts = 0
    external_scripts = 0

    for match in (
        _SCRIPT_RE.finditer(
            html
        )
    ):
        if _SRC_RE.search(
            match.group(
                "attrs"
            )
            or ""
        ):
            external_scripts += 1
        else:
            inline_scripts += 1

    return {
        "inline_script_count": (
            inline_scripts
        ),
        "external_script_count": (
            external_scripts
        ),
        "inline_event_handler_count": (
            len(
                _EVENT_RE.findall(
                    html
                )
            )
        ),
    }


def scan_production_forbidden_logic(
    html: str,
) -> list[str]:
    active = "\n".join(
        active_logic_fragments(
            html
        )
    )

    hits: list[str] = []

    for pattern in (
        PRODUCTION_FORBIDDEN_PATTERNS
    ):
        if re.search(
            pattern,
            active,
            flags=(
                re.I
                | re.S
            ),
        ):
            hits.append(
                pattern
            )

    return hits


def validate_production_html(
    html: str,
) -> dict[str, Any]:
    report = (
        validate_canonical_shell(
            html
        )
    )

    active = inspect_active_logic(
        html
    )

    if active[
        "inline_script_count"
    ]:
        raise UIContractError(
            "production HTML must not "
            "contain inline script"
        )

    if active[
        "inline_event_handler_count"
    ]:
        raise UIContractError(
            "production HTML must not "
            "contain inline event handlers"
        )

    hits = (
        scan_production_forbidden_logic(
            html
        )
    )

    if hits:
        raise UIContractError(
            "legacy/forbidden "
            "production logic found: "
            f"{hits}"
        )

    return {
        **report,
        **active,
    }


def display_value(
    value: Any,
    *,
    decimals: int | None = None,
) -> str:
    if (
        value is None
        or value == ""
    ):
        return "—"

    if isinstance(
        value,
        bool,
    ):
        return (
            "true"
            if value
            else "false"
        )

    if isinstance(
        value,
        float,
    ):
        if (
            value != value
            or value
            in (
                float("inf"),
                float("-inf"),
            )
        ):
            return "—"

    if (
        isinstance(
            value,
            (int, float),
        )
        and decimals
        is not None
    ):
        return f"{float(value):.{decimals}f}"

    return str(value)
