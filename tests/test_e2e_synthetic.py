import json
import numpy as np
import pandas as pd
from ofd import build_dataset, contract, evaluate, schema, se3, tracks

MS = 1_000_000


def test_e2e(tmp_path):
    seq, runs = tmp_path / "ext", tmp_path / "runs"
    seq.mkdir()
    n = 450                                                  # 45 s a 10 Hz, movimento acelerado
    t0 = 10**18
    end = (t0 + np.arange(n) * 100 * MS).astype(np.int64)
    vo_ts = end - 30 * MS                                    # câmera 30 ms antes do fim do scan
    pd.DataFrame({"ts_ns": end - 100 * MS, "end_ns": end}).to_csv(seq / "lidar_stamps.csv", index=False)

    def pose_at(ts_ns):                                      # x(t) = t + 0.05 t²  (não linear: ΔT depende do instante)
        t = (np.asarray(ts_ns, np.int64) - t0) / 1e9
        Ts = np.stack([np.eye(4)] * len(t))
        Ts[:, 0, 3] = t + 0.05 * t ** 2
        return Ts

    gt_ts = np.sort(np.r_[end, vo_ts])                       # GT também amostrado nos instantes da VO (interp. exata)
    gt = pose_at(end)
    se3.save_tum(seq / "gt.tum", gt_ts, pose_at(gt_ts))
    rng = np.random.default_rng(0)
    for m, kind in schema.METHODS.items():
        ts = vo_ts if kind == "vo" else end
        Ts = pose_at(ts)                                     # pose no instante do próprio método (sem "futuro")
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
    v = df[df["fastlio_valid"] == 1]
    np.testing.assert_allclose(v["fastlio_vx"], v["gt_vx"], atol=1e-9)
    # VO causal com timestamp 30 ms antes: erro contra o GT nos mesmos instantes de origem é zero fora da perda
    s = df[df["stella_valid"] == 1]
    assert len(s) > 400 and s["stella_err_t"].max() < 1e-9
