from __future__ import annotations

import math
from typing import Any, Iterable

import numpy as np
import pandas as pd

from .reference_gates import DATA_REQUIRED, mc57_reference_gate

CALCULATION_VERSION = "v38-mc57-diagnostics-1.0.0"
SCHEMA_VERSION = "v38.mc57.readiness.1"
CALIBRATION_LOOKBACK = 3780
EXPECTED_METRIC_COUNT = 12

MC57_METRICS = (
    "close_gt_sma10",
    "close_gt_sma20",
    "close_gt_sma50",
    "close_gt_sma200",
    "ret5_gt_0",
    "ret21_gt_0",
    "ret63_gt_0",
    "ret252_gt_0",
    "sma20_gt_sma50",
    "sma50_gt_sma200",
    "sma50_gt_sma50_shift20",
    "dd52_continuous_score",
)


class MC57Error(RuntimeError):
    """Raised when an MC57 diagnostics contract is invalid."""


def mc57_logistic(z: float) -> float:
    z = float(z)
    if not math.isfinite(z):
        return math.nan
    return 100.0 / (1.0 + 3.0 ** (-z))


def dd52_score(dd52: float | None) -> float | None:
    if dd52 is None:
        return None
    x = float(dd52)
    if not math.isfinite(x):
        return None
    return float(np.clip((x + 0.30) / 0.25 * 100.0, 0.0, 100.0))


def binary_participation(values: Iterable[Any]) -> float | None:
    scored: list[float] = []
    for value in values:
        if value is None or (
            isinstance(value, float)
            and math.isnan(value)
        ):
            continue
        if isinstance(value, (bool, np.bool_)):
            scored.append(100.0 if bool(value) else 0.0)
        else:
            raise MC57Error(
                "binary participation accepts only bool/None"
            )
    return float(np.mean(scored)) if scored else None


def continuous_participation(
    values: Iterable[float | None],
) -> float | None:
    scored: list[float] = []
    for value in values:
        if value is None:
            continue
        x = float(value)
        if math.isfinite(x):
            scored.append(x)
    return float(np.mean(scored)) if scored else None


def raw_score(
    metric_scores: dict[str, float | None],
) -> float | None:
    if set(metric_scores) != set(MC57_METRICS):
        return None
    vals = [
        metric_scores[name]
        for name in MC57_METRICS
    ]
    if any(
        v is None
        or not math.isfinite(float(v))
        for v in vals
    ):
        return None
    return float(
        np.mean(
            [float(v) for v in vals]
        )
    )


def ema2(raw: pd.Series) -> pd.Series:
    return raw.astype(float).ewm(
        span=2,
        adjust=False,
    ).mean()


def calibrate_mc57(
    raw: pd.Series,
    lookback: int = CALIBRATION_LOOKBACK,
) -> pd.DataFrame:
    if lookback < 2:
        raise MC57Error("lookback must be >=2")

    raw = raw.astype(float)
    smoothed = ema2(raw)

    prior_mean = (
        smoothed
        .shift(1)
        .rolling(
            lookback,
            min_periods=lookback,
        )
        .mean()
    )

    prior_std = (
        smoothed
        .shift(1)
        .rolling(
            lookback,
            min_periods=lookback,
        )
        .std(ddof=0)
    )

    z = (
        smoothed - prior_mean
    ) / prior_std

    z = z.where(prior_std > 0)

    mc57 = z.map(
        lambda x:
        mc57_logistic(x)
        if pd.notna(x)
        else np.nan
    )

    return pd.DataFrame(
        {
            "raw": raw,
            "ema2_raw": smoothed,
            "mu_prior": prior_mean,
            "sigma_prior": prior_std,
            "z": z,
            "mc57": mc57,
        }
    )


def readiness(
    *,
    session_date: str,
    generated_at: str,
    reference: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not session_date:
        raise MC57Error("session_date is required")
    if not generated_at:
        raise MC57Error("generated_at is required")

    gate = mc57_reference_gate(reference)

    return {
        "session_date": session_date,
        "generated_at": generated_at,
        "coverage": None,
        "source": "reference-gate:mc57",
        "schema_version": SCHEMA_VERSION,
        "calculation_version": CALCULATION_VERSION,
        "status": gate.status,
        "mc57": None,
        "raw": None,
        "ema2_raw": None,
        "mu_prior": None,
        "sigma_prior": None,
        "z": None,
        "data_required": gate.as_dict()["missing"],
        "spec": {
            "fixed_etf_count": 57,
            "metrics": list(MC57_METRICS),
            "metric_weighting": "equal",
            "ema_span": 2,
            "ema_adjust": False,
            "calibration_lookback_sessions": CALIBRATION_LOOKBACK,
            "calibration_excludes_current": True,
            "std_ddof": 0,
            "transform": "100/(1+3**(-Z))",
        },
        "reason": (
            "Fixed 57-ETF universe and MC57 golden fixture are not frozen; production MC57 must remain null."
            if gate.status == DATA_REQUIRED
            else "Reference package is present; MC57 implementation may be validated against it."
        ),
    }
