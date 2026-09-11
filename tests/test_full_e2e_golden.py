from __future__ import annotations

import json
import shutil
from pathlib import Path

import pandas as pd

from v38.allocation_engine import allocate_percentages
from v38.calculate_pipeline import calculate_pipeline
from v38.market_status import normalize_market_statuses
from v38.supplemental_engine import materialize_supplemental_shards
from v38.ui_payload import build_ui_payload
from v38.ui_view_model import build_ui_view_model

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "full_e2e" / "authorities.json"


def load_fixture():
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def write_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def with_meta(fx, payload):
    out = {
        "session_date": fx["session_date"],
        "generated_at": fx["generated_at"],
        "coverage": 1.0,
    }
    out.update(payload)
    return out


def prepare_inputs(root: Path, fx):
    root.mkdir(parents=True, exist_ok=True)
    session = fx["session_date"]
    generated = fx["generated_at"]
    tickers = fx["tickers"]
    dates = pd.bdate_range(end=session, periods=260)

    rows = []
    for i, ticker in enumerate(tickers):
        for j, dt in enumerate(dates):
            if i < 24:
                close = 20.0 + i * 0.25 + (i + 1) * j * 0.03
            else:
                close = 25.0 + (i - 24) * 0.05 + j * 0.002
            rows.append(
                {
                    "ticker": ticker,
                    "date": dt.strftime("%Y-%m-%d"),
                    "open": close * 0.995,
                    "high": close * 1.01,
                    "low": close * 0.99,
                    "close": close,
                    "volume": 1_000_000,
                    "is_complete": True,
                    "split_checked": True,
                    "split_anomaly": False,
                }
            )

    ohlcv = root / "ohlcv.csv"
    universe = root / "universe.csv"
    pd.DataFrame(rows).to_csv(ohlcv, index=False)
    pd.DataFrame(
        {"ticker": tickers, "session_date": session, "in_universe": True}
    ).to_csv(universe, index=False)

    nqsar = root / "nqsar.json"
    write_json(
        nqsar,
        with_meta(fx, fx["nqsar"]),
    )

    old = dict(fx["old_top24"])
    old["rows"] = [{"ticker": ticker} for ticker in tickers[:24]]
    old_top24 = root / "old_top24.json"
    write_json(old_top24, old)

    classifications = root / "classifications.json"
    write_json(
        classifications,
        with_meta(
            fx,
            {
                "source": "fixture:clinical-classification",
                "schema_version": "v38.classifications.fixture.1",
                "calculation_version": "fixture",
                "classification_version": "fixture-v1",
                "rows": [
                    {"ticker": ticker, "structural_clinical_biotech": False}
                    for ticker in tickers
                ],
            },
        ),
    )

    theme_scores = root / "theme_scores.json"
    write_json(
        theme_scores,
        with_meta(
            fx,
            {
                "source": "fixture:peer-theme-loo",
                "schema_version": "v38.peer_theme.fixture.1",
                "calculation_version": "fixture-loo",
                "rows": [
                    {
                        "ticker": ticker,
                        "peer_theme_score": (
                            50.0 + i * 2.0 if i < 24 else 5.0 + (i - 24) * 0.1
                        ),
                        "theme": "SYNTHETIC",
                    }
                    for i, ticker in enumerate(tickers)
                ],
            },
        ),
    )

    return {
        "ohlcv": ohlcv,
        "universe": universe,
        "nqsar": nqsar,
        "old_top24": old_top24,
        "classifications": classifications,
        "theme_scores": theme_scores,
    }


