"""Fase 0 do protocolo do modelo de fusão: orquestração das fases 1 e 2 de ponta a ponta, só com dados sintéticos."""
import json

import numpy as np
import pandas as pd
import pytest

from ofd import fusion_data as fd, fusion_run as fr
from tests.fusion_synth import synth_sequence

SMALL = {"B6": [{"alpha": a} for a in (0.1, 10.0)],
         "F1": [{"width": 8, "layers": 1, "weight_decay": wd} for wd in (1e-4, 1e-2)],
         "F2": [{"width": 8, "layers": 1, "weight_decay": 1e-3}]}


def _phase1(tmp_path, train=None, **kw):
    train = synth_sequence(300, seed=1, invalid_every={"orbslam3": 4}) if train is None else train
    out = tmp_path / "phase1" / "A"
    sel = fr.phase1(train, out, fold="A", grids=SMALL, seeds=(0, 1), max_epochs=8, **kw)
    return sel, out


def test_grids_follow_protocol():
    assert [c["alpha"] for c in fr.GRIDS["B6"]] == [1e-3, 1e-2, 1e-1, 1, 10, 100, 1000]
    assert len(fr.GRIDS["F1"]) == len(fr.GRIDS["F2"]) == 18
    assert fr.CV_SEEDS == (0, 1, 2) and fr.FINAL_SEEDS == (0, 1, 2, 3, 4) and fr.MAX_EPOCHS == 500


def test_phase1_writes_cv_table_and_frozen_selection(tmp_path):
    sel, out = _phase1(tmp_path)
    cv = pd.read_csv(out / "cv.csv")
    assert set(cv["family"]) == {"B1", "B2", "B3", "B4", "B6", "F1", "F2"}
    nn = cv[cv["family"] == "F1"]
    assert len(nn) == 2 * 5 * 2 and set(nn["seed"]) == {0, 1} and nn["best_epoch"].between(1, 8).all()
    assert len(cv[cv["family"] == "B6"]) == 2 * 5 and cv.loc[cv["family"] == "B6", "seed"].isna().all()
    saved = json.loads((out / "selected.json").read_text())
    assert saved == json.loads(json.dumps(sel))
    assert saved["fold"] == "A" and saved["train_sequence"] == "synth"
    assert saved["bsel"] in fd.METHODS
    assert saved["bsel"] == "fastlio"                               # menor ruído no sintético
    assert set(saved["families"]) == {"B6", "F1", "F2"}
    assert saved["families"]["F1"]["epochs"] >= 1 and "alpha" in saved["families"]["B6"]["config"]
    assert len(saved["standardizer"]["mean"]) == 52 and len(saved["target_sigma"]) == 6   # 56 − 4 colunas valid


def test_phase1_only_uses_rows_with_target(tmp_path):
    train = synth_sequence(300, seed=1)
    train.loc[:49, "gt_vx"] = np.nan                                  # sem GT: fora de treino e validação
    sel, _ = _phase1(tmp_path, train=train)
    assert sel["n_rows"] == 250


def test_phase1_subfold_with_empty_column_fails_every_config(tmp_path):
    train = synth_sequence(300, seed=1)
    train.loc[:239, "stella_reproj_err"] = np.nan                      # treino da subdobra 4 (linhas 0–229) vazio
    sel, out = _phase1(tmp_path, train=train)
    cv = pd.read_csv(out / "cv.csv")
    last = cv[(cv["subfold"] == 4) & cv["family"].isin(["B6", "F1", "F2"])]
    assert last["failed"].all()
    assert all(f["config"] is None for f in sel["families"].values())


