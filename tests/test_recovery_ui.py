from __future__ import annotations

import json
from pathlib import Path

from v38.recovery_ui import attach_recovered_theme_ui


def _write(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj), encoding="utf-8")


def test_attach_recovered_theme_ui_projects_fine_and_major_groups(tmp_path: Path) -> None:
    session = "2026-09-11"
    _write(
        tmp_path / "theme_rotation_recovered.json",
        {
            "session_date": session,
            "status": "READY",
            "rows": [
                {
                    "major_theme": "1. AI・テック成長テーマ",
                    "theme_id": "AIサーバー/冷却",
                    "theme_name": "AIサーバー/冷却",
                    "member_count": 3,
                    "rs63_median": 98.0,
                    "rs189_median": 99.0,
                    "theme_rs": 99.0,
                    "ret20_median": 0.12,
                    "leaders": ["DELL", "HPE"],
                },
                {
                    "major_theme": "1. AI・テック成長テーマ",
                    "theme_id": "AIネットワーキング",
                    "theme_name": "AIネットワーキング",
                    "member_count": 2,
                    "rs63_median": 92.0,
                    "rs189_median": 95.0,
                    "theme_rs": 94.0,
                    "ret20_median": 0.05,
                    "leaders": ["ANET"],
                },
                {
                    "major_theme": "6. バイオ・ヘルスケア",
                    "theme_id": "ゲノミクス/シーケンシング",
                    "theme_name": "ゲノミクス/シーケンシング",
                    "member_count": 5,
                    "rs63_median": 97.0,
                    "rs189_median": 98.0,
                    "theme_rs": 97.0,
                    "ret20_median": 0.10,
                    "leaders": ["TWST", "TXG"],
                },
            ],
        },
    )
    _write(
        tmp_path / "theme_membership.json",
        {
            "session_date": session,
            "status": "READY",
            "coverage": 0.96,
            "coverage_detail": {"exact": 3000, "inferred": 200, "unmapped": 100},
        },
    )
    view = {
        "session_date": session,
        "rotation": {
            "status": "READY",
            "diagnostics": {
                "industry": [{"group": "old diagnostic"}],
                "sector": [{"group": "old diagnostic"}],
            },
        },
    }

    out = attach_recovered_theme_ui(view, tmp_path)
    rotation = out["rotation"]

    assert rotation["fine_theme_status"] == "READY"
    assert rotation["fine_theme_count"] == 3
    assert rotation["fine_theme_coverage"] == 0.96
    assert rotation["diagnostics"]["industry"][0]["group"] == "AIサーバー/冷却"
    assert rotation["diagnostics"]["industry"][0]["leaders"] == ["DELL", "HPE"]
    assert rotation["diagnostics"]["industry"][0]["theme_rs"] == 99.0
    assert rotation["diagnostics"]["sector"][0]["group"] == "1. AI・テック成長テーマ"
    assert set(rotation["diagnostics"]["sector"][0]["leaders"]) >= {"DELL", "HPE", "ANET"}


def test_attach_recovered_theme_ui_fails_closed_when_missing(tmp_path: Path) -> None:
    view = {"session_date": "2026-09-11", "rotation": {"status": "READY"}}
    out = attach_recovered_theme_ui(view, tmp_path)
    assert out["rotation"]["fine_theme_status"] == "DATA_REQUIRED"
    assert out["rotation"]["fine_theme_rows"] == []
