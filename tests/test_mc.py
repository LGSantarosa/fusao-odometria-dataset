"""Fase 2 do estudo de comparação (docs/PLAN_model_comparison.md, seções 4.3, 4.4 e 9): contratos e tarefas
sintéticas de janelas, embargos, Pα, T2, encoders, cabeças e treino por orçamento de atualizações."""
import math

import numpy as np
import pandas as pd
import pytest
import torch

from ofd import fusion_data as fd, mc_data, mc_filters, mc_models

CFG = {"STEP": {"width": 16, "layers": 1}, "MLPW": {"width": 16, "layers": 1},
       "CNN": {"channels": 8, "layers": 2, "kernel": 3}, "LSTM": {"hidden": 8, "layers": 1}}


# ---------------------------------------------------------------- campo receptivo e embargos

def test_receptive_field_memory_and_embargo():
    assert mc_data.receptive_field(5) == 14
    assert mc_data.memory_rows(1.0) == 0
    assert mc_data.memory_rows(0.5) == math.ceil(math.log(0.01) / math.log(0.5)) == 7
    assert (1 - 0.3) ** mc_data.memory_rows(0.3) <= 0.01 < (1 - 0.3) ** (mc_data.memory_rows(0.3) - 1)
    assert mc_data.embargo(5, 0.5) == (21, 14)
    assert mc_data.embargo(5, 0.5, e_gt=30) == (30, 30)
    for a in (0, -0.1, 1.5):
        with pytest.raises(ValueError):
            mc_data.memory_rows(a)


@pytest.mark.parametrize("n,W,alpha,e_gt", [(500, 5, 0.5, 0), (503, 8, 0.2, 0), (500, 3, 1.0, 40), (97, 2, 0.9, 0)])
def test_training_windows_never_reach_validation_block(n, W, alpha, e_gt):
    eb, ea = mc_data.embargo(W, alpha, e_gt)
    R = mc_data.receptive_field(W)
    for f in mc_data.inner_folds(n, eb, ea):
        assert not (f["val"] & f["train"]).any() and not (f["val"] & f["embargo"]).any()
        assert (f["val"] | f["train"] | f["embargo"]).all()
        lo, hi = np.flatnonzero(f["val"])[[0, -1]]
        for t in np.flatnonzero(f["train"]):
            raw = set(range(t - R + 1, t + 1))           # linhas brutas que alimentam o endpoint t
            assert not raw & set(range(lo, hi + 1))
            if t < lo:                                    # antes do bloco: R + M_α linhas até o primeiro endpoint
                assert lo - t > R - 1 + mc_data.memory_rows(alpha) or lo - t > e_gt


def test_embargo_fraction():
    assert mc_data.embargo_fraction(500, 21, 14) == pytest.approx(35 / 500)
    assert mc_data.embargo_fraction(500, 0, 0) == 0


# ---------------------------------------------------------------- janelas

def test_windows_are_causal_and_zero_padded():
    X = np.arange(12, dtype=float).reshape(6, 2) + 1
    Xw = mc_data.windows(X, 3)
    assert Xw.shape == (6, 3, 2)
    np.testing.assert_array_equal(Xw[0], [[0, 0], [0, 0], X[0]])
    np.testing.assert_array_equal(Xw[4], X[2:5])
    assert np.array_equal(mc_data.windows(X, 1)[:, 0], X)


def test_windows_never_cross_sequences():
    X = np.arange(10, dtype=float)[:, None] + 1
    seq = np.array(["a"] * 4 + ["b"] * 6)
    Xw = mc_data.windows_by_sequence(X, seq, 3)
    np.testing.assert_array_equal(Xw[4, :, 0], [0, 0, 5])     # primeira linha de "b" não vê "a"
    np.testing.assert_array_equal(Xw[5, :, 0], [0, 5, 6])
    with pytest.raises(ValueError, match="contígua"):
        mc_data.windows_by_sequence(X, np.array(list("aabbaabbaa")), 2)


def test_invalid_source_is_fully_masked_inside_windows():
    rng = np.random.default_rng(0)
    n = 40
    df = pd.DataFrame({c: rng.normal(size=n) for c in fd.FEATURES})
    for m in fd.METHODS:
        df[f"{m}_valid"] = 1
    df.loc[10:14, "stella_valid"] = 0
    X = fd.Standardizer().fit(df).transform(df)
    Xw = mc_data.windows(X, 5)
    cols = [j for j, c in enumerate(fd.FEATURES) if c.startswith("stella_")]
    assert (Xw[14, :, cols] == 0).all()                       # janela inteira dentro da perda: só zeros
    assert (Xw[16, :3][:, cols] == 0).all() and (Xw[16, 3:][:, cols] != 0).all()   # linhas 12–14 inválidas, 15–16 não


# ---------------------------------------------------------------- Pα, T1 e T2

