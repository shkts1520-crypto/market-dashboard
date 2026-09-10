import json
import pytest
from v38.nqsar_input import NQSARInputError, normalize_nqsar_text

SESSION="2026-09-08"; ASOF="2026-09-09T05:00:00+09:00"

def test_full_authoritative_json_is_normalized():
    out=normalize_nqsar_text(json.dumps({"session_date":SESSION,"generated_at":"2026-09-08T16:00:00-04:00","source":"fixture","state":"Green"}),expected_session_date=SESSION,as_of=ASOF,source_name="nqsar.json")
    assert out["state"]=="Green" and out["input_kind"]=="state"

def test_exp_state_id_json_is_normalized():
    out=normalize_nqsar_text(json.dumps({"session_date":SESSION,"generated_at":"2026-09-08T16:00:00-04:00","source":"nq.csv","exp_state_id":4}),expected_session_date=SESSION,as_of=ASOF,source_name="nqsar.json")
    assert out["state"]=="Green" and out["exp_state_id"]==4

def test_raw_sar_state_text_is_normalized():
    out=normalize_nqsar_text("2026-09-08,Blue",expected_session_date=SESSION,as_of=ASOF,source_name="sar_state.txt")
    assert out["state"]=="Blue" and out["source"]=="sar_state.txt"

def test_dated_alias_json_is_normalized():
    out=normalize_nqsar_text('{"asof":"2026-09-08","color":"red"}',expected_session_date=SESSION,as_of=ASOF,source_name="sar_state.txt")
    assert out["state"]=="Red"

@pytest.mark.parametrize("raw",["","Blue","2026-09-07,Green",'{"status":"DATA_REQUIRED","state":null}'])
def test_bad_or_unusable_inputs_fail_closed(raw):
    with pytest.raises(NQSARInputError): normalize_nqsar_text(raw,expected_session_date=SESSION,as_of=ASOF,source_name="sar_state.txt")

def test_future_generated_at_fails_closed():
    raw=json.dumps({"session_date":SESSION,"generated_at":"2026-09-10T00:00:00+09:00","source":"fixture","state":"Green"})
    with pytest.raises(NQSARInputError): normalize_nqsar_text(raw,expected_session_date=SESSION,as_of=ASOF,source_name="nqsar.json")
