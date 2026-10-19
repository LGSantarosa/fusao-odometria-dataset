"""Sequências sintéticas no formato do dataset para a fase 0 do protocolo do modelo de fusão (nenhum dado real)."""
import numpy as np
import pandas as pd

from ofd import schema, se3

METHODS = list(schema.METHODS)
DT_NS = 100_000_000


def synth_sequence(n=400, seed=0, noise=(0.02, 0.05, 0.01, 0.03), invalid_every=None, seq="synth", t0=0):
    """Alvo = twist suave; cada método = alvo + ruído próprio; `invalid_every` = {método: período de invalidade}."""
    rng = np.random.default_rng(seed)
    k = np.arange(n)
    gt = np.stack([1.0 + 0.3 * np.sin(k / 40), 0.1 * np.cos(k / 25), 0.02 * np.sin(k / 10),
                   0.01 * np.cos(k / 30), 0.02 * np.sin(k / 50), 0.15 * np.sin(k / 35)], axis=1)
    cols = {"t": t0 + (k + 1) * DT_NS, "seq": seq, "dataset": "botanic", "gt_quality": "survey"}
    for c, col in zip(schema.TW, gt.T):
        cols[f"gt_{c}"] = col
    for c in schema.VEC:
        cols[f"gt_{c}"] = np.full(n, np.nan)
    for m, sd in zip(METHODS, noise):
        valid = np.ones(n, dtype=np.int64)
        if invalid_every and m in invalid_every:
            valid[k % invalid_every[m] == 0] = 0
        tw = gt + rng.normal(0, sd, gt.shape)
        tw[valid == 0] = np.nan
        for c, col in zip(schema.TW, tw.T):
            cols[f"{m}_{c}"] = col
        for c in schema.VEC:
            cols[f"{m}_{c}"] = np.full(n, np.nan)
        cols[f"{m}_valid"] = valid
        cols[f"{m}_dt_ms"] = np.where(valid == 1, 100.0, np.nan)
        cols[f"{m}_age_ms"] = np.where(valid == 1, 10.0 + sd * 100, np.nan)
        inds = schema.VO_IND if schema.METHODS[m] == "vo" else schema.LO_IND
        for j, c in enumerate(inds):
            cols[f"{m}_{c}"] = np.where(valid == 1, sd * (j + 1) + rng.normal(0, 0.001, n), np.nan)
        var = np.where(valid == 1, sd ** 2, np.nan)
        var[:10] = np.nan                                         # janela causal ainda incompleta
        cols[f"{m}_{schema.VAR_OF[schema.METHODS[m]]}_var_H"] = var
        for c in ("src_ts", "segment_id", "uses_imu", "err_t", "err_r"):
            cols[f"{m}_{c}"] = np.zeros(n)
    df = pd.DataFrame(cols)
    return df[list(schema.build_schema(schema.METHODS))]


def integrate_reference(t_ns, twists):
    """Integração de referência (laço explícito) para conferir ofd.fusion_eval.integrate."""
    T = [np.eye(4)]
    for k in range(1, len(t_ns)):
        T.append(T[-1] @ se3.exp_twist(np.asarray(twists[k]) * (t_ns[k] - t_ns[k - 1]) / 1e9))
    return np.stack(T)
