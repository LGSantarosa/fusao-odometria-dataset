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
    """Maior fração da sequência consumida pelos embargos de uma subdobra (critério estrutural, seção 4.3)."""
    return max(float(f["embargo"].mean()) for f in inner_folds(n, e_before, e_after, k))
