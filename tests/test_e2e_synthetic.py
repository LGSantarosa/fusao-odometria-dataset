import json
import numpy as np
import pandas as pd
from ofd import build_dataset, contract, evaluate, schema, se3, tracks

MS = 1_000_000


def test_e2e(tmp_path):
    seq, runs = tmp_path / "ext", tmp_path / "runs"
    seq.mkdir()
    n = 450                                                  # 45 s a 10 Hz, 1 m/s
    end = (10**18 + np.arange(n) * 100 * MS).astype(np.int64)
    pd.DataFrame({"ts_ns": end - 100 * MS, "end_ns": end}).to_csv(seq / "lidar_stamps.csv", index=False)
    gt = np.stack([np.eye(4)] * n)
    for i in range(n):
        gt[i][0, 3] = 0.1 * i
    se3.save_tum(seq / "gt.tum", end, gt)
    rng = np.random.default_rng(0)
    for m, kind in schema.METHODS.items():
        ts = end - (30 * MS if kind == "vo" else 0)       # VO: câmera 30 ms antes do fim do scan
        Ts = gt.copy()
        ok = np.ones(n, int)
        if m == "stella":
            ok[200:220] = 0                                  # perde tracking 2 s
        if m == "orbslam3":
            Ts[:, 0, 3] *= 1.05                              # erro de escala 5%
        if m == "kissicp":
            Ts[:, 1, 3] += rng.normal(0, 0.01, n)            # ruído lateral
        cols = schema.VO_IND if kind == "vo" else schema.LO_IND
        ind = pd.DataFrame({"ts_ns": ts, **{c: rng.random(n) for c in cols}})
        tracks.write_run(runs / m, ts[ok == 1], Ts[ok == 1], pd.DataFrame({"ts_ns": ts, "ok": ok, "map_id": 0}),
                         ind, {"method": m, "uses_imu": m == "fastlio"})
    T = {m: np.eye(4) for m in schema.METHODS}
    df = build_dataset.build_sequence(seq, runs, T, "synthetic", "survey")
    sch = schema.build_schema(schema.METHODS)
    contract.check(df, sch)
    build_dataset.write_outputs(df, sch, tmp_path / "out", "syn")
    assert json.loads((tmp_path / "out/schema.json").read_text()) == sch
    met = evaluate.evaluate_sequence(seq, runs, df, T).set_index("method")
    assert met.loc["fastlio", "ate_rmse"] < 1e-6 and met.loc["fastlio", "coverage"] > 0.99
    assert met.loc["stella", "n_failures"] == 1 and met.loc["stella", "n_resets"] == 1
    assert met.loc["stella", "coverage"] < met.loc["fastlio", "coverage"]
    assert met.loc["orbslam3", "ate_rmse"] > 0.1
    assert (met["eligible_frac"] <= 1.0).all()
    np.testing.assert_allclose(df.loc[df["fastlio_valid"] == 1, "fastlio_vx"], 1.0, atol=1e-6)
    np.testing.assert_allclose(df["gt_vx"].dropna(), 1.0, atol=1e-6)
