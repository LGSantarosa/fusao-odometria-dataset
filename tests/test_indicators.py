import numpy as np
import pandas as pd
from scipy.spatial.transform import Rotation as R
from ofd import indicators


def scene(seed=0):
    rng = np.random.default_rng(seed)
    ground = np.c_[rng.uniform(-20, 20, (4000, 2)), np.zeros(4000)]
    wall = np.c_[rng.uniform(-20, 20, 2000), np.full(2000, 10.0), rng.uniform(0, 3, 2000)]
    pole = np.c_[np.full(500, 3.0), np.full(500, -4.0), rng.uniform(0, 4, 500)]
    return np.vstack([ground, wall, pole])


def make_dT():
    T = np.eye(4)
    T[:3, :3] = R.from_euler("z", 5, degrees=True).as_matrix()
    T[:3, 3] = [0.8, 0.1, 0.0]
    return T


def test_correct_delta_scores_high():
    tgt = scene()
    dT = make_dT()
    src = (np.linalg.inv(dT) @ np.c_[tgt, np.ones(len(tgt))].T).T[:, :3]  # scan k visto do frame k
    q = indicators.registration_quality(src, tgt, dT)
    assert q["fitness"] > 0.95 and q["inlier_rmse"] < 0.15 and q["unmatched_ratio"] < 0.02


def test_wrong_delta_scores_low():
    tgt = scene()
    dT = make_dT()
    src = (np.linalg.inv(dT) @ np.c_[tgt, np.ones(len(tgt))].T).T[:, :3]
    bad = dT.copy(); bad[2, 3] += 1.5  # erro vertical: o chão inteiro deixa de casar
    q = indicators.registration_quality(src, tgt, bad)
    assert q["fitness"] < 0.6 and q["unmatched_ratio"] > 0.2


def test_causal_variance_ignores_future():
    s = pd.Series(np.arange(30, dtype=float))
    a = indicators.causal_rolling_var(s, H=5)
    s2 = s.copy(); s2.iloc[20:] = 1e6
    b = indicators.causal_rolling_var(s2, H=5)
    pd.testing.assert_series_equal(a.iloc[:20], b.iloc[:20])
    assert np.isnan(a.iloc[0])
