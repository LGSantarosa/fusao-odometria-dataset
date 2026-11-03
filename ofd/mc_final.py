"""Treino final e congelamento dos modelos — docs/amendment_phase4_hypothesis.md, seção 4.

Treina CNN-W, F1-R/STEP e MLP-W (sementes 0–4) e ajusta o T2 uma vez em ``1018-00`` + ``1018-13`` juntas, com as
escolhas do piloto formal da fase 3. A LSTM-W fica fora. B5/T1 é determinístico e não tem artefato. Grava de forma
atômica (diretório temporário renomeado no fim) normalizador, σ, configurações, pesos (``.npz``, sem pickle), T2 e um
manifesto com commit, hash da emenda, hash das tabelas de desenvolvimento e SHA-256 de cada arquivo. Recusa árvore suja,
raiz existente, qualquer sequência fora da allowlist e qualquer raiz sob ``data/sealed``.

O carregador (``load_predictors``) só aceita artefatos cujos hashes batem com o registro versionado
(``configs/model_comparison_frozen.json``, gerado por ``register`` e commitado antes de qualquer inferência externa).

Uso:
    python -m ofd.mc_final train [--workers 4]
    python -m ofd.mc_final register
"""
import argparse
import datetime as dt
import hashlib
import json
import math
import os
import shutil
import subprocess
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from ofd import fusion_data as fd, mc_data, mc_filters, mc_models, mc_pilot

DEV = ("1018-00", "1018-13")
ROOT = Path("data/analysis/model_comparison/final_models")
PILOT_ROOT = mc_pilot.ROOT
REGISTRY = Path("configs/model_comparison_frozen.json")
AMENDMENT = Path("docs/amendment_phase4_hypothesis.md")
SEALED = Path("data/sealed")

ALPHA = 1.0
W = 5
SEEDS = (0, 1, 2, 3, 4)
MODELS = {
    "STEP": {"cfg": {"layers": 1, "weight_decay": 1e-2, "width": 32}, "W": 1, "updates": 3300},
    "MLPW": {"cfg": {"layers": 1, "weight_decay": 1e-3, "width": 64}, "W": W, "updates": 500},
    "CNN": {"cfg": {"channels": 16, "kernel": 3, "layers": 1, "weight_decay": 1e-2}, "W": W, "updates": 1800},
}
T2 = {"q_scale": 1.0, "r_scale": 0.3}


class FrozenError(Exception):
    """Violação do congelamento (árvore suja, sobrescrita, hash divergente, configuração diferente do piloto)."""


def _git(*args):
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout.strip()


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 24), b""):
            h.update(chunk)
    return h.hexdigest()


def _write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


# ---------------------------------------------------------------- conferência contra o piloto

def check_pilot(pilot_root=PILOT_ROOT):
    """As constantes acima têm de ser exatamente as escolhas registradas no piloto formal (grid.json, t2.json)."""
    g = json.loads((Path(pilot_root) / "grid.json").read_text())
    t2 = json.loads((Path(pilot_root) / "t2.json").read_text())["chosen"]
    if (g["alpha"], g["W"]) != (ALPHA, W):
        raise FrozenError(f"α/W do piloto {g['alpha']}/{g['W']} ≠ {ALPHA}/{W}")
    for fam, spec in MODELS.items():
        sel = g["selected"][fam]
        if sel["config"] != spec["cfg"]:
            raise FrozenError(f"{fam}: configuração do piloto {sel['config']} ≠ {spec['cfg']}")
        cid = mc_pilot._cfg_id(spec["cfg"])
        budgets = [g["budgets"][f"{fam}|{cid}|{spec['W']}|{fold}"] for fold in mc_pilot.FOLDS]
        if int(math.ceil(float(np.median(budgets)))) != spec["updates"]:
            raise FrozenError(f"{fam}: orçamento final {budgets} ≠ {spec['updates']}")
    if g["selected_temporal"]["family"] != "CNN":
        raise FrozenError("a escolha temporal do piloto não é a CNN")
    if {k: t2[k] for k in T2} != T2:
        raise FrozenError(f"T2 do piloto {t2} ≠ {T2}")


# ---------------------------------------------------------------- dados de desenvolvimento

def _load(seq):
    if seq not in DEV:
        raise ValueError(f"sequência {seq!r} fora da allowlist de desenvolvimento")
    return mc_pilot._load(seq)


def development(load=_load):
    """Tabela das duas sequências concatenadas (na ordem de DEV) e os arrays usados no treino."""
    df = pd.concat([load(s) for s in DEV], ignore_index=True)
    if set(df["seq"].astype(str)) != set(DEV):
        raise FrozenError("tabela de desenvolvimento com sequências inesperadas")
    st = fd.Standardizer().fit(df)
    sigma = fd.target_sigma(df.loc[fd.target_rows(df)])
    tw, valid = fd.method_twists(df)
    return {"df": df, "st": st, "sigma": sigma, "X": st.transform(df), "Y": df[fd.TARGET].to_numpy(float),
            "tw": tw, "valid": valid, "seq": df["seq"].astype(str).to_numpy()}


