"""Orquestração do protocolo de fusão — docs/protocol_fusion_model.md, seções 4, 7, 9–12.

Fase 1 (`phase1`): validação interna só na sequência de treino da dobra; grava `cv.csv` e `selected.json`.
Fase 2 (`phase2`): modelos finais a partir do `selected.json` congelado, métricas na sequência de teste e regra de
decisão. `rellis_inference`: só descrições, sem métricas de erro.

uso: python -m ofd.fusion_run phase1 --fold A|B
     python -m ofd.fusion_run phase2
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from ofd import fusion_data as fd, fusion_eval as fe, fusion_models as fm, schema

GRIDS = {"B6": [{"alpha": a} for a in (1e-3, 1e-2, 1e-1, 1, 10, 100, 1000)],
         **{k: [{"width": w, "layers": n, "weight_decay": wd}
                for w in (16, 32, 64) for n in (1, 2) for wd in (1e-4, 1e-3, 1e-2)] for k in ("F1", "F2")}}
CV_SEEDS = (0, 1, 2)
FINAL_SEEDS = (0, 1, 2, 3, 4)
MAX_EPOCHS = 500
FOLDS = {"A": ("1018-00", "1018-13"), "B": ("1018-13", "1018-00")}   # dobra: (treino, teste)
RELLIS = ("rellis_example", "00000")
ROOT = Path("data/analysis/fusion")
SINGLE = [f"B{i + 1}" for i in range(len(fd.METHODS))]                # B1–B4 na ordem de fd.METHODS


def _cfg_id(cfg):
    return ",".join(f"{k}={v}" for k, v in cfg.items())


def _complexity(family, cfg):
    if family == "B6":
        return len(fd.FEATURES), cfg["alpha"]
    return fm.n_params(family, len(fd.FEATURES), cfg["width"], cfg["layers"]), cfg["weight_decay"]


def _gt_part(df):
    D = df[fd.target_rows(df)].reset_index(drop=True)
    return D, D[fd.TARGET].to_numpy(float), *fd.method_twists(D)


def _sequence_of(df):
    (seq,) = df["seq"].astype(str).unique()
    return seq


def phase1(train_df, out_dir, fold, grids=GRIDS, seeds=CV_SEEDS, max_epochs=MAX_EPOCHS):
    """Validação interna (seções 4 e 7) só com a sequência de treino; nenhuma outra sequência é recebida. A seleção
    registra a dobra e a sequência de treino, conferidas na fase 2."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    D, Y, tw, valid = _gt_part(train_df)
    singles = [fm.baseline_single(tw, valid, m) for m in range(len(fd.METHODS))]
    rows = []
    for j, (tr, va) in enumerate(fd.blocks(len(D))):
        sigma = fd.target_sigma(D.iloc[tr])
        for b, pred in zip(SINGLE, singles):
            rows.append({"family": b, "config": fd.METHODS[SINGLE.index(b)], "subfold": j, "seed": np.nan,
                         "loss": fm.loss(pred[va], Y[va], sigma), "best_epoch": np.nan, "failed": False})
        try:
            st = fd.Standardizer().fit(D.iloc[tr])
        except fd.EmptyColumnError as e:
            for family, cfgs in grids.items():
                for cfg in cfgs:
                    for seed in ([np.nan] if family == "B6" else seeds):
                        rows.append({"family": family, "config": _cfg_id(cfg), "subfold": j, "seed": seed,
                                     "loss": np.nan, "best_epoch": np.nan, "failed": True, "reason": str(e)})
            continue
        X = st.transform(D)
        for cfg in grids.get("B6", []):
            pred = fm.Ridge(cfg["alpha"]).fit(X[tr], Y[tr] / sigma).predict(X) * sigma
            rows.append({"family": "B6", "config": _cfg_id(cfg), "subfold": j, "seed": np.nan,
                         "loss": fm.loss(pred[va], Y[va], sigma), "best_epoch": np.nan, "failed": False})
        for family in ("F1", "F2"):
            for cfg in grids.get(family, []):
                for seed in seeds:
                    res = fm.train_nn(family, X[tr], Y[tr], tw[tr], valid[tr], sigma, seed=seed, epochs=max_epochs,
                                      val=(X[va], Y[va], tw[va], valid[va]), **cfg)
                    rows.append({"family": family, "config": _cfg_id(cfg), "subfold": j, "seed": seed,
                                 "loss": np.nan if res["failed"] else min(res["val_losses"]),
                                 "best_epoch": res["best_epoch"], "failed": res["failed"]})
    cv = pd.DataFrame(rows)
    cv.to_csv(out_dir / "cv.csv", index=False)

    single = cv[cv["family"].isin(SINGLE)].groupby("config", sort=False)["loss"].mean()
    families = {}
    for family, cfgs in grids.items():
        agg = fe.aggregate_cv(cv[cv["family"] == family])
        by_id = {_cfg_id(c): c for c in cfgs}
        agg["n_params"], agg["reg"] = zip(*(_complexity(family, by_id[c]) for c in agg["config"]))
        chosen = fe.select(agg)
        entry = {"config": by_id[chosen] if chosen else None, "epochs": None,
                 "cv_loss": float(agg.set_index("config").loc[chosen, "loss"]) if chosen else None}
        if chosen and family != "B6":
            entry["epochs"] = fe.final_epochs(cv[(cv["family"] == family) & (cv["config"] == chosen)]["best_epoch"])
        families[family] = entry
    try:
        st = fd.Standardizer().fit(D)
        standardizer = {"mean": st.mean, "scale": st.scale}
    except fd.EmptyColumnError:
        standardizer = None                                              # modelo final da dobra: falha
    selected = {"fold": fold, "train_sequence": _sequence_of(train_df), "n_rows": len(D), "bsel": single.idxmin(), "bsel_cv_loss": float(single.min()),
                "families": families, "standardizer": standardizer, "target_sigma": fd.target_sigma(D).tolist()}
    (out_dir / "selected.json").write_text(json.dumps(selected, indent=2))
    return selected