def build_full(root: Path, fx):
    inputs = prepare_inputs(root / "inputs", fx)
    data = root / "data"
    calculate_pipeline(
        ohlcv_path=inputs["ohlcv"],
        universe_path=inputs["universe"],
        nqsar_path=inputs["nqsar"],
        output_dir=data,
        session_date=fx["session_date"],
        generated_at=fx["generated_at"],
        stock_source="fixture:synthetic-ohlcv",
        old_top24_path=inputs["old_top24"],
        classifications_path=inputs["classifications"],
        theme_scores_path=inputs["theme_scores"],
    )
    normalize_market_statuses(data, session_date=fx["session_date"])

    shutil.copyfile(inputs["nqsar"], data / "nqsar.json")
    shutil.copyfile(inputs["theme_scores"], data / "theme_scores.json")
    shutil.copyfile(inputs["classifications"], data / "classifications.json")

    write_json(
        data / "state.json",
        with_meta(
            fx,
            {
                "source": "fixture:state",
                "schema_version": "v38.state.fixture.1",
                "calculation_version": "fixture",
                "status": "READY",
            },
        ),
    )
    write_json(
        data / "market_inputs.json",
        with_meta(
            fx,
            {
                "source": "fixture:market-inputs",
                "schema_version": "v38.market_inputs.fixture.1",
                "calculation_version": "fixture",
                "series": {
                    symbol: [{"date": fx["session_date"], "close": 100.0 + i}]
                    for i, symbol in enumerate(("QQQ", "TQQQ", "^VIX", "NQ=F", "SPY"))
                },
            },
        ),
    )
    write_json(data / "mc57.json", with_meta(fx, fx["mc57"]))
    write_json(data / "options" / "index.json", with_meta(fx, fx["options"]))
    write_json(data / "positions_ledger.json", with_meta(fx, fx["positions_ledger"]))
    write_json(
        data / "macro.json",
        with_meta(fx, fx["macro"]),
    )
    write_json(
        data / "prior_state.json",
        with_meta(fx, fx["prior_state"]),
    )

    materialize_supplemental_shards(
        data,
        session_date=fx["session_date"],
        generated_at=fx["generated_at"],
        theme_scores_path=data / "theme_scores.json",
        positions_ledger_path=data / "positions_ledger.json",
    )
    normalize_market_statuses(data, session_date=fx["session_date"])

    payload = build_ui_payload(
        data,
        generated_at=fx["generated_at"],
        target_session=fx["session_date"],
    )
    view = build_ui_view_model(data)
    return data, payload, view


def test_full_e2e_golden_reaches_nine_tab_ready_without_mock_values(tmp_path):
    fx = load_fixture()
    data, payload, view = build_full(tmp_path, fx)
    expected = fx["expected"]

    market = json.loads((data / "market_state.json").read_text())
    core = json.loads((data / "core12.json").read_text())
    f123 = json.loads((data / "f123.json").read_text())
    positions = json.loads((data / "positions.json").read_text())
    publish = json.loads((data / "publish.json").read_text())

    assert market["market_mode"] == expected["market_mode"]
    assert market["max_new_total_slots"] == expected["max_new_total_slots"]
    assert market["status"] == "READY"
    assert core["status"] == "READY"
    assert core["ranking"][0]["ticker"] == expected["core12_first_ticker"]
    assert f123["f1"]["status"] == expected["f1_status"]
    assert f123["f1"]["value"] == expected["f1_value"]
    assert positions["rows"][0]["next_open_action"]["action"] == expected["positions_first_action"]
    assert publish["full_v38_ready"] is expected["publish_full_v38_ready"]
    assert payload["status"] == expected["ui_payload_status"]

    assert set(
        key for key in view
        if key in {"daily", "positions", "core12", "rotation", "rs", "weekly", "options", "publish", "rules"}
    ) == {"daily", "positions", "core12", "rotation", "rs", "weekly", "options", "publish", "rules"}
    assert all(
        view[key]["status"] == "READY"
        for key in ("daily", "positions", "core12", "rotation", "rs", "weekly", "options", "publish", "rules")
    )

    assert json.loads((data / "macro.json").read_text())["values"]["DGS10"] == 4.0
    assert json.loads((data / "prior_state.json").read_text())["previous_session_date"] == "2026-09-04"

    gross = allocate_percentages(
        reset_desired_pct=11.6,
        tqqq_desired_pct=80,
        normal_stock_desired_pct=70,
    )
    assert gross["share_level"]["status"] == expected["gross_share_level_status"]
    assert gross["allocated"]["gross_pct"] == 100.0


def test_full_e2e_golden_is_byte_deterministic_for_fixed_inputs(tmp_path):
    fx = load_fixture()
    data1, payload1, view1 = build_full(tmp_path / "one", fx)
    data2, payload2, view2 = build_full(tmp_path / "two", fx)

    for name in (
        "rs.json",
        "breadth.json",
        "f123.json",
        "market_state.json",
        "core12.json",
        "positions.json",
        "rotation.json",
        "weekly.json",
        "rules.json",
        "publish.json",
    ):
        assert (data1 / name).read_bytes() == (data2 / name).read_bytes()
    assert payload1 == payload2
    assert view1 == view2