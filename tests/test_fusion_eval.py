"""Fase 0 do protocolo do modelo de fusão, seções 7–9: integração, métricas, escolha e decisão (sintético)."""
import numpy as np
import pandas as pd

from ofd import fusion_data as fd, fusion_eval as fe, se3
from tests.fusion_synth import integrate_reference, synth_sequence


def test_integration_starts_at_identity_and_applies_twist_from_row_one():
    t = np.array([0, 100_000_000, 300_000_000], dtype=np.int64)
    tw = np.array([[9.0, 9, 9, 9, 9, 9], [1.0, 0, 0, 0, 0, 0], [0.0, 2, 0, 0, 0, 0]])   # linha 0 não entra
    T = fe.integrate(t, tw)
    assert np.allclose(T[0], np.eye(4))
    assert np.allclose(T[1][:3, 3], [0.1, 0, 0]) and np.allclose(T[2][:3, 3], [0.1, 0.4, 0])


def test_integration_recovers_gt_trajectory_from_gt_twist():
    rng = np.random.default_rng(0)
    t = np.cumsum(rng.integers(90_000_000, 110_000_000, 300)).astype(np.int64)
    poses = [np.eye(4)]
    for k in range(1, 300):
        poses.append(poses[-1] @ se3.exp_twist(rng.normal(0, [0.1, 0.01, 0.01, 0.01, 0.01, 0.05])))
    poses = np.stack(poses)
    twist = np.zeros((300, 6))
    for k in range(1, 300):                                              # como ofd.sync.gt_deltas
        twist[k] = se3.log_twist(se3.delta(poses[k - 1], poses[k])) / ((t[k] - t[k - 1]) / 1e9)
    assert np.allclose(fe.integrate(t, twist), poses, atol=1e-9)
    assert np.allclose(fe.integrate(t, twist), integrate_reference(t, twist), atol=1e-12)


def test_primary_metrics():
    y = np.zeros((4, 6))
    pred = np.zeros((4, 6))
    pred[:, 0], pred[:, 5] = 3.0, 4.0
    m = fe.primary(pred, y)
    assert np.isclose(m["rmse_v"], 3.0) and np.isclose(m["rmse_w"], 4.0)


def test_secondary_metrics_zero_for_perfect_prediction():
    df = synth_sequence(400)
    y = df[fd.TARGET].to_numpy()
    m = fe.secondary(df["t"].to_numpy(np.int64), y, y)
    assert m["rpe_t_10m"] < 1e-9 and m["rpe_r_10m"] < 1e-9 and m["ate_rmse"] < 1e-9


def test_secondary_rpe_undefined_without_10m_window():
    df = synth_sequence(40)                                              # ~4 m
    y = df[fd.TARGET].to_numpy()
    m = fe.secondary(df["t"].to_numpy(np.int64), y, y)
    assert np.isnan(m["rpe_t_10m"]) and np.isnan(m["ate_rmse"])          # trecho curto: não elegível


def test_strata_report_n_and_undefined_when_empty():
    y = np.zeros((5, 6))
    pred = np.ones((5, 6))
    s = fe.strata(pred, y, np.array([1, 1, 2, 4, 4])).set_index("n_valid")
    assert list(s.index) == [1, 2, 3, 4] and list(s["n"]) == [2, 1, 0, 2]
    assert np.isnan(s.loc[3, "rmse_v"]) and np.isclose(s.loc[1, "rmse_v"], np.sqrt(3))


def test_select_uses_one_percent_tie_and_simplicity():
    cv = pd.DataFrame({"config": ["a", "b", "c", "d"], "loss": [1.000, 1.009, 1.02, np.inf],
                       "n_params": [500, 100, 50, 10], "reg": [1e-4, 1e-4, 1e-2, 1e-2]})
    assert fe.select(cv) == "b"                                          # a e b empatam; b tem menos parâmetros
    cv.loc[1, "n_params"] = 500
    cv.loc[1, "reg"] = 1e-3
    assert fe.select(cv) == "b"                                          # mesmo tamanho: maior regularização


def test_select_returns_none_when_all_failed():
    assert fe.select(pd.DataFrame({"config": ["a"], "loss": [np.inf], "n_params": [1], "reg": [0.0]})) is None


def test_cv_loss_is_infinite_if_any_run_failed():
    runs = pd.DataFrame({"config": ["a"] * 3 + ["b"] * 3, "loss": [1.0, 1.1, 0.9, 0.5, np.nan, 0.5],
                         "failed": [False] * 4 + [True, False]})
    agg = fe.aggregate_cv(runs).set_index("config")
    assert np.isclose(agg.loc["a", "loss"], 1.0) and np.isinf(agg.loc["b", "loss"])


def test_final_epochs_is_ceiling_of_median_best_epoch():
    assert fe.final_epochs([10, 13, 12, 11]) == 12                       # mediana 11,5 → 12


def test_decision_requires_both_folds_both_metrics_and_two_sd_margin():
    good = {"f": [1.0, 1.02, 0.98, 1.01, 0.99], "bsel": 1.5, "b6": 1.4}
    case = {fold: {"rmse_v": good, "rmse_w": good} for fold in ("A", "B")}
    assert fe.decision(case)["passed"]
    narrow = {"f": [1.0, 1.2, 0.8, 1.1, 0.9], "bsel": 1.2, "b6": 1.3}    # média 1,0; 2·sd ≈ 0,32 > 0,2
    case["B"]["rmse_w"] = narrow
    out = fe.decision(case)
    assert not out["passed"] and not out["detail"]["B"]["rmse_w"]


def test_decision_fails_with_undefined_metric_or_single_seed():
    good = {"f": [1.0, 1.02, 0.98], "bsel": 1.5, "b6": 1.4}
    case = {f: {"rmse_v": good, "rmse_w": good} for f in ("A", "B")}
    case["A"]["rmse_v"] = {"f": [np.nan, np.nan], "bsel": 1.5, "b6": 1.4}
    assert not fe.decision(case)["passed"]
    case["A"]["rmse_v"] = {"f": [1.0], "bsel": 1.5, "b6": 1.4}             # desvio indefinido
    assert not fe.decision(case)["passed"]
