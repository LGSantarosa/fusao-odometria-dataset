"""Avaliação do protocolo de fusão — docs/protocol_fusion_model.md, seções 7–9.

Integração causal do twist, métricas primárias e secundárias, estratos, escolha de configuração e regra de decisão.
"""
import math

import numpy as np
import pandas as pd

from ofd import evaluate, se3
from ofd.tracks import Track

TIE = 1.01


def integrate(t_ns, twists):
    """T̂_0 = I; T̂_k = T̂_{k−1} exp(ξ_k Δt_k) para k ≥ 1; o twist da linha 0 não entra (seção 8)."""
    t = np.asarray(t_ns, dtype=np.int64)
    T = np.empty((len(t), 4, 4))
    T[0] = np.eye(4)
    for k in range(1, len(t)):
        T[k] = T[k - 1] @ se3.exp_twist(np.asarray(twists[k], float) * ((t[k] - t[k - 1]) / 1e9))
    return T


def _rmse_norm(e):
    return float(np.sqrt(np.mean(np.sum(e ** 2, axis=1)))) if len(e) else np.nan


def primary(pred, y):
    """RMSE translacional (m/s) e rotacional (rad/s) da velocidade."""
    e = np.asarray(pred) - np.asarray(y)
    return {"rmse_v": _rmse_norm(e[:, :3]), "rmse_w": _rmse_norm(e[:, 3:])}


def per_component(pred, y, names):
    e = np.asarray(pred) - np.asarray(y)
    return {f"rmse_{n}": float(np.sqrt(np.mean(e[:, j] ** 2))) for j, n in enumerate(names)}


def secondary(t_ns, pred, y):
    """RPE 10 m e ATE (SE(3)) das trajetórias integradas, com `ofd.evaluate` e o trecho como um segmento."""
    t = np.asarray(t_ns, dtype=np.int64)
    est, gt = integrate(t, pred), integrate(t, y)
    track = Track(t, est, np.zeros(len(t), dtype=np.int64))
    r = evaluate.rpe(track, np.eye(4), t, gt)
    sm = evaluate.segment_metrics(track, np.eye(4), t, gt)
    return {"rpe_t_10m": r["rpe_t_10m"], "rpe_r_10m": r["rpe_r_10m"], "ate_rmse": evaluate.aggregate_ate(sm)}


def strata(pred, y, n_valid):
    """Primárias por número de fontes válidas (1–4), com n; estrato vazio → indefinido (só descritivo)."""
    rows = []
    for k in (1, 2, 3, 4):
        sel = np.asarray(n_valid) == k
        rows.append({"n_valid": k, "n": int(sel.sum()), **primary(np.asarray(pred)[sel], np.asarray(y)[sel])})
    return pd.DataFrame(rows)


def aggregate_cv(runs):
    """Perda média por configuração sobre subdobras e sementes; qualquer execução falha → perda infinita."""
    def agg(g):
        return np.inf if g["failed"].any() else float(g["loss"].mean())
    return runs.groupby("config", sort=False).apply(agg, include_groups=False).rename("loss").reset_index()


def select(cv):
    """Menor perda; empate = L ≤ 1,01 · L_min; entre empatadas, menos parâmetros e, depois, maior regularização."""
    finite = cv[np.isfinite(cv["loss"])]
    if finite.empty:
        return None
    tied = finite[finite["loss"] <= TIE * finite["loss"].min()]
    return tied.sort_values(["n_params", "reg"], ascending=[True, False], kind="stable")["config"].iat[0]


def final_epochs(best_epochs):
    return int(math.ceil(float(np.median(best_epochs))))


def decision(case):
    """Seção 9: {dobra: {métrica: {"f": valores por semente, "bsel": valor, "b6": valor}}}. Passa só se, em todas
    as dobras e métricas, média(f) < bsel e < b6 com margem > 2 · desvio amostral de f entre sementes."""
    detail = {}
    for fold, metrics in case.items():
        detail[fold] = {}
        for metric, d in metrics.items():
            f = np.asarray(d["f"], dtype=float)
            f = f[np.isfinite(f)]
            ok = len(f) >= 2 and np.isfinite(d["bsel"]) and np.isfinite(d["b6"])
            if ok:
                mean, sd = f.mean(), f.std(ddof=1)
                ok = bool(mean < d["bsel"] and mean < d["b6"] and min(d["bsel"], d["b6"]) - mean > 2 * sd)
            detail[fold][metric] = ok
    return {"passed": all(all(m.values()) for m in detail.values()), "detail": detail}