def test_phase2_trains_final_models_and_writes_tables(tmp_path):
    sel, _ = _phase1(tmp_path)
    test = synth_sequence(350, seed=2, invalid_every={"stella": 5}, seq="other", t0=10**12)
    out = tmp_path / "phase2"
    res = fr.phase2({"A": (synth_sequence(300, seed=1, invalid_every={"orbslam3": 4}), test, sel)}, out,
                    seeds=(0, 1, 2))
    m = pd.read_csv(out / "test_metrics.csv")
    assert set(m["model"]) == {"B1", "B2", "B3", "B4", "B5", "Bsel", "B6", "F1", "F2"}
    assert len(m[m["model"] == "F1"]) == 3 and m.loc[m["model"] == "B6", "seed"].isna().all()
    assert {"rmse_v", "rmse_w", "rpe_t_10m", "rpe_r_10m", "ate_rmse", "rmse_vx", "failed"} <= set(m.columns)
    assert np.allclose(m.loc[m["model"] == "Bsel", "rmse_v"].iat[0],
                       m.loc[m["model"] == "B3", "rmse_v"].iat[0])        # Bsel = FAST-LIO
    s = pd.read_csv(out / "stratified.csv")
    assert set(s["n_valid"]) == {1, 2, 3, 4} and (s.loc[s["n_valid"] == 1, "n"] == 0).all()
    w = pd.read_csv(out / "weights_f1.csv")
    w = w[w["n"] > 0]                                                   # estratos vazios: pesos indefinidos
    assert np.allclose(w[[f"w_{m}" for m in fd.METHODS]].sum(axis=1), 1.0)
    pq = pd.read_parquet(out / "predictions" / "A_F1_s0.parquet")
    assert len(pq) == 350 and {"t", "vx", "wz", "w_fastlio"} <= set(pq.columns)
    assert "A" in res["decision"]["detail"]


def test_phase2_refuses_without_frozen_selection(tmp_path):
    sel, _ = _phase1(tmp_path)
    sel = dict(sel, families={**sel["families"], "F1": {"config": None, "epochs": None}})
    with pytest.raises(ValueError, match="F1"):
        fr.phase2({"A": (synth_sequence(300, seed=1), synth_sequence(300, seed=2, seq="other"), sel)}, tmp_path / "p2",
                  seeds=(0,))


def test_rellis_inference_is_descriptive_only(tmp_path):
    sel, _ = _phase1(tmp_path)
    rellis = synth_sequence(120, seed=3, seq="rellis_example")
    rellis[fd.TARGET] = np.nan                                         # sem GT
    out = tmp_path / "rellis"
    fr.rellis_inference({"A": (synth_sequence(300, seed=1, invalid_every={"orbslam3": 4}), sel)},
                        {"rellis_example": rellis}, out, seeds=(0, 1))
    for model, seed in (("F1", 0), ("F1", 1), ("F2", 0), ("F2", 1)):
        pq = pd.read_parquet(out / "predictions" / f"A_rellis_example_{model}_s{seed}.parquet")
        assert len(pq) == 120 and np.array_equal(pq["t"], rellis["t"]) and np.isfinite(pq[["vx", "wz"]]).all().all()
        assert ({f"w_{m}" for m in fd.METHODS} <= set(pq.columns)) == (model == "F1")
    d = pd.read_csv(out / "describe.csv")
    assert not ({"rmse_v", "rmse_w", "ate_rmse"} & set(d.columns))
    assert {"speed_mean", "w_fastlio"} <= set(d.columns)
    assert len(d) == 2 * 2                                              # F1 e F2 × sementes, dobra A


def test_phase2_rejects_selection_from_another_fold_or_sequence(tmp_path):
    sel, _ = _phase1(tmp_path)                                          # dobra A, treino "synth"
    train = synth_sequence(300, seed=1, invalid_every={"orbslam3": 4})
    test = synth_sequence(300, seed=2, seq="other")
    with pytest.raises(ValueError, match="dobra"):
        fr.phase2({"B": (train, test, sel)}, tmp_path / "p2", seeds=(0,))
    with pytest.raises(ValueError, match="treino"):
        fr.phase2({"A": (synth_sequence(300, seed=1, seq="outra"), test, sel)}, tmp_path / "p2", seeds=(0,))
    with pytest.raises(ValueError, match="teste"):
        fr.phase2({"A": (train, synth_sequence(300, seed=2), sel)}, tmp_path / "p2", seeds=(0,))
    with pytest.raises(ValueError, match="dobra"):
        fr.rellis_inference({"B": (train, sel)}, {"r": test}, tmp_path / "r", seeds=(0,))
