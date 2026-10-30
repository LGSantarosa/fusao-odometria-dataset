"""Piloto provisório da fase 3 em 1018-00/1018-13.

Este módulo nunca aceita caminhos ou nomes de sequência pela CLI: a allowlist de
desenvolvimento é fixa. Resultados ficam em ``data/analysis/model_comparison/
provisional_phase3`` e não autorizam processamento do teste externo.

Uso:
    python -m ofd.mc_pilot alpha
    python -m ofd.mc_pilot window --workers 4
    python -m ofd.mc_pilot grid --workers 4
    python -m ofd.mc_pilot t2
"""
import argparse
import hashlib
import json
import math
import os
import subprocess
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from ofd import fusion_data as fd, mc_data, mc_filters, mc_models


DEV = ("1018-00", "1018-13")
FOLDS = {"A": ("1018-00", "1018-13"), "B": ("1018-13", "1018-00")}
ROOT = Path("data/analysis/model_comparison/provisional_phase3")
ALPHAS = (0.1, 0.2, 0.5, 1.0)
WINDOWS = (5, 10, 20)
CV_SEEDS = (0, 1, 2)
MAX_UPDATES = 8000
MAX_PARAMS = 100_000
MAX_EMBARGO_FRACTION = 0.25
W_REFERENCE = {"width": 32, "layers": 1, "weight_decay": 1e-3}
T2_Q = (0.1, 0.3, 1.0, 3.0, 10.0)
T2_R = (0.3, 1.0, 3.0)


def _neural_grids():
    decay = (1e-4, 1e-3, 1e-2)
    common = ((size, layers, wd) for size in (16, 32, 64) for layers in (1, 2) for wd in decay)
    out = {}
    for family in mc_models.FAMILIES:
        key = "width" if family in ("STEP", "MLPW") else ("channels" if family == "CNN" else "hidden")
        out[family] = [{key: size, "layers": layers, "weight_decay": wd,
                        **({"kernel": 3} if family == "CNN" else {})}
                       for size in (16, 32, 64) for layers in (1, 2) for wd in decay]
    return out


GRIDS = _neural_grids()


def _jsonable_cfg(cfg):
    return {k: cfg[k] for k in sorted(cfg)}


def _cfg_id(cfg):
    return ",".join(f"{k}={v}" for k, v in _jsonable_cfg(cfg).items())


def _git(*args):
    return subprocess.check_output(("git", *args), text=True).strip()


def _manifest_payload():
    return {
        "status": "PROVISIONAL_DEVELOPMENT_PILOT",
        "external_test_authorized": False,
        "development_sequences": list(DEV),
        "commit": _git("rev-parse", "HEAD"),
        "alphas": list(ALPHAS),
        "windows": list(WINDOWS),
        "cv_seeds": list(CV_SEEDS),
        "max_updates": MAX_UPDATES,
        "checkpoints": mc_models.checkpoint_schedule(MAX_UPDATES),
        "max_params": MAX_PARAMS,
        "max_embargo_fraction": MAX_EMBARGO_FRACTION,
        "w_reference": W_REFERENCE,
        "t2_q_scale": list(T2_Q),
        "t2_r_scale": list(T2_R),
        "grids": {k: [_jsonable_cfg(c) for c in v] for k, v in GRIDS.items()},
    }


def initialize(root=ROOT, require_clean=True):
    """Cria ou confere manifesto imutável. Uma árvore suja não inicia o piloto oficial provisório."""
    if require_clean and _git("status", "--porcelain"):
        raise RuntimeError("árvore Git suja; faça commit antes de iniciar o piloto")
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    path = root / "manifest.json"
    payload = _manifest_payload()
    if path.exists():
        old = json.loads(path.read_text())
        if old != payload:
            raise RuntimeError("manifesto provisório já existe com commit ou configuração diferente")
    else:
        _atomic_json(path, payload)
    return payload


def _atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(tmp, path)


def _load(seq):
    if seq not in DEV:
        raise ValueError(f"sequência {seq!r} fora da allowlist de desenvolvimento")
    path = Path("data/output") / f"{seq}.parquet"
    df = pd.read_parquet(path)
    got = df["seq"].astype(str).unique().tolist()
    if got != [seq]:
        raise ValueError(f"identidade inesperada em {path}: {got}")
    return df