def fit_t2(d):
    """T2 nas duas sequências: uma linha NaN entre elas impede que a diferença na fronteira entre em Q."""
    parts_tw, parts_v, parts_y = [], [], []
    for i, s in enumerate(DEV):
        r = d["seq"] == s
        if i:
            parts_tw.append(np.full((1,) + d["tw"].shape[1:], np.nan))
            parts_v.append(np.zeros((1, d["valid"].shape[1]), bool))
            parts_y.append(np.full((1, d["Y"].shape[1]), np.nan))
        parts_tw.append(d["tw"][r])
        parts_v.append(d["valid"][r])
        parts_y.append(d["Y"][r])
    return mc_filters.TwistKalman(**T2).fit(np.concatenate(parts_tw), np.concatenate(parts_v),
                                           np.concatenate(parts_y))


# ---------------------------------------------------------------- treino

def _train_one(job):
    torch.set_num_threads(1)
    fam, seed, d = job["family"], job["seed"], job["data"]
    spec = MODELS[fam]
    Xw = mc_data.windows_by_sequence(d["X"], d["seq"], spec["W"])
    model = mc_models.build(fam, "W", len(fd.FEATURES), spec["W"], mc_pilot._model_cfg(spec["cfg"]), seed)
    rows = np.isfinite(d["Y"]).all(axis=1)
    res = mc_models.train(model, "W", Xw, d["Y"], d["tw"], d["valid"], d["sigma"], rows, spec["updates"], seed,
                          weight_decay=spec["cfg"]["weight_decay"])
    state = {k: v.detach().cpu().numpy() for k, v in model.state_dict().items()}
    return {"family": fam, "seed": seed, "failed": res["failed"], "n_train": res["n_train"],
            "n_params": mc_models.n_params(model), "state": state}


def _guard_root(root):
    root = Path(root).resolve()
    sealed = SEALED.resolve()
    if root == sealed or sealed in root.parents:
        raise FrozenError(f"{root}: a raiz dos modelos não pode ficar sob {SEALED}")
    if root.exists():
        raise FrozenError(f"{root} já existe; modelos congelados não são sobrescritos")
    return root


def train(root=ROOT, workers=4, require_clean=True, load=_load, pilot_root=PILOT_ROOT):
    if require_clean and _git("status", "--porcelain"):
        raise FrozenError("árvore Git suja; faça commit antes do treino final")
    root = _guard_root(root)
    if _git("status", "--porcelain", "--", str(AMENDMENT)) or not _git("log", "-1", "--format=%H", "--",
                                                                         str(AMENDMENT)):
        raise FrozenError(f"{AMENDMENT}: emenda ausente, não registrada ou alterada")
    check_pilot(pilot_root)
    d = development(load)
    jobs = [{"family": f, "seed": s, "data": d} for f in MODELS for s in SEEDS]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(_train_one, jobs))
    failed = [(r["family"], r["seed"]) for r in results if r["failed"]]
    if failed:
        raise FrozenError(f"treino final falhou em {failed}; nada foi gravado")
    t2 = fit_t2(d)

    tmp = root.with_name(root.name + f".tmp-{os.getpid()}")
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    _write_json(tmp / "normalizer.json", {"features": list(fd.FEATURES), "mean": d["st"].mean,
                                          "scale": d["st"].scale, "clip": fd.CLIP,
                                          "target": list(fd.TARGET), "sigma": [float(x) for x in d["sigma"]]})
    _write_json(tmp / "t2.json", {**T2, "R": t2.R.tolist(), "Q": t2.Q.tolist(), "floor": t2.floor})
    models = []
    for r in results:
        rel = f"weights/{r['family']}_s{r['seed']}.npz"
        (tmp / "weights").mkdir(exist_ok=True)
        with open(tmp / rel, "wb") as f:
            np.savez(f, **r["state"])
        models.append({"family": r["family"], "seed": r["seed"], "path": rel, "n_train": r["n_train"],
                       "n_params": r["n_params"]})
    files = {str(p.relative_to(tmp)): _sha(p) for p in sorted(tmp.rglob("*")) if p.is_file()}
    manifest = {
        "kind": "frozen_models", "status": "FROZEN_BEFORE_EXTERNAL_INFERENCE", "external_test_authorized": False,
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(), "commit": _git("rev-parse", "HEAD"),
        "amendment": {"path": str(AMENDMENT), "sha256": _sha(AMENDMENT),
                      "commit": _git("log", "-1", "--format=%H", "--", str(AMENDMENT))},
        "development_sequences": list(DEV),
        "development_tables": {s: _sha(Path("data/output") / f"{s}.parquet") for s in DEV
                               if (Path("data/output") / f"{s}.parquet").is_file()},
        "alpha": ALPHA, "W": W, "seeds": list(SEEDS),
        "models": {f: {"cfg": s["cfg"], "W": s["W"], "updates": s["updates"]} for f, s in MODELS.items()},
        "t2": T2, "excluded": ["LSTM"], "seed_aggregation": "média das métricas por semente",
        "weights": models, "files": files,
    }
    _write_json(tmp / "manifest.json", manifest)
    os.rename(tmp, root)
    return manifest


