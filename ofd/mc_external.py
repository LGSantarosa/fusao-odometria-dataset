"""Análise externa pós-abertura conforme ``docs/amendment_phase4_hypothesis.md``.

Consome somente os artefatos imutáveis produzidos por ``ofd.blind unlock``. Recalcula as métricas primárias, acrescenta
RPE de 10 m e ATE com ``ofd.fusion_eval``, combina sementes pela média das métricas e aplica literalmente a regra da
H1'. Não treina, não escolhe modelos e não lê os bags de GT lacrados.

Uso:
    python -m ofd.mc_external --out data/blind_g1/external_results
"""
import argparse
import datetime as dt
import hashlib
import json
import math
import os
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

from ofd import fusion_data as fd, fusion_eval as fe, schema


ROOT = Path("data/blind_g1")
AMENDMENT = Path("docs/amendment_phase4_hypothesis.md")
FAMILIES = ("B5", "T1", "T2", "CNN", "STEP", "MLPW")
LEARNED = ("CNN", "STEP", "MLPW")
MODELS = ("B5", "T1", "T2") + tuple(f"{family}_s{seed}" for family in LEARNED for seed in range(5))
METRICS = ("rmse_v", "rmse_w", "rpe_t_10m", "rpe_r_10m", "ate_rmse")


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 24), b""):
            h.update(chunk)
    return h.hexdigest()


def _entry(path):
    path = Path(path)
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": _sha256(path)}


def _verify_entry(entry):
    path = Path(entry["path"])
    if not path.is_file() or _entry(path) != {k: entry[k] for k in ("path", "bytes", "sha256")}:
        raise RuntimeError(f"artefato ausente ou alterado: {path}")


def _family(model):
    return model.split("_s", 1)[0]


def aggregate_seeds(per_seed):
    """Média/desvio das métricas por sequência e família; determinísticos têm uma observação e desvio indefinido."""
    rows = []
    for (seq, family), g in per_seed.assign(family=per_seed["model"].map(_family)).groupby(
            ["seq", "family"], sort=True):
        row = {"seq": seq, "day": seq[:4], "family": family, "n_seeds": len(g)}
        for metric in METRICS:
            row[metric] = float(g[metric].mean())
            row[f"{metric}_sd"] = float(g[metric].std(ddof=1)) if len(g) > 1 else math.nan
        rows.append(row)
    out = pd.DataFrame(rows)
    expected = {(seq, family) for seq in per_seed["seq"].unique() for family in FAMILIES}
    if set(zip(out["seq"], out["family"])) != expected:
        raise RuntimeError("famílias incompletas na agregação por sequência")
    return out


def h1_table(per_sequence):
    """Δ = 1 − métrica_CNN / métrica_B5; positivo significa melhora da CNN."""
    rows = []
    for seq, g in per_sequence.groupby("seq", sort=True):
        b5, cnn = (g.set_index("family").loc[name] for name in ("B5", "CNN"))
        row = {"seq": seq, "day": seq[:4]}
        for metric in METRICS:
            row[f"b5_{metric}"] = float(b5[metric])
            row[f"cnn_{metric}"] = float(cnn[metric])
            row[f"delta_{metric}"] = 1.0 - float(cnn[metric]) / float(b5[metric])
        row["cnn_rmse_w_sd"] = float(cnn["rmse_w_sd"])
        row["favorable_angular"] = bool(row["delta_rmse_w"] > 0)
        rows.append(row)
    return pd.DataFrame(rows)


def decide_h1(h1):
    """Regra congelada: métricas definidas, mediana geral > 0 e mediana > 0 em cada um dos três dias."""
    required_days = ("1005", "1006", "1008")
    complete = (len(h1) == 8 and set(h1["day"]) == set(required_days)
                and np.isfinite(h1[["b5_rmse_w", "cnn_rmse_w", "delta_rmse_w"]].to_numpy(float)).all())
    overall = float(h1["delta_rmse_w"].median()) if complete else math.nan
    day = {d: float(h1.loc[h1["day"] == d, "delta_rmse_w"].median()) for d in required_days}
    if not complete:
        status = "indeterminate"
    else:
        status = "positive" if overall > 0 and all(v > 0 for v in day.values()) else "negative"
    return {"hypothesis": "H1_prime", "status": status, "all_angular_metrics_defined": bool(complete),
            "overall_median_delta_rmse_w": overall, "day_median_delta_rmse_w": day,
            "favorable_sequences": int(h1["favorable_angular"].sum()), "n_sequences": int(len(h1)),
            "delta_definition": "1 - metric_CNN_mean_over_5_seed_metrics / metric_B5",
            "rule": "overall median > 0 and median > 0 in each of 1005, 1006 and 1008"}


