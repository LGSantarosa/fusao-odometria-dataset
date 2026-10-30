"""Modelos do estudo de comparação — docs/PLAN_model_comparison.md, seções 3, 4.2 e 5.

Encoders sobre janelas (n, W, F): STEP (F1-R, MLP por passo: só a última linha), MLPW (MLP sobre a janela achatada),
CNN (convolução 1D causal, saída no último passo) e LSTM (estado reiniciado em cada janela). Cabeças: W (pesos softmax
mascarados sobre as fontes válidas no endpoint, combinando só os twists atuais) e D (twist direto, espaço padronizado).

Treino sem Pα por um orçamento exato de chamadas a `optimizer.step()` (lotes de 64 reembaralhados quando o iterador
esgota); a validação e a escolha do orçamento usam a perda depois de Pα (`ofd.mc_filters.apply_p_alpha`).
"""
import numpy as np
import torch

from ofd import mc_filters

LR = 1e-3
BATCH = 64
FAMILIES = ("STEP", "MLPW", "CNN", "LSTM")
N_SOURCES = 4
N_OUT = 6


class _MLP(torch.nn.Module):
    def __init__(self, n_in, width, layers, last_only):
        super().__init__()
        mods, d = [], n_in
        for _ in range(layers):
            mods += [torch.nn.Linear(d, width), torch.nn.ReLU()]
            d = width
        self.net, self.out_dim, self.last_only = torch.nn.Sequential(*mods), d, last_only

    def forward(self, x):                      # x: (B, W, F)
        return self.net(x[:, -1] if self.last_only else x.flatten(1))


class _CNN(torch.nn.Module):
    def __init__(self, n_feat, channels, layers, kernel):
        super().__init__()
        self.kernel = kernel
        self.convs = torch.nn.ModuleList(
            torch.nn.Conv1d(n_feat if i == 0 else channels, channels, kernel) for i in range(layers))
        self.out_dim = channels

    def forward(self, x):                      # (B, W, F) → (B, C, W); preenchimento só à esquerda (causal)
        h = x.transpose(1, 2)
        for conv in self.convs:
            h = torch.relu(conv(torch.nn.functional.pad(h, (self.kernel - 1, 0))))
        return h[:, :, -1]


class _LSTM(torch.nn.Module):
    def __init__(self, n_feat, hidden, layers):
        super().__init__()
        self.lstm = torch.nn.LSTM(n_feat, hidden, layers, batch_first=True)
        self.out_dim = hidden

    def forward(self, x):                      # estado zero em cada janela
        return self.lstm(x)[0][:, -1]


def build(family, head, n_feat, W, cfg, seed):
    """Modelo = encoder + camada linear da cabeça (4 logits em W, 6 saídas em D)."""
    if family not in FAMILIES or head not in ("W", "D"):
        raise ValueError(f"família {family!r} ou cabeça {head!r} desconhecida")
    torch.manual_seed(seed)
    if family in ("STEP", "MLPW"):
        enc = _MLP(n_feat if family == "STEP" else n_feat * W, cfg["width"], cfg["layers"], family == "STEP")
    elif family == "CNN":
        enc = _CNN(n_feat, cfg["channels"], cfg["layers"], cfg["kernel"])
    else:
        enc = _LSTM(n_feat, cfg["hidden"], cfg["layers"])
    return torch.nn.Sequential(enc, torch.nn.Linear(enc.out_dim, N_SOURCES if head == "W" else N_OUT)).double()


def n_params(model):
    return sum(p.numel() for p in model.parameters())


def _forward(model, head, xw, tw, valid, sigma):
    """W: predição física (m/s, rad/s) combinando só os twists atuais válidos; D: ŷ / σ (espaço padronizado)."""
    z = model(xw)
    if head == "D":
        return z, None
    w = torch.nan_to_num(torch.softmax(z.masked_fill(~valid, float("-inf")), dim=1), nan=0.0)
    return torch.einsum("nm,nmc->nc", w, torch.nan_to_num(tw)), w


