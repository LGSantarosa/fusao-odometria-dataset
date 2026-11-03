"""Gate de desenvolvimento: RMSE físico (m/s, rad/s) por dobra das escolhas do piloto formal da fase 3.

Refaz os jobs finais das configurações selecionadas (mesmas sementes e orçamentos de dobra de ``grid.json``), confere a
perda padronizada contra o piloto e grava ``gate_dev_rmse.json`` na raiz do piloto formal. Usa somente ``1018-00`` e
``1018-13`` pela allowlist de ``ofd.mc_pilot``; nunca lê dados externos.

Uso:
    python -m ofd.mc_gate
"""
import json
from concurrent.futures import ProcessPoolExecutor

import numpy as np

from ofd import mc_filters, mc_models, mc_pilot as P

FAMILIES = ("STEP", "MLPW", "CNN", "LSTM")


def rmse(pred, y):
    """RMSE vetorial da velocidade linear (vx, vy, vz) e angular (wx, wy, wz) nas linhas finitas."""
    rows = np.isfinite(y).all(axis=1) & np.isfinite(pred).all(axis=1)
    e = pred[rows] - y[rows]
    return {"lin": float(np.sqrt(np.mean(np.sum(e[:, :3] ** 2, axis=1)))),
            "ang": float(np.sqrt(np.mean(np.sum(e[:, 3:] ** 2, axis=1))))}


def _neural(spec):
    import torch
    torch.set_num_threads(1)
    family, cfg, W, alpha, fold, seed, updates = (
        spec[k] for k in ("family", "cfg", "W", "alpha", "fold", "seed", "updates"))
    a = P._arrays(*P.FOLDS[fold], W)
    model = mc_models.build(family, "W", len(P.fd.FEATURES), W, P._model_cfg(cfg), seed)
    rows = np.isfinite(a["Ytr"]).all(axis=1)
    mc_models.train(model, "W", a["Xtr"], a["Ytr"], a["twtr"], a["vtr"], a["sigma"], rows, updates, seed,
                    weight_decay=cfg["weight_decay"])
    pred = mc_filters.apply_p_alpha(mc_models.predict_raw(model, "W", a["Xte"], a["twte"], a["vte"], a["sigma"]),
                                    alpha)
    return {**spec, "cfg": P._cfg_id(cfg), **rmse(pred, a["Yte"]), "loss": P._loss(pred, a["Yte"], a["sigma"])}


def run(root=P.ROOT, workers=4):
    g = json.loads((root / "grid.json").read_text())
    t2 = json.loads((root / "t2.json").read_text())["chosen"]
    alpha, W = g["alpha"], g["W"]
    rows = []
    for fold, (tr, te) in P.FOLDS.items():
        a = P._arrays(tr, te, 1)
        p = mc_filters.t1(a["twte"], a["vte"], alpha)
        rows.append({"family": "B5", "fold": fold, "seed": None, **rmse(p, a["Yte"]),
                     "loss": P._loss(p, a["Yte"], a["sigma"])})
        k = mc_filters.TwistKalman(q_scale=t2["q_scale"], r_scale=t2["r_scale"]).fit(a["twtr"], a["vtr"], a["Ytr"])
        p = k.predict(a["twte"], a["vte"])
        rows.append({"family": "T2", "fold": fold, "seed": None, **rmse(p, a["Yte"]),
                     "loss": P._loss(p, a["Yte"], a["sigma"])})
    specs = []
    for fam in FAMILIES:
        cfg = g["selected"][fam]["config"]
        used_W = 1 if fam == "STEP" else W
        for fold in P.FOLDS:
            upd = g["budgets"][f"{fam}|{P._cfg_id(cfg)}|{used_W}|{fold}"]
            specs += [{"family": fam, "cfg": cfg, "W": used_W, "alpha": alpha, "fold": fold, "seed": s,
                       "updates": upd} for s in P.CV_SEEDS]
    with ProcessPoolExecutor(workers) as pool:
        neural = list(pool.map(_neural, specs))
    ref = {(r["family"], P._cfg_id(r["cfg"]), r["fold"], r["seed"]): r["loss"] for r in g["final"]}
    diff = max(abs(r["loss"] - ref[(r["family"], r["cfg"], r["fold"], r["seed"])]) for r in neural)
    rows += neural
    summary = {}
    for fam in ("B5", "T2") + FAMILIES:
        for fold in P.FOLDS:
            rr = [r for r in rows if r["family"] == fam and r["fold"] == fold]
            summary[f"{fam}|{fold}"] = {m: float(np.mean([r[m] for r in rr])) for m in ("lin", "ang", "loss")}
    out = {"alpha": alpha, "W": W, "max_abs_loss_diff_vs_grid": diff, "summary": summary, "runs": rows,
           "seed_aggregation": "média das métricas por semente"}
    P._atomic_json(root / "gate_dev_rmse.json", out)
    return out


def main():
    out = run()
    print(f"max |perda - grid| = {out['max_abs_loss_diff_vs_grid']}")
    for k, v in out["summary"].items():
        print(f"{k:8} lin {v['lin']:.4f} m/s  ang {v['ang']:.4f} rad/s  perda {v['loss']:.4f}")


if __name__ == "__main__":
    main()
