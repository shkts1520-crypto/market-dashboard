from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path


CANONICAL = Path("V38_Command_Center_mock_v5.html")
SITE_JS = Path("assets/v38-site.js")
REPAIR_JS = Path("assets/v38-data-repair.js")


class CardTitleParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.section_stack: list[str | None] = []
        self.current_section: str | None = None
        self.div_card_stack: list[bool] = []
        self.card_depth = 0
        self.capture_h2 = False
        self.h2_parts: list[str] = []
        self.titles: dict[str, list[str]] = {}

    @staticmethod
    def _attrs(attrs: list[tuple[str, str | None]]) -> dict[str, str]:
        return {k: (v or "") for k, v in attrs}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        amap = self._attrs(attrs)
        if tag == "section":
            self.section_stack.append(self.current_section)
            self.current_section = amap.get("id") or None
            if self.current_section:
                self.titles.setdefault(self.current_section, [])
        if tag == "div":
            classes = set(amap.get("class", "").split())
            is_card = "card" in classes
            self.div_card_stack.append(is_card)
            if is_card:
                self.card_depth += 1
        if tag == "h2" and self.current_section and self.card_depth > 0:
            self.capture_h2 = True
            self.h2_parts = []

    def handle_data(self, data: str) -> None:
        if self.capture_h2:
            self.h2_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "h2" and self.capture_h2:
            title = " ".join("".join(self.h2_parts).split())
            if title and self.current_section:
                self.titles.setdefault(self.current_section, []).append(title)
            self.capture_h2 = False
            self.h2_parts = []
        if tag == "div" and self.div_card_stack:
            if self.div_card_stack.pop():
                self.card_depth -= 1
        if tag == "section":
            self.current_section = self.section_stack.pop() if self.section_stack else None


def canonical_titles() -> dict[str, list[str]]:
    parser = CardTitleParser()
    parser.feed(CANONICAL.read_text(encoding="utf-8"))
    return parser.titles


def preferred_bindings() -> dict[str, str]:
    js = SITE_JS.read_text(encoding="utf-8")
    match = re.search(r"const PREFERRED_CARD_TITLES\s*=\s*\{(?P<body>.*?)\};", js, re.S)
    assert match, "PREFERRED_CARD_TITLES not found"
    return {
        key: value
        for key, value in re.findall(r"([A-Za-z0-9_]+)\s*:\s*'([^']+)'", match.group("body"))
    }


def test_preferred_bindings_exist_in_canonical_v5() -> None:
    titles = canonical_titles()
    section_for = {
        "positions": "t-alloc",
        "core12": "t-port",
        "rotation": "t-rotation",
        "weekly": "t-weekly",
        "options": "t-options",
    }
    errors: list[str] = []
    for key, preferred in preferred_bindings().items():
        section = section_for[key]
        available = titles.get(section, [])
        if not any(preferred in title for title in available):
            errors.append(
                f"{key} -> {preferred!r} is not a canonical card in {section}; "
                f"canonical titles={available!r}"
            )
    assert not errors, "\n".join(errors)


def test_repair_targets_are_named_canonical_cards() -> None:
    titles = canonical_titles()
    required = {
        "t-market": ("MC57推移",),
        "t-alloc": (
            "現在の想定ポジション",
            "マーケット回復後のポジション入り銘柄",
            "エクイティカーブ×21日EMA",
        ),
        "t-port": ("レジーム警戒灯", "新規参入（ポート候補36位圏）", "個別株スリーブ", "RSリーダー控え"),
        "t-rotation": ("サブテーマ別RS",),
        "t-rs": (
            "RS63 Top10", "RS126 Top10", "RS189 Top10", "RS189 継続性",
            "RSマルチタイムフレーム比較", "三窓一致リーダー", "Top10 IN / OUT履歴",
        ),
        "t-weekly": ("今週の結論", "今週の変化", "週次騰落ボード", "自分 vs QQQ円建て"),
        "t-options": ("0–6 DTE", "7–21 DTE", "22–45 DTE", "0–45 DTE"),
    }
    errors: list[str] = []
    for section, needles in required.items():
        available = titles.get(section, [])
        for needle in needles:
            if not any(needle in title for title in available):
                errors.append(f"{section}: missing canonical card {needle!r}; titles={available!r}")
    assert not errors, "\n".join(errors)


def test_repair_never_targets_cards_by_position() -> None:
    js = REPAIR_JS.read_text(encoding="utf-8")
    assert "Number.isInteger(index)" not in js
    assert not re.search(r"cardByTitle\([^\n]+,\s*['\"]['\"]\s*,", js)
    assert "v38CanonicalTitle" in js
    assert "v38BindingKey" in js


def test_repair_restores_canonical_headings_instead_of_inventing_titles() -> None:
    js = REPAIR_JS.read_text(encoding="utf-8")
    assert "heading.cloneNode(true)" in js
    assert "restoreAllCanonicalHeadings" in js
    assert "h2.textContent = title" not in js


def test_canonical_has_exact_nine_production_sections() -> None:
    titles = canonical_titles()
    expected = {
        "t-market", "t-alloc", "t-port", "t-rotation", "t-rs",
        "t-weekly", "t-options", "t-post1", "t-rules",
    }
    assert expected.issubset(titles.keys()), sorted(titles)
