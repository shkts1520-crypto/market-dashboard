from __future__ import annotations

import hashlib
import re
from pathlib import Path

from .ui_contract import (
    EXPECTED_TABS,
    validate_canonical_shell,
    validate_production_html,
)

CALCULATION_VERSION = (
    "v38-safe-site-builder-1.0.0"
)

CANONICAL_BLOB_SHA = (
    "966fe157e3d35344f6e373877b3de5689409dd67"
)

CANONICAL_SIZE = 1412062

_SCRIPT_RE = re.compile(
    (
        r"<script\b[^>]*>"
        r".*?"
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

_STYLE_RE = re.compile(
    (
        r"<style\b[^>]*>"
        r".*?"
        r"</style\s*>"
    ),
    re.I | re.S,
)

_BODY_RE = re.compile(
    (
        r"<body\b"
        r"(?P<attrs>[^>]*)>"
    ),
    re.I | re.S,
)

_HEAD_END_RE = re.compile(
    r"</head\s*>",
    re.I,
)

_BODY_END_RE = re.compile(
    r"</body\s*>",
    re.I,
)

SECTION_IDS = tuple(
    href[1:]
    for _, href
    in EXPECTED_TABS
)

SHIELD_STYLE = """<style id="v38-production-shield">
body[data-v38-production="shielded"] #t-market > :not(.v38-production-state),
body[data-v38-production="shielded"] #t-alloc > :not(.v38-production-state),
body[data-v38-production="shielded"] #t-port > :not(.v38-production-state),
body[data-v38-production="shielded"] #t-rotation > :not(.v38-production-state),
body[data-v38-production="shielded"] #t-rs > :not(.v38-production-state),
body[data-v38-production="shielded"] #t-weekly > :not(.v38-production-state),
body[data-v38-production="shielded"] #t-options > :not(.v38-production-state),
body[data-v38-production="shielded"] #t-post1 > :not(.v38-production-state),
body[data-v38-production="shielded"] #t-rules > :not(.v38-production-state){visibility:hidden!important}
.v38-production-state{visibility:visible!important;min-height:84px;display:flex;flex-direction:column;justify-content:center;gap:5px}
.v38-production-state b{font-size:14px}
.v38-production-state span{font-size:11px;opacity:.75}
</style>"""

RUNTIME_SCRIPTS = (
    '<script '
    'src="assets/v38-runtime.js" '
    'defer></script>\n'
    '<script '
    'src="assets/v38-site.js" '
    'defer></script>'
)


class SiteBuildError(
    RuntimeError
):
    pass


def git_blob_sha(
    data: bytes,
) -> str:
    header = (
        f"blob {len(data)}\0"
    ).encode(
        "ascii"
    )

    return hashlib.sha1(
        header + data
    ).hexdigest()


def canonical_fingerprint(
    data: bytes,
) -> dict[str, object]:
    return {
        "size": len(data),
        "blob_sha": (
            git_blob_sha(
                data
            )
        ),
    }


def verify_canonical_bytes(
    data: bytes,
) -> None:
    fp = canonical_fingerprint(
        data
    )

    if (
        fp["size"]
        != CANONICAL_SIZE
    ):
        raise SiteBuildError(
            "canonical size mismatch: "
            f"{fp['size']} != "
            f"{CANONICAL_SIZE}"
        )

    if (
        fp["blob_sha"]
        != CANONICAL_BLOB_SHA
    ):
        raise SiteBuildError(
            "canonical blob mismatch: "
            f"{fp['blob_sha']} != "
            f"{CANONICAL_BLOB_SHA}"
        )


def _style_blocks(
    html: str,
) -> tuple[str, ...]:
    return tuple(
        _STYLE_RE.findall(
            html
        )
    )


def _strip_active_inline_logic(
    html: str,
) -> str:
    without_scripts = (
        _SCRIPT_RE.sub(
            "",
            html,
        )
    )

    return _EVENT_RE.sub(
        "",
        without_scripts,
    )


def _mark_body_shielded(
    html: str,
) -> str:
    match = _BODY_RE.search(
        html
    )

    if not match:
        raise SiteBuildError(
            "canonical body element "
            "is missing"
        )

    attrs = (
        match.group(
            "attrs"
        )
        or ""
    )

    if (
        "data-v38-production"
        in attrs
    ):
        raise SiteBuildError(
            "canonical unexpectedly "
            "already contains "
            "production marker"
        )

    replacement = (
        '<body '
        'data-v38-production="shielded"'
        f"{attrs}>"
    )

    return (
        html[
            : match.start()
        ]
        + replacement
        + html[
            match.end() :
        ]
    )


def _insert_section_state(
    html: str,
    section_id: str,
) -> str:
    pattern = re.compile(
        (
            r"(<section\b"
            r"(?=[^>]*\bid\s*=\s*"
            r"[\"']"
            + re.escape(
                section_id
            )
            + r"[\"'])"
            r"[^>]*>)"
        ),
        re.I | re.S,
    )

    state = (
        '<div '
        'class="card '
        'v38-production-state" '
        'role="status" '
        'data-v38-section="'
        f"{section_id}"
        '">'
        '<b>DATA_REQUIRED</b>'
        '<span>'
        'Authoritative data binding '
        'is not ready. '
        'Mock values are shielded.'
        '</span>'
        '</div>'
    )

    out, count = (
        pattern.subn(
            lambda m: (
                m.group(1)
                + state
            ),
            html,
            count=1,
        )
    )

    if count != 1:
        raise SiteBuildError(
            "section insertion "
            "failed: "
            f"{section_id}"
        )

    return out


def build_safe_shell(
    canonical_html: str,
) -> str:
    validate_canonical_shell(
        canonical_html
    )

    original_styles = (
        _style_blocks(
            canonical_html
        )
    )

    out = (
        _strip_active_inline_logic(
            canonical_html
        )
    )

    out = _mark_body_shielded(
        out
    )

    for section_id in (
        SECTION_IDS
    ):
        out = (
            _insert_section_state(
                out,
                section_id,
            )
        )

    if not _HEAD_END_RE.search(
        out
    ):
        raise SiteBuildError(
            "head end tag is missing"
        )

    out = _HEAD_END_RE.sub(
        (
            SHIELD_STYLE
            + "\n</head>"
        ),
        out,
        count=1,
    )

    if not _BODY_END_RE.search(
        out
    ):
        raise SiteBuildError(
            "body end tag is missing"
        )

    out = _BODY_END_RE.sub(
        (
            RUNTIME_SCRIPTS
            + "\n</body>"
        ),
        out,
        count=1,
    )

    generated_styles = tuple(
        block
        for block
        in _style_blocks(
            out
        )
        if (
            'id="v38-production-shield"'
            not in block
        )
    )

    if (
        generated_styles
        != original_styles
    ):
        raise SiteBuildError(
            "canonical style blocks "
            "changed during build"
        )

    report = (
        validate_production_html(
            out
        )
    )

    if (
        report[
            "external_script_count"
        ]
        != 2
    ):
        raise SiteBuildError(
            "production HTML must "
            "contain exactly two "
            "external scripts"
        )

    if (
        out.count(
            'class="card '
            'v38-production-state"'
        )
        != len(
            SECTION_IDS
        )
    ):
        raise SiteBuildError(
            "all nine sections "
            "must be fail-closed "
            "shielded"
        )

    if (
        'data-v38-production="shielded"'
        not in out
    ):
        raise SiteBuildError(
            "production shield "
            "marker missing"
        )

    return out


def build_site(
    canonical_path: str | Path,
    output_path: str | Path,
) -> Path:
    src = Path(
        canonical_path
    )

    raw = src.read_bytes()

    verify_canonical_bytes(
        raw
    )

    try:
        html = raw.decode(
            "utf-8"
        )

    except UnicodeDecodeError as exc:
        raise SiteBuildError(
            "canonical must be UTF-8"
        ) from exc

    out_html = build_safe_shell(
        html
    )

    dst = Path(
        output_path
    )

    dst.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    dst.write_text(
        out_html,
        encoding="utf-8",
    )

    return dst
