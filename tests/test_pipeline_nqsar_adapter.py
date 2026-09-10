import json
from pathlib import Path
import pytest
import v38.calculate_pipeline as cp
from v38.market_engine import MarketEngineError

SESSION="2026-09-08"
GENERATED="2026-09-09T05:00:00+09:00"


def install_stage_stubs(monkeypatch, seen):
    def stocks(ohlcv, universe, stage, **kwargs):
        stage=Path(stage)
        meta={"session_date":SESSION,"generated_at":GENERATED,"coverage":1.0,"source":"fixture","schema_version":"x","calculation_version":"x"}
        (stage/"rs.json").write_text(json.dumps(meta),encoding="utf-8")
        (stage/"breadth.json").write_text(json.dumps(meta),encoding="utf-8")
        return stage/"rs.json",stage/"breadth.json"
    def f123(rs_path, output_path, **kwargs):
        meta={"session_date":SESSION,"generated_at":GENERATED,"coverage":1.0,"source":"fixture","schema_version":"x","calculation_version":"x"}
        Path(output_path).write_text(json.dumps(meta),encoding="utf-8")
    def market(rs_path,breadth_path,nqsar_path,stage,**kwargs):
        nq=json.loads(Path(nqsar_path).read_text(encoding="utf-8"))
        seen.append(nq)
        meta={"session_date":SESSION,"generated_at":GENERATED,"coverage":1.0,"source":"fixture","schema_version":"x","calculation_version":"x"}
        Path(stage,"market_state.json").write_text(json.dumps(meta),encoding="utf-8")
        Path(stage,"core12.json").write_text(json.dumps(meta),encoding="utf-8")
    monkeypatch.setattr(cp,"calculate_from_files",stocks)
    monkeypatch.setattr(cp,"calculate_f123_from_files",f123)
    monkeypatch.setattr(cp,"calculate_market_from_files",market)


def run(tmp_path,monkeypatch,raw):
    seen=[]; install_stage_stubs(monkeypatch,seen)
    nq=tmp_path/"nqsar.input"; nq.write_text(raw,encoding="utf-8")
    paths=cp.calculate_pipeline(ohlcv_path="unused",universe_path="unused",nqsar_path=nq,output_dir=tmp_path/"data",session_date=SESSION,generated_at=GENERATED,stock_source="fixture")
    return seen,paths


def test_pipeline_accepts_raw_dated_sar_state(monkeypatch,tmp_path):
    seen,paths=run(tmp_path,monkeypatch,"2026-09-08,Blue")
    assert seen[0]["state"]=="Blue" and len(paths)==5


def test_pipeline_accepts_authoritative_json(monkeypatch,tmp_path):
    raw=json.dumps({"session_date":SESSION,"generated_at":GENERATED,"source":"fixture","state":"Green"})
    seen,_=run(tmp_path,monkeypatch,raw)
    assert seen[0]["state"]=="Green"


def test_pipeline_accepts_exp_state_id(monkeypatch,tmp_path):
    raw=json.dumps({"session_date":SESSION,"generated_at":GENERATED,"source":"nq.csv","exp_state_id":3})
    seen,_=run(tmp_path,monkeypatch,raw)
    assert seen[0]["state"]=="Red"

@pytest.mark.parametrize("raw",[
    "Blue",
    "2026-09-07,Green",
    json.dumps({"status":"DATA_REQUIRED","state":None}),
])
def test_pipeline_rejects_unusable_nqsar_before_publish(monkeypatch,tmp_path,raw):
    seen=[]; install_stage_stubs(monkeypatch,seen)
    nq=tmp_path/"nqsar.input"; nq.write_text(raw,encoding="utf-8")
    out=tmp_path/"data"; out.mkdir(); sentinel=out/"rs.json"; sentinel.write_text("SENTINEL")
    with pytest.raises(MarketEngineError):
        cp.calculate_pipeline(ohlcv_path="unused",universe_path="unused",nqsar_path=nq,output_dir=out,session_date=SESSION,generated_at=GENERATED,stock_source="fixture")
    assert sentinel.read_text()=="SENTINEL" and seen==[]


def test_stale_nqsar_preserves_legacy_stale_error_contract(monkeypatch,tmp_path):
    seen=[]; install_stage_stubs(monkeypatch,seen)
    nq=tmp_path/"nqsar.json"; nq.write_text(json.dumps({"session_date":"2026-09-07","generated_at":GENERATED,"source":"fixture","state":"Green"}))
    with pytest.raises(MarketEngineError,match="STALE shard session mismatch"):
        cp.calculate_pipeline(ohlcv_path="unused",universe_path="unused",nqsar_path=nq,output_dir=tmp_path/"data",session_date=SESSION,generated_at=GENERATED,stock_source="fixture")
