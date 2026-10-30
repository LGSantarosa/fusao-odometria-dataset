"""Dados do estudo de comparação de arquiteturas — docs/PLAN_model_comparison.md, seções 3.4 e 4.

Janelas causais de `W` passos por sequência, campo receptivo, embargos das subdobras internas e máscaras distintas de
endpoints supervisionados, contexto e linhas embargadas. Não altera `ofd.fusion_data` (protocolo anterior).
"""
import math

import numpy as np

from ofd import fusion_data as fd

H = 10          # janela causal da variância móvel dos indicadores
EPS = 0.01      # peso residual máximo aceito para a memória anterior de Pα (seção 4.3)


def receptive_field(W, h=H):
    """R = W + H − 1 linhas brutas."""
    return W + h - 1


def memory_rows(alpha, eps=EPS):
    """M_α = ⌈ln ε / ln(1 − α)⌉ para 0 < α < 1; 0 para α = 1."""
    if not 0 < alpha <= 1:
        raise ValueError("α deve estar em (0, 1]")
    return 0 if alpha == 1 else math.ceil(math.log(eps) / math.log(1 - alpha))


def _lag_corr(x, lag):
    """Correlação de Pearson entre x_t e x_{t+lag} nos pares com os dois valores finitos; None se indefinida."""
    a, b = x[:-lag], x[lag:]
    ok = np.isfinite(a) & np.isfinite(b)
    if ok.sum() < 3:
        return None
    a, b = a[ok], b[ok]
    sa, sb = a.std(), b.std()
    if sa == 0 or sb == 0:
        return None
    return float(np.mean((a - a.mean()) * (b - b.mean())) / (sa * sb))


def e_gt(y, threshold=0.2, max_lag=50):
    """E_gt da sequência de treino: por componente do alvo, o menor L ≤ max_lag tal que |ρ(l)| < threshold para
    todo l em [L, max_lag] (ρ indefinida conta como não abaixo); sem tal L, max_lag. E_gt = máximo entre componentes."""
    y = np.asarray(y, float)
    out = 0
    for c in range(y.shape[1]):
        below = [r is not None and abs(r) < threshold for r in (_lag_corr(y[:, c], l) for l in range(1, max_lag + 1))]
        L = max_lag
        for l in range(max_lag, 0, -1):
            if not below[l - 1]:
                break
            L = l
        out = max(out, L if below[-1] else max_lag)
    return out


def embargo(W, alpha, e_gt=0, h=H, eps=EPS):
    """(E_antes, E_depois) = (max(E_gt, R + M_α), max(E_gt, R))."""
    R = receptive_field(W, h)
    return max(e_gt, R + memory_rows(alpha, eps)), max(e_gt, R)


def windows(X, W):
    """(n, F) → (n, W, F): a janela do endpoint k cobre as linhas k−W+1..k da mesma sequência. Antes do início da
    sequência a janela é preenchida com zeros, o que equivale a todas as fontes inválidas (`valid = 0`, demais features
    zeradas). Assim, todo endpoint tem janela e todos os modelos são avaliados nas mesmas linhas."""
    X = np.asarray(X)
    pad = np.zeros((W - 1, X.shape[1]), X.dtype)
    Xp = np.concatenate([pad, X])
    idx = np.arange(len(X))[:, None] + np.arange(W)[None, :]
    return Xp[idx]


def windows_by_sequence(X, seq, W):
    """Janelas sobre várias sequências concatenadas; nenhuma janela atravessa a fronteira entre sequências."""
    seq = np.asarray(seq)
    out = np.empty((len(X), W, X.shape[1]), np.asarray(X).dtype)
    for s in dict.fromkeys(seq):
        rows = np.flatnonzero(seq == s)
        if np.any(np.diff(rows) != 1):
            raise ValueError(f"sequência {s!r} não é contígua")
        out[rows] = windows(np.asarray(X)[rows], W)
    return out


def inner_folds(n, e_before, e_after, k=fd.N_BLOCKS):
    """Subdobras internas da sequência de treino: k blocos contíguos (o último absorve o resto). Para cada bloco,
    devolve máscaras booleanas de tamanho n:

    - `val`: linhas do bloco (endpoints de validação, se o alvo for finito);
    - `train`: linhas fora de [início − E_antes, fim + E_depois) (endpoints de treino, se o alvo for finito);
    - `embargo`: linhas excluídas do ajuste e fora do bloco; podem servir só como contexto de features.
    """
    size = n // k
    pos = np.arange(n)
    out = []
    for j in range(k):
        lo, hi = j * size, (n if j == k - 1 else (j + 1) * size)
        val = (pos >= lo) & (pos < hi)
        train = (pos < lo - e_before) | (pos >= hi + e_after)
        out.append({"val": val, "train": train, "embargo": ~val & ~train})
    return out


def embargo_fraction(n, e_before, e_after, k=fd.N_BLOCKS):
    """Maior fração consumida pelos embargos de uma subdobra (critério estrutural, seção 4.3); denominador = total
    de linhas `n` da sequência de treino da dobra LOSO."""
    return max(float(f["embargo"].mean()) for f in inner_folds(n, e_before, e_after, k))
