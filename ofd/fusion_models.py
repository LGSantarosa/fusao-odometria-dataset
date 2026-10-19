"""Modelos do protocolo de fusão — docs/protocol_fusion_model.md, seções 6–7.

Perda L = média de ((ŷ − y) / σ)², com ŷ e y em m/s e rad/s. F1 e B1–B5 predizem em unidades físicas; F2 e B6
predizem no espaço padronizado (ŷ / σ) e são despadronizados antes de qualquer métrica.
"""
import numpy as np
import torch

LR = 1e-3
BATCH = 64


def loss(pred, y, sigma):
    return float(np.mean(((np.asarray(pred) - np.asarray(y)) / np.asarray(sigma)) ** 2))


def hold_causal(pred):
    """Linhas sem predição (NaN) repetem a última predição; antes da primeira, zero (seção 6.1)."""
    out = np.array(pred, dtype=float)
    last = np.zeros(out.shape[1])
    for k in range(len(out)):
        if np.isfinite(out[k]).all():
            last = out[k]
        else:
            out[k] = last
    return out


def baseline_single(tw, valid, m):
    """B1–B4: twist do método m; inválido → retenção causal."""
    p = tw[:, m].copy()
    p[~valid[:, m]] = np.nan
    return hold_causal(p)


def baseline_mean(tw, valid):
    """B5: média simples dos twists válidos; nenhum válido → retenção causal."""
    n = valid.sum(axis=1, keepdims=True)
    with np.errstate(invalid="ignore", divide="ignore"):
        p = np.where(valid[..., None], np.nan_to_num(tw), 0.0).sum(axis=1) / n
    return hold_causal(p)


class Ridge:
    """B6: ridge com intercepto não penalizado e solução fechada (centra X e Z; resolve o sistema normal)."""

    def __init__(self, alpha):
        self.alpha = float(alpha)

    def fit(self, X, Z):
        xm, zm = X.mean(axis=0), Z.mean(axis=0)
        Xc, Zc = X - xm, Z - zm
        self.coef = np.linalg.solve(Xc.T @ Xc + self.alpha * np.eye(X.shape[1]), Xc.T @ Zc)
        self.intercept = zm - xm @ self.coef
        return self

    def predict(self, X):
        return X @ self.coef + self.intercept


def n_params(kind, n_in, width, layers):
    n_out = 4 if kind == "F1" else 6
    sizes = [n_in] + [width] * layers + [n_out]
    return sum(a * b + b for a, b in zip(sizes[:-1], sizes[1:]))


def build_net(kind, n_in, width, layers, seed):
    torch.manual_seed(seed)
    mods, d = [], n_in
    for _ in range(layers):
        mods += [torch.nn.Linear(d, width), torch.nn.ReLU()]
        d = width
    mods.append(torch.nn.Linear(d, 4 if kind == "F1" else 6))
    return torch.nn.Sequential(*mods).double()


def f1_weights(net, X, valid):
    """Softmax dos logits com os métodos inválidos mascarados; linha sem válidos → pesos nulos."""
    logits = net(X).masked_fill(~valid, float("-inf"))
    w = torch.softmax(logits, dim=1)
    return torch.nan_to_num(w, nan=0.0)


def _f1_forward(net, X, tw, valid):
    w = f1_weights(net, X, valid)
    return torch.einsum("nm,nmc->nc", w, torch.nan_to_num(tw)), w


def predict_f1(net, X, tw, valid):
    """Predição física de F1 e pesos; linha sem fonte válida → retenção causal."""
    with torch.no_grad():
        pred, w = _f1_forward(net, torch.from_numpy(X), torch.from_numpy(tw), torch.from_numpy(valid))
    pred = pred.numpy().copy()
    pred[~valid.any(axis=1)] = np.nan
    return hold_causal(pred), w.numpy()


def predict(res, X, tw, valid):
    """Predição física (m/s, rad/s) de um modelo treinado por `train_nn`."""
    if res["kind"] == "F1":
        return predict_f1(res["net"], X, tw, valid)[0]
    with torch.no_grad():
        return res["net"](torch.from_numpy(X)).numpy() * res["sigma"]


def train_nn(kind, X, Y, tw, valid, sigma, width, layers, weight_decay, seed, epochs, val=None, lr=LR,
             batch=BATCH):
    """Adam, lotes embaralhados com a semente, `epochs` épocas sem parada antecipada (seção 7).

    `val` = (X, Y, tw, valid) registra L de validação por época. Perda não finita (lote, treino ou validação) →
    `failed`. Em F1, linhas sem fonte
    válida não entram no gradiente (nenhum parâmetro as afeta; a predição delas é retenção causal).
    """
    torch.use_deterministic_algorithms(True)
    net = build_net(kind, X.shape[1], width, layers, seed)
    opt = torch.optim.Adam(net.parameters(), lr=lr, weight_decay=weight_decay)
    gen = torch.Generator().manual_seed(seed)
    s = torch.from_numpy(np.asarray(sigma, dtype=float))
    rows = np.flatnonzero(valid.any(axis=1)) if kind == "F1" else np.arange(len(X))
    Xt, Yt = torch.from_numpy(X[rows]), torch.from_numpy(Y[rows])
    twt, vt = torch.from_numpy(tw[rows]), torch.from_numpy(valid[rows])
    res = {"kind": kind, "net": net, "sigma": np.asarray(sigma, dtype=float), "train_losses": [], "val_losses": [],
           "best_epoch": None, "failed": False}
    for _ in range(epochs):
        for idx in torch.randperm(len(rows), generator=gen).split(batch):
            if kind == "F1":
                pred, _ = _f1_forward(net, Xt[idx], twt[idx], vt[idx])
                batch_loss = (((pred - Yt[idx]) / s) ** 2).mean()
            else:
                batch_loss = ((net(Xt[idx]) - Yt[idx] / s) ** 2).mean()
            if not torch.isfinite(batch_loss):
                res["failed"] = True
                return res
            opt.zero_grad()
            batch_loss.backward()
            opt.step()
        train_loss = loss(predict(res, X, tw, valid), Y, sigma)
        if not np.isfinite(train_loss):
            res["failed"] = True
            return res
        res["train_losses"].append(train_loss)
        if val is not None:
            Xv, Yv, twv, vv = val
            val_loss = loss(predict(res, Xv, twv, vv), Yv, sigma)
            if not np.isfinite(val_loss):
                res["failed"] = True
                return res
            res["val_losses"].append(val_loss)
    if val is not None:
        res["best_epoch"] = int(np.argmin(res["val_losses"])) + 1
    return res
