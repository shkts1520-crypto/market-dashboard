import math

import numpy as np
import pandas as pd
import pytest

from v38.mc57_engine import (
    MC57_METRICS,
    binary_participation,
    calibrate_mc57,
    continuous_participation,
    dd52_score,
    ema2,
    mc57_logistic,
    raw_score,
    readiness,
)


def test_logistic_exact_anchor_points():
    assert mc57_logistic(-1) == pytest.approx(
        25.0,
        abs=1e-10,
    )

    assert mc57_logistic(0) == pytest.approx(
        50.0,
        abs=1e-10,
    )

    assert mc57_logistic(1) == pytest.approx(
        75.0,
        abs=1e-10,
    )


def test_dd52_continuous_score_clips_to_zero_and_hundred():
    assert dd52_score(-0.30) == 0.0
    assert dd52_score(-0.05) == 100.0

    assert dd52_score(
        -0.175
    ) == pytest.approx(
        50.0
    )


def test_binary_participation_excludes_missing_from_denominator():
    assert binary_participation(
        [
            True,
            True,
            False,
            None,
        ]
    ) == pytest.approx(
        200 / 3
    )


def test_continuous_participation_ignores_missing_and_nan():
    assert continuous_participation(
        [
            0.0,
            50.0,
            100.0,
            None,
            math.nan,
        ]
    ) == 50.0


def test_raw_score_is_equal_weight_across_exact_12_metrics():
    scores = {
        name: float(i)
        for i, name
        in enumerate(
            MC57_METRICS,
            start=1,
        )
    }

    assert raw_score(
        scores
    ) == pytest.approx(
        6.5
    )


def test_raw_score_returns_none_when_any_metric_missing():
    scores = {
        name: 50.0
        for name
        in MC57_METRICS
    }

    scores.pop(
        MC57_METRICS[-1]
    )

    assert raw_score(scores) is None


def test_ema2_uses_span_two_adjust_false():
    s = pd.Series(
        [
            0.0,
            100.0,
            100.0,
        ]
    )

    expected = s.ewm(
        span=2,
        adjust=False,
    ).mean()

    pd.testing.assert_series_equal(
        ema2(s),
        expected,
    )


def test_calibration_excludes_current_and_uses_ddof_zero():
    raw = pd.Series(
        [
            10.0,
            20.0,
            30.0,
            40.0,
            80.0,
        ]
    )

    out = calibrate_mc57(
        raw,
        lookback=4,
    )

    prior = ema2(raw).iloc[:4]

    assert out.loc[
        4,
        "mu_prior",
    ] == pytest.approx(
        prior.mean()
    )

    assert out.loc[
        4,
        "sigma_prior",
    ] == pytest.approx(
        prior.std(ddof=0)
    )


def test_calibration_is_null_when_history_insufficient_or_sigma_zero():
    short = calibrate_mc57(
        pd.Series(
            [
                1.0,
                2.0,
                3.0,
            ]
        ),
        lookback=4,
    )

    assert short["mc57"].isna().all()

    flat = calibrate_mc57(
        pd.Series(
            [5.0] * 6
        ),
        lookback=4,
    )

    assert np.isnan(
        flat.loc[
            4,
            "mc57",
        ]
    )


def test_mc57_readiness_never_guesses_fixed_57_universe():
    out = readiness(
        session_date="2026-09-08",
        generated_at="2026-09-10T19:00:00+09:00",
    )

    assert out["status"] == "DATA_REQUIRED"
    assert out["mc57"] is None

    assert (
        "FIXED_57_ETF_UNIVERSE"
        in out["data_required"]
    )