def _frozen_standardizer(selected):
    st = fd.Standardizer()
    st.mean, st.scale = dict(selected["standardizer"]["mean"]), dict(selected["standardizer"]["scale"])
    return st


def _check_frozen(selected, fold, train_df, test_df=None):
    """Seleção congelada completa e da mesma dobra e sequência de treino; teste ≠ treino (evita vazamento)."""
    if selected.get("fold") != fold:
        raise ValueError(f"seleção da dobra {selected.get('fold')!r} usada na dobra {fold!r}")
    if selected.get("train_sequence") != _sequence_of(train_df):
        raise ValueError(f"{fold}: sequência de treino {_sequence_of(train_df)!r} difere da seleção "
                         f"({selected.get('train_sequence')!r})")
    if test_df is not None and _sequence_of(test_df) == selected["train_sequence"]:
        raise ValueError(f"{fold}: sequência de teste igual à de treino")
    if selected["standardizer"] is None:
        raise ValueError("seleção sem padronização: modelo final da dobra falhou")
    for family, entry in selected["families"].items():
        if entry["config"] is None:
            raise ValueError(f"{family}: nenhuma configuração escolhida na fase 1")


def fit_final(train_df, selected, seeds):
    """Modelos finais (seção 7) na sequência de treino inteira, com a seleção congelada (já conferida)."""
    D, Y, tw, valid = _gt_part(train_df)
    st, sigma = _frozen_standardizer(selected), np.asarray(selected["target_sigma"])
    X = st.transform(D)
    fam = selected["families"]
    models = {"B6": fm.Ridge(fam["B6"]["config"]["alpha"]).fit(X, Y / sigma)}
    for family in ("F1", "F2"):
        cfg = fam[family]["config"]
        for seed in seeds:
            models[(family, seed)] = fm.train_nn(family, X, Y, tw, valid, sigma, seed=seed,
                                                 epochs=fam[family]["epochs"], **cfg)
    return st, sigma, models