def _verify_unlock(root):
    unlock = root / "unlock"
    um_path = unlock / "unlock_manifest.json"
    um = json.loads(um_path.read_text())
    if um.get("kind") != "unlock" or len(um.get("gt", {})) != 8 or len(um.get("evaluation", {})) != 8:
        raise RuntimeError("manifesto de abertura incompleto")
    _verify_entry(um["feature_manifest"])
    _verify_entry(um["prediction_manifest"])
    for item in um["evaluation"].values():
        _verify_entry(item)
    for item in um["gt"].values():
        _verify_entry(item["tum"])
    for item in um["metrics"]:
        _verify_entry(item)
    pm = json.loads((root / "predict/prediction_manifest.json").read_text())
    if tuple(pm["model_names"]) != MODELS:
        raise RuntimeError(f"lista de modelos inesperada: {pm['model_names']}")
    return um, _entry(um_path)


def calculate(root=ROOT):
    """Recalcula primárias e secundárias e devolve tabelas derivadas mais a decisão pré-registrada."""
    root = Path(root)
    um, unlock_entry = _verify_unlock(root)
    raw_primary = pd.read_csv(root / "unlock/prediction_metrics.csv")
    per_seed = []
    for seq in sorted(um["evaluation"]):
        ev = pd.read_parquet(um["evaluation"][seq]["path"])
        pred = pd.read_parquet(root / "predict/predictions" / f"{seq}.parquet")
        target = np.isfinite(ev[fd.TARGET].to_numpy(float)).all(axis=1)
        idx = np.flatnonzero(target)
        if not len(idx) or not np.array_equal(idx, np.arange(idx[0], idx[-1] + 1)):
            raise RuntimeError(f"{seq}: suporte de GT não é um trecho contínuo")
        t = ev.loc[target, "t"].to_numpy(np.int64)
        y = ev.loc[target, fd.TARGET].to_numpy(float)
        for model in MODELS:
            cols = [f"{model}_pred_{c}" for c in schema.TW]
            p = pred.loc[target, cols].to_numpy(float)
            if not np.isfinite(p).all():
                raise RuntimeError(f"{seq}/{model}: predição ausente no suporte do GT")
            primary = fe.primary(p, y)
            ref = raw_primary[(raw_primary["seq"] == seq) & (raw_primary["model"] == model)]
            if len(ref) != 1 or not np.allclose([primary["rmse_v"], primary["rmse_w"]],
                                               ref[["rmse_v", "rmse_w"]].iloc[0], rtol=0, atol=1e-15):
                raise RuntimeError(f"{seq}/{model}: primárias divergem da abertura")
            per_seed.append({"seq": seq, "day": seq[:4], "model": model, **primary, **fe.secondary(t, p, y)})
    per_seed = pd.DataFrame(per_seed)
    per_sequence = aggregate_seeds(per_seed)
    h1 = h1_table(per_sequence)
    decision = decide_h1(h1)
    by_day = per_sequence.groupby(["day", "family"], as_index=False)[list(METRICS)].median()
    overall = per_sequence.groupby("family", as_index=False)[list(METRICS)].median()
    meta = {"unlock_manifest": unlock_entry, "unlock_commit": um["commit"], "amendment": _entry(AMENDMENT)}
    return {"per_seed": per_seed, "per_sequence": per_sequence, "h1": h1, "by_day": by_day,
            "overall": overall, "decision": decision, "meta": meta}


def run(out, root=ROOT):
    """Grava uma raiz nova de resultados derivados; nunca sobrescreve uma análise existente."""
    out = Path(out)
    if out.exists():
        raise RuntimeError(f"{out} já existe")
    if subprocess.check_output(("git", "status", "--porcelain"), text=True).strip():
        raise RuntimeError("árvore Git suja; registre o analisador antes de calcular o resultado externo")
    result = calculate(root)
    tmp = out.with_name(f".{out.name}.{os.getpid()}.tmp")
    if tmp.exists():
        raise RuntimeError(f"temporário já existe: {tmp}")
    tmp.mkdir(parents=True)
    try:
        files = {
            "per_seed_metrics.csv": result["per_seed"],
            "per_sequence_metrics.csv": result["per_sequence"],
            "h1_prime_by_sequence.csv": result["h1"],
            "descriptive_by_day.csv": result["by_day"],
            "descriptive_overall.csv": result["overall"],
        }
        for name, table in files.items():
            table.to_csv(tmp / name, index=False)
        (tmp / "h1_prime_decision.json").write_text(json.dumps(result["decision"], indent=2) + "\n")
        commit = subprocess.check_output(("git", "rev-parse", "HEAD"), text=True).strip()
        outputs = []
        for path in sorted(tmp.iterdir()):
            entry = _entry(path)
            entry["path"] = str(out / path.name)
            outputs.append(entry)
        manifest = {"kind": "external_results", "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                    "analysis_commit": commit, **result["meta"],
                    "outputs": outputs}
        (tmp / "result_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        os.replace(tmp, out)
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=Path, default=ROOT)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    result = run(args.out, args.root)
    print(json.dumps(result["decision"], indent=2))


if __name__ == "__main__":
    main()