# ---------------------------------------------------------------- registro e carregamento

def register(root=ROOT, registry=REGISTRY):
    """Grava o registro versionado (hash do manifesto e de cada arquivo) a partir de um diretório congelado."""
    root, registry = Path(root), Path(registry)
    if registry.exists():
        raise FrozenError(f"{registry} já existe; o registro não é sobrescrito")
    m = json.loads((root / "manifest.json").read_text())
    for rel, sha in m["files"].items():
        if _sha(root / rel) != sha:
            raise FrozenError(f"{rel}: hash diferente do manifesto")
    reg = {"root": str(ROOT) if root.resolve() == ROOT.resolve() else str(root),
           "manifest_sha256": _sha(root / "manifest.json"), "files": m["files"], "commit_trained": m["commit"],
           "amendment_sha256": m["amendment"]["sha256"]}
    registry.parent.mkdir(parents=True, exist_ok=True)
    _write_json(registry, reg)
    return reg


def verify(registry=REGISTRY, root=None):
    """Confere manifesto e arquivos contra o registro; devolve (raiz, manifesto, entradas de arquivo)."""
    reg = json.loads(Path(registry).read_text())
    root = Path(root or reg["root"])
    if _sha(root / "manifest.json") != reg["manifest_sha256"]:
        raise FrozenError("manifest.json diferente do registro")
    m = json.loads((root / "manifest.json").read_text())
    if m["files"] != reg["files"]:
        raise FrozenError("lista de arquivos do manifesto diferente do registro")
    bad = [rel for rel, sha in reg["files"].items() if not (root / rel).is_file() or _sha(root / rel) != sha]
    if bad:
        raise FrozenError(f"arquivos ausentes ou alterados: {bad}")
    return root, m, [root / "manifest.json"] + [root / rel for rel in sorted(reg["files"])]


def _standardizer(norm):
    if norm["features"] != list(fd.FEATURES):
        raise FrozenError("features do normalizador diferentes de fusion_data.FEATURES")
    st = fd.Standardizer()
    st.mean, st.scale = norm["mean"], norm["scale"]
    return st


def _one_sequence(df):
    if df["seq"].astype(str).nunique() != 1:
        raise FrozenError("o preditor recebe uma sequência por vez")


def _neural_predictor(model, family, st, sigma):
    used_W = MODELS[family]["W"]

    def predict(df):
        _one_sequence(df)
        tw, valid = fd.method_twists(df)
        Xw = mc_data.windows(st.transform(df), used_W)
        return mc_filters.apply_p_alpha(mc_models.predict_raw(model, "W", Xw, tw, valid, sigma), ALPHA)
    return predict


def load_predictors(registry=REGISTRY, root=None):
    """{nome: função(df) → (n, 6)} para T1, T2 e cada família/semente (``CNN_s0`` …); e as entradas de arquivo."""
    root, m, entries = verify(registry, root)
    norm = json.loads((root / "normalizer.json").read_text())
    st, sigma = _standardizer(norm), np.asarray(norm["sigma"], float)
    preds = {}

    def t1(df):
        _one_sequence(df)
        tw, valid = fd.method_twists(df)
        return mc_filters.t1(tw, valid, ALPHA)
    preds["T1"] = t1

    t2p = json.loads((root / "t2.json").read_text())
    kal = mc_filters.TwistKalman(t2p["q_scale"], t2p["r_scale"], t2p["floor"])
    kal.R, kal.Q = np.asarray(t2p["R"], float), np.asarray(t2p["Q"], float)

    def t2(df):
        _one_sequence(df)
        tw, valid = fd.method_twists(df)
        return kal.predict(tw, valid)
    preds["T2"] = t2

    for w in m["weights"]:
        fam, seed = w["family"], w["seed"]
        spec = MODELS[fam]
        model = mc_models.build(fam, "W", len(fd.FEATURES), spec["W"], mc_pilot._model_cfg(spec["cfg"]), seed)
        with np.load(root / w["path"], allow_pickle=False) as z:
            model.load_state_dict({k: torch.from_numpy(z[k]) for k in z.files})
        model.eval()
        preds[f"{fam}_s{seed}"] = _neural_predictor(model, fam, st, sigma)
    return preds, entries


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("action", choices=("train", "register"))
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    if args.action == "train":
        m = train(workers=args.workers)
        print(json.dumps({"root": str(ROOT), "commit": m["commit"], "n_files": len(m["files"])}, indent=2))
    else:
        reg = register()
        print(json.dumps({"registry": str(REGISTRY), "manifest_sha256": reg["manifest_sha256"]}, indent=2))


if __name__ == "__main__":
    main()
