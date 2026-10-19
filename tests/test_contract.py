import numpy as np
import pytest
from ofd import contract, schema
from tests.test_build_dataset import fake_seq
from ofd import build_dataset


def built(tmp_path):
    seq, runs = fake_seq(tmp_path)
    return build_dataset.build_sequence(seq, runs, {m: np.eye(4) for m in schema.METHODS}, "botanic", "survey")


def test_contract_ok(tmp_path):
    contract.check(built(tmp_path), schema.build_schema(schema.METHODS))


def test_contract_catches_future_source(tmp_path):
    df = built(tmp_path)
    k = df.index[df["kissicp_valid"] == 1][0]
    df.loc[k, "kissicp_src_ts"] = df.loc[k, "t"] + 1
    with pytest.raises(AssertionError, match="causal"):
        contract.check(df, schema.build_schema(schema.METHODS))


def test_contract_catches_negative_qw(tmp_path):
    df = built(tmp_path)
    k = df.index[df["stella_valid"] == 1][0]
    df.loc[k, "stella_qw"] = -0.5
    with pytest.raises(AssertionError, match="qw"):
        contract.check(df, schema.build_schema(schema.METHODS))


def test_contract_checks_sequence_identity(tmp_path):
    df = built(tmp_path)
    contract.check(df, schema.build_schema(schema.METHODS), seq=df["seq"].iat[0])
    with pytest.raises(AssertionError, match="seq"):
        contract.check(df, schema.build_schema(schema.METHODS), seq="00000")
