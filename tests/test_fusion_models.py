"""Fase 0 do protocolo do modelo de fusão, seções 6–7: baselines, ridge, F1, F2, perda e treinamento (sintético)."""
import numpy as np
import pytest

from ofd import fusion_data as fd, fusion_models as fm
from tests.fusion_synth import synth_sequence


def test_loss_is_physical_error_divided_by_sigma():
    y = np.zeros((2, 6))
    pred = np.array([[1.0, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 2.0]])
    sigma = np.array([2.0, 1, 1, 1, 1, 4.0])
    assert np.isclose(fm.loss(pred, y, sigma), ((0.5 ** 2) + (0.5 ** 2)) / 12)


def test_hold_causal_repeats_last_and_starts_at_zero():
    p = np.array([[np.nan] * 6, [1.0] * 6, [np.nan] * 6, [2.0] * 6])
    out = fm.hold_causal(p)
    assert np.array_equal(out[:, 0], [0.0, 1.0, 1.0, 2.0])


def test_single_baseline_uses_method_twist_and_holds_when_invalid():
    df = synth_sequence(10, invalid_every={"stella": 3})
    tw, valid = fd.method_twists(df)
    pred = fm.baseline_single(tw, valid, 1)
    assert np.allclose(pred[1], tw[1, 1]) and np.allclose(pred[3], tw[2, 1])   # linha 3 inválida → retém a 2
    assert np.allclose(pred[0], 0.0)                                          # inválida antes de qualquer válida


def test_mean_baseline_averages_only_valid_sources():
    df = synth_sequence(6, invalid_every={"orbslam3": 2})
    tw, valid = fd.method_twists(df)
    pred = fm.baseline_mean(tw, valid)
    assert np.allclose(pred[0], tw[0, 1:].mean(axis=0)) and np.allclose(pred[1], tw[1].mean(axis=0))


def test_ridge_intercept_is_not_penalized_and_is_deterministic():
    rng = np.random.default_rng(0)
    X = rng.normal(size=(200, 3))
    Z = 5.0 + X @ np.array([[1.0], [0.0], [-2.0]]) + rng.normal(0, 0.01, (200, 1))
    exact = fm.Ridge(1e-9).fit(X, Z)
    assert np.allclose(exact.coef[:, 0], [1, 0, -2], atol=0.01) and np.isclose(exact.intercept[0], 5.0, atol=0.01)
    huge = fm.Ridge(1e12).fit(X, Z)
    assert np.allclose(huge.coef, 0, atol=1e-6) and np.isclose(huge.intercept[0], Z.mean())   # só a inclinação encolhe
    again = fm.Ridge(1e12).fit(X, Z)
    assert np.array_equal(huge.coef, again.coef)


def test_f1_weights_mask_invalid_and_sum_to_one():
    torch = pytest.importorskip("torch")
    net = fm.build_net("F1", n_in=4, width=8, layers=1, seed=0)
    X = torch.zeros((3, 4), dtype=torch.float64)
    valid = torch.tensor([[1, 0, 1, 1], [0, 0, 0, 1], [1, 1, 1, 1]], dtype=torch.bool)
    w = fm.f1_weights(net, X, valid)
    assert torch.allclose(w.sum(dim=1), torch.ones(3, dtype=torch.float64))
    assert (w[~valid] == 0).all() and w[1, 3] == 1.0


def test_f1_prediction_is_weighted_mean_of_valid_twists():
    df = synth_sequence(30, invalid_every={"orbslam3": 2})
    tw, valid = fd.method_twists(df)
    X = fd.Standardizer().fit(df).transform(df)
    net = fm.build_net("F1", n_in=X.shape[1], width=8, layers=1, seed=0)
    pred, w = fm.predict_f1(net, X, tw, valid)
    expected = np.einsum("nm,nmc->nc", w, np.nan_to_num(tw))
    assert np.allclose(pred, expected) and np.allclose(w[~valid], 0)


def test_f1_without_valid_source_holds_previous_prediction():
    df = synth_sequence(20)
    tw, valid = fd.method_twists(df)
    valid[2] = False
    tw[2] = np.nan
    X = fd.Standardizer().fit(df).transform(df)
    net = fm.build_net("F1", n_in=X.shape[1], width=8, layers=1, seed=0)
    pred, _ = fm.predict_f1(net, X, tw, valid)
    assert np.allclose(pred[2], pred[1])


