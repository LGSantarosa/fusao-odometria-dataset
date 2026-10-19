"""Dados do modelo de fusão — docs/protocol_fusion_model.md, seções 3–5.

Entradas = as 56 colunas `feature` do schema; alvo = velocidade do GT em se(3). Divisão em blocos temporais com purga
e padronização ajustadas só nas linhas de treino.
"""
import numpy as np

from ofd import schema

METHODS = list(schema.METHODS)
FEATURES = [c for c, r in schema.build_schema(schema.METHODS).items() if r == "feature"]
TARGET = [f"gt_{c}" for c in schema.TW]
N_BLOCKS = 5
PURGE = 10  # janela H da variância móvel causal (seção 4)


class EmptyColumnError(ValueError):
    """Coluna de entrada sem nenhum valor definido nas linhas de treino (seção 5)."""


def target_rows(df):
    """Linhas com as 6 componentes do alvo finitas (seção 3)."""
    return np.isfinite(df[TARGET].to_numpy(float)).all(axis=1)


def blocks(n, k=N_BLOCKS, purge=PURGE):
    """Subdobras (treino, validação) sobre posições 0..n−1: k blocos contíguos, o último absorve o resto; o treino
    exclui `purge` posições de cada lado do bloco de validação (seção 4)."""
    size = n // k
    out = []
    for j in range(k):
        lo, hi = j * size, (n if j == k - 1 else (j + 1) * size)
        val = np.arange(lo, hi)
        pos = np.arange(n)
        train = pos[(pos < lo - purge) | (pos >= hi + purge)]
        out.append((train, val))
    return out


def _method_of(col):
    return next((m for m in METHODS if col.startswith(f"{m}_")), None)


class Standardizer:
    """Seção 5: média e desvio populacional por coluna nas linhas de treino em que está definida (colunas de um
    método: só linhas com `valid = 1`); `valid` fica binário; desvio zero → escala 1; ausentes → 0 (imputação
    neutra) depois de padronizar."""

    def fit(self, df):
        self.mean, self.scale = {}, {}
        for c in FEATURES:
            if c.endswith("_valid"):
                continue
            m = _method_of(c)
            rows = df[f"{m}_valid"].to_numpy() == 1 if m else np.ones(len(df), bool)
            x = df[c].to_numpy(float)[rows]
            x = x[np.isfinite(x)]
            if not len(x):
                raise EmptyColumnError(f"{c}: nenhum valor definido nas linhas de treino")
            sd = float(x.std(ddof=0))
            self.mean[c], self.scale[c] = float(x.mean()), (sd if sd > 0 else 1.0)
        return self

    def transform(self, df):
        X = np.empty((len(df), len(FEATURES)))
        for j, c in enumerate(FEATURES):
            if c.endswith("_valid"):
                X[:, j] = df[c].to_numpy(float)
            else:
                X[:, j] = (df[c].to_numpy(float) - self.mean[c]) / self.scale[c]
        return np.nan_to_num(X, nan=0.0)


def target_sigma(df):
    """σ_c por componente do alvo: desvio populacional nas linhas de treino; zero → 1 (seção 5)."""
    sd = df[TARGET].to_numpy(float).std(axis=0, ddof=0)
    return np.where(sd > 0, sd, 1.0)


def method_twists(df):
    """(n, 4, 6) twists físicos dos métodos (NaN onde inválido) e (n, 4) máscara de validade."""
    tw = np.stack([df[[f"{m}_{c}" for c in schema.TW]].to_numpy(float) for m in METHODS], axis=1)
    valid = np.stack([df[f"{m}_valid"].to_numpy() == 1 for m in METHODS], axis=1)
    tw[~valid] = np.nan
    return tw, valid


def n_valid(df):
    return np.stack([df[f"{m}_valid"].to_numpy() == 1 for m in METHODS], axis=1).sum(axis=1)
