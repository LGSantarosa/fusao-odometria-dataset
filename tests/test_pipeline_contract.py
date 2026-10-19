import json
from pathlib import Path
import pandas as pd
import pytest
from ofd import config, contract, schema

OUT = Path("data/output")
SEQUENCES = {"1018-00": "botanic", "1018-13": "botanic", "rellis_example": "rellis", "00000": "rellis"}


@pytest.mark.skipif(not (OUT / "schema.json").exists(), reason="sem saída real do pipeline")
def test_real_outputs_respect_contract():
    sch = json.loads((OUT / "schema.json").read_text())
    assert sorted(p.stem for p in OUT.glob("*.parquet")) == sorted(SEQUENCES), "sequências diferentes das esperadas"
    for seq, ds in SEQUENCES.items():
        df = pd.read_parquet(OUT / f"{seq}.parquet")
        assert (df["dataset"] == ds).all(), f"{seq}: dataset diferente de {ds}"
        contract.check(df, sch, max_age_ms=config.load(f"configs/{ds}/dataset.yaml").max_age_ms, seq=seq)
        csv = pd.read_csv(OUT / f"{seq}.csv", dtype=schema.CSV_DTYPE, usecols=["seq"])
        assert (csv["seq"] == seq).all(), f"{seq}: seq do CSV difere com a leitura tipada"
