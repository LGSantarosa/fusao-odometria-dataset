from pathlib import Path

import numpy as np
import pandas as pd

from ofd import kissicp_analysis, se3, tracks


def _write_run(path, ts, Ts):
    state = pd.DataFrame({"ts_ns": ts, "ok": 1, "map_id": 0})
    tracks.write_run(path, ts, Ts, state, pd.DataFrame({"ts_ns": ts}),
                     {"continuous_frame": True, "method": "kissicp"})


def test_repeatability_hash_and_pose_delta(tmp_path):
    ts = np.arange(4, dtype=np.int64) * 1_000_000_000
    Ts = np.repeat(np.eye(4)[None], 4, axis=0)
    _write_run(tmp_path / "a", ts, Ts)
    _write_run(tmp_path / "b", ts, Ts)
    moved = Ts.copy(); moved[-1, 0, 3] = .002
    _write_run(tmp_path / "c", ts, moved)
    same = kissicp_analysis.compare_repetitions([tmp_path / "a", tmp_path / "b"])
    assert same["sha256"].nunique() == 1 and same["max_delta_t_m"].max() == 0
    assert kissicp_analysis.repeatability_decision(same) == "deterministic"
    changed = kissicp_analysis.compare_repetitions([tmp_path / "a", tmp_path / "c"])
    assert changed.iloc[1]["max_delta_t_m"] == .002
    assert kissicp_analysis.repeatability_decision(changed) == "escalate_to_10"
    assert kissicp_analysis.operational_metrics(tmp_path / "a") == {"coverage": 1.0, "n_failures": 0}


def test_common_paired_rpe_and_motion_series(tmp_path):
    ts = np.arange(31, dtype=np.int64) * 1_000_000_000
    gt = np.repeat(np.eye(4)[None], len(ts), axis=0)
    gt[:, 0, 3] = np.arange(len(ts), dtype=float)
    est0 = gt.copy()
    est1 = gt.copy(); est1[:, 0, 3] *= 1.01
    _write_run(tmp_path / "d0", ts, est0)
    _write_run(tmp_path / "d1", ts, est1)
    common_ts, common_gt, runs = kissicp_analysis.common_support(
        {"D0": tmp_path / "d0", "D1": tmp_path / "d1"}, ts, gt)
    rpe = kissicp_analysis.relative_error_series(common_ts, common_gt, runs, 10.0)
    assert len(rpe) == 42 and rpe[rpe.condition == "D0"]["error_t_m"].max() == 0
    np.testing.assert_allclose(rpe[rpe.condition == "D1"]["error_t_m"], .1)
    motion = kissicp_analysis.motion_series(common_ts, common_gt)
    np.testing.assert_allclose(motion["v_dt_m"], 1.0)
    np.testing.assert_allclose(motion["omega_dt_rad"], 0.0)
    summary, series = kissicp_analysis.metric_summary(common_ts, common_gt, runs)
    assert summary.set_index("condition").loc["D0", "ate_rmse"] == 0
    np.testing.assert_allclose(summary.set_index("condition").loc["D1", "rpe_t_10m"], .1)
    stratified = kissicp_analysis.stratify_frame_errors(series["rpe_frame"], motion)
    assert "omega_dt_rad_quantile" in stratified


def test_structure_metrics_distinguish_line_plane_and_volume():
    x = np.linspace(-10, 10, 1000)
    line = np.c_[x, np.zeros_like(x), np.zeros_like(x)]
    grid = np.linspace(-10, 10, 40)
    xx, yy = np.meshgrid(grid, grid)
    plane = np.c_[xx.ravel(), yy.ravel(), np.zeros(xx.size)]
    rng = np.random.default_rng(4)
    volume = rng.uniform(-10, 10, (5000, 3))
    a = kissicp_analysis.structure_metrics(line)
    b = kissicp_analysis.structure_metrics(plane)
    c = kissicp_analysis.structure_metrics(volume)
    assert a["pca_linearity"] > .99
    assert b["pca_planarity"] > .45
    assert c["pca_scattering"] > .8
    assert c["n_voxels_1m"] > b["n_voxels_1m"] > a["n_voxels_1m"]


def test_promotion_requires_every_gate_on_both_sequences():
    rows = []
    for seq in ("1018-00", "1018-13"):
        rows.append({"sequence": seq, "condition": "D0", "rpe_t_10m": 1., "rpe_r_10m_deg": 2.,
                     "ate_rmse": 1., "coverage": 1., "n_failures": 0})
        rows.append({"sequence": seq, "condition": "D1", "rpe_t_10m": .94, "rpe_r_10m_deg": 1.89,
                     "ate_rmse": 1.04, "coverage": 1., "n_failures": 0})
        rows.append({"sequence": seq, "condition": "D2", "rpe_t_10m": .94, "rpe_r_10m_deg": 1.89,
                     "ate_rmse": 1.06, "coverage": 1., "n_failures": 0})
    out = kissicp_analysis.promotion_checks(pd.DataFrame(rows))
    assert out[out.condition == "D1"]["promote_across_botanic"].all()
    assert not out[out.condition == "D2"]["promote_across_botanic"].any()