def predict_raw(model, head, Xw, tw, valid, sigma, chunk=4096):
    """Predição física antes da retenção e de Pα; na cabeça W, linha sem fonte válida → NaN."""
    out = []
    with torch.no_grad():
        for a in range(0, len(Xw), chunk):
            s = slice(a, a + chunk)
            p, _ = _forward(model, head, torch.from_numpy(Xw[s]), torch.from_numpy(tw[s]),
                            torch.from_numpy(valid[s]), sigma)
            out.append(p.numpy() * (np.asarray(sigma) if head == "D" else 1.0))
    pred = np.concatenate(out) if out else np.zeros((0, N_OUT))
    if head == "W":
        pred[~valid.any(axis=1)] = np.nan
    return pred


def weights(model, Xw, tw, valid):
    with torch.no_grad():
        return _forward(model, "W", torch.from_numpy(Xw), torch.from_numpy(tw), torch.from_numpy(valid), None)[1].numpy()


def loss(pred, y, sigma, rows):
    """L = média de ((ŷ − y) / σ)² nos endpoints `rows` com alvo finito."""
    rows = np.asarray(rows, bool) & np.isfinite(y).all(axis=1)
    return float(np.mean(((pred[rows] - y[rows]) / np.asarray(sigma)) ** 2)) if rows.any() else np.nan


def val_loss_after_p_alpha(model, head, Xw, tw, valid, y, sigma, alpha, val_rows):
    """Pα percorre a sequência inteira a partir do início; a perda é recortada nos endpoints de validação."""
    out = mc_filters.apply_p_alpha(predict_raw(model, head, Xw, tw, valid, sigma), alpha)
    return loss(out, y, sigma, val_rows)


def checkpoint_schedule(max_updates, early=(50, 100), every=200):
    """Checkpoints em 50, 100 e depois a cada 200 atualizações até o máximo (inclusive)."""
    steps = [s for s in early if s < max_updates] + list(range(every, max_updates + 1, every))
    return sorted(set(steps) | {max_updates})


def train(model, head, Xw, Y, tw, valid, sigma, train_rows, updates, seed, weight_decay=0.0, lr=LR, batch=BATCH,
          checkpoints=None, val=None):
    """Adam por exatamente `updates` chamadas a `optimizer.step()`.

    `train_rows`: endpoints de treino (alvo finito exigido; na cabeça W também ao menos uma fonte válida, pois nenhum
    parâmetro afeta as outras linhas). `val`: função model → perda de validação depois de Pα, avaliada nos números de
    atualizações em `checkpoints`. Perda não finita → `failed`. Devolve checkpoints, o melhor orçamento (menor perda;
    empate → menos atualizações) e `saturated` quando o melhor é o último checkpoint.
    """
    torch.use_deterministic_algorithms(True)
    rows = np.asarray(train_rows, bool) & np.isfinite(Y).all(axis=1)
    if head == "W":
        rows &= valid.any(axis=1)
    idx_all = np.flatnonzero(rows)
    res = {"checkpoints": [], "best_updates": None, "failed": False, "n_train": int(len(idx_all))}
    if not len(idx_all):
        res["failed"] = True
        return res
    s = torch.from_numpy(np.asarray(sigma, float))
    Xt, Yt = torch.from_numpy(Xw[idx_all]), torch.from_numpy(Y[idx_all])
    twt, vt = torch.from_numpy(tw[idx_all]), torch.from_numpy(valid[idx_all])
    opt = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=weight_decay)
    gen = torch.Generator().manual_seed(seed)
    marks = set(checkpoints or ())
    order = []
    for step in range(1, updates + 1):
        if not order:
            order = list(torch.randperm(len(idx_all), generator=gen).split(batch))
        b = order.pop(0)
        p, _ = _forward(model, head, Xt[b], twt[b], vt[b], s)
        target = Yt[b] / s if head == "D" else Yt[b]
        batch_loss = (((p - target) / (1.0 if head == "D" else s)) ** 2).mean()
        if not torch.isfinite(batch_loss):
            res["failed"] = True
            return res
        opt.zero_grad()
        batch_loss.backward()
        opt.step()
        if val is not None and step in marks:
            v = val(model)
            if not np.isfinite(v):
                res["failed"] = True
                return res
            res["checkpoints"].append((step, v))
    if res["checkpoints"]:
        res["best_updates"] = min(res["checkpoints"], key=lambda c: (c[1], c[0]))[0]
        res["saturated"] = res["best_updates"] == res["checkpoints"][-1][0]
    return res
