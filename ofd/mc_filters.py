"""Filtros clássicos do estudo de comparação — docs/PLAN_model_comparison.md, seções G2 e 3.3.

Pα (EMA causal comum), T1 = B5 + Pα e T2 (Kalman de twist). Não participam de gradiente.
"""
import numpy as np

from ofd import fusion_models as fm


def p_alpha(pred, started, alpha):
    """Pα: y'_k = α y_k + (1 − α) y'_{k−1}, componente a componente, sobre a predição já com retenção causal.

    `started[k]` indica se já houve predição válida até k (inclusive). Antes da primeira predição válida a saída é zero;
    nela o estado é inicializado com y'_k = y_k; a EMA começa na seguinte. Não há reinício em lacunas, só por sequência
    (chamar uma vez por sequência).
    """
    if not 0 < alpha <= 1:
        raise ValueError("α deve estar em (0, 1]")
    pred = np.asarray(pred, float)
    out = np.zeros_like(pred)
    state = None
    for k in range(len(pred)):
        if state is None:
            if started[k]:
                state = pred[k].copy()
                out[k] = state
            continue
        state = alpha * pred[k] + (1 - alpha) * state
        out[k] = state
    return out


def first_valid_mask(has_pred):
    """started[k] = já houve predição válida em alguma linha ≤ k."""
    return np.maximum.accumulate(np.asarray(has_pred, bool)) if len(has_pred) else np.zeros(0, bool)


def apply_p_alpha(raw, alpha):
    """Política comum a todas as saídas W e a B5: NaN = sem predição → retenção causal → Pα."""
    raw = np.asarray(raw, float)
    has = np.isfinite(raw).all(axis=1)
    return p_alpha(fm.hold_causal(raw), first_valid_mask(has), alpha)


def b5_raw(tw, valid):
    """Média dos twists válidos; NaN onde nenhuma fonte é válida (antes da retenção)."""
    n = valid.sum(axis=1, keepdims=True)
    with np.errstate(invalid="ignore", divide="ignore"):
        p = np.where(valid[..., None], np.nan_to_num(tw), 0.0).sum(axis=1) / n
    p[~valid.any(axis=1)] = np.nan
    return p


def t1(tw, valid, alpha):
    """T1 = B5 + Pα."""
    return apply_p_alpha(b5_raw(tw, valid), alpha)


class TwistKalman:
    """T2: estado = 6 velocidades, dinâmica de persistência (passeio aleatório), uma atualização por fonte válida.

    Covariâncias diagonais estimadas exclusivamente no treino: R_m = variância de (twist_m − alvo) nas linhas em que m é
    válido; Q = variância da diferença do alvo entre linhas consecutivas; ambas com piso numérico `floor` aplicado no
    treino. Hiperparâmetros: `q_scale` e `r_scale` multiplicam Q e R_m (já com o piso), inclusive na inicialização.
    Componentes independentes (matrizes diagonais), portanto o filtro é escalar por componente.
    Antes da primeira fonte válida a saída é zero; nessa linha o estado é a fusão por informação das medidas.
    """

    def __init__(self, q_scale=1.0, r_scale=1.0, floor=1e-12):
        self.q_scale, self.r_scale, self.floor = float(q_scale), float(r_scale), floor

    def fit(self, tw, valid, y):
        y = np.asarray(y, float)
        fin = np.isfinite(y).all(axis=1)
        self.R = np.empty((tw.shape[1], y.shape[1]))
        for m in range(tw.shape[1]):
            rows = fin & valid[:, m]
            if rows.sum() < 2:
                raise ValueError(f"fonte {m}: menos de 2 linhas válidas com alvo no treino")
            self.R[m] = np.maximum((tw[rows, m] - y[rows]).var(axis=0), self.floor)
        d = np.diff(y, axis=0)
        d = d[np.isfinite(d).all(axis=1)]
        self.Q = np.maximum(d.var(axis=0), self.floor)
        return self

    def predict(self, tw, valid):
        n, M, C = tw.shape
        R, Q = self.R * self.r_scale, self.Q * self.q_scale
        out = np.zeros((n, C))
        x = P = None
        for k in range(n):
            if x is not None:
                P = P + Q
            for m in np.flatnonzero(valid[k]):
                z = tw[k, m]
                if x is None:
                    x, P = z.copy(), R[m].copy()
                    continue
                K = P / (P + R[m])
                x = x + K * (z - x)
                P = (1 - K) * P
            if x is not None:
                out[k] = x
        return out
