from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load_materializer():
    path = ROOT / "scripts" / "materialize_py_source_display.py"
    spec = importlib.util.spec_from_file_location("materialize_py_source_display", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_uploaded_py_owns_every_non_options_tab() -> None:
    js = (ROOT / "assets" / "v38-py-source-authority.js").read_text(encoding="utf-8")
    css = (ROOT / "assets" / "v38-py-source-authority.css").read_text(encoding="utf-8")
    guard = (ROOT / "assets" / "v38-py-source-guard.css").read_text(encoding="utf-8")

    for section_id in (
        "t-market", "t-alloc", "t-port", "t-today", "t-rotation",
        "t-movers", "t-rs", "t-weekly", "t-post1", "t-rules",
    ):
        assert section_id in js
    assert "const NON_OPTIONS" in js
    assert "'t-options'" not in js.split("const NON_OPTIONS", 1)[1].split("];", 1)[0]
    assert "section:not(#t-options)" in css
    assert "section:not(#t-options)" in guard


def test_rotation_order_is_the_uploaded_py_order() -> None:
    js = (ROOT / "assets" / "v38-py-source-authority.js").read_text(encoding="utf-8")
    labels = [
        "① どこに資金が向かっているか",
        "② その資金は広いか、数銘柄か",
        "③ 自ユニバースで主導しているのは誰か",
        "④ その中で買える銘柄はどれか",
        "⑤ 一覧で確認する",
    ]
    positions = [js.index(label) for label in labels]
    assert positions == sorted(positions)
    for card in (
        "資金フロー", "セクター温度マップ", "指数と中身の乖離",
        "主導セクター・業種", "強い業種の主導株", "セクターETF強弱", "サブテーマ別RS",
    ):
        assert card in js


def test_build_disables_previous_visual_reinterpretation() -> None:
    build = (ROOT / "scripts" / "build_site.py").read_text(encoding="utf-8")
    assert 'Path("assets/v38-py-source-authority.css")' in build
    assert 'Path("assets/v38-py-source-guard.css")' in build
    assert 'Path("assets/v38-py-source-authority.js")' in build
    assert 'Path("assets/v38-source-fidelity.css")' not in build
    assert 'Path("assets/v38-visual-polish.js")' not in build
    assert 'options_ui_authority": "current_options_implementation"' in build
    assert 'trading_logic_changed": False' in build


def test_f1_display_reconstruction_is_non_gating_and_exact_20_session(tmp_path: Path) -> None:
    module = _load_materializer()
    history_dir = tmp_path / "history"
    history_dir.mkdir()

    snapshots = []
    for day in range(21):
        rows = []
        for rank in range(1, 25):
            ticker = f"T{rank:02d}"
            current_rank = 40 if day == 20 and ticker == "T01" else rank
            rows.append({"ticker": ticker, "rank": current_rank})
        snapshots.append({"date": f"2026-08-{day + 1:02d}", "windows": {"189": rows}})
    (history_dir / "rs_history.json").write_text(
        json.dumps({"snapshots": snapshots}), encoding="utf-8"
    )

    result = module.f1_display(
        tmp_path,
        "2026-08-21",
        {"f1": {"value": None, "status": "DATA_REQUIRED"}},
    )
    assert result["status"] == "READY"
    assert result["display_only"] is True
    assert result["baseline_session"] == "2026-08-01"
    assert result["current_session"] == "2026-08-21"
    assert result["denominator"] == 24
    assert result["drop_count"] == 1
    assert result["value"] == 1 / 24
    assert result["reason"] == "STRICT_PIT_UNAVAILABLE_DISPLAY_ONLY"


def test_vix_source_adapter_restores_lwma_series(tmp_path: Path) -> None:
    module = _load_materializer()
    history_dir = tmp_path / "history"
    history_dir.mkdir()
    rows = [
        {"date": f"2026-09-{day:02d}", "vix": 14.0 + day / 10.0}
        for day in range(1, 16)
    ]
    (history_dir / "vix_fear_cycle.json").write_text(
        json.dumps({
            "current": {
                "vix": 17.2, "high": 18.03, "lwma5": 17.932, "lwma10": 17.185455,
                "plus1_sigma": 33.173301, "plus2_sigma": 47.658412,
            },
            "state": "NORMAL",
            "series": rows,
        }),
        encoding="utf-8",
    )

    result = module.vix_display(tmp_path)
    assert result["status"] == "READY"
    assert result["state"] == "NORMAL"
    assert len(result["rows"]) == 15
    assert result["rows"][-1]["lwma5"] is not None
    assert result["rows"][-1]["lwma10"] is not None
    assert result["current"]["plus1_sigma"] == 33.173301
    assert result["current"]["plus2_sigma"] == 47.658412


def test_machine_source_keys_are_not_public_display_values() -> None:
    js = (ROOT / "assets" / "v38-py-source-authority.js").read_text(encoding="utf-8")
    assert "SOURCE_DEFINED_" in js
    assert "観測中" in js
    assert "SOURCE_UNAVAILABLE" in js
    assert "未取得" in js