def _arrays(train_seq, test_seq, W):
    train, test = _load(train_seq), _load(test_seq)
    target_train = train.loc[fd.target_rows(train)]
    st = fd.Standardizer().fit(train)
    sigma = fd.target_sigma(target_train)
    Xtr, Xte = st.transform(train), st.transform(test)
    Ytr, Yte = train[fd.TARGET].to_numpy(float), test[fd.TARGET].to_numpy(float)
    twtr, vtr = fd.method_twists(train)
    twte, vte = fd.method_twists(test)
    return {
        "train": train, "test": test, "Xtr": mc_data.windows(Xtr, W), "Xte": mc_data.windows(Xte, W),
        "Ytr": Ytr, "Yte": Yte, "twtr": twtr, "twte": twte, "vtr": vtr, "vte": vte, "sigma": sigma,
    }


def _loss(pred, y, sigma):
    rows = np.isfinite(y).all(axis=1)
    return mc_models.loss(pred, y, sigma, rows)


def _choose(rows, loss_key="loss", complexity_key=None):
    valid = [r for r in rows if np.isfinite(r[loss_key])]
    if not valid:
        return None
    best = min(r[loss_key] for r in valid)
    eligible = [r for r in valid if r[loss_key] <= 1.01 * best]
    if complexity_key is None:
        return min(eligible, key=lambda r: r[loss_key])
    return min(eligible, key=lambda r: (r[complexity_key], r[loss_key]))


def select_alpha(root=ROOT):
    initialize(root)
    rows = []
    for alpha in ALPHAS:
        losses, structural = [], []
        for fold, (train_seq, test_seq) in FOLDS.items():
            a = _arrays(train_seq, test_seq, max(WINDOWS))
            egt = mc_data.e_gt(a["Ytr"])
            eb, ea = mc_data.embargo(max(WINDOWS), alpha, egt)
            frac = mc_data.embargo_fraction(len(a["train"]), eb, ea)
            structural.append(frac <= MAX_EMBARGO_FRACTION)
            pred = mc_filters.t1(a["twte"], a["vte"], alpha)
            loss = _loss(pred, a["Yte"], a["sigma"])
            losses.append(loss)
            rows.append({"alpha": alpha, "fold": fold, "loss": loss, "e_gt": egt,
                         "e_before": eb, "e_after": ea, "embargo_fraction": frac,
                         "structurally_valid": frac <= MAX_EMBARGO_FRACTION})
        if not all(structural):
            for r in rows:
                if r["alpha"] == alpha:
                    r["loss"] = None
    agg = []
    for alpha in ALPHAS:
        rr = [r for r in rows if r["alpha"] == alpha and r["loss"] is not None]
        agg.append({"alpha": alpha, "loss": float(np.mean([r["loss"] for r in rr])) if len(rr) == len(FOLDS) else None})
    valid = [r for r in agg if r["loss"] is not None]
    best = min(r["loss"] for r in valid)
    # Dentro de 1% da melhor, maior alpha = menor memória e solução mais simples.
    chosen = max((r for r in valid if r["loss"] <= 1.01 * best), key=lambda r: r["alpha"])
    out = {"chosen_alpha": chosen["alpha"], "folds": rows, "aggregate": agg,
           "tie_rule": "loss <= 1.01 * minimum; choose largest alpha"}
    _atomic_json(Path(root) / "alpha.json", out)
    return out


def _model_cfg(cfg):
    return {k: v for k, v in cfg.items() if k != "weight_decay"}