def test_p_alpha_initialization_and_gaps():
    raw = np.array([[np.nan] * 6, [np.nan] * 6, [2.0] * 6, [np.nan] * 6, [4.0] * 6])
    out = mc_filters.apply_p_alpha(raw, 0.5)
    np.testing.assert_allclose(out[:, 0], [0, 0, 2, 2, 3])   # zero, inicialização sem mistura, retenção, EMA
    np.testing.assert_allclose(mc_filters.apply_p_alpha(raw, 1.0)[:, 0], [0, 0, 2, 2, 4])
    with pytest.raises(ValueError):
        mc_filters.apply_p_alpha(raw, 0.0)


def test_p_alpha_memory_before_embargo_is_bounded_by_eps():
    rng = np.random.default_rng(1)
    for alpha in (0.05, 0.2, 0.5, 0.9):
        n, lo = 300, 200
        eb, _ = mc_data.embargo(4, alpha)
        a = rng.normal(size=(n, 6))
        b = a.copy()
        cut = lo - eb
        b[:cut] = a[:cut] + rng.uniform(-1, 1, size=(cut, 6))   # predições in-sample anteriores ao embargo
        d0 = np.abs(b[:cut] - a[:cut]).max()
        diff = np.abs(mc_filters.apply_p_alpha(b, alpha)[lo] - mc_filters.apply_p_alpha(a, alpha)[lo]).max()
        assert diff <= mc_data.EPS * d0 + 1e-12


def _noisy_sources(n=3000, seed=0, sd=(0.3, 0.3, 0.3, 0.3)):
    rng = np.random.default_rng(seed)
    t = np.arange(n) / 10
    y = np.c_[np.sin(t / 5), np.cos(t / 7), 0 * t, 0 * t, 0 * t, 0.1 * np.sin(t / 3)]
    tw = y[:, None, :] + rng.normal(size=(n, 4, 6)) * np.asarray(sd)[None, :, None]
    valid = rng.random((n, 4)) > 0.1
    tw[~valid] = np.nan
    return y, tw, valid


def test_smooth_target_gain_comes_from_filtering():
    y, tw, valid = _noisy_sources()
    b5 = mc_filters.apply_p_alpha(mc_filters.b5_raw(tw, valid), 1.0)
    t1 = mc_filters.t1(tw, valid, 0.2)
    err = lambda p: np.sqrt(np.mean((p - y) ** 2))
    assert err(t1) < 0.6 * err(b5)


def test_t2_kalman_uses_train_covariances_and_beats_b5():
    y, tw, valid = _noisy_sources(sd=(0.1, 0.3, 0.6, 1.0))
    kf = mc_filters.TwistKalman().fit(tw[:2000], valid[:2000], y[:2000])
    assert kf.R[0].mean() < kf.R[3].mean()
    p = kf.predict(tw[2000:], valid[2000:])
    b5 = mc_filters.apply_p_alpha(mc_filters.b5_raw(tw[2000:], valid[2000:]), 1.0)
    err = lambda q: np.sqrt(np.mean((q - y[2000:]) ** 2))
    assert err(p) < 0.5 * err(b5)
    v = valid[2000:].copy()
    v[:5] = False
    assert (kf.predict(tw[2000:], v)[:5] == 0).all()           # antes da primeira fonte válida: zero


# ---------------------------------------------------------------- encoders e cabeças

def _batch(n=30, W=6, F=7, seed=0):
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, F))
    tw = rng.normal(size=(n, 4, 6))
    valid = rng.random((n, 4)) > 0.3
    return X, tw, valid


@pytest.mark.parametrize("family", mc_models.FAMILIES)
def test_changing_future_rows_never_changes_past_predictions(family):
    X, tw, valid = _batch()
    W = 1 if family == "STEP" else 6
    model = mc_models.build(family, "W", X.shape[1], W, CFG[family], seed=0)
    p1 = mc_models.predict_raw(model, "W", mc_data.windows(X, W), tw, valid, np.ones(6))
    X2, tw2 = X.copy(), tw.copy()
    X2[15:] += 100.0
    tw2[15:] += 100.0
    p2 = mc_models.predict_raw(model, "W", mc_data.windows(X2, W), tw2, valid, np.ones(6))
    np.testing.assert_array_equal(np.isnan(p1[:15]), np.isnan(p2[:15]))
    np.testing.assert_allclose(np.nan_to_num(p1[:15]), np.nan_to_num(p2[:15]), atol=0)


@pytest.mark.parametrize("family", mc_models.FAMILIES)
def test_w_head_combines_only_current_valid_twists(family):
    X, tw, valid = _batch()
    W = 1 if family == "STEP" else 6
    model = mc_models.build(family, "W", X.shape[1], W, CFG[family], seed=1)
    Xw = mc_data.windows(X, W)
    w = mc_models.weights(model, Xw, tw, valid)
    assert (w[~valid] == 0).all()
    any_v = valid.any(axis=1)
    np.testing.assert_allclose(w[any_v].sum(axis=1), 1.0)
    p = mc_models.predict_raw(model, "W", Xw, tw, valid, np.ones(6))
    np.testing.assert_allclose(p[any_v], np.einsum("nm,nmc->nc", w, np.nan_to_num(tw))[any_v])
    assert np.isnan(p[~any_v]).all()


