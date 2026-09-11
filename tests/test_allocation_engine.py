import pytest

from v38.allocation_engine import AllocationError, allocate_percentages


def test_normal_30_tqqq_70_stock_fills_gross100():
    out = allocate_percentages(
        reset_desired_pct=0,
        tqqq_desired_pct=30,
        normal_stock_desired_pct=70,
    )
    a = out["allocated"]
    assert a["reset_pct"] == 0
    assert a["tqqq_protected_pct"] == 30
    assert a["normal_stock_pct"] == 70
    assert a["tqqq_extra_pct"] == 0
    assert a["gross_pct"] == 100
    assert a["cash_pct"] == 0


def test_reset_is_allocated_before_tqqq_and_normal_stock():
    out = allocate_percentages(
        reset_desired_pct=11.6,
        tqqq_desired_pct=80,
        normal_stock_desired_pct=70,
    )
    a = out["allocated"]
    assert a["reset_pct"] == pytest.approx(11.6)
    assert a["tqqq_protected_pct"] == pytest.approx(80.0)
    assert a["normal_stock_pct"] == pytest.approx(8.4)
    assert a["gross_pct"] == pytest.approx(100.0)


def test_tqqq_above_80_is_extra_and_only_after_normal_stock():
    out = allocate_percentages(
        reset_desired_pct=0,
        tqqq_desired_pct=100,
        normal_stock_desired_pct=15,
    )
    a = out["allocated"]
    assert a["tqqq_protected_pct"] == 80
    assert a["normal_stock_pct"] == 15
    assert a["tqqq_extra_pct"] == 5
    assert a["tqqq_total_pct"] == 85
    assert a["gross_pct"] == 100


def test_reset_can_consume_all_gross_without_overflow():
    out = allocate_percentages(
        reset_desired_pct=120,
        tqqq_desired_pct=80,
        normal_stock_desired_pct=70,
    )
    a = out["allocated"]
    assert a["reset_pct"] == 100
    assert a["tqqq_total_pct"] == 0
    assert a["normal_stock_pct"] == 0
    assert a["gross_pct"] == 100


def test_share_level_execution_remains_data_required():
    out = allocate_percentages(
        reset_desired_pct=0,
        tqqq_desired_pct=30,
        normal_stock_desired_pct=20,
    )
    assert out["share_level"]["status"] == "DATA_REQUIRED"
    assert "share_rounding" in out["share_level"]["unresolved"]


def test_bad_percentage_rejected():
    with pytest.raises(AllocationError):
        allocate_percentages(
            reset_desired_pct=-1,
            tqqq_desired_pct=30,
            normal_stock_desired_pct=70,
        )
