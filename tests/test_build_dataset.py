import json
import numpy as np
import pandas as pd
from ofd import build_dataset, schema, se3, tracks

MS = 1_000_000


def fake_seq(tmp_path, n=50, empty=None):
    seq, runs = tmp_path / "ext", tmp_path / "runs"
    seq.mkdir()
    grid = (np.arange(n) * 100 * MS + 1_000 * MS).astype(np.int64)
    pd.DataFrame({"ts_ns": grid, "end_ns": grid}).to_csv(seq / "lidar_stamps.csv", index=False)
    Ts = np.stack([np.eye(4)] * n)
    for i in range(n):
        Ts[i][0, 3] = 0.5 * i
    se3.save_tum(seq / "gt.tum", grid, Ts)
    for m, kind in schema.METHODS.items():
        st = pd.DataFrame({"ts_ns": grid, "ok": 0 if m == empty else 1, "map_id": 0})
        cols = schema.VO_IND if kind == "vo" else schema.LO_IND
        ind = pd.DataFrame({"ts_ns": grid, **{c: 1.0 for c in cols}})
        good = grid if m != empty else grid[:0]
        tracks.write_run(runs / m, good, Ts[: len(good)], st, ind, {"method": m, "uses_imu": m == "fastlio"})
    return seq, runs


def test_build_shape_and_values(tmp_path):
    seq, runs = fake_seq(tmp_path)
    df = build_dataset.build_sequence(seq, runs, {m: np.eye(4) for m in schema.METHODS}, "botanic", "survey")
    assert len(df) == 50
    s = schema.build_schema(schema.METHODS)
    assert set(s) == set(df.columns)
    v = df[df["kissicp_valid"] == 1]
    np.testing.assert_allclose(v["kissicp_dx"], 0.5)
    assert v["kissicp_err_t"].max() < 1e-6
    feat_cols = [c for c in df.columns if c.startswith("kissicp_") and s[c] == "feature" and not c.endswith("_var_H")]
    assert not v[feat_cols].isna().any().any()  # variância móvel começa com NaN por definição
    assert df["fastlio_uses_imu"].all() and not df["kissicp_uses_imu"].any()


def test_build_with_empty_method(tmp_path):
    seq, runs = fake_seq(tmp_path, empty="orbslam3")
    df = build_dataset.build_sequence(seq, runs, {m: np.eye(4) for m in schema.METHODS}, "botanic", "survey")
    assert (df["orbslam3_valid"] == 0).all()
    assert df["orbslam3_err_t"].isna().all()


def test_write_outputs(tmp_path):
    seq, runs = fake_seq(tmp_path)
    df = build_dataset.build_sequence(seq, runs, {m: np.eye(4) for m in schema.METHODS}, "botanic", "survey")
    s = schema.build_schema(schema.METHODS)
    build_dataset.write_outputs(df, s, tmp_path / "out", "seqA")
    assert (tmp_path / "out" / "seqA.parquet").exists()
    assert json.loads((tmp_path / "out" / "schema.json").read_text())["gt_dx"] == "evaluation"