def test_d_head_outputs_physical_units():
    X, tw, valid = _batch()
    model = mc_models.build("MLPW", "D", X.shape[1], 4, CFG["MLPW"], seed=0)
    s = np.array([1, 2, 3, 4, 5, 6.0])
    Xw = mc_data.windows(X, 4)
    with torch.no_grad():
        z = model(torch.from_numpy(Xw)).numpy()
    np.testing.assert_allclose(mc_models.predict_raw(model, "D", Xw, tw, valid, s), z * s)


# ---------------------------------------------------------------- treino por orçamento de atualizações

def test_update_budget_is_exact_and_reshuffles_across_epochs():
    X, tw, valid = _batch(n=50)
    Y = np.random.default_rng(3).normal(size=(50, 6))
    Xw = mc_data.windows(X, 3)
    model = mc_models.build("MLPW", "W", X.shape[1], 3, CFG["MLPW"], seed=0)
    calls = {"n": 0}
    rows = np.ones(50, bool)
    res = mc_models.train(model, "W", Xw, Y, tw, valid, np.ones(6), rows, updates=7, seed=0, batch=16,
                          checkpoint_every=1, val=lambda m: calls.__setitem__("n", calls["n"] + 1) or 1.0)
    assert [c[0] for c in res["checkpoints"]] == list(range(1, 8)) and calls["n"] == 7
    assert res["n_train"] == int(valid.any(axis=1).sum())        # cabeça W: linha sem fonte válida não treina


def test_training_is_deterministic_by_seed():
    X, tw, valid = _batch(n=80)
    Y = np.random.default_rng(4).normal(size=(80, 6))
    Xw = mc_data.windows(X, 4)

    def run(seed):
        m = mc_models.build("LSTM", "W", X.shape[1], 4, CFG["LSTM"], seed=seed)
        mc_models.train(m, "W", Xw, Y, tw, valid, np.ones(6), np.ones(80, bool), updates=20, seed=seed)
        return mc_models.predict_raw(m, "W", Xw, tw, valid, np.ones(6))
    np.testing.assert_array_equal(run(0), run(0))
    assert not np.allclose(np.nan_to_num(run(0)), np.nan_to_num(run(1)))


def test_non_finite_loss_marks_failure():
    X, tw, valid = _batch(n=40)
    Y = np.full((40, 6), 1e308)
    model = mc_models.build("STEP", "D", X.shape[1], 1, CFG["STEP"], seed=0)
    res = mc_models.train(model, "D", mc_data.windows(X, 1), Y, tw, valid, np.full(6, 1e-300), np.ones(40, bool),
                          updates=5, seed=0)
    assert res["failed"]


def _history_task(n=4000, seed=0, lag=3):
    """Fonte 0 é precisa, exceto quando o indicador estava ativo `lag` passos antes; fonte 1 tem ruído médio.
    O indicador atual não informa nada: só um modelo com histórico escolhe bem os pesos."""
    rng = np.random.default_rng(seed)
    ind = (rng.random(n) < 0.5).astype(float)
    bad = np.r_[np.zeros(lag), ind[:-lag]] == 1
    y = rng.normal(size=(n, 6)) * 0.5
    tw = np.zeros((n, 4, 6))
    tw[:, 0] = y + rng.normal(size=(n, 6)) * np.where(bad, 2.0, 0.05)[:, None]
    tw[:, 1] = y + rng.normal(size=(n, 6)) * 0.4
    valid = np.zeros((n, 4), bool)
    valid[:, :2] = True
    X = np.c_[ind, rng.normal(size=(n, 3))]
    return X, y, tw, valid


def test_history_dependent_task_needs_the_window():
    X, y, tw, valid = _history_task()
    tr = np.arange(len(X)) < 3000
    va = ~tr
    out = {}
    for family, W in (("STEP", 1), ("MLPW", 5)):
        Xw = mc_data.windows(X, W)
        m = mc_models.build(family, "W", X.shape[1], W, {"width": 32, "layers": 1}, seed=0)
        res = mc_models.train(m, "W", Xw, y, tw, valid, np.ones(6), tr, updates=1500, seed=0, checkpoint_every=500,
                              val=lambda mm: mc_models.val_loss_after_p_alpha(mm, "W", Xw, tw, valid, y, np.ones(6),
                                                                              1.0, va))
        out[family] = res["checkpoints"][-1][1]
    assert out["MLPW"] < 0.7 * out["STEP"]


def test_val_loss_runs_p_alpha_over_whole_sequence():
    X, tw, valid = _batch(n=60)
    Y = np.random.default_rng(5).normal(size=(60, 6))
    model = mc_models.build("STEP", "W", X.shape[1], 1, CFG["STEP"], seed=0)
    Xw = mc_data.windows(X, 1)
    val = np.zeros(60, bool)
    val[40:] = True
    full = mc_filters.apply_p_alpha(mc_models.predict_raw(model, "W", Xw, tw, valid, np.ones(6)), 0.3)
    assert mc_models.val_loss_after_p_alpha(model, "W", Xw, tw, valid, Y, np.ones(6), 0.3, val) == pytest.approx(
        np.mean((full[40:] - Y[40:]) ** 2))
