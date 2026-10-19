"""Output contract checks shared by the synthetic E2E test and the real-output test."""
import numpy as np

from ofd import schema as sch


def check(df, schema, max_age_ms=100.0, seq=None):
    assert list(df.columns) == list(schema), "colunas diferentes do schema"
    if seq is not None:
        assert (df["seq"].astype(str) == seq).all(), f"seq diferente de {seq!r}"
    sch.assert_no_leak(schema)
    t = df["t"].to_numpy(np.int64)
    assert np.all(np.diff(t) > 0), "t não é estritamente crescente"
    for m in sch.METHODS:
        v = df[df[f"{m}_valid"] == 1]
        assert (v[f"{m}_qw"] >= 0).all(), f"{m}: qw < 0"
        assert v[f"{m}_age_ms"].between(0, max_age_ms).all(), f"{m}: age_ms fora de [0, {max_age_ms}]"
        assert (v[f"{m}_src_ts"] <= v["t"]).all(), f"{m}: pose não causal (src_ts > t)"
        assert (v[f"{m}_dt_ms"] > 0).all(), f"{m}: dt_ms <= 0"
        feats = [c for c, r in schema.items() if r == "feature" and c.startswith(f"{m}_") and not c.endswith("_var_H")]
        bad = [c for c in feats if v[c].isna().any()]
        assert not bad, f"{m}: features NaN em linhas válidas: {bad}"
