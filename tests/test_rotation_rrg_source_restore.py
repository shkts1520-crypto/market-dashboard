from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_rotation_rrg_is_first_source_group_and_not_hidden_by_authority() -> None:
    js = (ROOT / "assets" / "v38-py-source-authority.js").read_text(encoding="utf-8")

    rrg_label = "① ローテーションの向き（RRG）"
    rrg_card = "セクター・ローテーション（テーマETF）"
    money_label = "② どこに資金が向かっているか"

    assert "const SOURCE='build_dashboard(3).py'" in js
    assert "build_dashboard_3_py" in js
    assert rrg_label in js
    assert rrg_card in js
    assert money_label in js
    assert js.index(rrg_label) < js.index(rrg_card) < js.index(money_label)


def test_rotation_source_group_numbering_is_unique_after_rrg_restore() -> None:
    js = (ROOT / "assets" / "v38-py-source-authority.js").read_text(encoding="utf-8")
    labels = [
        "① ローテーションの向き（RRG）",
        "② どこに資金が向かっているか",
        "③ その資金は広いか、数銘柄か",
        "④ 自ユニバースで主導しているのは誰か",
        "⑤ その中で買える銘柄はどれか",
        "⑥ 一覧で確認する",
    ]
    positions = [js.index(label) for label in labels]
    assert positions == sorted(positions)
