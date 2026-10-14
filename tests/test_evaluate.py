import numpy as np
import pandas as pd
from scipy.spatial.transform import Rotation as R
from ofd import evaluate
from ofd.tracks import Track

S = 1_000_000_000


def straight(n, step=1.0, seg=None):
    Ts = np.stack([np.eye(4)] * n)
    for i in range(n):
        Ts[i][0, 3] = step * i
    ts = (np.arange(n) * S // 10).astype(np.int64)  # 10 Hz
    return Track(ts, Ts, np.array(seg if seg is not None else [0] * n, dtype=np.int64))


def test_umeyama_recovers_rigid():
    rng = np.random.default_rng(0)
    P = rng.normal(size=(100, 3))
    T = np.eye(4); T[:3, :3] = R.from_euler("xyz", [10, 20, 30], degrees=True).as_matrix(); T[:3, 3] = [1, 2, 3]
    Q = (T[:3, :3] @ P.T).T + T[:3, 3]
    np.testing.assert_allclose(evaluate.umeyama_se3(P, Q), T, atol=1e-9)


def test_perfect_track_zero_ate():
    gt = straight(400, 0.1)  # 39.9 s, 39.9 m
    sm = evaluate.segment_metrics(gt, np.eye(4), gt.ts_ns, gt.Ts)
    assert sm["eligible"].all() and sm["ate_rmse"].max() < 1e-9


def test_short_segments_not_eligible():
    seg = [0] * 100 + [1] * 310
    tr = straight(410, 0.1, seg)
    sm = evaluate.segment_metrics(tr, np.eye(4), tr.ts_ns, tr.Ts).set_index("segment")
    assert not sm.loc[0, "eligible"]   # 9.9 s
    assert sm.loc[1, "eligible"]       # 30.9 s, 30.9 m


def test_metrics_no_eligible_segment():
    tr = straight(50, 0.1)
    sm = evaluate.segment_metrics(tr, np.eye(4), tr.ts_ns, tr.Ts)
    assert np.isnan(evaluate.aggregate_ate(sm))


def test_aggregate_weighted_by_poses():
    sm = pd.DataFrame({"n": [100, 300], "eligible": [True, True], "ate_rmse": [1.0, 2.0]})
    assert abs(evaluate.aggregate_ate(sm) - np.sqrt((100 * 1 + 300 * 4) / 400)) < 1e-12


def table(valid, seg=None):
    n = len(valid)
    return pd.DataFrame({"t": np.arange(n) * S // 10, "m_valid": valid,
                         "m_segment_id": seg if seg is not None else [0] * n,
                         "gt_dx": 0.5, "gt_dy": 0.0, "gt_dz": 0.0})


def test_coverage_longest_and_failures_from_state():
    df = table([0, 1, 1, 1, 0, 0, 1, 1, 0, 1])
    state = pd.DataFrame({"ts_ns": range(6), "ok": [1, 1, 0, 1, 0, 1], "map_id": 0})
    c = evaluate.coverage(df, "m", state)
    assert abs(c["coverage"] - 0.6) < 1e-12
    assert c["n_failures"] == 2 and c["n_resets"] == 2
    assert abs(c["longest_s"] - 0.3) < 1e-9 and abs(c["longest_m"] - 1.5) < 1e-9


def test_repeated_sample_is_not_failure():
    # valid cai para 0 (amostra repetida) mas o estado nunca perdeu tracking
    df = table([0, 1, 0, 1, 1])
    state = pd.DataFrame({"ts_ns": range(5), "ok": 1, "map_id": 0})
    assert evaluate.coverage(df, "m", state)["n_failures"] == 0


def test_longest_breaks_on_segment_change():
    df = table([0, 1, 1, 1, 1], seg=[0, 0, 0, 1, 1])
    state = pd.DataFrame({"ts_ns": range(5), "ok": 1, "map_id": [0, 0, 0, 1, 1]})
    c = evaluate.coverage(df, "m", state)
    assert abs(c["longest_s"] - 0.2) < 1e-9


def test_gt_path_length_ignores_nan():
    df = table([0, 1, 1]); df.loc[0, "gt_dx"] = np.nan
    assert abs(evaluate.gt_path_length(df) - 1.0) < 1e-12


def test_rpe_10m_includes_rotation_with_known_drift():
    # GT reto; estimativa com deriva de guinada constante de 0.01 rad por passo de 1 m
    n = 40
    gt = straight(n, 1.0)
    Ts = np.stack([np.eye(4)] * n)
    for i in range(n):
        Ts[i][:3, :3] = R.from_euler("z", 0.01 * i).as_matrix()
        Ts[i][0, 3] = float(i)
    est = Track(gt.ts_ns, Ts, gt.segment)
    r = evaluate.rpe(est, np.eye(4), gt.ts_ns, gt.Ts, delta_m=10.0)
    assert abs(r["rpe_r_10m"] - 0.10) < 1e-9   # 10 passos × 0.01 rad
    assert abs(r["rpe_r_frame"] - 0.01) < 1e-9


def test_continuous_frame_drops_are_not_resets():
    df = table([0, 1, 1, 0, 1])
    state = pd.DataFrame({"ts_ns": range(5), "ok": [1, 1, 1, 0, 1], "map_id": 0})
    c = evaluate.coverage(df, "m", state, continuous_frame=True)
    assert c["n_resets"] == 0 and c["n_failures"] == 1   # saída perdida conta como falha, não como reset