def _predictions(df, selected, st, sigma, models, seeds):
    """{(modelo, semente|None): (predição física em todas as linhas, pesos F1 | None, falhou)}."""
    tw, valid = fd.method_twists(df)
    X = st.transform(df)
    out = {(b, None): (fm.baseline_single(tw, valid, m), None, False) for m, b in enumerate(SINGLE)}
    out[("B5", None)] = (fm.baseline_mean(tw, valid), None, False)
    out[("Bsel", None)] = out[(SINGLE[fd.METHODS.index(selected["bsel"])], None)]
    out[("B6", None)] = (models["B6"].predict(X) * sigma, None, False)
    for family in ("F1", "F2"):
        for seed in seeds:
            res = models[(family, seed)]
            if res["failed"]:
                out[(family, seed)] = (None, None, True)
            elif family == "F1":
                pred, w = fm.predict_f1(res["net"], X, tw, valid)
                out[(family, seed)] = (pred, w, False)
            else:
                out[(family, seed)] = (fm.predict(res, X, tw, valid), None, False)
    return out


def phase2(folds, out_dir, seeds=FINAL_SEEDS):
    """{dobra: (treino, teste, selected)} → métricas da seção 9 na sequência de teste, estratos, pesos e decisão."""
    out_dir = Path(out_dir)
    (out_dir / "predictions").mkdir(parents=True, exist_ok=True)
    for fold, (train_df, test_df, selected) in folds.items():
        _check_frozen(selected, fold, train_df, test_df)
    metrics, strata, weights, case_f1, case_f2 = [], [], [], {}, {}
    for fold, (train_df, test_df, selected) in folds.items():
        st, sigma, models = fit_final(train_df, selected, seeds)
        gt = fd.target_rows(test_df)
        idx = np.flatnonzero(gt)
        if len(idx) and not np.array_equal(idx, np.arange(idx[0], idx[-1] + 1)):
            raise ValueError(f"{fold}: linhas com GT não formam um trecho contínuo (seção 8)")
        t, y, nv = test_df["t"].to_numpy(np.int64)[gt], test_df[fd.TARGET].to_numpy(float)[gt], fd.n_valid(test_df)[gt]
        for (model, seed), (pred, w, failed) in _predictions(test_df, selected, st, sigma, models, seeds).items():
            row = {"fold": fold, "model": model, "seed": seed, "failed": failed, "n_rows": int(gt.sum())}
            name = f"{fold}_{model}" + ("" if seed is None else f"_s{seed}")
            if not failed:
                p = pred[gt]
                row.update(fe.primary(p, y), **fe.per_component(p, y, schema.TW), **fe.secondary(t, p, y))
                for r in fe.strata(p, y, nv).to_dict("records"):
                    strata.append({"fold": fold, "model": model, "seed": seed, **r})
                pq = pd.DataFrame(pred, columns=schema.TW)
                pq.insert(0, "t", test_df["t"].to_numpy(np.int64))
                if w is not None:
                    for m, col in zip(fd.METHODS, w.T):
                        pq[f"w_{m}"] = col
                    for k in ("all", 1, 2, 3, 4):
                        sel = np.ones(len(nv), bool) if k == "all" else nv == k
                        ws = w[gt][sel]
                        weights.append({"fold": fold, "seed": seed, "stratum": k, "n": int(sel.sum()),
                                        **{f"w_{m}": (float(ws[:, i].mean()) if len(ws) else np.nan)
                                           for i, m in enumerate(fd.METHODS)}})
                pq.to_parquet(out_dir / "predictions" / f"{name}.parquet", index=False)
            metrics.append(row)
        m = pd.DataFrame([r for r in metrics if r["fold"] == fold])
        for case, family in ((case_f1, "F1"), (case_f2, "F2")):
            case[fold] = {k: {"f": m.loc[m["model"] == family, k].tolist() if k in m else [],
                              "bsel": float(m.loc[m["model"] == "Bsel", k].iat[0]),
                              "b6": float(m.loc[m["model"] == "B6", k].iat[0])} for k in ("rmse_v", "rmse_w")}
    pd.DataFrame(metrics).to_csv(out_dir / "test_metrics.csv", index=False)
    pd.DataFrame(strata).to_csv(out_dir / "stratified.csv", index=False)
    pd.DataFrame(weights).to_csv(out_dir / "weights_f1.csv", index=False)
    result = {"decision": fe.decision(case_f1), "decision_f2": fe.decision(case_f2)}
    (out_dir / "decision.json").write_text(json.dumps(result, indent=2))
    return result


