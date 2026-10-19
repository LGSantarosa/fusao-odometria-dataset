"""Fase 2 do protocolo das VOs — docs/protocol_vo_repeat.md, seção 7.

Avalia cada execução r1–r10 com as mesmas funções do pipeline (`ofd.evaluate`, `ofd.sync`), sobre a sua própria
cobertura, e resume as dez com a estatística fixada por métrica. Não executa as VOs. Métricas de erro só nas
sequências confirmatórias (BotanicGarden); no RELLIS (veredito C) nem `gt.tum` nem os passos do GT da tabela são
lidos, e o maior trecho contínuo é reportado só em segundos (emenda de 19/10/2026 à seção 7). A execução oficial
(`data/runs/<seq>/<método>`) é avaliada do mesmo modo, mas gravada à parte e fora das estatísticas (seção 8).

uso: python -m ofd.vo_repeat_phase2 --from-decisions data/analysis/vo_repeat/phase1/decisions.json \
         --out data/analysis/vo_repeat/phase2
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from ofd import config, evaluate, se3, sync, tracks
from ofd.vo_repeat import INDICATORS, describe, indicator_medians, read_record, validate_run

# Seção 7: estatística principal fixada por métrica (RPE rotacional em rad, como em ofd.evaluate.rpe)
ERROR_METRICS = {"ate_rmse": "mean_sd", "rpe_t_10m": "mean_sd", "rpe_r_10m": "mean_sd",
                 "n_segments": "median_iqr", "n_eligible": "median_iqr"}
OPERATION_METRICS = {"coverage": "mean_sd", "n_failures": "median_iqr", "n_resets": "median_iqr",
                     "longest_s": "median_iqr", "longest_m": "median_iqr"}
INDICATOR_METRICS = {f"{c}_median": "mean_sd" for c in INDICATORS}
GT_LENGTH_METRICS = ("longest_m",)  # medida com os passos do GT: fora do RELLIS (emenda de 19/10/2026)
DECISIONS = ("variable", "deterministic", "numerically_equivalent")
CONFIRMATORY = ("1018-00", "1018-13")  # seção 3: únicas com métricas de erro


def evaluate_run(run_dir, method, table, T_L_S, max_age_ms, gt=None):
    """Uma execução: operação na grade LiDAR de `table`, indicadores e, com `gt` = (ts, Ts), métricas de erro e o
    maior trecho contínuo em metros; sem `gt`, `table` só precisa de `t`."""
    track, _, meta = tracks.load_run(run_dir)
    md = sync.method_deltas(track, table["t"].to_numpy(np.int64), T_L_S, max_age_ms)
    grid = table[["t"]].copy()
    for c in ("gt_dx", "gt_dy", "gt_dz"):
        grid[c] = table[c] if gt is not None else np.nan   # sem GT: passos nulos, e longest_m é descartado
    grid[f"{method}_valid"] = md["valid"].to_numpy()
    grid[f"{method}_segment_id"] = md["segment_id"].to_numpy()
    state = pd.read_csv(f"{run_dir}/state.csv")
    row = evaluate.coverage(grid, method, state, bool(meta.get("continuous_frame", False)))
    if gt is None:
        for m in GT_LENGTH_METRICS:
            del row[m]
    else:
        sm = evaluate.segment_metrics(track, T_L_S, *gt)
        r = evaluate.rpe(track, T_L_S, *gt)
        row.update(ate_rmse=evaluate.aggregate_ate(sm), rpe_t_10m=r["rpe_t_10m"], rpe_r_10m=r["rpe_r_10m"],
                   n_segments=len(sm), n_eligible=int(sm["eligible"].sum()))
    row.update(indicator_medians(run_dir))
    return row


def evaluate_combination(run_dirs, records, canonical_ts, method, table, T_L_S, max_age_ms, gt=None, reps=None):
    """Tabela por execução de uma combinação; a inválida (seção 5.1) fica na tabela, sem métricas."""
    rows = []
    reps = reps or range(1, len(run_dirs) + 1)
    for k, run_dir, record in zip(reps, run_dirs, records):
        code, status = read_record(record)
        valid, reasons = validate_run(run_dir, canonical_ts, code)
        row = {"repetition": k, "path": str(run_dir), "exit_code": code, "record_status": status,
               "valid": valid, "reasons": "; ".join(reasons)}
        if valid:
            row.update(evaluate_run(run_dir, method, table, T_L_S, max_age_ms, gt))
        rows.append(row)
    return pd.DataFrame(rows)


def summarize(runs, with_gt):
    """Seção 7: uma linha por métrica com a estatística fixada; execuções inválidas e métricas indefinidas (NaN)
    ficam de fora, e `n_defined` diz quantas execuções contribuíram."""
    operation = {m: k for m, k in OPERATION_METRICS.items() if with_gt or m not in GT_LENGTH_METRICS}
    metrics = {**(ERROR_METRICS if with_gt else {}), **operation, **INDICATOR_METRICS}
    rows = []
    for metric, kind in metrics.items():
        values = runs[metric] if metric in runs else []
        rows.append({"metric": metric, "statistic": kind, **describe(values, kind)})
    cols = ["metric", "statistic", "n_defined", "mean", "sd", "median", "q1", "q3", "min", "max"]
    return pd.DataFrame(rows).reindex(columns=cols)


def success_rate(runs):
    """Execuções válidas / total; as inválidas ficam no denominador (seção 7)."""
    codes = ["NA" if pd.isna(c) else str(int(c)) for c in runs["exit_code"]]
    n, valid = len(runs), int(runs["valid"].sum())
    return {"n_runs": n, "n_valid": valid, "success_rate": valid / n if n else np.nan, "exit_codes": ",".join(codes)}


def phase2(plan, runs_root, extracted_root, tables_root, log_dir, configs, out_dir):
    """Seção 7 para cada combinação {(seq, método): [k, ...]}; `configs` = {seq: (T_L_S por método, max_age_ms)}.

    `tables_root/<seq>.parquet` (tabela do dataset derivado) fornece a grade LiDAR e os passos do GT usados pela
    cobertura do pipeline (no RELLIS, só a grade `t`). Grava `<seq>_<método>_runs.csv`, `summary.csv`,
    `success.csv` e `official.csv`.
    """
    runs_root, extracted_root, tables_root, log_dir, out_dir = map(
        Path, (runs_root, extracted_root, tables_root, log_dir, out_dir))
    out_dir.mkdir(parents=True, exist_ok=True)
    summaries, success, official = [], [], []
    for (seq, method), reps in plan.items():
        canonical = pd.read_csv(extracted_root / seq / "images" / "stamps.csv")["ts_ns"].to_numpy(np.int64)
        with_gt = seq in CONFIRMATORY
        table = pd.read_parquet(tables_root / f"{seq}.parquet",
                                columns=["t", "gt_dx", "gt_dy", "gt_dz"] if with_gt else ["t"])
        T_L_S, max_age_ms = configs[seq]
        T = T_L_S[method]
        gt = se3.load_tum(extracted_root / seq / "gt.tum") if with_gt else None
        key = {"sequence": seq, "method": method}
        runs = evaluate_combination([runs_root / seq / f"{method}_r{k}" for k in reps],
                                    [log_dir / f"{seq}_{method}_r{k}.json" for k in reps],
                                    canonical, method, table, T, max_age_ms, gt, reps)
        runs.to_csv(out_dir / f"{seq}_{method}_runs.csv", index=False)
        s = summarize(runs, with_gt)
        summaries.append(s.assign(**key)[list(key) + list(s.columns)])
        success.append({**key, **success_rate(runs)})
        official.append({**key, **evaluate_run(runs_root / seq / method, method, table, T, max_age_ms, gt)})
    pd.concat(summaries, ignore_index=True).to_csv(out_dir / "summary.csv", index=False)
    pd.DataFrame(success).to_csv(out_dir / "success.csv", index=False)
    pd.DataFrame(official).to_csv(out_dir / "official.csv", index=False)


def phase2_plan(decisions):
    """Seção 6: r1–r10 nas combinações variáveis; só r1 nas determinísticas ou numericamente equivalentes."""
    unknown = {k: d for k, d in decisions.items() if d not in DECISIONS}
    if unknown:
        raise ValueError(f"decisões desconhecidas: {unknown}")
    return {tuple(key.split("/")): (list(range(1, 11)) if d == "variable" else [1]) for key, d in decisions.items()}


def load_configs(sequences):
    from ofd.run_vo_repeat import dataset_of
    out = {}
    for seq in sequences:
        cfg = config.load(Path("configs") / dataset_of(seq) / "dataset.yaml")
        out[seq] = (cfg.T_L_S, cfg.max_age_ms)
    return out


def main():
    import argparse
    from ofd.run_vo_repeat import LOG_DIR
    ap = argparse.ArgumentParser(description="Fase 2 do protocolo das VOs: métricas como distribuição (seção 7)")
    ap.add_argument("--from-decisions", required=True, help="decisions.json da fase 1 (data/analysis/vo_repeat/phase1)")
    ap.add_argument("--out", required=True, help="ex.: data/analysis/vo_repeat/phase2")
    a = ap.parse_args()
    plan = phase2_plan(json.loads(Path(a.from_decisions).read_text()))
    configs = load_configs(sorted({seq for seq, _ in plan}))
    phase2(plan, "data/runs", "data/extracted", "data/output", LOG_DIR, configs, a.out)


if __name__ == "__main__":
    main()