def _fit(kind, df, seed=0, epochs=30, **kw):
    st = fd.Standardizer().fit(df)
    tw, valid = fd.method_twists(df)
    return fm.train_nn(kind, st.transform(df), df[fd.TARGET].to_numpy(), tw, valid, fd.target_sigma(df),
                       width=16, layers=1, weight_decay=1e-4, seed=seed, epochs=epochs, **kw)


def test_training_is_deterministic_per_seed():
    df = synth_sequence(200)
    a, b, c = _fit("F2", df, seed=1), _fit("F2", df, seed=1), _fit("F2", df, seed=2)
    assert a["train_losses"] == b["train_losses"] and a["train_losses"] != c["train_losses"]


def test_f1_learns_to_weight_the_least_noisy_source():
    df = synth_sequence(400, noise=(0.05, 0.05, 0.002, 0.05))                 # FAST-LIO muito melhor
    res = _fit("F1", df, epochs=60)
    st = fd.Standardizer().fit(df)
    tw, valid = fd.method_twists(df)
    _, w = fm.predict_f1(res["net"], st.transform(df), tw, valid)
    assert w.mean(axis=0).argmax() == fd.METHODS.index("fastlio")


def test_f2_predicts_in_physical_units_after_destandardizing():
    df = synth_sequence(300)
    res = _fit("F2", df, epochs=80)
    st = fd.Standardizer().fit(df)
    tw, valid = fd.method_twists(df)
    pred = fm.predict(res, st.transform(df), tw, valid)
    y = df[fd.TARGET].to_numpy()
    assert fm.loss(pred, y, fd.target_sigma(df)) < 0.2                          # bem abaixo de prever zero (~1)
    assert abs(pred[:, 0].mean() - y[:, 0].mean()) < 0.1                      # vx ≈ 1 m/s, não ≈ 1σ


def test_validation_curve_and_best_epoch_are_recorded():
    df = synth_sequence(200)
    tr, va = df.iloc[:150], df.iloc[150:]
    st = fd.Standardizer().fit(tr)
    tw_tr, v_tr = fd.method_twists(tr)
    tw_va, v_va = fd.method_twists(va)
    res = fm.train_nn("F2", st.transform(tr), tr[fd.TARGET].to_numpy(), tw_tr, v_tr, fd.target_sigma(tr),
                      width=16, layers=1, weight_decay=1e-4, seed=0, epochs=20,
                      val=(st.transform(va), va[fd.TARGET].to_numpy(), tw_va, v_va))
    assert len(res["val_losses"]) == 20 and res["best_epoch"] == int(np.argmin(res["val_losses"])) + 1


def test_non_finite_loss_marks_training_as_failed():
    df = synth_sequence(100)
    st = fd.Standardizer().fit(df)
    tw, valid = fd.method_twists(df)
    Y = df[fd.TARGET].to_numpy().copy()
    Y[7, 0] = np.inf
    res = fm.train_nn("F2", st.transform(df), Y, tw, valid, fd.target_sigma(df.iloc[8:]), width=8, layers=1,
                      weight_decay=0.0, seed=0, epochs=3)
    assert res["failed"] and res["train_losses"] == []


def test_parameter_count():
    assert fm.n_params("F2", n_in=56, width=16, layers=1) == 56 * 16 + 16 + 16 * 6 + 6
    assert fm.n_params("F1", n_in=56, width=16, layers=2) == 56 * 16 + 16 + 16 * 16 + 16 + 16 * 4 + 4


def test_non_finite_validation_loss_marks_training_as_failed():
    df = synth_sequence(200)
    tr, va = df.iloc[:150], df.iloc[150:]
    st = fd.Standardizer().fit(tr)
    tw_tr, v_tr = fd.method_twists(tr)
    tw_va, v_va = fd.method_twists(va)
    Yv = va[fd.TARGET].to_numpy().copy()
    Yv[3, 5] = np.nan                                                   # só a validação fica não finita
    res = fm.train_nn("F2", st.transform(tr), tr[fd.TARGET].to_numpy(), tw_tr, v_tr, fd.target_sigma(tr),
                      width=8, layers=1, weight_decay=1e-4, seed=0, epochs=4,
                      val=(st.transform(va), Yv, tw_va, v_va))
    assert res["failed"] and res["best_epoch"] is None