def rellis_inference(folds, sequences, out_dir, seeds=FINAL_SEEDS):
    """Seção 10: {dobra: (treino, selected)} aplicados a {nome: df}; só descrições, sem métricas de erro."""
    out_dir = Path(out_dir)
    (out_dir / "predictions").mkdir(parents=True, exist_ok=True)
    for fold, (train_df, selected) in folds.items():
        _check_frozen(selected, fold, train_df)
    rows, preds = [], {}
    for fold, (train_df, selected) in folds.items():
        st, sigma, models = fit_final(train_df, selected, seeds)
        for name, df in sequences.items():
            for (model, seed), (pred, w, failed) in _predictions(df, selected, st, sigma, models, seeds).items():
                if model not in ("F1", "F2"):
                    continue
                row = {"fold": fold, "sequence": name, "model": model, "seed": seed, "failed": failed}
                if not failed:
                    speed = np.linalg.norm(pred[:, :3], axis=1)
                    row.update(speed_mean=float(speed.mean()), speed_sd=float(speed.std(ddof=1)),
                               yaw_rate_mean=float(pred[:, 5].mean()),
                               **{f"w_{m}": (float(w[:, i].mean()) if w is not None else np.nan)
                                  for i, m in enumerate(fd.METHODS)})
                    preds[(fold, name, model, seed)] = pred
                    pq = pd.DataFrame(pred, columns=schema.TW)
                    pq.insert(0, "t", df["t"].to_numpy(np.int64))
                    if w is not None:
                        for m, col in zip(fd.METHODS, w.T):
                            pq[f"w_{m}"] = col
                    pq.to_parquet(out_dir / "predictions" / f"{fold}_{name}_{model}_s{seed}.parquet", index=False)
                rows.append(row)
    pd.DataFrame(rows).to_csv(out_dir / "describe.csv", index=False)
    agreement = []
    fold_names = list(folds)
    for name in sequences:
        for model in ("F1", "F2"):
            for seed in seeds:
                ps = [preds.get((f, name, model, seed)) for f in fold_names]
                if len(ps) == 2 and all(p is not None for p in ps):
                    d = ps[0] - ps[1]
                    agreement.append({"sequence": name, "model": model, "seed": seed,
                                      "rms_diff_v": float(np.sqrt(np.mean(np.sum(d[:, :3] ** 2, axis=1)))),
                                      "rms_diff_w": float(np.sqrt(np.mean(np.sum(d[:, 3:] ** 2, axis=1))))})
    pd.DataFrame(agreement).to_csv(out_dir / "agreement.csv", index=False)


def _load(seq):
    return pd.read_parquet(Path("data/output") / f"{seq}.parquet")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="phase", required=True)
    p1 = sub.add_parser("phase1", help="validação interna de uma dobra (lê só a sequência de treino)")
    p1.add_argument("--fold", choices=sorted(FOLDS), required=True)
    sub.add_parser("phase2", help="teste e RELLIS a partir dos selected.json congelados")
    a = ap.parse_args()
    if a.phase == "phase1":
        train_seq, _ = FOLDS[a.fold]
        phase1(_load(train_seq), ROOT / "phase1" / a.fold, fold=a.fold)
        return
    sel = {f: json.loads((ROOT / "phase1" / f / "selected.json").read_text()) for f in FOLDS}
    data = {seq: _load(seq) for seq in {s for pair in FOLDS.values() for s in pair}}
    phase2({f: (data[tr], data[te], sel[f]) for f, (tr, te) in FOLDS.items()}, ROOT / "phase2")
    rellis_inference({f: (data[tr], sel[f]) for f, (tr, _) in FOLDS.items()}, {s: _load(s) for s in RELLIS},
                     ROOT / "phase2" / "rellis")


if __name__ == "__main__":
    main()
