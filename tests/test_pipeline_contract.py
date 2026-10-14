import json
from pathlib import Path
import pandas as pd
import pytest
from ofd import contract

OUT = Path("data/output")


@pytest.mark.skipif(not (OUT / "schema.json").exists(), reason="sem saída real do pipeline")
def test_real_outputs_respect_contract():
    sch = json.loads((OUT / "schema.json").read_text())
    for p in OUT.glob("*.parquet"):
        contract.check(pd.read_parquet(p), sch)
