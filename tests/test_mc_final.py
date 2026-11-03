import json

import numpy as np
import pytest

from ofd import mc_final, mc_filters, mc_models, mc_pilot
from tests.fusion_synth import synth_sequence


def _clean_git(*a):
    if a[0] == "status":
        return ""
    return "abc123"


@pytest.fixture
def synth(monkeypatch):
    data = {s: synth_sequence(n=120, seed=i, seq=s, invalid_every={"orb": 7}) for i, s in enumerate(mc_final.DEV)}
    monkeypatch.setattr(mc_final, "_git", _clean_git)
    monkeypatch.setattr(mc_final, "check_pilot", lambda *a, **k: None)
    monkeypatch.setattr(mc_final, "MODELS", {f: {**s, "updates": 5} for f, s in mc_final.MODELS.items()})
    monkeypatch.setattr(mc_final, "SEEDS", (0, 1))
    return lambda s: mc_final._load(s) if s not in data else data[s].copy()


def test_frozen_constants_match_amendment():
    assert mc_final.DEV == mc_pilot.DEV
    assert mc_final.ALPHA == 1.0 and mc_final.W == 5 and mc_final.SEEDS == (0, 1, 2, 3, 4)
    assert set(mc_final.MODELS) == {"STEP", "MLPW", "CNN"}          # LSTM excluída
    assert {f: s["updates"] for f, s in mc_final.MODELS.items()} == {"STEP": 3300, "MLPW": 500, "CNN": 1800}
    assert mc_final.MODELS["STEP"]["W"] == 1
    assert mc_final.MODELS["CNN"]["cfg"] == {"channels": 16, "kernel": 3, "layers": 1, "weight_decay": 1e-2}
    assert mc_final.T2 == {"q_scale": 1.0, "r_scale": 0.3}


def test_allowlist_rejects_external_sequences():
    with pytest.raises(ValueError, match="allowlist"):
        mc_final._load("1005-00")


def test_root_under_sealed_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(mc_final, "SEALED", tmp_path / "sealed")
    with pytest.raises(mc_final.FrozenError, match="sealed"):
        mc_final._guard_root(tmp_path / "sealed" / "x")


def test_dirty_tree_and_existing_root_are_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(mc_final, "_git", lambda *a: " M x.py" if a[0] == "status" else "abc")
    with pytest.raises(mc_final.FrozenError, match="suja"):
        mc_final.train(tmp_path / "m")
    monkeypatch.setattr(mc_final, "_git", _clean_git)
    (tmp_path / "m").mkdir()
    with pytest.raises(mc_final.FrozenError, match="sobrescritos"):
        mc_final.train(tmp_path / "m")


def test_check_pilot_refuses_divergent_config(tmp_path):
    g = {"alpha": 1.0, "W": 5, "selected_temporal": {"family": "CNN"}, "selected": {}, "budgets": {}}
    for fam, spec in mc_final.MODELS.items():
        g["selected"][fam] = {"config": spec["cfg"]}
        cid = mc_pilot._cfg_id(spec["cfg"])
        for fold in mc_pilot.FOLDS:
            g["budgets"][f"{fam}|{cid}|{spec['W']}|{fold}"] = spec["updates"]
    (tmp_path / "grid.json").write_text(json.dumps(g))
    (tmp_path / "t2.json").write_text(json.dumps({"chosen": {"q_scale": 1.0, "r_scale": 0.3, "loss": 0.4}}))
    mc_final.check_pilot(tmp_path)
    g["budgets"][next(iter(g["budgets"]))] += 1000
    (tmp_path / "grid.json").write_text(json.dumps(g))
    with pytest.raises(mc_final.FrozenError, match="orçamento"):
        mc_final.check_pilot(tmp_path)


def test_t2_fit_ignores_the_boundary_between_sequences(synth):
    d = mc_final.development(synth)
    k = mc_final.fit_t2(d)
    per = [np.diff(d["Y"][d["seq"] == s], axis=0) for s in mc_final.DEV]
    assert np.allclose(k.Q, np.maximum(np.concatenate(per).var(axis=0), k.floor))


def test_train_register_load_roundtrip_and_tamper(tmp_path, synth):
    root, reg = tmp_path / "final", tmp_path / "frozen.json"
    m = mc_final.train(root, workers=1, load=synth)
    assert not list(tmp_path.glob("final.tmp-*"))
    assert m["excluded"] == ["LSTM"] and not m["external_test_authorized"]
    assert {(w["family"], w["seed"]) for w in m["weights"]} == {(f, s) for f in ("STEP", "MLPW", "CNN") for s in (0, 1)}
    mc_final.register(root, reg)
    with pytest.raises(mc_final.FrozenError, match="não é sobrescrito"):
        mc_final.register(root, reg)
    with pytest.raises(mc_final.FrozenError, match="sobrescritos"):
        mc_final.train(root, workers=1, load=synth)

    preds, entries = mc_final.load_predictors(reg, root)
    assert set(preds) == {"T1", "T2"} | {f"{f}_s{s}" for f in ("STEP", "MLPW", "CNN") for s in (0, 1)}
    assert all(p.is_file() for p in entries)
    ext = synth_sequence(n=60, seed=9, seq="1005-00")
    for name, f in preds.items():
        out = f(ext)
        assert out.shape == (60, 6) and np.isfinite(out).all(), name

    # o preditor carregado reproduz o modelo treinado em memória
    d = mc_final.development(synth)
    job = mc_final._train_one({"family": "CNN", "seed": 1, "data": d})
    model = mc_models.build("CNN", "W", len(mc_final.fd.FEATURES), 5,
                            mc_pilot._model_cfg(mc_final.MODELS["CNN"]["cfg"]), 1)
    model.load_state_dict({k: mc_final.torch.from_numpy(v) for k, v in job["state"].items()})
    tw, valid = mc_final.fd.method_twists(ext)
    Xw = mc_final.mc_data.windows(d["st"].transform(ext), 5)
    ref = mc_filters.apply_p_alpha(mc_models.predict_raw(model, "W", Xw, tw, valid, d["sigma"]), 1.0)
    assert np.array_equal(preds["CNN_s1"](ext), ref)

    with pytest.raises(mc_final.FrozenError, match="uma sequência"):
        preds["T1"](mc_final.pd.concat([ext, synth_sequence(n=10, seq="1005-01")]))

    w = root / "weights" / "CNN_s0.npz"
    w.write_bytes(w.read_bytes() + b"\x00")
    with pytest.raises(mc_final.FrozenError, match="alterados"):
        mc_final.load_predictors(reg, root)