def _inner_job(spec):
    """Uma configuração/semente/dobra; devolve os cinco orçamentos internos."""
    torch.set_num_threads(1)
    family, cfg, W, alpha, fold, seed = (spec[k] for k in ("family", "cfg", "W", "alpha", "fold", "seed"))
    train_seq, test_seq = FOLDS[fold]
    a = _arrays(train_seq, test_seq, W)
    egt = mc_data.e_gt(a["Ytr"])
    eb, ea = mc_data.embargo(W, alpha, egt)
    frac = mc_data.embargo_fraction(len(a["train"]), eb, ea)
    if frac > MAX_EMBARGO_FRACTION:
        raise RuntimeError(f"{fold}/{family}/{W}: embargo {frac:.6f} > {MAX_EMBARGO_FRACTION}")
    checkpoints = mc_models.checkpoint_schedule(MAX_UPDATES)
    runs = []
    for subfold, masks in enumerate(mc_data.inner_folds(len(a["train"]), eb, ea)):
        model = mc_models.build(family, "W", len(fd.FEATURES), W, _model_cfg(cfg), seed)
        if mc_models.n_params(model) > MAX_PARAMS:
            raise RuntimeError(f"{family}/{_cfg_id(cfg)} excede {MAX_PARAMS} parâmetros")
        val = lambda m, masks=masks: mc_models.val_loss_after_p_alpha(
            m, "W", a["Xtr"], a["twtr"], a["vtr"], a["Ytr"], a["sigma"], alpha, masks["val"])
        res = mc_models.train(model, "W", a["Xtr"], a["Ytr"], a["twtr"], a["vtr"], a["sigma"],
                              masks["train"], MAX_UPDATES, seed, weight_decay=cfg["weight_decay"],
                              checkpoints=checkpoints, val=val)
        runs.append({"subfold": subfold, "best_updates": res["best_updates"], "failed": res["failed"],
                     "saturated": res.get("saturated"), "n_train": res["n_train"],
                     "checkpoints": res["checkpoints"]})
    return {**spec, "cfg": _jsonable_cfg(cfg), "e_gt": egt, "e_before": eb, "e_after": ea,
            "embargo_fraction": frac, "runs": runs}


def _final_job(spec):
    torch.set_num_threads(1)
    family, cfg, W, alpha, fold, seed, updates = (
        spec[k] for k in ("family", "cfg", "W", "alpha", "fold", "seed", "updates"))
    train_seq, test_seq = FOLDS[fold]
    a = _arrays(train_seq, test_seq, W)
    model = mc_models.build(family, "W", len(fd.FEATURES), W, _model_cfg(cfg), seed)
    rows = np.isfinite(a["Ytr"]).all(axis=1)
    res = mc_models.train(model, "W", a["Xtr"], a["Ytr"], a["twtr"], a["vtr"], a["sigma"], rows,
                          updates, seed, weight_decay=cfg["weight_decay"])
    if res["failed"]:
        return {**spec, "cfg": _jsonable_cfg(cfg), "failed": True, "loss": None}
    raw = mc_models.predict_raw(model, "W", a["Xte"], a["twte"], a["vte"], a["sigma"])
    pred = mc_filters.apply_p_alpha(raw, alpha)
    return {**spec, "cfg": _jsonable_cfg(cfg), "failed": False,
            "loss": _loss(pred, a["Yte"], a["sigma"]), "n_params": mc_models.n_params(model)}


def _run_parallel(jobs, fn, workers):
    out = []
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(fn, j): j for j in jobs}
        for i, future in enumerate(as_completed(futures), 1):
            out.append(future.result())
            print(f"{fn.__name__}: {i}/{len(jobs)}", flush=True)
    return out


def _median_up(values):
    return int(math.ceil(float(np.median(values))))


def _run_family_configs(configs, alpha, workers):
    inner_specs = [{"family": family, "cfg": cfg, "W": W, "alpha": alpha, "fold": fold, "seed": seed}
                   for family, cfg, W in configs for fold in FOLDS for seed in CV_SEEDS]
    inner = _run_parallel(inner_specs, _inner_job, workers)
    budgets = {}
    for family, cfg, W in configs:
        cid = _cfg_id(cfg)
        for fold in FOLDS:
            rr = [r for r in inner if r["family"] == family and _cfg_id(r["cfg"]) == cid
                  and r["W"] == W and r["fold"] == fold]
            best = [x["best_updates"] for r in rr for x in r["runs"] if not x["failed"]]
            budgets[(family, cid, W, fold)] = _median_up(best) if len(best) == len(CV_SEEDS) * fd.N_BLOCKS else None
    final_specs = []
    for family, cfg, W in configs:
        cid = _cfg_id(cfg)
        for fold in FOLDS:
            updates = budgets[(family, cid, W, fold)]
            if updates is not None:
                final_specs.extend({"family": family, "cfg": cfg, "W": W, "alpha": alpha, "fold": fold,
                                    "seed": seed, "updates": updates} for seed in CV_SEEDS)
    final = _run_parallel(final_specs, _final_job, workers)
    return inner, final, {"|".join(map(str, k)): v for k, v in budgets.items()}


