from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path

CANONICAL = Path('V38_Command_Center_mock_v5.html')
BINDER = Path('assets/v38-canonical-binder.js')
BROWSER = Path('scripts/browser_data_completeness.py')


class CardTitleParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.section: str | None = None
        self.section_stack: list[str | None] = []
        self.card_depth = 0
        self.card_stack: list[bool] = []
        self.capture = False
        self.parts: list[str] = []
        self.titles: dict[str, list[str]] = {}

    @staticmethod
    def attrs(items):
        return {k: (v or '') for k, v in items}

    def handle_starttag(self, tag, attrs):
        amap = self.attrs(attrs)
        if tag == 'section':
            self.section_stack.append(self.section)
            self.section = amap.get('id') or None
            if self.section:
                self.titles.setdefault(self.section, [])
        if tag == 'div':
            is_card = 'card' in set(amap.get('class', '').split())
            self.card_stack.append(is_card)
            if is_card:
                self.card_depth += 1
        if tag == 'h2' and self.section and self.card_depth:
            self.capture = True
            self.parts = []

    def handle_data(self, data):
        if self.capture:
            self.parts.append(data)

    def handle_endtag(self, tag):
        if tag == 'h2' and self.capture:
            title = ' '.join(''.join(self.parts).split())
            if title and self.section:
                self.titles[self.section].append(title)
            self.capture = False
        if tag == 'div' and self.card_stack:
            if self.card_stack.pop():
                self.card_depth -= 1
        if tag == 'section':
            self.section = self.section_stack.pop() if self.section_stack else None


def canonical_titles():
    parser = CardTitleParser()
    parser.feed(CANONICAL.read_text(encoding='utf-8'))
    return parser.titles


def test_single_binder_targets_named_canonical_cards():
    js = BINDER.read_text(encoding='utf-8')
    for needle in (
        '現在の想定ポジション', 'マーケット回復後', 'エクイティカーブ×21日EMA',
        '新規参入', '個別株スリーブ Core 12', 'RSリーダー控え',
        '資金フロー', 'セクター温度マップ', '主導セクター・業種',
        'RS189 継続性', '今週の結論', '来週の経済指標', '自分 vs QQQ',
    ):
        assert needle in js
    assert '[63,126,189].forEach' in js
    assert '`RS${period} Top10`' in js
    assert "const OPTION_BUCKETS = ['0-6','7-21','22-45','0-45'];" in js
    assert 'simpleList(c,`DTE ${bucket}`' in js


def test_single_binder_never_silently_hides_unbound_cards():
    js = BINDER.read_text(encoding='utf-8')
    assert 'UNBOUND_VISIBLE_CARD' in js
    assert 'renderFailure' in js
    assert 'hideDiagnostics' not in js
    assert 'style.display' not in js


def test_browser_gate_checks_all_eleven_tabs_and_every_visible_card():
    script = BROWSER.read_text(encoding='utf-8')
    for tab in ('#t-market','#t-alloc','#t-port','#t-today','#t-rotation','#t-movers','#t-rs','#t-weekly','#t-options','#t-post1','#t-rules'):
        assert tab in script
    assert 'visible card has no truth source' in script
    assert 'visible card binding error' in script


def test_canonical_core_sections_still_exist():
    titles = canonical_titles()
    expected = {'t-market','t-alloc','t-port','t-rotation','t-rs','t-weekly','t-options','t-post1','t-rules'}
    assert expected.issubset(titles.keys()), sorted(titles)