def select_window(root=ROOT, workers=4):
    initialize(root)
    alpha_path = Path(root) / "alpha.json"
    alpha = json.loads(alpha_path.read_text())["chosen_alpha"] if alpha_path.exists() else select_alpha(root)["chosen_alpha"]
    cfg = dict(W_REFERENCE)
    configs = [("MLPW", cfg, W) for W in WINDOWS]
    inner, final, budgets = _run_family_configs(configs, alpha, workers)
    agg = []
    for W in WINDOWS:
        rr = [r for r in final if r["W"] == W and not r["failed"]]
        agg.append({"W": W, "loss": float(np.mean([r["loss"] for r in rr])) if len(rr) == len(FOLDS) * len(CV_SEEDS) else None})
    valid = [r for r in agg if r["loss"] is not None]
    best = min(r["loss"] for r in valid)
    chosen = min((r for r in valid if r["loss"] <= 1.01 * best), key=lambda r: r["W"])
    out = {"chosen_W": chosen["W"], "alpha": alpha, "reference": cfg, "aggregate": agg,
           "inner": inner, "final": final, "budgets": budgets,
           "tie_rule": "loss <= 1.01 * minimum; choose smallest W"}
    _atomic_json(Path(root) / "window.json", out)
    return out


def run_grid(root=ROOT, workers=4):
    initialize(root)
    wp = Path(root) / "window.json"
    win = json.loads(wp.read_text()) if wp.exists() else select_window(root, workers)
    alpha, W = win["alpha"], win["chosen_W"]
    configs = [(family, cfg, (1 if family == "STEP" else W)) for family, grid in GRIDS.items() for cfg in grid]
    inner, final, budgets = _run_family_configs(configs, alpha, workers)
    agg = []
    for family, cfg, used_W in configs:
        cid = _cfg_id(cfg)
        rr = [r for r in final if r["family"] == family and _cfg_id(r["cfg"]) == cid and not r["failed"]]
        loss = float(np.mean([r["loss"] for r in rr])) if len(rr) == len(FOLDS) * len(CV_SEEDS) else None
        params = rr[0]["n_params"] if rr else None
        agg.append({"family": family, "config": _jsonable_cfg(cfg), "W": used_W, "loss": loss, "n_params": params})
    selected = {}
    for family in GRIDS:
        chosen = _choose([r for r in agg if r["family"] == family], complexity_key="n_params")
        selected[family] = chosen
    temporal = _choose([selected[k] for k in ("CNN", "LSTM") if selected[k] is not None], complexity_key="n_params")
    out = {"alpha": alpha, "W": W, "aggregate": agg, "selected": selected,
           "selected_temporal": temporal, "inner": inner, "final": final, "budgets": budgets,
           "tie_rule": "loss <= 1.01 * minimum; choose fewer parameters"}
    _atomic_json(Path(root) / "grid.json", out)
    return out


def select_t2(root=ROOT):
    initialize(root)
    rows = []
    for q in T2_Q:
        for r in T2_R:
            losses = []
            for fold, (train_seq, test_seq) in FOLDS.items():
                a = _arrays(train_seq, test_seq, 1)
                model = mc_filters.TwistKalman(q_scale=q, r_scale=r).fit(a["twtr"], a["vtr"], a["Ytr"])
                loss = _loss(model.predict(a["twte"], a["vte"]), a["Yte"], a["sigma"])
                rows.append({"q_scale": q, "r_scale": r, "fold": fold, "loss": loss})
                losses.append(loss)
    agg = [{"q_scale": q, "r_scale": r,
            "loss": float(np.mean([x["loss"] for x in rows if x["q_scale"] == q and x["r_scale"] == r]))}
           for q in T2_Q for r in T2_R]
    best = min(x["loss"] for x in agg)
    eligible = [x for x in agg if x["loss"] <= 1.01 * best]
    chosen = min(eligible, key=lambda x: (abs(math.log10(x["q_scale"])), abs(math.log10(x["r_scale"])), x["loss"]))
    out = {"chosen": chosen, "folds": rows, "aggregate": agg,
           "tie_rule": "loss <= 1.01 * minimum; scales closest to 1"}
    _atomic_json(Path(root) / "t2.json", out)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("phase", choices=("alpha", "window", "grid", "t2"))
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    if args.workers < 1:
        ap.error("--workers deve ser >= 1")
    result = {"alpha": select_alpha, "window": lambda: select_window(workers=args.workers),
              "grid": lambda: run_grid(workers=args.workers), "t2": select_t2}[args.phase]()
    summary = {k: result[k] for k in ("chosen_alpha", "chosen_W", "selected", "chosen") if k in result}
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
